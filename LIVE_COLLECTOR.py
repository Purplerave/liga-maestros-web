import argparse
import json
import time
from datetime import datetime, timedelta
from pathlib import Path

from app import (
    HIGHLIGHTLY_REFRESH_ENABLED,
    compute_refresh_window,
    get_db,
    get_highlightly_usage,
    refresh_current_matches_from_highlightly,
)
from SCRAPE_QUINIELA15_DIRECTO import scrape as scrape_q15_directo
import utils

LOG_PATH = Path(__file__).resolve().parent / "data" / "LIVE_COLLECTOR.log"
DATA_DIR = Path(__file__).resolve().parent / "data"
HEALTH_PATH = DATA_DIR / "LIVE_COLLECTOR_HEALTH.json"
LAST_HIGHLIGHTLY_RUN = 0


def log_line(message):
    line = f"{datetime.now():%Y-%m-%d %H:%M:%S} {message}"
    print(line, flush=True)
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        pass


def write_health(status, window=None, error=None):
    payload = {
        "status": status,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "jornada": (window or {}).get("jornada"),
        "reason": (window or {}).get("reason"),
        "live_now": bool((window or {}).get("live_now")),
        "error": str(error) if error else "",
    }
    utils.safe_write_json(str(HEALTH_PATH), payload)


def choose_refresh_window(conn, jornada=None):
    if jornada:
        return compute_refresh_window(conn, jornada)

    jornadas = [
        row[0]
        for row in conn.execute(
            "SELECT DISTINCT jornada FROM resultados ORDER BY jornada DESC"
        ).fetchall()
        if row[0] is not None
    ]
    if not jornadas:
        return {"enabled": False, "reason": "sin_jornada"}

    windows = [compute_refresh_window(conn, jornada_id) for jornada_id in jornadas]
    enabled = [w for w in windows if w.get("enabled")]
    if enabled:
        return sorted(
            enabled,
            key=lambda w: (
                not bool(w.get("live_now")),
                w.get("next_kickoff") or w.get("first_kickoff") or datetime.max,
            ),
        )[0]

    now = datetime.now()
    upcoming = [
        w for w in windows
        if w.get("next_kickoff") and w.get("next_kickoff") >= now - timedelta(minutes=5)
    ]
    if upcoming:
        return sorted(upcoming, key=lambda w: w.get("next_kickoff"))[0]

    return windows[0]


def should_refresh(jornada=None):
    with get_db() as conn:
        window = choose_refresh_window(conn, jornada)
    return bool(window.get("enabled")), window


def write_q15_directo_cache(jornada):
    if not jornada:
        return 0
    payload = scrape_q15_directo(int(jornada))
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / f"quiniela15_directo_J{int(jornada)}.json"
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    updates = apply_q15_results_to_db(int(jornada), payload)
    if updates:
        log_line(f"q15_result_updates={updates}")
    return len(payload.get("matches") or [])


def apply_q15_results_to_db(jornada, payload):
    matches = payload.get("matches") or []
    if not matches:
        return 0
    updates = 0
    with get_db() as conn:
        current = {
            int(row["partido_id"]): row
            for row in conn.execute(
                """
                SELECT partido_id, goles_local, goles_visitante, status, minuto
                FROM resultados
                WHERE jornada = ?
                """,
                (jornada,),
            ).fetchall()
        }
        for match in matches:
            try:
                partido_id = int(match.get("id"))
            except Exception:
                continue
            home_goals = match.get("score_home")
            away_goals = match.get("score_away")
            if home_goals is None or away_goals is None:
                continue
            row = current.get(partido_id)
            if not row:
                continue
            minute = str(row["minuto"] or "")
            if minute.upper().startswith("SUSPENDIDO LAE"):
                continue
            signo = utils.signo_for_match(partido_id, int(home_goals), int(away_goals))
            q15_status = str(match.get("status") or "").upper()
            status = "LIVE" if q15_status == "LIVE" else "FT"
            match_minute = str(match.get("minute") or ("Finalizado" if status == "FT" else "")).strip()
            if (
                row["goles_local"] == home_goals
                and row["goles_visitante"] == away_goals
                and str(row["status"] or "").upper() == status
                and str(row["minuto"] or "") == match_minute
            ):
                continue
            conn.execute(
                """
                UPDATE resultados
                SET goles_local = ?, goles_visitante = ?, status = ?, minuto = ?, signo_actual = ?
                WHERE jornada = ? AND partido_id = ?
                """,
                (int(home_goals), int(away_goals), status, match_minute, signo, jornada, partido_id),
            )
            updates += 1
        conn.commit()
    return updates


def next_sleep_seconds(window, base_interval):
    """Refresco adaptativo: rapido en directo, lento fuera de ventana."""
    if window.get("live_now"):
        return max(60, min(int(base_interval or 120), 120))
    if not window.get("enabled"):
        next_kickoff = window.get("next_kickoff")
        if next_kickoff and next_kickoff > datetime.now() + timedelta(minutes=20):
            return 900
        return max(120, min(int(base_interval or 300), 300))
    now = datetime.now()
    next_kickoff = window.get("next_kickoff") or window.get("first_kickoff")
    if next_kickoff and next_kickoff > now + timedelta(minutes=20):
        return 900
    return max(120, min(int(base_interval or 120), 120))


def run_once(force=False, q15=True, jornada=None, highlightly_interval=60):
    global LAST_HIGHLIGHTLY_RUN
    enabled, window = should_refresh(jornada)
    if not force and not enabled:
        log_line(f"skip jornada={window.get('jornada')} reason={window.get('reason')}")
        return 0, window

    updates = 0
    if HIGHLIGHTLY_REFRESH_ENABLED:
        now_ts = time.time()
        if force or now_ts - LAST_HIGHLIGHTLY_RUN >= max(60, int(highlightly_interval or 300)):
            updates = refresh_current_matches_from_highlightly(
                force=True,
                jornada=window.get("jornada") or jornada,
            )
            LAST_HIGHLIGHTLY_RUN = now_ts
        else:
            log_line("highlightly_skip=throttle")
    else:
        log_line("Highlightly disabled")

    usage = get_highlightly_usage()
    q15_matches = "-"
    if q15:
        try:
            q15_matches = write_q15_directo_cache(window.get("jornada"))
        except Exception as exc:
            q15_matches = f"error:{exc}"
    log_line(
        f"updates={updates} live={window.get('live_now')} "
        f"calls={usage.get('calls')}/{usage.get('limit')} "
        f"usable={usage.get('usable_remaining')} "
        f"q15={q15_matches}"
    )
    write_health("ok", window=window)
    return updates, window


def main():
    parser = argparse.ArgumentParser(description="Actualiza cache live sin depender del refresco de usuarios.")
    parser.add_argument("--once", action="store_true", help="Ejecuta una sola pasada.")
    parser.add_argument("--force", action="store_true", help="Ignora ventana horaria.")
    parser.add_argument("--interval", type=int, default=120, help="Segundos entre pasadas cuando hay partidos en ventana.")
    parser.add_argument("--highlightly-interval", type=int, default=120, help="Segundos minimos entre pasadas a Highlightly.")
    parser.add_argument("--jornada", type=int, help="Jornada concreta a vigilar.")
    parser.add_argument("--no-q15", action="store_true", help="No actualiza el cache de directo de Quiniela15.")
    args = parser.parse_args()

    if args.once:
        run_once(force=args.force, q15=not args.no_q15, jornada=args.jornada, highlightly_interval=args.highlightly_interval)
        return

    while True:
        try:
            _, window = run_once(force=args.force, q15=not args.no_q15, jornada=args.jornada, highlightly_interval=args.highlightly_interval)
            sleep_seconds = next_sleep_seconds(window, args.interval)
        except Exception as exc:
            log_line(f"collector_error={exc}")
            write_health("error", error=exc)
            sleep_seconds = max(60, min(int(args.interval or 60), 300))
        time.sleep(sleep_seconds)


if __name__ == "__main__":
    main()
