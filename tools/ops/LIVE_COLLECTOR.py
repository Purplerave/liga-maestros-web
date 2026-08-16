import argparse
import json
import shutil
import sqlite3
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

_tools_root = str(Path(__file__).resolve().parent.parent)
if _tools_root not in sys.path:
    sys.path.insert(0, _tools_root)
_scrapers_dir = str(Path(__file__).resolve().parent.parent / "scrapers")
if _scrapers_dir not in sys.path:
    sys.path.insert(0, _scrapers_dir)
if str(Path(__file__).resolve().parent.parent.parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from SCRAPE_QUINIELA15_DIRECTO import scrape as scrape_q15_directo  # noqa: E402

import config  # noqa: E402
from liga_maestros import utils  # noqa: E402
from liga_maestros.db.connection import get_db  # noqa: E402
from liga_maestros.middleware.json_lock import write_json_locked  # noqa: E402
from liga_maestros.services import (  # noqa: E402
    HIGHLIGHTLY_REFRESH_ENABLED,
    compute_refresh_window,
    get_highlightly_circuit,
    get_highlightly_usage,
    madrid_now,
    parse_madrid_datetime,
    refresh_current_matches_from_highlightly,
    validate_q15_payload,
)
from liga_maestros.services.live_state import (  # noqa: E402
    CLOSE_FINAL,
    FINAL_MINUTE,
    FINAL_STATUS,
    NO_UPDATE_TIMEOUT,
    RESET_TO_SCHEDULED,
    closes_live,
    evaluate_match_state,
    is_live_status,
)

DATA_DIR = Path(config.DATA_DIR)
LOG_PATH = DATA_DIR / "LIVE_COLLECTOR.log"
HEALTH_PATH = DATA_DIR / "LIVE_COLLECTOR_HEALTH.json"
BACKUP_DIR = DATA_DIR / "backups"
LAST_HIGHLIGHTLY_RUN = 0
LAST_BACKUP_DATE = ""
MADRID_TZ = ZoneInfo("Europe/Madrid")


def log_line(message):
    line = f"{madrid_now():%Y-%m-%d %H:%M:%S} {message}"
    print(line, flush=True)
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        pass


def write_health(status, window=None, error=None, metrics=None):
    metrics = metrics or {}
    previous = utils.safe_read_json(str(HEALTH_PATH), {})
    previous_q15 = previous.get("q15") if isinstance(previous, dict) else {}
    now = madrid_now()
    usage = get_highlightly_usage()
    circuit = {key: value for key, value in get_highlightly_circuit().items() if key != "path"}
    if circuit.get("open_until"):
        try:
            circuit["open_until_iso"] = datetime.fromtimestamp(
                float(circuit["open_until"]),
                tz=MADRID_TZ,
            ).isoformat(timespec="seconds")
        except Exception:
            circuit["open_until_iso"] = ""
    blocked_by_circuit = bool(circuit.get("open"))
    q15_ok = metrics.get("q15_status") == "ok"
    stuck_live_count = int(metrics.get("stuck_live_count") or 0)
    snapshot_at = now.isoformat(timespec="seconds")
    snapshot_age_seconds = 0
    operational_status = (
        "q15_ok_api_paused"
        if blocked_by_circuit and q15_ok
        else "circuit_open"
        if blocked_by_circuit
        else "degraded"
        if stuck_live_count
        else "degraded"
        if status == "error" or metrics.get("q15_status") == "error"
        else "idle"
        if status == "idle"
        else "healthy"
    )
    payload = {
        "status": status,
        "operational_status": operational_status,
        "updated_at": snapshot_at,
        "snapshot_at": snapshot_at,
        "snapshot_age_seconds": snapshot_age_seconds,
        "stale": False,
        "source_priority": ["highlightly", "quiniela15", "highlightly_cache"],
        "jornada": (window or {}).get("jornada"),
        "reason": (window or {}).get("reason"),
        "live_now": bool((window or {}).get("live_now")),
        "error": str(error) if error else "",
        "highlightly": {
            "enabled": bool(HIGHLIGHTLY_REFRESH_ENABLED),
            "blocked_by_circuit": blocked_by_circuit,
            "next_retry_at": circuit.get("open_until_iso", "") if blocked_by_circuit else "",
            "usage": usage,
            "circuit": circuit,
        },
        "q15": {
            "status": metrics.get("q15_status", "unknown"),
            "fallback_used": bool(blocked_by_circuit and q15_ok),
            "matches": metrics.get("q15_matches", "-"),
            "duration_ms": metrics.get("q15_duration_ms"),
            "parse_errors": metrics.get("q15_parse_errors", 0),
            "last_success_per_match": metrics.get("last_success_per_match", {}),
        },
        "metrics": metrics,
    }
    if status == "idle" and previous_q15:
        previous_snapshot = previous.get("snapshot_at") or previous.get("updated_at")
        if previous_snapshot:
            try:
                previous_dt = datetime.fromisoformat(str(previous_snapshot))
                if previous_dt.tzinfo is None:
                    previous_dt = previous_dt.replace(tzinfo=MADRID_TZ)
                payload["previous_q15_age_seconds"] = max(0, int((now - previous_dt).total_seconds()))
            except Exception:
                pass
        payload["q15"]["status"] = "idle"
        payload["q15"]["last_success_per_match"] = {}
        payload["metrics"]["previous_q15_preserved"] = False
    write_json_locked(str(HEALTH_PATH), payload)


def _row_updated_at(row):
    """Best-effort read of the freshness stamp (column may not exist yet)."""
    try:
        raw = row["updated_at"]
    except (IndexError, KeyError):
        return None
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(str(raw))
    except ValueError:
        return None
    return parsed.replace(tzinfo=MADRID_TZ) if parsed.tzinfo is None else parsed


def detect_stuck_live_matches(jornada, grace_minutes=None):
    """Return live rows that cannot legitimately be live any more.

    Three independent signals are checked (see ``services.live_state``): a
    kickoff still in the future, a broadcast minute ahead of the real clock,
    and no provider update for 30 minutes. The schedule alone is not enough:
    a row stuck at LIVE minute 90 with a 17:00 kickoff never expires by time.
    """
    if not jornada:
        return []
    stuck = []
    with get_db() as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(resultados)").fetchall()}
        updated_at_select = "updated_at" if "updated_at" in columns else "NULL AS updated_at"
        rows = conn.execute(
            f"""
            SELECT partido_id, local, visitante, fecha, hora, status, minuto, {updated_at_select}
            FROM resultados
            WHERE jornada = ?
            ORDER BY partido_id
            """,  # noqa: S608 - column name comes from a local allowlist, never user input
            (jornada,),
        ).fetchall()
    now = madrid_now()
    for row in rows:
        if not is_live_status(row["status"]):
            continue
        kickoff_at = parse_madrid_datetime(row["fecha"], row["hora"])
        decision = evaluate_match_state(
            row["status"],
            kickoff_at,
            now,
            last_update_at=_row_updated_at(row),
            minute=row["minuto"],
            no_update_timeout=timedelta(minutes=grace_minutes) if grace_minutes else NO_UPDATE_TIMEOUT,
        )
        if not closes_live(decision["action"]):
            continue
        stuck.append(
            {
                "id": int(row["partido_id"]),
                "local": row["local"],
                "visitante": row["visitante"],
                "status": row["status"],
                "minuto": row["minuto"],
                "kickoff_at": kickoff_at.isoformat(timespec="minutes") if kickoff_at else "",
                "action": decision["action"],
                "reason": decision["reason"],
                "new_status": decision["status"],
                "new_minute": decision["minute"],
            }
        )
    return stuck


def close_stuck_live_matches(jornada, grace_minutes=None):
    """Persistently close live DB rows that are impossible or frozen.

    Last-resort path for a missed provider FT event or a corrupted snapshot.
    Runs on every collector pass (not only once the jornada window closes) so
    a single stuck match cannot keep Directo open while others continue.

    The written state depends on why the row is being closed: a match whose
    full window elapsed is finalised (FT + sign), one that is merely frozen or
    inconsistent is marked STALE (score kept, no sign invented), and one that
    was never actually playing goes back to NS.
    """
    stuck = detect_stuck_live_matches(jornada, grace_minutes=grace_minutes)
    if not stuck:
        return []
    with get_db() as conn:
        conn.execute("PRAGMA busy_timeout = 30000")
        conn.execute("BEGIN IMMEDIATE")
        for match in stuck:
            action = match.get("action") or CLOSE_FINAL
            new_status = match.get("new_status") or FINAL_STATUS
            new_minute = match.get("new_minute")
            if new_minute is None:
                new_minute = FINAL_MINUTE
            row = conn.execute(
                "SELECT goles_local, goles_visitante FROM resultados WHERE jornada = ? AND partido_id = ?",
                (jornada, match["id"]),
            ).fetchone()
            if action == RESET_TO_SCHEDULED:
                # Never played: drop the phantom score so the fixture can be
                # repopulated cleanly when it really kicks off.
                conn.execute(
                    """
                    UPDATE resultados
                    SET status = ?, minuto = ?, goles_local = NULL, goles_visitante = NULL, signo_actual = '-'
                    WHERE jornada = ? AND partido_id = ?
                    """,
                    (new_status, new_minute, jornada, match["id"]),
                )
                continue
            if action == CLOSE_FINAL:
                signo = utils.signo_for_match(
                    match["id"],
                    row["goles_local"] if row else None,
                    row["goles_visitante"] if row else None,
                )
                conn.execute(
                    "UPDATE resultados SET status = ?, minuto = ?, signo_actual = ? WHERE jornada = ? AND partido_id = ?",
                    (new_status, new_minute, signo, jornada, match["id"]),
                )
                continue
            # CLOSE_NO_DATA: stop showing it live but do not invent a result.
            conn.execute(
                "UPDATE resultados SET status = ?, minuto = ? WHERE jornada = ? AND partido_id = ?",
                (new_status, new_minute, jornada, match["id"]),
            )
        conn.commit()
    log_line(
        "auto_close="
        + str(len(stuck))
        + " "
        + " ".join(f"{match['id']}:{match.get('reason', 'desconocido')}" for match in stuck)
    )
    return stuck


def cleanup_old_backups(retention_days=14):
    cutoff = madrid_now() - timedelta(days=max(1, int(retention_days or 14)))
    for path in BACKUP_DIR.glob("*"):
        if not path.is_file():
            continue
        try:
            if datetime.fromtimestamp(path.stat().st_mtime, tz=MADRID_TZ) < cutoff:
                path.unlink()
        except Exception as exc:
            log_line(f"backup_cleanup_error={path.name}:{exc}")


def backup_runtime_state(force=False, window=None):
    global LAST_BACKUP_DATE
    today = madrid_now().strftime("%Y-%m-%d")
    if not force and LAST_BACKUP_DATE == today:
        return False
    if not force and window and window.get("live_now"):
        log_line("backup_skip=live_window")
        return False

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = madrid_now().strftime("%Y%m%d_%H%M%S")
    db_source = Path(config.DB_PATH)
    if db_source.exists():
        db_target = BACKUP_DIR / f"LIGA_MAESTROS_PRO_{stamp}.db"
        source_conn = sqlite3.connect(str(db_source), timeout=30)
        target_conn = sqlite3.connect(str(db_target), timeout=30)
        try:
            source_conn.execute("PRAGMA busy_timeout=30000")
            source_conn.execute("PRAGMA wal_checkpoint(PASSIVE)")
            source_conn.backup(target_conn)
        finally:
            target_conn.close()
            source_conn.close()
        log_line(f"backup_db={db_target.name}")

    copied = 0
    for path in DATA_DIR.glob("*.json"):
        if path.name.startswith("quiniela15_directo_") or path.name in {
            "API_USAGE_HIGHLIGHTLY.json",
            "HIGHLIGHTLY_CIRCUIT.json",
            "LIVE_COLLECTOR_HEALTH.json",
            "RADAR_NOTICIAS.json",
        }:
            shutil.copy2(path, BACKUP_DIR / f"{path.stem}_{stamp}{path.suffix}")
            copied += 1
    if copied:
        log_line(f"backup_json={copied}")
    cleanup_old_backups()
    LAST_BACKUP_DATE = today
    return True


def choose_refresh_window(conn, jornada=None):
    if jornada:
        return compute_refresh_window(conn, jornada)

    jornadas = [
        row[0]
        for row in conn.execute("SELECT DISTINCT jornada FROM resultados ORDER BY jornada DESC").fetchall()
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

    now = madrid_now().replace(tzinfo=None)
    upcoming = [w for w in windows if w.get("next_kickoff") and w.get("next_kickoff") >= now - timedelta(minutes=5)]
    if upcoming:
        return sorted(upcoming, key=lambda w: w.get("next_kickoff"))[0]

    return windows[0]


def should_refresh(jornada=None):
    with get_db() as conn:
        window = choose_refresh_window(conn, jornada)
    return bool(window.get("enabled")), window


def write_q15_directo_cache(jornada):
    if not jornada:
        return {"matches": 0, "last_success_per_match": {}}
    started_at = time.time()
    payload = scrape_q15_directo(int(jornada))
    matches = validate_q15_payload(payload, jornada)
    fetched_at = madrid_now().isoformat(timespec="seconds")
    payload["fetched_at"] = fetched_at
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / f"quiniela15_directo_J{int(jornada)}.json"
    write_json_locked(str(path), payload)
    match_count = len(matches)
    updates = apply_q15_results_to_db(int(jornada), payload)
    if updates:
        log_line(f"q15_result_updates={updates}")
    last_success_per_match = {}
    parse_errors = 0
    for match in payload.get("matches") or []:
        match_id = match.get("id")
        if match_id is None:
            continue
        if match.get("status") in ("LIVE", "FT") and not match.get("events"):
            parse_errors += 1
        last_success_per_match[str(match_id)] = {
            "updated_at": fetched_at,
            "status": match.get("status") or "",
            "score": (
                f"{match.get('score_home')}-{match.get('score_away')}"
                if match.get("score_home") is not None and match.get("score_away") is not None
                else ""
            ),
        }
    return {
        "matches": match_count,
        "duration_ms": int((time.time() - started_at) * 1000),
        "parse_errors": parse_errors,
        "last_success_per_match": last_success_per_match,
    }


def apply_q15_results_to_db(jornada, payload):
    matches = payload.get("matches") or []
    if not matches:
        return 0
    updates = 0
    now = madrid_now()
    stamp = now.isoformat(timespec="seconds")
    with get_db() as conn:
        conn.execute("PRAGMA busy_timeout = 30000")
        conn.execute("BEGIN IMMEDIATE")
        current = {
            int(row["partido_id"]): row
            for row in conn.execute(
                """
                SELECT partido_id, local, visitante, fecha, hora, goles_local, goles_visitante, status, minuto
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
            try:
                home_goals = int(str(home_goals).strip().replace("?", ""))
                away_goals = int(str(away_goals).strip().replace("?", ""))
            except (TypeError, ValueError):
                log_line(f"q15_corrupt_score_skipped id={match.get('id')}")
                continue
            row = current.get(partido_id)
            if not row:
                continue
            q15_home = utils.normalize_team_key(match.get("local"))
            q15_away = utils.normalize_team_key(match.get("visitante"))
            db_home = utils.normalize_team_key(row["local"])
            db_away = utils.normalize_team_key(row["visitante"])
            if q15_home and q15_away and (q15_home != db_home or q15_away != db_away):
                log_line(
                    "q15_team_mismatch_skipped "
                    f"id={partido_id} q15={match.get('local')}|{match.get('visitante')} "
                    f"db={row['local']}|{row['visitante']}"
                )
                continue
            minute = str(row["minuto"] or "")
            if minute.upper().startswith("SUSPENDIDO LAE"):
                continue
            signo = utils.signo_for_match(partido_id, home_goals, away_goals)
            q15_status = str(match.get("status") or "").upper()
            if q15_status in ("LIVE", "IN PLAY"):
                status = "LIVE"
            elif q15_status in ("HT", "HALF TIME BREAK"):
                status = "HT"
            elif q15_status in ("FT", "FINISHED", "TERMINADO"):
                status = "FT"
            elif q15_status == "STALE":
                kickoff_at = parse_madrid_datetime(row["fecha"], row["hora"])
                if not kickoff_at or madrid_now() < kickoff_at + timedelta(minutes=105):
                    continue
                status = "FT"
            else:
                continue
            match_minute = str(match.get("minute") or ("Finalizado" if status == "FT" else "")).strip()

            # A provider snapshot must never (re)open an impossible live state,
            # e.g. LIVE minute 90 on a match that kicks off later today.
            if is_live_status(status):
                decision = evaluate_match_state(
                    status,
                    parse_madrid_datetime(row["fecha"], row["hora"]),
                    now,
                    last_update_at=now,
                    minute=match_minute,
                )
                if closes_live(decision["action"]):
                    log_line(f"q15_live_incoherente_descartado id={partido_id} reason={decision['reason']}")
                    continue

            unchanged = (
                row["goles_local"] == home_goals
                and row["goles_visitante"] == away_goals
                and str(row["status"] or "").upper() == status
                and str(row["minuto"] or "") == match_minute
            )
            if unchanged:
                # Same values still mean "the provider confirmed this row now":
                # refresh the freshness stamp so a legitimately quiet 0-0 is
                # not closed by the 30-minute no-update rule.
                conn.execute(
                    "UPDATE resultados SET updated_at = ? WHERE jornada = ? AND partido_id = ?",
                    (stamp, jornada, partido_id),
                )
                continue
            conn.execute(
                """
                UPDATE resultados
                SET goles_local = ?, goles_visitante = ?, status = ?, minuto = ?, signo_actual = ?,
                    updated_at = ?
                WHERE jornada = ? AND partido_id = ?
                """,
                (int(home_goals), int(away_goals), status, match_minute, signo, stamp, jornada, partido_id),
            )
            updates += 1
        conn.commit()
    return updates


def next_sleep_seconds(window, base_interval):
    """Refresco adaptativo: rapido en directo, lento fuera de ventana."""
    circuit = get_highlightly_circuit()
    if not window.get("enabled") and window.get("reason") == "ventana_jornada":
        return max(60, min(int(base_interval or 300), 300))
    if circuit.get("open"):
        try:
            remaining = int(float(circuit.get("open_until") or 0) - time.time())
        except Exception:
            remaining = 0
        if remaining > 0:
            return max(60, min(remaining, 900))
    if window.get("live_now"):
        return max(60, min(int(base_interval or 120), 120))
    if window.get("needs_result_catchup"):
        return 900
    if not window.get("enabled"):
        next_kickoff = window.get("next_kickoff")
        if next_kickoff and next_kickoff > madrid_now().replace(tzinfo=None) + timedelta(minutes=20):
            return 900
        return max(60, min(int(base_interval or 300), 300))
    now = madrid_now().replace(tzinfo=None)
    next_kickoff = window.get("next_kickoff") or window.get("first_kickoff")
    if next_kickoff and next_kickoff > now + timedelta(minutes=20):
        return 900
    return max(60, min(int(base_interval or 120), 120))


LAST_STANDINGS_UPDATE = 0


def _update_spanish_standings_from_matches():
    """Calculate La Liga and Segunda standings from all collected matches."""
    global LAST_STANDINGS_UPDATE
    now = time.time()
    # Only update every 30 minutes
    if now - LAST_STANDINGS_UPDATE < 1800:
        return
    LAST_STANDINGS_UPDATE = now

    matches_path = DATA_DIR / "LIVE_ALL_MATCHES_V3.json"
    if not matches_path.exists():
        return
    try:
        with matches_path.open(encoding="utf-8") as f:
            all_matches = json.load(f)
    except Exception:
        return
    if not all_matches:
        return

    from liga_maestros.services.standings_calculator import calculate_standings_from_matches

    result = calculate_standings_from_matches(all_matches)
    leagues = result.get("leagues", [])

    for league in leagues:
        name = league.get("name", "").upper()
        teams = league.get("teams", [])
        if not teams:
            continue

        if "LA LIGA" in name:
            filename = "STANDINGS_LALIGA_BASE.json"
            category = "primera"
        elif "SEGUNDA" in name:
            filename = "STANDINGS_SEGUNDA_BASE.json"
            category = "segunda"
        else:
            continue

        from liga_maestros.services.season_rosters import merge_official_stats, official_name_set, official_names

        incoming = {str(t.get("n") or "").strip() for t in teams}
        if incoming - official_name_set(category):
            log_line(f"standings_skip={name} reason=roster_not_2026_27")
            continue
        base_teams = merge_official_stats(official_names(category), teams)

        path = DATA_DIR / filename
        try:
            with path.open("w", encoding="utf-8") as f:
                json.dump(base_teams, f, ensure_ascii=False, indent=2)
            log_line(f"standings_updated={name} teams={len(base_teams)}")
        except Exception as exc:
            log_line(f"standings_write_error={filename} err={exc}")


def run_once(force=False, q15=True, jornada=None, highlightly_interval=60):
    global LAST_HIGHLIGHTLY_RUN
    started_at = time.time()
    enabled, window = should_refresh(jornada)
    backup_runtime_state(window=window)
    target_jornada = window.get("jornada") or jornada
    auto_closed = []
    q15_catchup = bool(q15 and window.get("jornada") and window.get("reason") == "ventana_jornada" and enabled)
    if not force and not enabled and not q15_catchup:
        log_line(f"skip jornada={window.get('jornada')} reason={window.get('reason')}")
        try:
            auto_closed = close_stuck_live_matches(target_jornada)
        except Exception as exc:
            log_line(f"auto_ft_error={exc}")
        stuck_live = detect_stuck_live_matches(target_jornada)
        write_health(
            "idle",
            window=window,
            metrics={
                "duration_ms": int((time.time() - started_at) * 1000),
                "stuck_live_count": len(stuck_live),
                "stuck_live_matches": stuck_live,
                "auto_closed_count": len(auto_closed),
                "auto_closed_matches": auto_closed,
            },
        )
        return 0, window

    q15_matches = "-"
    q15_status = "disabled"
    q15_detail = {}
    if q15:
        try:
            q15_detail = write_q15_directo_cache(window.get("jornada"))
            q15_matches = q15_detail.get("matches", 0)
            q15_status = "ok"
        except Exception as exc:
            q15_matches = f"error:{exc}"
            q15_status = "error"

    updates = 0
    highlightly_status = "disabled"
    if HIGHLIGHTLY_REFRESH_ENABLED and (enabled or force):
        now_ts = time.time()
        api_interval = max(60, int(highlightly_interval or 300))
        if window.get("needs_result_catchup") and not window.get("live_now"):
            api_interval = max(api_interval, 900)
        circuit = get_highlightly_circuit()
        if circuit.get("open"):
            highlightly_status = "circuit_open"
            try:
                until = datetime.fromtimestamp(float(circuit.get("open_until") or 0)).strftime("%H:%M:%S")
            except Exception:
                until = "desconocido"
            log_line(f"highlightly_skip=circuit_open until={until}")
        elif force or now_ts - LAST_HIGHLIGHTLY_RUN >= api_interval:
            highlightly_status = "refresh_api"
            updates = refresh_current_matches_from_highlightly(
                force=True,
                jornada=window.get("jornada") or jornada,
            )
            LAST_HIGHLIGHTLY_RUN = now_ts
        else:
            highlightly_status = "throttle"
            log_line("highlightly_skip=throttle")
    else:
        highlightly_status = "window_closed"
        log_line("highlightly_skip=window_closed")

    # Provider/Q15 refreshes can return a stale LIVE snapshot and reopen a row.
    # Apply the hard deadline afterwards so the same pass always ends closed.
    try:
        auto_closed = close_stuck_live_matches(target_jornada)
    except Exception as exc:
        log_line(f"auto_ft_error={exc}")

    # Update Spanish league standings from all collected matches
    if updates > 0 or highlightly_status == "refresh_api":
        try:
            _update_spanish_standings_from_matches()
        except Exception as exc:
            log_line(f"standings_update_error={exc}")

    usage = get_highlightly_usage()
    log_line(
        f"updates={updates} live={window.get('live_now')} "
        f"calls={usage.get('calls')}/{usage.get('limit')} "
        f"usable={usage.get('usable_remaining')} "
        f"q15={q15_matches}"
    )
    stuck_live = detect_stuck_live_matches(window.get("jornada") or jornada)
    if stuck_live:
        log_line(f"stuck_live={len(stuck_live)} ids={','.join(str(item['id']) for item in stuck_live)}")
    write_health(
        "ok",
        window=window,
        metrics={
            "duration_ms": int((time.time() - started_at) * 1000),
            "highlightly_status": highlightly_status,
            "highlightly_updates": updates,
            "q15_status": q15_status,
            "q15_matches": q15_matches,
            "q15_duration_ms": q15_detail.get("duration_ms"),
            "q15_parse_errors": q15_detail.get("parse_errors", 0),
            "last_success_per_match": q15_detail.get("last_success_per_match", {}),
            "stuck_live_count": len(stuck_live),
            "stuck_live_matches": stuck_live,
            "auto_closed_count": len(auto_closed),
            "auto_closed_matches": auto_closed,
        },
    )
    return updates, window


def main():
    parser = argparse.ArgumentParser(description="Actualiza cache live sin depender del refresco de usuarios.")
    parser.add_argument("--once", action="store_true", help="Ejecuta una sola pasada.")
    parser.add_argument("--force", action="store_true", help="Ignora ventana horaria.")
    parser.add_argument(
        "--interval", type=int, default=60, help="Segundos entre pasadas cuando hay partidos en ventana."
    )
    parser.add_argument(
        "--highlightly-interval", type=int, default=60, help="Segundos minimos entre pasadas a Highlightly."
    )
    parser.add_argument("--jornada", type=int, help="Jornada concreta a vigilar.")
    parser.add_argument("--no-q15", action="store_true", help="No actualiza el cache de directo de Quiniela15.")
    parser.add_argument("--backup-now", action="store_true", help="Crea backup local de DB y JSON y sale.")
    args = parser.parse_args()

    if args.backup_now:
        backup_runtime_state(force=True)
        return

    if args.once:
        run_once(
            force=args.force, q15=not args.no_q15, jornada=args.jornada, highlightly_interval=args.highlightly_interval
        )
        return

    while True:
        try:
            _, window = run_once(
                force=args.force,
                q15=not args.no_q15,
                jornada=args.jornada,
                highlightly_interval=args.highlightly_interval,
            )
            sleep_seconds = next_sleep_seconds(window, args.interval)
        except Exception as exc:
            log_line(f"collector_error={exc}")
            write_health("error", error=exc)
            sleep_seconds = max(60, min(int(args.interval or 60), 300))
        time.sleep(sleep_seconds)


if __name__ == "__main__":
    main()
