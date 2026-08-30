"""Highlightly API integration: circuit breaker, usage tracking, refresh."""

import logging
import os
import threading
import time
from datetime import timedelta

import requests

import config

from ..db.connection import get_db
from ..middleware.json_lock import update_json_list_by_id_locked, update_json_object_locked
from ..utils import (
    highlightly_match_to_panel,
    highlightly_status,
    normalize_team_key,
    parse_db_match_datetime,
    parse_score_text,
    signo_for_match,
)
from .highlightly_limits import (
    get_highlightly_circuit,
    get_highlightly_usage,
    record_highlightly_failure,
    record_highlightly_success,
    reserve_highlightly_calls,
)
from .live_state import closes_live, evaluate_match_state, is_live_status
from .ticket import madrid_now, today_madrid

logger = logging.getLogger(__name__)

HIGHLIGHTLY_REFRESH_ENABLED = os.getenv("HIGHLIGHTLY_REFRESH_ENABLED", "1").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)
HIGHLIGHTLY_MAX_CALLS_PER_REFRESH = max(0, int(os.getenv("HIGHLIGHTLY_MAX_CALLS_PER_REFRESH", "1")))
HIGHLIGHTLY_ACTIVE_LEAGUES = {
    item.strip().upper() for item in os.getenv("HIGHLIGHTLY_ACTIVE_LEAGUES", "").split(",") if item.strip()
}
HIGHLIGHTLY_BUDGET_RESERVE_PCT = float(os.getenv("HIGHLIGHTLY_BUDGET_RESERVE_PCT", "0.10"))
Q15_EXPECTED_MATCHES = 15

# Liga F league names the provider may return. leagueName queries are more
# stable than the season-dependent leagueId, so they are the first choice for
# the guaranteed Liga F fetch (see _append_liga_f_matches).
_LIGA_F_NAME_VARIANTS = (
    "Liga F",
    "Liga F Moeve",
    "Primera Division Femenina",
    "Primera División Femenina",
)
_FEMININE_ROW_MARKERS = ("(F)", "FEMENINO", "FEMENINA")
# Canonical keys of Liga F sides, so a fixture stored without the "(F)" marker
# (e.g. "Las Planas") is still recognised as a women's match.
_FEMININE_CANONICAL_KEYS = frozenset(
    {
        "ATHLETIC CLUB FEMENINO",
        "EIBAR FEMENINO",
        "ESPANYOL FEMENINO",
        "VALENCIA FEMENINO",
        "REAL MADRID FEMENINO",
        "ATLETICO MADRID FEMENINO",
        "ALAVES FEMENINO",
        "LEVANTE LAS PLANAS",
        "SEVILLA FEMENINO",
        "GRANADA FEMENINO",
        "MADRID CFF",
        "REAL SOCIEDAD FEMENINO",
        "COSTA ADEJE TENERIFE",
        "DEPORTIVO ABANCA",
        "LOGROÑO UNITED",
    }
)

_highlightly_refresh_lock = threading.RLock()
_highlightly_last_refresh = 0
_highlightly_refresh_thread = None
_highlightly_refresh_started_at = 0
_highlightly_thread_management_lock = threading.Lock()


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

    rows = conn.execute(
        """
        SELECT fecha, hora, status
        FROM resultados
        WHERE jornada = ?
        ORDER BY partido_id ASC
    """,
        (target_jornada,),
    ).fetchall()
    if not rows:
        return {"enabled": False, "reason": "sin_partidos", "jornada": target_jornada}

    match_times = [dt for dt in (parse_db_match_datetime(r["fecha"], r["hora"]) for r in rows) if dt]
    live_now = any(
        str(r["status"] or "").upper() in ("LIVE", "IN PLAY", "HT", "HALF TIME BREAK", "EN JUEGO") for r in rows
    )
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
        row
        for row in rows
        if (normalize_team_key(row["local"]) in teams and normalize_team_key(row["visitante"]) in teams)
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
        data = response.json().get("data", [])
        # If searching by leagueId for Liga F returns empty, try leagueName search as fallback
        if not data and "leagueId" in params:
            league_id = params.get("leagueId")
            # Known Liga F IDs we try to fallback to name query
            liga_f_ids = {
                config.HIGHLIGHTLY_LEAGUES.get("LIGA F"),
                config.HIGHLIGHTLY_LEAGUES.get("LIGA F MOEVE"),
                config.HIGHLIGHTLY_LEAGUES.get("PRIMERA DIVISION FEMENINA"),
            }
            if league_id in liga_f_ids:
                for name_variant in (
                    "Liga F",
                    "Liga F Moeve",
                    "Primera Division Femenina",
                    "Primera División Femenina",
                ):
                    try:
                        fallback_params = {
                            "date": params.get("date"),
                            "leagueName": name_variant,
                            "timezone": params.get("timezone", "Europe/Madrid"),
                            "limit": params.get("limit", 100),
                        }
                        if not reserve_highlightly_calls(1):
                            break
                        fb_resp = requests.get(url, params=fallback_params, headers=headers, timeout=8)
                        fb_resp.raise_for_status()
                        record_highlightly_success()
                        fb_data = fb_resp.json().get("data", [])
                        if fb_data:
                            return fb_data
                    except requests.RequestException as exc:
                        record_highlightly_failure(exc)
                        continue
        return data
    except requests.RequestException as exc:
        record_highlightly_failure(exc)
        return []


def _quiniela_has_feminine_matches_on_date(conn, jornada, date_text):
    """True when the active quiniela has a women's fixture on ``date_text``."""
    if conn is None or jornada is None or not date_text:
        return False
    try:
        rows = conn.execute(
            "SELECT local, visitante FROM resultados WHERE jornada = ? AND substr(COALESCE(fecha, ''), 1, 10) = ?",
            (int(jornada), str(date_text)),
        ).fetchall()
    except Exception:
        return False
    for row in rows:
        local = str(row["local"] or "")
        visitante = str(row["visitante"] or "")
        if any(marker in local.upper() for marker in _FEMININE_ROW_MARKERS) or any(
            marker in visitante.upper() for marker in _FEMININE_ROW_MARKERS
        ):
            return True
        if (
            normalize_team_key(local) in _FEMININE_CANONICAL_KEYS
            or normalize_team_key(visitante) in _FEMININE_CANONICAL_KEYS
        ):
            return True
    return False


def _append_liga_f_matches(matches, date_text, headers, needed):
    """Guarantee Liga F coverage for the quiniela feed.

    The generic ``/matches`` list is paginated (``limit=100``) and on a busy
    matchday the women's fixtures can fall outside the first page, so the
    quiniela never sees them live. When the active jornada has a feminine
    fixture on this date we query Liga F explicitly by name and merge the
    results (dedup by id). One extra call per date, only when the quiniela
    actually tracks a women's fixture that day.
    """
    if not needed:
        return matches
    known_ids = {str(match.get("id")) for match in matches if match.get("id") is not None}
    for name_variant in _LIGA_F_NAME_VARIANTS:
        try:
            extra = _highlightly_get_matches(
                {"date": date_text, "leagueName": name_variant, "timezone": "Europe/Madrid", "limit": 100},
                headers,
            )
        except Exception:
            extra = []
        if not extra:
            continue
        for match in extra:
            match_id = match.get("id")
            if match_id is not None and str(match_id) in known_ids:
                continue
            match["_competition_name"] = "LIGA F"
            matches.append(match)
            if match_id is not None:
                known_ids.add(str(match_id))
        break
    return matches


def fetch_highlightly_matches(date_text, conn=None, jornada=None, max_calls=None):
    circuit = get_highlightly_circuit()
    if circuit.get("open"):
        return []
    # Budget guard: when budget <10%, only fetch critical leagues
    low_budget = False
    try:
        usage = get_highlightly_usage()
        remaining = int(usage.get("usable_remaining", usage.get("limit", 7500)))
        limit = int(usage.get("limit", 7500))
        low_budget = bool(limit and remaining / limit < HIGHLIGHTLY_BUDGET_RESERVE_PCT)
    except Exception:
        low_budget = False
    call_limit = HIGHLIGHTLY_MAX_CALLS_PER_REFRESH if max_calls is None else max(0, int(max_calls))
    if call_limit <= 0:
        return []
    headers = {"x-rapidapi-key": os.getenv("HIGHLIGHTLY_API_KEY", "")}
    matches = []
    needs_liga_f = _quiniela_has_feminine_matches_on_date(conn, jornada, date_text)

    if not HIGHLIGHTLY_ACTIVE_LEAGUES:
        for match in _highlightly_get_matches(
            {
                "date": date_text,
                "timezone": "Europe/Madrid",
                "limit": 100,
            },
            headers,
        ):
            league = match.get("league") or {}
            match["_competition_name"] = league.get("name") or ""
            matches.append(match)
        return _append_liga_f_matches(matches, date_text, headers, needs_liga_f)

    calls_used = 0
    # CEO fix: ensure Liga F is always considered critical, even in low budget
    critical_leagues = {"LA LIGA", "SEGUNDA DIVISION", "LIGA F", "LIGA F MOEVE", "PRIMERA DIVISION FEMENINA"}
    for league_name, league_id in config.HIGHLIGHTLY_LEAGUES.items():
        if low_budget and league_name.upper() not in critical_leagues:
            continue
        if HIGHLIGHTLY_ACTIVE_LEAGUES and league_name.upper() not in HIGHLIGHTLY_ACTIVE_LEAGUES:
            # If active leagues filter is set but Liga F is in quiniela, still fetch it
            # unless filter explicitly excludes feminine leagues
            if league_name.upper() in critical_leagues:
                # Allow if quiniela contains feminine matches (checked via conn)
                pass
            else:
                continue
        if calls_used >= call_limit:
            break
        if conn is not None and jornada is not None:
            local_status = _local_league_status_for_date(conn, jornada, date_text, league_name)
            if local_status["known"] and local_status["all_finished"]:
                continue
        calls_used += 1
        for match in _highlightly_get_matches(
            {
                "date": date_text,
                "leagueId": league_id,
                "timezone": "Europe/Madrid",
                "limit": 100,
            },
            headers,
        ):
            match["_competition_name"] = league_name
            matches.append(match)
        if get_highlightly_circuit().get("open"):
            break
    return _append_liga_f_matches(matches, date_text, headers, needs_liga_f)


def refresh_dates_for_jornada(conn, jornada=None):
    today = today_madrid()
    target_jornada = resolve_jornada(conn, jornada)
    dates = {today}
    if not target_jornada:
        return sorted(dates)
    rows = conn.execute(
        """
        SELECT fecha, status, goles_local, goles_visitante
        FROM resultados WHERE jornada = ?
    """,
        (target_jornada,),
    ).fetchall()
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
                api_matches.extend(
                    fetch_highlightly_matches(
                        date_text,
                        conn=conn,
                        jornada=target_jornada,
                        max_calls=calls_left,
                    )
                )
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
                    # Additional feminine fallback: if team is feminine, also register base name without FEMENINO
                    # to match quiniela entries that may have omitted (F) marker (e.g. Alaves vs Valencia F)
                    for hk, ak in [(home_key, away_key)]:
                        # Try base variants
                        for key in (hk, ak):
                            if key.endswith(" FEMENINO"):
                                base = key[: -len(" FEMENINO")].strip()
                                # Register base variants for cross-matching
                                if base:
                                    # home base vs away, etc will be handled via separate logic below
                                    pass

                if home_name and home_team.get("logo"):
                    logos[home_name.upper()] = home_team["logo"]
                if away_name and away_team.get("logo"):
                    logos[away_name.upper()] = away_team["logo"]

            panel_matches = [highlightly_match_to_panel(match) for match in api_matches if match.get("id")]
            if panel_matches:
                panel_path = os.path.join(config.DATA_DIR, "LIVE_ALL_MATCHES_V3.json")
                update_json_list_by_id_locked(panel_path, panel_matches)

            rows = conn.execute(
                """
                SELECT partido_id, local, visitante, status, minuto, goles_local, goles_visitante, fecha, hora
                FROM resultados WHERE jornada = ?
            """,
                (target_jornada,),
            ).fetchall()
            now = madrid_now()
            stamp = now.isoformat(timespec="seconds")
            for row in rows:
                if str(row["minuto"] or "").upper().startswith("SUSPENDIDO LAE"):
                    continue
                local_key = normalize_team_key(row["local"])
                visit_key = normalize_team_key(row["visitante"])
                feed_item = feed.get((local_key, visit_key))
                # CEO fix Liga F: if not found, try feminine/base cross-matching
                if not feed_item:
                    # If one side is known feminine canonical but the other is ambiguous (Alaves),
                    # try treating Alaves as feminine too
                    alt_local_keys = [local_key]
                    alt_visit_keys = [visit_key]
                    # If key is ALAVES and the opponent is feminine, try ALAVES FEMENINO
                    feminine_set = {
                        "VALENCIA FEMENINO",
                        "ALAVES FEMENINO",
                        "ATHLETIC CLUB FEMENINO",
                        "EIBAR FEMENINO",
                        "ESPANYOL FEMENINO",
                        "REAL MADRID FEMENINO",
                        "ATLETICO MADRID FEMENINO",
                        "LEVANTE LAS PLANAS",
                    }
                    if local_key == "ALAVES" and visit_key in feminine_set:
                        alt_local_keys.append("ALAVES FEMENINO")
                    if visit_key == "ALAVES" and local_key in feminine_set:
                        alt_visit_keys.append("ALAVES FEMENINO")
                    # Try all combinations
                    for lk in alt_local_keys:
                        for vk in alt_visit_keys:
                            feed_item = feed.get((lk, vk))
                            if feed_item:
                                break
                        if feed_item:
                            break
                    # Also try stripping FEMENINO for matching
                    if not feed_item:
                        for lk in alt_local_keys:
                            base_lk = lk[: -len(" FEMENINO")].strip() if lk.endswith(" FEMENINO") else lk
                            for vk in alt_visit_keys:
                                base_vk = vk[: -len(" FEMENINO")].strip() if vk.endswith(" FEMENINO") else vk
                                feed_item = (
                                    feed.get((base_lk, base_vk)) or feed.get((lk, base_vk)) or feed.get((base_lk, vk))
                                )
                                if feed_item:
                                    break
                            if feed_item:
                                break

                if not feed_item:
                    continue
                match, reversed_match = feed_item
                state = match.get("state") or {}
                score_text = (state.get("score") or {}).get("current") or ""
                home_goals, away_goals = parse_score_text(score_text)
                if reversed_match:
                    home_goals, away_goals = away_goals, home_goals
                status, minute = highlightly_status(state)

                # Reject incoherent live snapshots (kickoff still ahead, minute
                # running faster than the clock): writing them is exactly how a
                # match got stuck at LIVE 90' with a 17:00 kickoff.
                if is_live_status(status):
                    decision = evaluate_match_state(
                        status,
                        parse_db_match_datetime(row["fecha"], row["hora"]),
                        now.replace(tzinfo=None),
                        last_update_at=now.replace(tzinfo=None),
                        minute=minute,
                    )
                    if closes_live(decision["action"]):
                        logger.warning(
                            "Snapshot LIVE incoherente descartado j=%s partido=%s motivo=%s",
                            target_jornada,
                            row["partido_id"],
                            decision["reason"],
                        )
                        continue

                signo = signo_for_match(row["partido_id"], home_goals, away_goals)
                conn.execute(
                    """
                    UPDATE resultados
                    SET goles_local = ?, goles_visitante = ?, status = ?, minuto = ?, signo_actual = ?,
                        updated_at = ?
                    WHERE jornada = ? AND partido_id = ?
                """,
                    (home_goals, away_goals, status, minute, signo, stamp, target_jornada, row["partido_id"]),
                )
                updates += 1

        if logos:
            logo_path = os.path.join(config.DATA_DIR, "TEAM_LOGOS.json")
            update_json_object_locked(logo_path, logos)

        # Check and award porra points after updating results. The `conn` used
        # above was closed when its `with` block ended, so open a fresh one
        # (previously this always failed with "Cannot operate on a closed
        # database" and porra points were never awarded from this path).
        if updates > 0:
            try:
                from ..routes.porra import check_and_award_porra_points

                with get_db() as porra_conn:
                    check_and_award_porra_points(porra_conn, target_jornada)
            except Exception:
                logger.exception("Error verificando puntos de porra")

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
            refresh_current_matches_from_highlightly(force=force, jornada=jornada)

        _highlightly_refresh_started_at = now
        _highlightly_refresh_thread = threading.Thread(target=_runner, name="highlightly-refresh", daemon=True)
        _highlightly_refresh_thread.start()
        return True
