"""Highlightly API integration: circuit breaker, usage tracking, refresh."""

import logging
import os
import re
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
    team_key_variants,
)
from .highlightly_limits import (
    get_highlightly_circuit,
    get_highlightly_usage,
    record_highlightly_failure,
    record_highlightly_success,
    reserve_highlightly_calls,
)
from .live_state import KEEP, evaluate_match_state, is_live_status
from .ticket import madrid_now, today_madrid

logger = logging.getLogger(__name__)

HIGHLIGHTLY_REFRESH_ENABLED = os.getenv("HIGHLIGHTLY_REFRESH_ENABLED", "1").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)
# Presupuesto de llamadas por pasada de refresco. Con 1 llamada, una jornada
# que ocupa varias fechas (vie/sab/dom) solo refrescaba "hoy": los partidos
# terminados de ayer quedaban para siempre en NS ("no aparecen"). 4 llamadas
# cubren una jornada tipica de fin de semana (2-3 fechas + garantia Liga F).
HIGHLIGHTLY_MAX_CALLS_PER_REFRESH = max(0, int(os.getenv("HIGHLIGHTLY_MAX_CALLS_PER_REFRESH", "4")))
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
# States that confirm a final score. STALE is deliberately absent: a row frozen
# with a partial score is exactly what needs an explicit re-query.
_CONFIRMED_FINAL_STATUSES = frozenset(
    {
        "FT",
        "FINISHED",
        "TERMINADO",
        "AET",
        "PEN",
        "AWARDED",
        "FINISHED AFTER EXTRA TIME",
        "FINISHED AFTER PENALTIES",
    }
)
# Male competitions the quiniela mixes. They need an explicit per-league query
# when the active jornada has an unconfirmed result: the generic /matches page
# is capped at 100 rows and a match that has just finished drops out of the
# first page, so its row kept the last live score forever (Ceuta 1-1 STALE).
_PENDING_LEAGUE_NAMES = ("SEGUNDA DIVISION", "LA LIGA")
# Legal-form tokens that carry no identity: the quiniela writes "Ceuta" where
# the provider writes "AD Ceuta FC". They are dropped before the fuzzy feed
# lookup, which is only accepted when it is unambiguous.
_CORE_NOISE_TOKENS = frozenset(
    {
        "AD",
        "CF",
        "FC",
        "CD",
        "UD",
        "SD",
        "RC",
        "R",
        "CP",
        "CV",
        "SAD",
        "CLUB",
        "DEPORTIVO",
        "SPORTING",
    }
)
# How long after kickoff a match without a confirmed result is still polled.
# Covers the weekend chain (Fri -> Sat -> Sun) without burning quota on rows
# that need manual intervention.
HIGHLIGHTLY_PENDING_WINDOW_HOURS = float(os.getenv("HIGHLIGHTLY_PENDING_WINDOW_HOURS", "30"))

_highlightly_refresh_lock = threading.RLock()
_highlightly_last_refresh = 0
_highlightly_refresh_thread = None
_highlightly_refresh_started_at = 0
_highlightly_thread_management_lock = threading.Lock()


def resolve_jornada(conn, jornada=None):
    raw = str(jornada or "").strip()
    if raw.isdigit():
        return int(raw)
    # Sin jornada explicita hay que usar la jornada ACTIVA de la temporada
    # publicada (J1..42), no MAX(jornada): la BD conserva jornadas 51-76 del
    # periodo de pruebas 2025/26 y con MAX() el sync, el refresco manual y el
    # refresh-all apuntaban a la quiniela nordica de agosto en vez de a la
    # jornada en juego.
    from .jornada import resolve_active_jornada

    try:
        active = resolve_active_jornada(conn)
    except Exception:
        active = None
    if active:
        return int(active)
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

    all_finished = all(str(r["status"] or "").upper() in ("FT", "FINISHED", "TERMINADO") for r in rows)
    if all_finished:
        needs_result_catchup = False
        enabled = False
    else:
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


def _quiniela_has_pending_matches_on_date(conn, jornada, date_text, now=None):
    """True when the active jornada has a kickoff-passed match on ``date_text``
    whose final result is still unconfirmed.

    ``STALE`` and rows without goals count as pending on purpose: a match frozen
    with a partial score is precisely the case that needs an explicit query.
    """
    if conn is None or jornada is None or not date_text:
        return False
    now = now or madrid_now().replace(tzinfo=None)
    earliest = now - timedelta(hours=HIGHLIGHTLY_PENDING_WINDOW_HOURS)
    try:
        rows = conn.execute(
            """
            SELECT status, goles_local, goles_visitante, fecha, hora
            FROM resultados
            WHERE jornada = ? AND substr(COALESCE(fecha, ''), 1, 10) = ?
            """,
            (int(jornada), str(date_text)),
        ).fetchall()
    except Exception:
        return False
    for row in rows:
        status = str(row["status"] or "").upper()
        has_score = row["goles_local"] is not None and row["goles_visitante"] is not None
        if has_score and status in _CONFIRMED_FINAL_STATUSES:
            continue
        try:
            kickoff = parse_db_match_datetime(row["fecha"], row["hora"])
        except Exception:
            kickoff = None
        if kickoff is None or kickoff > now or kickoff < earliest:
            continue
        return True
    return False


def _merge_unique_matches(matches, extra, competition_name):
    known_ids = {str(match.get("id")) for match in matches if match.get("id") is not None}
    for match in extra or []:
        match_id = match.get("id")
        if match_id is not None and str(match_id) in known_ids:
            continue
        match["_competition_name"] = competition_name
        matches.append(match)
        if match_id is not None:
            known_ids.add(str(match_id))
    return matches


def _append_priority_league_matches(matches, date_text, headers, league_names, budget=0):
    """Explicit per-league fetch for the competitions the quiniela follows.

    The generic ``/matches`` list is paginated (``limit=100``) and on a busy
    matchday a match that has just finished falls outside the first page, so the
    quiniela never saw its final score and the row kept the last live one. One
    extra call per competition, only while the active jornada still has an
    unconfirmed result, recovers it.
    """
    for league_name in league_names or ():
        if budget <= 0:
            break
        league_id = config.HIGHLIGHTLY_LEAGUES.get(league_name)
        if not league_id:
            continue
        budget -= 1
        _merge_unique_matches(
            matches,
            _highlightly_get_matches(
                {"date": date_text, "leagueId": league_id, "timezone": "Europe/Madrid", "limit": 100},
                headers,
            ),
            league_name,
        )
    return matches


def _append_liga_f_matches(matches, date_text, headers, needed, budget=None):
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
    for name_variant in _LIGA_F_NAME_VARIANTS:
        if budget is not None and budget <= 0:
            break
        try:
            extra = _highlightly_get_matches(
                {"date": date_text, "leagueName": name_variant, "timezone": "Europe/Madrid", "limit": 100},
                headers,
            )
        except Exception:
            extra = []
        if budget is not None:
            budget -= 1
        if not extra:
            continue
        _merge_unique_matches(matches, extra, "LIGA F")
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
    has_pending = _quiniela_has_pending_matches_on_date(conn, jornada, date_text)

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
        # La llamada generica ya consumio una unidad del presupuesto de la pasada.
        budget = max(0, call_limit - 1)
        if needs_liga_f:
            before = int(get_highlightly_usage().get("calls", 0))
            matches = _append_liga_f_matches(matches, date_text, headers, True, budget=budget)
            budget = max(0, budget - max(0, int(get_highlightly_usage().get("calls", 0)) - before))
        if has_pending:
            matches = _append_priority_league_matches(matches, date_text, headers, _PENDING_LEAGUE_NAMES, budget=budget)
        return matches

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
    return _append_liga_f_matches(
        matches,
        date_text,
        headers,
        needs_liga_f,
        budget=max(0, call_limit - calls_used),
    )


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


def _core_team_key(value):
    """Tokens of a team name without legal-form noise ("AD Ceuta FC" -> CEUTA)."""
    tokens = [
        token
        for token in re.split(r"[^A-Z0-9]+", str(value or "").upper())
        if token and token not in _CORE_NOISE_TOKENS
    ]
    return tuple(sorted(tokens))


def _find_feed_item(feed, local_raw, visitante_raw, core_feed=None):
    """Busca el partido del feed cruzando nombres por variantes.

    El feed esta indexado por pares de claves canonicas del proveedor en
    ambas orientaciones. Aqui se prueban las variantes de cada lado
    (canonico, base sin sufijo femenino, base con sufijos F/FEMENINO), de
    modo que "Barcelona (F)" cruza con "Barcelona Femenino" o
    "Logrono (F)" con "EDF Logrono" aunque los sufijos de origen difieran.
    El cruce masculino/femenino sigue siendo imposible: las variantes
    respetan el genero del nombre original.

    Segundo nivel: si el cruce canonico falla, se ignora la forma juridica
    ("Ceuta" <-> "AD Ceuta FC", "R. Sociedad" <-> "Real Sociedad"). Solo se
    acepta si ese par no es ambiguo dentro del feed, para no cruzar el
    partido equivocado.
    """
    for local_variant in team_key_variants(local_raw):
        for visit_variant in team_key_variants(visitante_raw):
            item = feed.get((local_variant, visit_variant))
            if item:
                return item
    if not core_feed:
        return None
    local_core = _core_team_key(local_raw)
    visit_core = _core_team_key(visitante_raw)
    if not local_core or not visit_core:
        return None
    candidates = {}
    for orientation in ((local_core, visit_core), (visit_core, local_core)):
        for item in core_feed.get(orientation, []):
            candidates[item[0].get("id")] = item
    if len(candidates) != 1:
        # 0 = no hay cruce; >1 = ambiguo, no se escribe nada.
        return None
    return next(iter(candidates.values()))


def refresh_current_matches_from_highlightly(force=False, jornada=None):
    global _highlightly_last_refresh
    HIGHLIGHTLY_API_KEY = os.getenv("HIGHLIGHTLY_API_KEY", "")
    if not HIGHLIGHTLY_REFRESH_ENABLED or not HIGHLIGHTLY_API_KEY:
        return 0
    if not force:
        with get_db() as conn:
            target_j = resolve_jornada(conn, jornada)
            win = compute_refresh_window(conn, target_j)
            if not win.get("enabled"):
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
            # Fechas pasadas primero: son partidos terminados que necesitan
            # recuperar su resultado (catch-up). Con el orden anterior (hoy
            # primero) y presupuesto bajo, "ayer" nunca recibia llamada y sus
            # resultados no aparecian aunque se hubiera jugado.
            dates = sorted(dates)
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
            core_feed = {}
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
                    home_core = _core_team_key(home_name)
                    away_core = _core_team_key(away_name)
                    if home_core and away_core:
                        core_feed.setdefault((home_core, away_core), []).append((match, False))
                        core_feed.setdefault((away_core, home_core), []).append((match, True))

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
                feed_item = _find_feed_item(feed, row["local"], row["visitante"], core_feed)

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
                # match got stuck at LIVE 90' with a 17:00 kickoff. SKIP_SNAPSHOT
                # (minuto por delante con ventana abierta) tampoco se escribe:
                # la fila conserva su ultimo estado bueno.
                if is_live_status(status):
                    decision = evaluate_match_state(
                        status,
                        parse_db_match_datetime(row["fecha"], row["hora"]),
                        now.replace(tzinfo=None),
                        last_update_at=now.replace(tzinfo=None),
                        minute=minute,
                    )
                    if decision["action"] != KEEP:
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
    if not force:
        with get_db() as conn:
            target_j = resolve_jornada(conn, jornada)
            win = compute_refresh_window(conn, target_j)
            if not win.get("enabled"):
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
