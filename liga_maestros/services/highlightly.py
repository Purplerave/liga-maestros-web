"""Highlightly API integration: circuit breaker, usage tracking, refresh."""
import logging
import os, time, threading, requests
from datetime import datetime, timedelta

import config
from ..db.connection import get_db
from ..middleware.json_lock import write_json_locked, update_json_object_locked, update_json_list_by_id_locked
from ..utils import normalize_team_key, parse_score_text, highlightly_status, highlightly_match_to_panel, parse_db_match_datetime, safe_read_json, signo_for_match

logger = logging.getLogger(__name__)

HIGHLIGHTLY_REFRESH_ENABLED = os.getenv("HIGHLIGHTLY_REFRESH_ENABLED", "1").strip().lower() in ("1", "true", "yes", "on")
HIGHLIGHTLY_DAILY_CALL_LIMIT = int(os.getenv("HIGHLIGHTLY_DAILY_CALL_LIMIT", "7500"))
HIGHLIGHTLY_DAILY_CALL_RESERVE = int(os.getenv("HIGHLIGHTLY_DAILY_CALL_RESERVE", "250"))
HIGHLIGHTLY_MAX_CALLS_PER_REFRESH = max(0, int(os.getenv("HIGHLIGHTLY_MAX_CALLS_PER_REFRESH", "1")))
HIGHLIGHTLY_ACTIVE_LEAGUES = {
    item.strip().upper()
    for item in os.getenv("HIGHLIGHTLY_ACTIVE_LEAGUES", "").split(",")
    if item.strip()
}
HIGHLIGHTLY_CIRCUIT_FAILURE_LIMIT = int(os.getenv("HIGHLIGHTLY_CIRCUIT_FAILURE_LIMIT", "3"))
HIGHLIGHTLY_CIRCUIT_COOLDOWN_SECONDS = int(os.getenv("HIGHLIGHTLY_CIRCUIT_COOLDOWN_SECONDS", "600"))
HIGHLIGHTLY_CIRCUIT_MAX_COOLDOWN_SECONDS = int(os.getenv("HIGHLIGHTLY_CIRCUIT_MAX_COOLDOWN_SECONDS", "3600"))
Q15_EXPECTED_MATCHES = 15

_highlightly_refresh_lock = threading.Lock()
_highlightly_last_refresh = 0
_highlightly_refresh_thread = None
_highlightly_refresh_started_at = 0
_highlightly_thread_management_lock = threading.Lock()
_highlightly_circuit_lock = threading.RLock()


def madrid_now():
    from zoneinfo import ZoneInfo
    return datetime.now(ZoneInfo("Europe/Madrid"))


def today_madrid():
    return madrid_now().strftime("%Y-%m-%d")


def resolve_jornada(conn, jornada=None):
    raw = str(jornada or "").strip()
    if raw.isdigit():
        return int(raw)
    row = conn.execute("SELECT MAX(jornada) FROM resultados").fetchone()
    return row[0] if row and row[0] is not None else None


def compute_refresh_window(conn, jornada=None):
    target_jornada = resolve_jornada(conn, jornada)
    if not target_jornada:
        return {"enabled": False, "reason": "sin_jornada"}

    rows = conn.execute("""
        SELECT fecha, hora, status
        FROM resultados
        WHERE jornada = ?
        ORDER BY partido_id ASC
    """, (target_jornada,)).fetchall()
    if not rows:
        return {"enabled": False, "reason": "sin_partidos", "jornada": target_jornada}

    match_times = [dt for dt in (parse_db_match_datetime(r["fecha"], r["hora"]) for r in rows) if dt]
    live_now = any(str(r["status"] or "").upper() in ("LIVE", "IN PLAY", "HT", "HALF TIME BREAK", "EN JUEGO") for r in rows)
    has_pending = any(str(r["status"] or "").upper() in ("NS", "SCHEDULED", "NOT STARTED") for r in rows)
    needs_result_catchup = False

    if not match_times:
        return {
            "enabled": live_now,
            "reason": "solo_estados",
            "jornada": target_jornada,
            "live_now": live_now,
            "has_pending": has_pending,
        }

    first_kickoff = min(match_times)
    last_kickoff = max(match_times)
    now = madrid_now().replace(tzinfo=None)
    active_windows = []
    for row in rows:
        kickoff = parse_db_match_datetime(row["fecha"], row["hora"])
        if not kickoff:
            continue
        status = str(row["status"] or "").upper()
        if status in ("FT", "FINISHED", "TERMINADO"):
            continue
        window_start = kickoff - timedelta(minutes=2)
        window_end = kickoff + timedelta(hours=3)
        if window_start <= now <= window_end:
            active_windows.append((window_start, window_end, kickoff))
        elif kickoff < now <= kickoff + timedelta(hours=24):
            needs_result_catchup = True

    enabled = live_now or bool(active_windows) or needs_result_catchup
    if active_windows:
        current_window_start = min(item[0] for item in active_windows)
        current_window_end = max(item[1] for item in active_windows)
        next_kickoff = min(item[2] for item in active_windows)
    elif needs_result_catchup:
        current_window_start = first_kickoff - timedelta(minutes=2)
        current_window_end = last_kickoff + timedelta(hours=3)
        future_times = [dt for dt in match_times if dt >= now]
        next_kickoff = min(future_times) if future_times else None
    else:
        current_window_start = first_kickoff - timedelta(minutes=2)
        current_window_end = last_kickoff + timedelta(hours=3)
        future_times = [dt for dt in match_times if dt >= now]
        next_kickoff = min(future_times) if future_times else None
    return {
        "enabled": enabled,
        "reason": "ventana_jornada",
        "jornada": target_jornada,
        "live_now": live_now,
        "has_pending": has_pending,
        "needs_result_catchup": needs_result_catchup,
        "first_kickoff": first_kickoff,
        "last_kickoff": last_kickoff,
        "next_kickoff": next_kickoff,
        "window_start": current_window_start,
        "window_end": current_window_end,
    }


# --- Circuit Breaker ---

def get_highlightly_circuit():
    path = os.path.join(config.DATA_DIR, "HIGHLIGHTLY_CIRCUIT.json")
    with _highlightly_circuit_lock:
        state = safe_read_json(path, {})
        now = time.time()
        until = float(state.get("open_until") or 0)
        return {
            "path": path,
            "failures": int(state.get("failures") or 0),
            "reopen_failures": int(state.get("reopen_failures") or 0),
            "cooldown_seconds": int(state.get("cooldown_seconds") or HIGHLIGHTLY_CIRCUIT_COOLDOWN_SECONDS),
            "open_until": until,
            "open": until > now,
            "last_error": state.get("last_error", ""),
            "last_success_at": state.get("last_success_at", ""),
            "calls_since_last_success": int(state.get("calls_since_last_success") or 0),
        }


def record_highlightly_success():
    path = os.path.join(config.DATA_DIR, "HIGHLIGHTLY_CIRCUIT.json")
    with _highlightly_circuit_lock:
        write_json_locked(path, {
            "failures": 0,
            "reopen_failures": 0,
            "cooldown_seconds": HIGHLIGHTLY_CIRCUIT_COOLDOWN_SECONDS,
            "open_until": 0,
            "last_error": "",
            "last_success_at": datetime.now().isoformat(timespec="seconds"),
            "calls_since_last_success": 0,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        })


def record_highlightly_failure(exc):
    with _highlightly_circuit_lock:
        circuit = get_highlightly_circuit()
        failures = int(circuit.get("failures") or 0) + 1
        reopen_failures = int(circuit.get("reopen_failures") or 0)
        if failures >= HIGHLIGHTLY_CIRCUIT_FAILURE_LIMIT:
            reopen_failures += 1
        base_cooldown = int(circuit.get("cooldown_seconds") or HIGHLIGHTLY_CIRCUIT_COOLDOWN_SECONDS)
        cooldown = base_cooldown
        if reopen_failures >= 3:
            cooldown = min(max(base_cooldown * 2, HIGHLIGHTLY_CIRCUIT_COOLDOWN_SECONDS), HIGHLIGHTLY_CIRCUIT_MAX_COOLDOWN_SECONDS)
        open_until = 0
        if failures >= HIGHLIGHTLY_CIRCUIT_FAILURE_LIMIT:
            open_until = time.time() + cooldown
        write_json_locked(circuit["path"], {
            "failures": failures,
            "reopen_failures": reopen_failures,
            "cooldown_seconds": cooldown,
            "open_until": open_until,
            "last_error": str(exc),
            "last_success_at": circuit.get("last_success_at", ""),
            "calls_since_last_success": int(circuit.get("calls_since_last_success") or 0) + 1,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        })


# --- Usage Tracking ---

def ensure_api_usage_table(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS api_usage_daily (
            service TEXT NOT NULL,
            date TEXT NOT NULL,
            calls INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (service, date)
        )
    """)


def highlightly_usage_payload(date_text, calls):
    calls = int(calls or 0)
    remaining = max(0, HIGHLIGHTLY_DAILY_CALL_LIMIT - calls)
    return {
        "date": date_text,
        "calls": calls,
        "limit": HIGHLIGHTLY_DAILY_CALL_LIMIT,
        "reserve": HIGHLIGHTLY_DAILY_CALL_RESERVE,
        "remaining": remaining,
        "usable_remaining": max(0, remaining - HIGHLIGHTLY_DAILY_CALL_RESERVE),
    }


def mirror_highlightly_usage_json(data):
    path = os.path.join(config.DATA_DIR, "API_USAGE_HIGHLIGHTLY.json")
    try:
        write_json_locked(path, data)
    except Exception:
        pass


def get_highlightly_usage():
    today = today_madrid()
    conn = get_db()
    try:
        ensure_api_usage_table(conn)
        row = conn.execute(
            "SELECT calls FROM api_usage_daily WHERE service = ? AND date = ?",
            ("highlightly", today)
        ).fetchone()
        if not row:
            legacy = safe_read_json(os.path.join(config.DATA_DIR, "API_USAGE_HIGHLIGHTLY.json"), {})
            legacy_calls = int(legacy.get("calls") or 0) if legacy.get("date") == today else 0
            conn.execute("""
                INSERT OR IGNORE INTO api_usage_daily (service, date, calls, updated_at)
                VALUES (?, ?, ?, ?)
            """, ("highlightly", today, legacy_calls, datetime.now().isoformat(timespec="seconds")))
            conn.commit()
            calls = legacy_calls
        else:
            calls = int(row["calls"] or 0)
        data = highlightly_usage_payload(today, calls)
        mirror_highlightly_usage_json(data)
        return data
    finally:
        conn.close()


def record_highlightly_call(count=1):
    count = max(0, int(count or 0))
    today = today_madrid()
    conn = get_db()
    try:
        ensure_api_usage_table(conn)
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("""
            INSERT OR IGNORE INTO api_usage_daily (service, date, calls, updated_at)
            VALUES (?, ?, 0, ?)
        """, ("highlightly", today, datetime.now().isoformat(timespec="seconds")))
        conn.execute("""
            UPDATE api_usage_daily
            SET calls = calls + ?, updated_at = ?
            WHERE service = ? AND date = ?
        """, (count, datetime.now().isoformat(timespec="seconds"), "highlightly", today))
        row = conn.execute(
            "SELECT calls FROM api_usage_daily WHERE service = ? AND date = ?",
            ("highlightly", today)
        ).fetchone()
        conn.commit()
        data = highlightly_usage_payload(today, row["calls"] if row else count)
        mirror_highlightly_usage_json(data)
        return data
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def reserve_highlightly_calls(count=1):
    count = max(1, int(count or 1))
    today = today_madrid()
    conn = get_db()
    try:
        ensure_api_usage_table(conn)
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("""
            INSERT OR IGNORE INTO api_usage_daily (service, date, calls, updated_at)
            VALUES (?, ?, 0, ?)
        """, ("highlightly", today, datetime.now().isoformat(timespec="seconds")))
        row = conn.execute(
            "SELECT calls FROM api_usage_daily WHERE service = ? AND date = ?",
            ("highlightly", today)
        ).fetchone()
        calls = int(row["calls"] or 0) if row else 0
        data = highlightly_usage_payload(today, calls)
        if count > int(data.get("usable_remaining") or 0):
            conn.rollback()
            return None
        conn.execute("""
            UPDATE api_usage_daily
            SET calls = calls + ?, updated_at = ?
            WHERE service = ? AND date = ?
        """, (count, datetime.now().isoformat(timespec="seconds"), "highlightly", today))
        updated = highlightly_usage_payload(today, calls + count)
        conn.commit()
        mirror_highlightly_usage_json(updated)
        return updated
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# --- API Calls ---

def _local_league_status_for_date(conn, jornada, date_text, league_name):
    from ..utils import normalize_team_key
    league = str(league_name or "").upper()
    if league not in ("LA LIGA", "SEGUNDA DIVISION"):
        return {"known": False, "all_finished": False}
    target_division = 1 if league == "LA LIGA" else 2
    teams = {
        normalize_team_key(row["equipo"])
        for row in conn.execute(
            "SELECT equipo FROM clasificacion WHERE division = ?",
            (target_division,),
        ).fetchall()
    }
    if not teams:
        return {"known": False, "all_finished": False}
    rows = conn.execute(
        """
        SELECT local, visitante, status
        FROM resultados
        WHERE jornada = ? AND substr(COALESCE(fecha, ''), 1, 10) = ?
        """,
        (jornada, date_text),
    ).fetchall()
    league_rows = [
        row for row in rows
        if (
            normalize_team_key(row["local"]) in teams
            and normalize_team_key(row["visitante"]) in teams
        )
    ]
    if not league_rows:
        return {"known": False, "all_finished": False}
    final_statuses = {"FT", "FINISHED", "TERMINADO"}
    return {
        "known": True,
        "all_finished": all(str(row["status"] or "").upper() in final_statuses for row in league_rows),
    }


def _highlightly_get_matches(params, headers):
    if not reserve_highlightly_calls(1):
        return []
    url = f"https://{config.HIGHLIGHTLY_HOST}/matches"
    try:
        response = requests.get(url, params=params, headers=headers, timeout=8)
        response.raise_for_status()
        record_highlightly_success()
        return response.json().get("data", [])
    except requests.RequestException as exc:
        record_highlightly_failure(exc)
        return []


def fetch_highlightly_matches(date_text, conn=None, jornada=None, max_calls=None):
    circuit = get_highlightly_circuit()
    if circuit.get("open"):
        return []
    call_limit = HIGHLIGHTLY_MAX_CALLS_PER_REFRESH if max_calls is None else max(0, int(max_calls))
    if call_limit <= 0:
        return []
    headers = {"x-rapidapi-key": os.getenv("HIGHLIGHTLY_API_KEY", "")}
    matches = []

    if not HIGHLIGHTLY_ACTIVE_LEAGUES:
        for match in _highlightly_get_matches({
            "date": date_text,
            "timezone": "Europe/Madrid",
            "limit": 100,
        }, headers):
            league = match.get("league") or {}
            match["_competition_name"] = league.get("name") or ""
            matches.append(match)
        return matches

    calls_used = 0
    for league_name, league_id in config.HIGHLIGHTLY_LEAGUES.items():
        if HIGHLIGHTLY_ACTIVE_LEAGUES and league_name.upper() not in HIGHLIGHTLY_ACTIVE_LEAGUES:
            continue
        if calls_used >= call_limit:
            break
        if conn is not None and jornada is not None:
            local_status = _local_league_status_for_date(conn, jornada, date_text, league_name)
            if local_status["known"] and local_status["all_finished"]:
                continue
        calls_used += 1
        for match in _highlightly_get_matches({
            "date": date_text,
            "leagueId": league_id,
            "timezone": "Europe/Madrid",
            "limit": 100,
        }, headers):
            match["_competition_name"] = league_name
            matches.append(match)
        if get_highlightly_circuit().get("open"):
            break
    return matches


def refresh_dates_for_jornada(conn, jornada=None):
    today = today_madrid()
    target_jornada = resolve_jornada(conn, jornada)
    dates = {today}
    if not target_jornada:
        return sorted(dates)
    rows = conn.execute("""
        SELECT fecha, status, goles_local, goles_visitante
        FROM resultados WHERE jornada = ?
    """, (target_jornada,)).fetchall()
    for row in rows:
        fecha = str(row["fecha"] or "").strip()[:10]
        if not fecha or fecha > today:
            continue
        status = str(row["status"] or "").upper()
        has_score = row["goles_local"] is not None and row["goles_visitante"] is not None
        if not has_score or status in ("NS", "SCHEDULED", "NOT STARTED", "LIVE", "IN PLAY", "HT", "EN JUEGO"):
            dates.add(fecha)
    return sorted(dates)


def refresh_current_matches_from_highlightly(force=False, jornada=None):
    global _highlightly_last_refresh
    HIGHLIGHTLY_API_KEY = os.getenv("HIGHLIGHTLY_API_KEY", "")
    if not HIGHLIGHTLY_REFRESH_ENABLED or not HIGHLIGHTLY_API_KEY:
        return 0
    now = time.time()
    with _highlightly_thread_management_lock:
        if not force and now - _highlightly_last_refresh < 35:
            return 0
        _highlightly_last_refresh = now
    if not _highlightly_refresh_lock.acquire(blocking=False):
        return 0
    try:
        updates = 0
        api_matches = []
        with get_db() as conn:
            target_jornada = resolve_jornada(conn, jornada)
            if not target_jornada:
                return 0
            calls_left = HIGHLIGHTLY_MAX_CALLS_PER_REFRESH
            dates = refresh_dates_for_jornada(conn, target_jornada)
            today = today_madrid()
            dates = sorted(dates, key=lambda item: (item != today, item))
            for date_text in dates:
                if calls_left <= 0:
                    break
                if get_highlightly_circuit().get("open"):
                    break
                usage_before = get_highlightly_usage().get("calls", 0)
                api_matches.extend(fetch_highlightly_matches(
                    date_text,
                    conn=conn,
                    jornada=target_jornada,
                    max_calls=calls_left,
                ))
                usage_after = get_highlightly_usage().get("calls", usage_before)
                calls_left -= max(0, int(usage_after or 0) - int(usage_before or 0))

            feed = {}
            logos = {}
            for match in api_matches:
                home_team = match.get("homeTeam") or {}
                away_team = match.get("awayTeam") or {}
                home_name = home_team.get("name")
                away_name = away_team.get("name")
                if home_name and away_name:
                    home_key = normalize_team_key(home_name)
                    away_key = normalize_team_key(away_name)
                    feed[(home_key, away_key)] = (match, False)
                    feed[(away_key, home_key)] = (match, True)
                if home_name and home_team.get("logo"):
                    logos[home_name.upper()] = home_team["logo"]
                if away_name and away_team.get("logo"):
                    logos[away_name.upper()] = away_team["logo"]

            panel_matches = [highlightly_match_to_panel(match) for match in api_matches if match.get("id")]
            if panel_matches:
                panel_path = os.path.join(config.DATA_DIR, "LIVE_ALL_MATCHES_V3.json")
                update_json_list_by_id_locked(panel_path, panel_matches)

            rows = conn.execute("""
                SELECT partido_id, local, visitante, status, minuto, goles_local, goles_visitante
                FROM resultados WHERE jornada = ?
            """, (target_jornada,)).fetchall()
            for row in rows:
                if str(row["minuto"] or "").upper().startswith("SUSPENDIDO LAE"):
                    continue
                feed_item = feed.get((normalize_team_key(row["local"]), normalize_team_key(row["visitante"])))
                if not feed_item:
                    continue
                match, reversed_match = feed_item
                state = match.get("state") or {}
                score_text = ((state.get("score") or {}).get("current") or "")
                home_goals, away_goals = parse_score_text(score_text)
                if reversed_match:
                    home_goals, away_goals = away_goals, home_goals
                status, minute = highlightly_status(state)
                signo = signo_for_match(row["partido_id"], home_goals, away_goals)
                conn.execute("""
                    UPDATE resultados
                    SET goles_local = ?, goles_visitante = ?, status = ?, minuto = ?, signo_actual = ?
                    WHERE jornada = ? AND partido_id = ?
                """, (home_goals, away_goals, status, minute, signo, target_jornada, row["partido_id"]))
                updates += 1

        if logos:
            logo_path = os.path.join(config.DATA_DIR, "TEAM_LOGOS.json")
            update_json_object_locked(logo_path, logos)
        return updates
    except Exception:
        logger.exception("Error refrescando resultados desde Highlightly")
        return 0
    finally:
        _highlightly_refresh_lock.release()


def trigger_highlightly_refresh_async(force=False, jornada=None):
    global _highlightly_refresh_thread, _highlightly_refresh_started_at, _highlightly_last_refresh
    HIGHLIGHTLY_API_KEY = os.getenv("HIGHLIGHTLY_API_KEY", "")
    if not HIGHLIGHTLY_REFRESH_ENABLED or not HIGHLIGHTLY_API_KEY:
        return False
    if get_highlightly_circuit().get("open"):
        return False
    now = time.time()
    with _highlightly_thread_management_lock:
        if not force and now - _highlightly_last_refresh < 35:
            return False
        thread = _highlightly_refresh_thread
        if thread and thread.is_alive():
            if now - _highlightly_refresh_started_at < 300:
                return False
            _highlightly_refresh_thread = None

        def _runner():
            try:
                refresh_current_matches_from_highlightly(force=force, jornada=jornada)
            finally:
                pass

        _highlightly_refresh_started_at = now
        _highlightly_refresh_thread = threading.Thread(target=_runner, name="highlightly-refresh", daemon=True)
        _highlightly_refresh_thread.start()
        return True
