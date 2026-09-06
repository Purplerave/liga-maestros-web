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
_owner_lock_fh = None


def _truthy(value):
    return str(value or "").strip().lower() in ("1", "true", "yes", "on")


def _acquire_owner_lock():
    """Un solo collector por disco: bloquea el fichero y dice si nos toca.

    El collector es un hilo dentro del proceso web. Si el despliegue arranca mas
    de un worker (gunicorn/uwsgi, o un reinicio con el proceso viejo aun vivo),
    cada worker duplica las llamadas a la API y se pisan los JSON del panel: la
    cuota diaria se agota a mitad de la jornada del finde y los resultados dejan de
    llegar. Con un flock por fichero, el segundo proceso no colecciona.

    Devuelve el manejador abierto (el llamador lo guarda: si se cierra o se deja
    morir, se suelta el lock) o ``None`` cuando otro proceso ya es el dueno.
    """
    try:
        import fcntl
    except ImportError:  # Windows (desarrollo): sin flock, un solo collector de todos modos
        return object()

    import config

    lock_path = os.path.join(config.DATA_DIR, "LIVE_COLLECTOR_OWNER.lock")
    try:
        os.makedirs(os.path.dirname(lock_path), exist_ok=True)
        handle = open(lock_path, "a+")
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return None
    except Exception:
        return None
    try:
        handle.seek(0)
        handle.truncate()
        handle.write(str(os.getpid()))
        handle.flush()
    except Exception:
        pass
    return handle


def _release_owner_lock():
    global _owner_lock_fh
    handle = _owner_lock_fh
    _owner_lock_fh = None
    if handle is None:
        return
    try:
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    except Exception:
        pass
    try:
        handle.close()
    except Exception:
        pass


def start_web_collector(app):
    """Start the background collector when WEB_COLLECTOR_ENABLED=1."""
    global _collector_started, _owner_lock_fh
    if not _truthy(os.getenv("WEB_COLLECTOR_ENABLED", "0")):
        logger.info("web_collector=disabled")
        return

    with _collector_lock:
        if _collector_started:
            logger.info("web_collector=already_running")
            return
        _collector_started = True

    _owner_lock_fh = _acquire_owner_lock()
    if _owner_lock_fh is None:
        # Otro proceso del mismo despliegue ya colecciona: no se duplican llamadas
        # a la API ni escrituras al panel.
        _collector_started = False
        logger.info("web_collector=otro_proceso_ya_colecciona")
        return

    interval = int(os.getenv("WEB_COLLECTOR_INTERVAL_SECONDS", "60"))
    highlightly_interval = int(os.getenv("WEB_COLLECTOR_HIGHLIGHTLY_INTERVAL_SECONDS", "60"))
    q15_enabled = not _truthy(os.getenv("WEB_COLLECTOR_DISABLE_Q15", "0"))

    def _loop():
        import sys
        from pathlib import Path

        tools_ops = str(Path(__file__).resolve().parents[2] / "tools" / "ops")
        if tools_ops not in sys.path:
            sys.path.insert(0, tools_ops)
        from LIVE_COLLECTOR import log_line, next_sleep_seconds, run_once, write_health

        log_line("web_collector=start")
        # Cierre de huecos al arrancar: tras un despliegue o un reinicio del
        # proceso (Alwaysdata lo hace con frecuencia), lo que no se capturo
        # mientras el collector estaba caido hay que ir a buscarlo YA, no cuando
        # vuelva a abrir una ventana de partido. Es la diferencia entre "el
        # sabado no aparece ningun resultado" y que aparezca en 1 minuto.
        try:
            run_once(force=True, q15=q15_enabled, highlightly_interval=0)
        except Exception as exc:
            logger.warning("web_collector=catchup_failed error=%s", exc)
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
            time.sleep(max(30, int(sleep_seconds)))

    def _guarded_loop():
        try:
            _loop()
        finally:
            _release_owner_lock()

    thread = threading.Thread(target=_guarded_loop, name="liga-web-collector", daemon=True)
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
        try:
            summary = refresh_all_standings(season=2026)
            logger.info("Standings refreshed on boot: %s", summary)
        except Exception:
            logger.exception("Boot standings refresh failed")
        while True:
            time.sleep(seconds_until_next_slot())
            try:
                summary = refresh_all_standings(season=2026)
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
