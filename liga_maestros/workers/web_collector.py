"""Optional in-process live collector for single-service deployments.

Render persistent disks are attached to one service. For the beta deploy we run
the collector inside the web service so live updates and the web app use the
same SQLite database and JSON cache.
"""

import logging
import os
import threading
import time

logger = logging.getLogger(__name__)

_collector_started = False
_collector_lock = threading.Lock()
_collector_startup_complete = threading.Event()
_collector_startup_complete.set()
# Marca temporal en la que se libero la barrera de arranque. Un proceso lanzado
# solo para una CLI (migraciones, seeds, scripts) tambien ejecuta
# ``create_app`` y por tanto ``start_web_collector``: si esa primera pasada se
# queda a medias, no puede dejar el barrier cerrado para siempre.
_collector_startup_released_at = 0.0
# Cuanto puede esperar una peticion a que acabe la primera pasada. Medido en
# local: la pasada inicial se queda colgada en los scrapes de terceros y no
# termina en 4 s, asi que esperar mas solo traslada la latencia del 503 a la
# respuesta. 1,2 s basta para recoger una pasada que estaba a punto de acabar.
WARMUP_MAX_WAIT_SECONDS = 1.2
# A partir de aqui la primera pasada se da por atascada y se sirve el snapshot
# persistido sin esperar mas (el poll del directo lo cura en segundos).
STARTUP_STALE_AFTER_SECONDS = 30.0


def collector_startup_pending():
    """Whether the collector's first post-boot pass is still in progress.

    The web app may receive requests as soon as ``create_app`` returns, while
    the collector is still refreshing the persistent result snapshot in its
    daemon thread. A reader that has a previous snapshot can wait a little for
    that pass instead of answering 503.
    """
    return not _collector_startup_complete.is_set()


def _mark_collector_startup_started():
    """Marca el instante del cierre de la barrera (ultimo arranque)."""
    global _collector_startup_released_at
    _collector_startup_released_at = time.time()


def mark_collector_startup_complete():
    """Abre la barrera del arranque (deja la marca de cuando se cerro)."""
    _collector_startup_complete.set()


def collector_startup_stale(max_age_seconds=STARTUP_STALE_AFTER_SECONDS):
    """True si la primera pasada lleva demasiado tiempo sin terminar.

    El collector corre en un hilo daemon dentro del proceso web. Si ese hilo
    nunca llega a su primera pasada (import roto, proceso sin WEB_COLLECTOR
    real, CLI que solo construyo la app), la barrera se quedaba cerrada y la
    portada contestaba 503 indefinidamente: la pagina se quedaba en
    «Cargando el directo… Reintentando» hasta agotar los 4 reintentos. Pasado
    el margen, se sirve el snapshot persistido y el poll del directo lo cura.
    """
    if _collector_startup_complete.is_set():
        return False
    started = _collector_startup_released_at
    return bool(started) and (time.time() - started) > max_age_seconds


def wait_for_collector_startup(timeout=WARMUP_MAX_WAIT_SECONDS):
    """Espera (como mucho ``timeout``) a que acabe la primera pasada.

    Se llama desde los lectores que SI tienen un snapshot anterior: esperar
    unos cientos de milisegundos y servir datos frescos es mejor que un 503
    que el navegador convierte en «Cargando el directo… Reintentando».
    Devuelve True si la barrera se abrio.
    """
    if _collector_startup_complete.wait(timeout=max(0.0, float(timeout or 0))):
        return True
    return False


def _truthy(value):
    return str(value or "").strip().lower() in ("1", "true", "yes", "on")


def _try_acquire_leader_lock():
    """File-based leader election for single-instance workers.

    With gunicorn --workers 1 this is a no-op. If someone scales to >1 worker
    only the first process to grab the lock runs schedulers; the rest log
    `leader_skipped` and return. This prevents duplicate collectors/backups
    competing for SQLite.
    """
    import fcntl

    try:
        import config as _cfg

        lock_path = os.path.join(_cfg.DATA_DIR, ".collector_leader.lock")
        os.makedirs(os.path.dirname(lock_path) or ".", exist_ok=True)
        fh = open(lock_path, "a+", encoding="utf-8")  # noqa: SIM115
        try:
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            fh.close()
            return None
        # Keep file handle alive for the lifetime of the process
        return fh
    except Exception:
        # If fcntl not available (Windows) or any error, fall back to single-process guard
        return True


_leader_lock_handle = None


def start_web_collector(app):
    """Start the background collector when WEB_COLLECTOR_ENABLED=1."""
    global _collector_started, _leader_lock_handle
    if not _truthy(os.getenv("WEB_COLLECTOR_ENABLED", "0")):
        logger.info("web_collector=disabled")
        return

    with _collector_lock:
        if _collector_started:
            logger.info("web_collector=already_running")
            return
        _collector_started = True
        # Clear before returning from create_app: the first HTTP request must
        # not race ahead of the collector's initial data pass. La marca de
        # cuando se cerro permite que un lector deje de esperar (ver
        # ``collector_startup_stale``) si la pasada nunca termina.
        _collector_startup_complete.clear()
        _mark_collector_startup_started()

    # Leader election: only one gunicorn worker should run schedulers
    _leader_lock_handle = _try_acquire_leader_lock()
    if _leader_lock_handle is None:
        # Another process owns the collector; this worker must not hold page
        # requests behind a pass it will never run itself.
        mark_collector_startup_complete()
        logger.info("web_collector=leader_skipped another worker is leader")
        return
    if _leader_lock_handle is not True:
        # keep handle in app extensions so it isn't garbage-collected
        app.extensions["collector_leader_lock"] = _leader_lock_handle

    interval = int(os.getenv("WEB_COLLECTOR_INTERVAL_SECONDS", "60"))
    highlightly_interval = int(os.getenv("WEB_COLLECTOR_HIGHLIGHTLY_INTERVAL_SECONDS", "60"))
    q15_enabled = not _truthy(os.getenv("WEB_COLLECTOR_DISABLE_Q15", "0"))

    def _loop():
        first_pass_pending = True
        try:
            import sys
            from pathlib import Path

            tools_ops = str(Path(__file__).resolve().parents[2] / "tools" / "ops")
            if tools_ops not in sys.path:
                sys.path.insert(0, tools_ops)
            from LIVE_COLLECTOR import log_line, next_sleep_seconds, run_once, write_health

            log_line("web_collector=start")
            logger.info(
                "web_collector=started interval=%s highlightly_interval=%s q15=%s",
                interval,
                highlightly_interval,
                q15_enabled,
            )
            while True:
                try:
                    _, window = run_once(
                        force=False,
                        q15=q15_enabled,
                        highlightly_interval=highlightly_interval,
                    )
                    sleep_seconds = next_sleep_seconds(window, interval)
                except Exception as exc:
                    try:
                        log_line(f"web_collector_error={exc}")
                        write_health("error", error=exc)
                    except Exception:
                        pass
                    logger.exception("web_collector loop error")
                    sleep_seconds = max(60, min(interval or 60, 300))
                finally:
                    if first_pass_pending:
                        # Release the first-page barrier even on a failed pass;
                        # the API can then serve its last known snapshot rather
                        # than making the site unavailable indefinitely.
                        mark_collector_startup_complete()
                        first_pass_pending = False
                time.sleep(max(30, int(sleep_seconds)))
        except Exception:
            logger.exception("web_collector failed before completing startup")
        finally:
            # Import/setup errors must not strand all first-page requests at 503.
            mark_collector_startup_complete()

    thread = threading.Thread(target=_loop, name="liga-web-collector", daemon=True)
    thread.start()
    app.extensions["web_collector_thread"] = thread
    logger.info("web_collector=thread_started")

    # Background standings refresh: ALL leagues (Spanish BASE files + foreign
    # cache) at fixed local times, so midweek matches (Copa days, Friday
    # matches, a Wednesday Castellon game...) appear in the tables the same
    # night instead of waiting for the weekend cycle.
    #
    # Default schedule (Europe/Madrid): 01:30 (after late matches end),
    # 08:00 (morning catch-up), 14:30, 19:00 and 23:30. Cost: 5 leagues x
    # 5 slots = ~25 calls/day out of the 7500 daily quota (~0.3%).
    def _standings_loop():
        from datetime import datetime, timedelta
        from zoneinfo import ZoneInfo

        import config as _season_config

        from ..services.multi_standings import refresh_all_standings

        madrid = ZoneInfo("Europe/Madrid")
        raw_slots = os.getenv("STANDINGS_REFRESH_TIMES", "01:30,08:00,14:30,19:00,23:30")
        slots = []
        for chunk in raw_slots.split(","):
            chunk = chunk.strip()
            try:
                hour, minute = chunk.split(":")
                slots.append((int(hour), int(minute)))
            except Exception:
                continue
        if not slots:
            slots = [(8, 0), (23, 30)]
        slots.sort()

        def seconds_until_next_slot():
            now = datetime.now(madrid)
            candidates = []
            for hour, minute in slots:
                slot_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if slot_time <= now:
                    slot_time += timedelta(days=1)
                candidates.append(slot_time)
            return max(60, (min(candidates) - now).total_seconds())

        time.sleep(30)  # Wait for app to start
        # Refresh once on boot so a redeploy never leaves stale tables.
        season = getattr(_season_config, "CURRENT_SEASON_START_YEAR", 2026)
        try:
            summary = refresh_all_standings(season=season)
            logger.info("Standings refreshed on boot: %s", summary)
        except Exception:
            logger.exception("Boot standings refresh failed")
        while True:
            time.sleep(seconds_until_next_slot())
            try:
                summary = refresh_all_standings(season=season)
                logger.info("Standings refreshed: %s", summary)
            except Exception:
                logger.exception("Standings refresh failed")

    standings_thread = threading.Thread(target=_standings_loop, name="liga-standings-refresh", daemon=True)
    standings_thread.start()
    logger.info("web_collector=standings_thread_started")

    # Daily tracker: agenda + live scores + stats history for ALL followed
    # leagues, every day (not only during the quiniela window). This is what
    # makes a midweek Castellon match show up in the Directo and feed the
    # standings/stats the same night.
    if _truthy(os.getenv("DAILY_TRACKER_ENABLED", "1")):
        from ..services.daily_matches import start_daily_tracker

        start_daily_tracker(app)
        logger.info("web_collector=daily_tracker_started")
