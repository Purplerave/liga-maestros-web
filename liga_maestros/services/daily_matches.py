"""Daily league tracking beyond the quiniela.

Keeps every match of the followed leagues (La Liga, Segunda, Premier,
Bundesliga, Ligue 1) fresh every day of the week:

1. Agenda: once per day, fetch today's fixtures for all leagues
   (1 call per league) and store the day's schedule.
2. Live windows: when any of today's matches is in its play window
   (kickoff-2min .. kickoff+3h), refresh scores so the Directo column shows
   them even on a random Tuesday (e.g. a midweek Castellon match).
3. Stats history: when a match reaches FT, fetch its statistics once
   (1 call) and append the full record to a per-season JSONL history that
   external tooling can consume for analysis.

Quota impact (7500/day): agenda ~5 calls, live refresh 5 per tick only
while matches are actually playing, stats 1 per finished match.
"""

import json
import logging
import os
import time
from datetime import datetime, timedelta

import requests

import config

from ..middleware.json_lock import update_json_list_by_id_locked
from ..utils import highlightly_match_to_panel
from .highlightly_limits import (
    get_highlightly_circuit,
    record_highlightly_failure,
    record_highlightly_success,
    reserve_highlightly_calls,
)
from .season_rosters import SEASON_ID
from .ticket import madrid_now, today_madrid

logger = logging.getLogger(__name__)

AGENDA_PATH_TEMPLATE = "DAILY_AGENDA_{date}.json"
STATE_PATH = "DAILY_TRACKER_STATE.json"
HISTORY_PATH_TEMPLATE = "HISTORICO_PARTIDOS_{season}.jsonl"

LIVE_WINDOW_BEFORE = timedelta(minutes=2)
LIVE_WINDOW_AFTER = timedelta(hours=3)


def _agenda_path(date_text):
    return os.path.join(config.DATA_DIR, AGENDA_PATH_TEMPLATE.format(date=date_text))


def _state_path():
    return os.path.join(config.DATA_DIR, STATE_PATH)


def history_path(season=None):
    return os.path.join(config.DATA_DIR, HISTORY_PATH_TEMPLATE.format(season=season or SEASON_ID))


def _load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return default


def _save_json(path, payload):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False)
    os.replace(tmp_path, path)


def _load_state():
    return _load_json(_state_path(), {})


def _save_state(state):
    _save_json(_state_path(), state)


def _api_get(path, params):
    """One quota-accounted GET against the Highlightly API."""
    api_key = os.getenv("HIGHLIGHTLY_API_KEY", "")
    if not api_key:
        return None
    if get_highlightly_circuit().get("open"):
        return None
    if not reserve_highlightly_calls(1):
        return None
    try:
        response = requests.get(
            f"https://{config.HIGHLIGHTLY_HOST}{path}",
            params=params,
            headers={"x-rapidapi-key": api_key},
            timeout=10,
        )
        response.raise_for_status()
        record_highlightly_success()
        return response.json()
    except requests.RequestException as exc:
        record_highlightly_failure(exc)
        logger.warning("Daily tracker request failed %s %s: %s", path, params, exc)
        return None


def fetch_today_agenda(date_text=None):
    """Fetch today's fixtures for every followed league (1 call per league)."""
    date_text = date_text or today_madrid()
    matches = []
    for league_name, league_id in config.HIGHLIGHTLY_LEAGUES.items():
        if league_name not in config.STANDINGS_LEAGUES and league_name not in ("LA LIGA", "SEGUNDA DIVISION"):
            continue
        payload = _api_get(
            "/matches",
            {"date": date_text, "leagueId": league_id, "timezone": "Europe/Madrid", "limit": 100},
        )
        if payload is None:
            continue
        for match in payload.get("data", []):
            match["_competition_name"] = league_name
            matches.append(match)
    return matches


def refresh_daily_agenda(force=False):
    """Build/update today's agenda file once per day. Returns the agenda."""
    today = today_madrid()
    path = _agenda_path(today)
    state = _load_state()
    if not force and state.get("agenda_date") == today and os.path.exists(path):
        return _load_json(path, {"date": today, "matches": []})

    matches = fetch_today_agenda(today)
    agenda = {
        "date": today,
        "fetched_at": madrid_now().isoformat(timespec="seconds"),
        "matches": [
            {
                "id": match.get("id"),
                "league": match.get("_competition_name", ""),
                "home": (match.get("homeTeam") or {}).get("name", ""),
                "away": (match.get("awayTeam") or {}).get("name", ""),
                "kickoff": match.get("date", ""),
            }
            for match in matches
            if match.get("id")
        ],
    }
    _save_json(path, agenda)
    state["agenda_date"] = today
    _save_state(state)

    # Feed the shared live panel so the Directo column knows today's fixtures
    # (status SCHEDULED) even before any of them kicks off.
    panel_matches = [highlightly_match_to_panel(match) for match in matches if match.get("id")]
    if panel_matches:
        panel_path = os.path.join(config.DATA_DIR, "LIVE_ALL_MATCHES_V3.json")
        update_json_list_by_id_locked(panel_path, panel_matches)

    logger.info("Daily agenda %s: %d matches in followed leagues", today, len(agenda["matches"]))
    return agenda


def _parse_kickoff(raw):
    try:
        from zoneinfo import ZoneInfo

        dt = datetime.strptime(str(raw), "%Y-%m-%dT%H:%M:%S.%fZ")
        return dt.replace(tzinfo=ZoneInfo("UTC")).astimezone(ZoneInfo("Europe/Madrid")).replace(tzinfo=None)
    except Exception:
        return None


def any_live_window_open(agenda=None):
    """True when at least one of today's matches is inside its play window."""
    agenda = agenda or _load_json(_agenda_path(today_madrid()), None)
    if not agenda:
        return False
    now = madrid_now().replace(tzinfo=None)
    for match in agenda.get("matches", []):
        kickoff = _parse_kickoff(match.get("kickoff"))
        if not kickoff:
            continue
        if kickoff - LIVE_WINDOW_BEFORE <= now <= kickoff + LIVE_WINDOW_AFTER:
            return True
    return False


def refresh_live_scores():
    """Refresh today's scores for all followed leagues into the live panel.

    Costs 1 call per league. Also detects newly finished matches and archives
    their statistics.
    """
    matches = fetch_today_agenda(today_madrid())
    if not matches:
        return 0
    panel_matches = [highlightly_match_to_panel(match) for match in matches if match.get("id")]
    if panel_matches:
        panel_path = os.path.join(config.DATA_DIR, "LIVE_ALL_MATCHES_V3.json")
        update_json_list_by_id_locked(panel_path, panel_matches)
    archive_finished_matches(matches)
    return len(panel_matches)


# --- Stats history (JSONL, one line per finished match) ---


def _already_archived_ids():
    state = _load_state()
    return set(state.get("archived_match_ids", []))


def _remember_archived(match_id):
    state = _load_state()
    archived = state.get("archived_match_ids", [])
    archived.append(match_id)
    # Keep the memory bounded; 2000 ids cover several seasons.
    state["archived_match_ids"] = archived[-2000:]
    _save_state(state)


def fetch_match_statistics(match_id):
    """Fetch post-match statistics for one match (1 call)."""
    payload = _api_get(f"/statistics/{match_id}", {})
    if payload is None:
        return None
    return payload


def _stat_value(stats_payload, names, side_index):
    """Best-effort extraction of one statistic from the Highlightly payload."""
    if not stats_payload:
        return None
    groups = stats_payload if isinstance(stats_payload, list) else stats_payload.get("data") or []
    try:
        for team_block in groups:
            statistics = team_block.get("statistics") if isinstance(team_block, dict) else None
            if statistics is None:
                continue
            if groups.index(team_block) != side_index:
                continue
            for item in statistics:
                display = str(item.get("displayName") or item.get("name") or "").strip().lower()
                if display in names:
                    raw = str(item.get("value") or "").replace("%", "").strip()
                    if raw.replace(".", "", 1).isdigit():
                        return int(float(raw))
    except Exception:
        return None
    return None


def _update_db_match_stats(record):
    """Fill posesion/tiros columns for quiniela matches when stats arrive."""
    stats = record.get("statistics")
    if not stats:
        return False
    possession_names = {"ball possession", "possession", "posesion", "posesión"}
    shots_names = {"total shots", "shots", "tiros", "tiros totales"}
    pos_h = _stat_value(stats, possession_names, 0)
    pos_a = _stat_value(stats, possession_names, 1)
    shots_h = _stat_value(stats, shots_names, 0)
    shots_a = _stat_value(stats, shots_names, 1)
    if pos_h is None and shots_h is None:
        return False
    try:
        from ..db.connection import get_db
        from ..utils import normalize_team_key

        home_key = normalize_team_key(record.get("home"))
        away_key = normalize_team_key(record.get("away"))
        with get_db() as conn:
            rows = conn.execute(
                "SELECT rowid, local, visitante FROM resultados WHERE fecha = ?",
                (str(record.get("date") or "")[:10],),
            ).fetchall()
            for row in rows:
                if normalize_team_key(row["local"]) == home_key and normalize_team_key(row["visitante"]) == away_key:
                    conn.execute(
                        "UPDATE resultados SET posesion_h = ?, posesion_a = ?, tiros_h = ?, tiros_a = ? "
                        "WHERE rowid = ?",
                        (pos_h, pos_a, shots_h, shots_a, row["rowid"]),
                    )
                    conn.commit()
                    return True
    except Exception:
        logger.exception("Could not update DB stats for match %s", record.get("match_id"))
    return False


def archive_finished_matches(api_matches):
    """Append full records for newly finished matches to the season history.

    Each JSONL line contains the raw match payload plus its statistics, so
    external analysis tooling gets goals, minute-by-minute state, possession,
    shots, cards... everything the API exposes.
    """
    archived = _already_archived_ids()
    added = 0
    for match in api_matches:
        match_id = match.get("id")
        if not match_id or match_id in archived:
            continue
        state = match.get("state") or {}
        description = str(state.get("description") or "").upper()
        if description not in ("FINISHED", "FULL TIME", "FT"):
            continue
        stats = fetch_match_statistics(match_id)
        record = {
            "archived_at": madrid_now().isoformat(timespec="seconds"),
            "season": SEASON_ID,
            "league": match.get("_competition_name") or (match.get("league") or {}).get("name", ""),
            "match_id": match_id,
            "date": match.get("date", ""),
            "home": (match.get("homeTeam") or {}).get("name", ""),
            "away": (match.get("awayTeam") or {}).get("name", ""),
            "score": (state.get("score") or {}).get("current", ""),
            "match": match,
            "statistics": stats,
        }
        path = history_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        _remember_archived(match_id)
        archived.add(match_id)
        _update_db_match_stats(record)
        added += 1
        logger.info(
            "Archived match %s (%s %s - %s)",
            match_id,
            record["league"],
            record["home"],
            record["away"],
        )
    return added


def run_daily_tick():
    """One scheduler tick: keep agenda fresh, refresh scores when needed.

    Returns a summary dict; the caller decides how long to sleep.
    """
    summary = {"agenda": 0, "panel": 0, "window_open": False}
    try:
        agenda = refresh_daily_agenda()
        summary["agenda"] = len(agenda.get("matches", []))
    except Exception:
        logger.exception("Daily agenda refresh failed")
        agenda = None
    window_open = any_live_window_open(agenda)
    summary["window_open"] = window_open
    if window_open:
        try:
            summary["panel"] = refresh_live_scores()
        except Exception:
            logger.exception("Daily live scores refresh failed")
    return summary


def cleanup_old_agendas(keep_days=7):
    """Remove agenda files older than keep_days."""
    cutoff = (madrid_now() - timedelta(days=keep_days)).strftime("%Y-%m-%d")
    try:
        for name in os.listdir(config.DATA_DIR):
            if not name.startswith("DAILY_AGENDA_") or not name.endswith(".json"):
                continue
            date_part = name[len("DAILY_AGENDA_") : -len(".json")]
            if date_part < cutoff:
                try:
                    os.remove(os.path.join(config.DATA_DIR, name))
                except OSError:
                    pass
    except OSError:
        pass


def start_daily_tracker(app=None):
    """Start the daily tracker loop (called from the web collector startup)."""
    import threading

    interval_idle = max(300, int(os.getenv("DAILY_TRACKER_IDLE_SECONDS", "900")))
    interval_live = max(60, int(os.getenv("DAILY_TRACKER_LIVE_SECONDS", "120")))

    def _loop():
        time.sleep(45)  # Let the app settle first.
        while True:
            try:
                summary = run_daily_tick()
                cleanup_old_agendas()
                sleep_seconds = interval_live if summary.get("window_open") else interval_idle
            except Exception:
                logger.exception("Daily tracker tick failed")
                sleep_seconds = interval_idle
            time.sleep(sleep_seconds)

    thread = threading.Thread(target=_loop, name="liga-daily-tracker", daemon=True)
    thread.start()
    if app is not None:
        app.extensions["daily_tracker_thread"] = thread
    return thread
