"""Build league/directo match payloads for the newspaper pages."""

import json
import os
import re
import threading
from datetime import datetime, timedelta
from typing import Any

import config

from ...services.live_state import (
    RESET_TO_SCHEDULED,
    closes_live,
    evaluate_match_state,
    is_final_status,
    is_live_status,
)
from ...services.teams import signo_desde_goles
from ...services.ticket import madrid_now, today_madrid
from ...utils import FEMININE_CANONICALS, is_feminine_competition, normalize_team_key, parse_any_match_datetime

STALE_LIVE_AFTER = timedelta(minutes=120)
_LIVE_STATUSES = {"LIVE", "IN PLAY", "HT", "HALF TIME BREAK", "EN JUEGO", "1H", "2H", "ET", "P", "SUSPENDED"}


def _close_stale_live_match(match):
    """Return a display-safe copy of a live match that cannot really be live.

    Three independent signals are evaluated (see ``services.live_state``) so
    the page never depends on the clock alone:

    * the kickoff is still in the future (a reschedule or a mismatched fixture
      left the row at LIVE, sometimes at minute 90);
    * the broadcast minute is ahead of the elapsed real time (frozen snapshot);
    * the provider stopped updating (quota, network error, collector restart).

    STALE is used rather than inventing an official FT result: the score is
    kept and the next genuine provider update still replaces this fallback. A
    match that was never actually playing goes back to SCHEDULED instead, so it
    is announced with its kickoff time rather than a fake final score.
    """
    if not is_live_status(match.get("status")):
        return match
    kickoff = parse_any_match_datetime(match)
    now = madrid_now().replace(tzinfo=None)
    decision = evaluate_match_state(
        match.get("status"),
        kickoff,
        now,
        last_update_at=_match_updated_at(match),
        minute=match.get("time") or match.get("minute") or match.get("minuto"),
        full_match_window=STALE_LIVE_AFTER,
        # Panel externo de solo lectura: aqui si se cierra un minuto imposible
        # (fallback de pintado; el snapshot se reemplaza entero en la siguiente
        # pasada). Las filas de la quiniela usan el default (SKIP) para no
        # congelar marcadores parciales como finales.
        close_minute_ahead=True,
    )
    if not closes_live(decision["action"]):
        return match
    closed = dict(match)
    if decision["action"] == RESET_TO_SCHEDULED:
        closed["status"] = "SCHEDULED"
        closed["time"] = ""
        closed["minute"] = ""
        closed["score"] = ""
        closed["marcador"] = ""
        return closed
    closed["status"] = "STALE"
    closed["time"] = "Finalizado"
    closed["minute"] = "Finalizado"
    return closed


def _match_updated_at(match):
    """Read the provider freshness stamp from a payload match, if present."""
    raw = match.get("updated_at") or match.get("fetched_at")
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(str(raw))
    except ValueError:
        return None
    return parsed.replace(tzinfo=None) if parsed.tzinfo is not None else parsed


def _close_stale_live_matches(matches):
    return [_close_stale_live_match(match) for match in matches]


def build_all_league_matches(jornada, partidos, standings_db, team_logos):
    quiniela_league_matches = _close_stale_live_matches(_build_quiniela_league_matches(jornada, partidos, standings_db))
    # Prefiltro barato sobre el panel cacheado (superconjunto de lo que deja
    # pasar el filtro de ventana): no se copian ni se evaluan miles de partidos
    # de otras fechas. El filtro completo se aplica igual justo debajo.
    today_str, _, _, window_dates = _jornada_window(quiniela_league_matches)
    all_league_matches = _external_matches_where(
        lambda match: _could_keep_external_match(match, today_str, window_dates)
    )
    quiniela_pairs = {_match_pair_key(match) for match in quiniela_league_matches}

    all_league_matches = _filter_external_matches_to_jornada_window(all_league_matches, quiniela_league_matches)
    all_league_matches = [
        match
        for match in all_league_matches
        if _is_domestic_league_match(match) and not _duplicates_quiniela_match(match, quiniela_pairs)
    ]
    all_league_matches = quiniela_league_matches + all_league_matches

    return _add_team_logos(all_league_matches, team_logos)


def build_live_matches(partidos, team_logos, standings_db=None):
    """Return genuinely live matches, never expired provider snapshots.

    The same fixture reaches this payload from two sources with different ids:
    the quiniela row in the DB (id ``quiniela-*``) and the external provider
    panel (numeric fixture id). Deduplicating by id alone let both through, so
    DIRECTO showed the same match twice — once in its real league group and
    once mislabelled. Matches are therefore merged by team pair as well, and
    the quiniela copy wins so the competition label stays consistent with the
    rest of the app.
    """
    # Cerrar un directo nunca convierte en directo lo que no lo era: basta con
    # copiar y evaluar los que el panel trae en vivo.
    external_live = [match for match in _external_matches_where(_is_live_match) if _is_live_match(match)]
    quiniela_live = [
        match
        for match in _close_stale_live_matches(_build_quiniela_league_matches("", partidos, standings_db or {}))
        if _is_live_match(match)
    ]
    merged = []
    seen_keys = set()
    seen_pairs = set()
    for match in quiniela_live + external_live:
        pair = _match_pair_key(match)
        key = str(match.get("fixture_id") or match.get("id") or "").strip() or pair
        if not key or key in seen_keys or (pair and pair in seen_pairs):
            continue
        seen_keys.add(key)
        if pair:
            seen_pairs.add(pair)
        merged.append(match)
    return _add_team_logos(merged, team_logos)


def apply_verified_provider_scores(partidos):
    """Keep verified provider scores on quiniela fixtures after they leave live.

    The Directo payload intentionally drops a fixture as soon as it is no
    longer live. The quiniela row has a different lifetime: it keeps the last
    verified live score and then the final result, even while the database
    result collector is catching up.
    """
    # Solo pueden cruzar los partidos del proveedor a +-1 dia de alguna casilla
    # (la misma regla que se aplica abajo con las fechas ya parseadas). Filtrar
    # antes por la cadena de fecha evita normalizar nombres y parsear fechas de
    # miles de partidos de otras jornadas: era el 60 % del coste de la peticion.
    candidate_dates = _candidate_dates_around(partidos)

    def could_cross(provider):
        status = str(provider.get("status") or "").strip().upper()
        if status == "STALE" or not (is_live_status(status) or is_final_status(status)):
            return False
        date_hint = _match_date_hint(provider)
        return candidate_dates is None or not date_hint or date_hint in candidate_dates

    provider_matches = _external_matches_where(could_cross)
    by_pair = {}
    for provider in provider_matches:
        # Cerrar un directo caducado lo deja en STALE: se vuelve a mirar.
        status = str(provider.get("status") or "").strip().upper()
        if status == "STALE" or not (is_live_status(status) or is_final_status(status)):
            continue
        home = provider.get("local") or provider.get("home_name") or (provider.get("home") or {}).get("name")
        away = provider.get("visitante") or provider.get("away_name") or (provider.get("away") or {}).get("name")
        competition = provider.get("competition_name") or provider.get("competition")
        feminine_competition = is_feminine_competition(competition)
        pair = (
            normalize_team_key(home, feminine=feminine_competition),
            normalize_team_key(away, feminine=feminine_competition),
        )
        if not pair[0] or not pair[1]:
            continue
        kickoff = parse_any_match_datetime(provider)
        if not kickoff:
            continue
        scores = provider.get("scores")
        raw_score = provider.get("score") or provider.get("marcador")
        if not raw_score:
            raw_score = scores.get("score") if isinstance(scores, dict) else scores
        score_match = re.match(r"^\s*(\d{1,2})\s*[-–:]\s*(\d{1,2})", str(raw_score or ""))
        if not score_match:
            continue
        # If both a live and a finished snapshot exist, the final one wins.
        previous = by_pair.get(pair)
        if previous and is_final_status(previous["status"]) and not is_final_status(status):
            continue
        by_pair[pair] = {
            "status": status,
            "home_goals": int(score_match.group(1)),
            "away_goals": int(score_match.group(2)),
            "minute": str(provider.get("time") or provider.get("minute") or provider.get("minuto") or "").strip(),
            "kickoff_date": kickoff.date(),
        }

    merged = []
    for match in partidos:
        pair = (normalize_team_key(match.get("local")), normalize_team_key(match.get("visitante")))
        result = by_pair.get(pair)
        kickoff = parse_any_match_datetime(match)
        if not result or not kickoff or abs((result["kickoff_date"] - kickoff.date()).days) > 1:
            merged.append(match)
            continue
        row = dict(match)
        home_goals = result["home_goals"]
        away_goals = result["away_goals"]
        score = f"{home_goals}-{away_goals}"
        status = result["status"]
        row.update(
            {
                "status": status,
                "goles_local": home_goals,
                "goles_visitante": away_goals,
                "signo_actual": signo_desde_goles(home_goals, away_goals) or "-",
                "marcador_base": score,
                "marcador": score,
            }
        )
        minute = result["minute"]
        if is_live_status(status):
            row["minuto"] = minute
            minute_number = re.search(r"\d{1,3}", minute)
            row["minuto_live"] = f"{minute_number.group(0)}'" if minute_number else ""
            if minute_number:
                row["marcador"] = f"{score} ({minute_number.group(0)}')"
        merged.append(row)
    return merged


def _match_date_hint(match):
    """Fecha (YYYY-MM-DD) que usara ``parse_any_match_datetime``, sin parsear."""
    raw = str(match.get("fecha_raw") or "").strip()[:10] or str(match.get("added") or "").strip()[:10]
    return raw if len(raw) == 10 and raw[4] == "-" and raw[7] == "-" else ""


def _candidate_dates_around(partidos, days=1):
    """Fechas de las casillas +-``days``; None si alguna casilla no tiene fecha."""
    dates = set()
    for match in partidos or []:
        kickoff = parse_any_match_datetime(match)
        if kickoff is None:
            return None
        for offset in range(-days, days + 1):
            dates.add((kickoff.date() + timedelta(days=offset)).isoformat())
    return dates


def _match_pair_key(match):
    """Team-pair identity key, robust across the two payload shapes."""
    competition = match.get("competition_name") or match.get("competition")
    feminine_competition = is_feminine_competition(competition)
    home = normalize_team_key(
        match.get("local") or match.get("home_name") or (match.get("home") or {}).get("name"),
        feminine=feminine_competition,
    )
    away = normalize_team_key(
        match.get("visitante") or match.get("away_name") or (match.get("away") or {}).get("name"),
        feminine=feminine_competition,
    )
    if not home or not away:
        return ""
    return f"{home}|{away}"


def _add_team_logos(matches, team_logos):
    def logo_for(team_name):
        if not team_name:
            return ""
        key = normalize_team_key(team_name)
        logo = team_logos.get(key, "")
        if logo:
            return logo
        # Fallback: strip FEMENINO / F suffix and try base team
        base = key
        for suffix in (" FEMENINO", " F"):
            if base.endswith(suffix):
                base = base[: -len(suffix)].strip()
                break
        if base and base in team_logos:
            return team_logos[base]
        # Also try clean base
        from ...utils import clean_team_key

        clean_base = clean_team_key(base)
        if clean_base in team_logos:
            return team_logos[clean_base]
        # Last resort: try without any feminine marker
        return team_logos.get(base, "")

    for match in matches:
        home_name = match.get("local") or match.get("home_name") or (match.get("home") or {}).get("name")
        away_name = match.get("visitante") or match.get("away_name") or (match.get("away") or {}).get("name")
        match["home_logo"] = match.get("home_logo") or (match.get("home") or {}).get("logo") or logo_for(home_name)
        match["away_logo"] = match.get("away_logo") or (match.get("away") or {}).get("logo") or logo_for(away_name)
    return matches


def _is_live_match(match):
    # _close_stale_live_matches ya elimina snapshots caducados. No filtres un
    # partido confirmado por la fecha de "added" (que puede ser de importación)
    # ni por el día de inicio: un partido nocturno puede seguir en juego pasada
    # la medianoche. Usa el mismo catálogo de estados que el cierre de directos.
    return is_live_status(match.get("status"))


# Cache del panel externo ya parseado, por (ruta, mtime_ns, tamaño). El panel
# acumula todos los partidos que ha visto el proveedor (varios MB a mitad de
# temporada) y cada /api/liga/data lo parseaba tres veces: medido en local con
# 6.000 partidos, ~150 ms por peticion solo en json.load. Ahora se parsea una
# vez por version del fichero y cada lector recibe copias superficiales (los
# builders añaden claves como los logos y no deben tocar la copia cacheada).
_EXTERNAL_CACHE_LOCK = threading.Lock()
_EXTERNAL_CACHE: dict[str, Any] = {"key": None, "matches": []}


def _external_candidate_paths():
    candidate_match_paths = [
        os.path.join(config.DATA_DIR, "LIVE_ALL_MATCHES_V3.json"),
        os.path.join(config.BASE_DIR, "LIVE_ALL_MATCHES_V3.json"),
        os.path.join(config.DATA_DIR, "LIVE_ALL_MATCHES.json"),
    ]
    extra_panel_path = os.getenv("LIVE_ALL_MATCHES_EXTRA_PATH", "").strip()
    if extra_panel_path:
        candidate_match_paths.insert(0, extra_panel_path)
    return candidate_match_paths


def _read_external_file(path):
    try:
        stat = os.stat(path)
    except OSError:
        return None
    key = (path, stat.st_mtime_ns, stat.st_size)
    with _EXTERNAL_CACHE_LOCK:
        if _EXTERNAL_CACHE["key"] == key:
            return _EXTERNAL_CACHE["matches"]
    try:
        with open(path, encoding="utf-8") as fh:
            loaded_matches = json.load(fh)
    except Exception:
        return None
    if not isinstance(loaded_matches, list):
        return None
    loaded_matches = [match for match in loaded_matches if isinstance(match, dict)]
    with _EXTERNAL_CACHE_LOCK:
        _EXTERNAL_CACHE["key"] = key
        _EXTERNAL_CACHE["matches"] = loaded_matches
    return loaded_matches


def _load_external_matches():
    """Copias superficiales del panel externo (el primer candidato con datos)."""
    for path in _external_candidate_paths():
        loaded_matches = _read_external_file(path)
        if loaded_matches:
            return [dict(match) for match in loaded_matches]
    return []


def _external_matches_where(predicate):
    """Panel externo ya filtrado por ``predicate`` y con los directos caducados cerrados.

    El filtro barato va antes del cierre (que evalua el estado de cada partido
    contra el reloj): con miles de partidos de otras fechas en el panel, cerrar
    solo los candidatos es lo que mantiene la peticion por debajo de 50 ms.
    """
    return _close_stale_live_matches([match for match in _load_external_matches() if predicate(match)])


def _build_quiniela_league_matches(jornada, partidos, standings_db):
    quiniela_league_matches = []
    for match in partidos:
        comp = _infer_match_competition(match, standings_db)
        fecha = match.get("fecha_raw") or ""
        hora = match.get("hora") or ""
        quiniela_league_matches.append(
            {
                "id": f"quiniela-{jornada}-{match['id']}",
                "fixture_id": f"quiniela-{jornada}-{match['id']}",
                "competition_name": comp,
                "competition": {"name": comp},
                "local": match["local"],
                "visitante": match["visitante"],
                "home": {"name": match["local"]},
                "away": {"name": match["visitante"]},
                "home_logo": match.get("logo_local", ""),
                "away_logo": match.get("logo_visitante", ""),
                "status": match["status"],
                "time": match.get("minuto") or "",
                "score": match["marcador"] if match["status"] not in ("NS", "SCHEDULED") else "",
                "marcador": match["marcador"],
                "added": f"{fecha} {hora}".strip(),
                "scheduled": hora,
                "fecha_raw": fecha,
                "hora": hora,
            }
        )
    return quiniela_league_matches


def _infer_match_competition(match, standings_db):
    home_raw = str(match.get("local") or "")
    away_raw = str(match.get("visitante") or "")
    home_key = normalize_team_key(home_raw)
    away_key = normalize_team_key(away_raw)

    # Liga F detection: explicit (F) marker or feminine canonical
    feminine_indicators = ("(F)", "FEMENINO", "FEMENINA", " WOMEN")
    is_feminine_raw = any(ind in f"{home_raw.upper()} {away_raw.upper()}" for ind in feminine_indicators)
    # If either side is known feminine canonical or raw has (F), it's Liga F
    if is_feminine_raw or home_key in FEMININE_CANONICALS or away_key in FEMININE_CANONICALS:
        # If one side is feminine and the other is ambiguous (e.g. Alaves without marker paired with Valencia F),
        # treat as Liga F as well - this fixes J3 partido 13
        return "LIGA F"

    if "HYPERMOTION" in home_key or "HYPERMOTION" in away_key:
        return "SEGUNDA DIVISION"
    if home_key in standings_db.get("primera", {}) and away_key in standings_db.get("primera", {}):
        return "LA LIGA"
    if home_key in standings_db.get("segunda", {}) and away_key in standings_db.get("segunda", {}):
        return "SEGUNDA DIVISION"
    return "FRIENDLIES"


def _jornada_window(quiniela_league_matches):
    """(hoy, inicio, fin, fechas) de la ventana de la jornada; sin ventana -> None."""
    today_str = today_madrid()
    window_start = window_end = None
    if quiniela_league_matches:
        quiniela_datetimes = [dt for dt in (parse_any_match_datetime(m) for m in quiniela_league_matches) if dt]
        quiniela_has_live = any(
            str(m.get("status") or "").upper() in ("LIVE", "IN PLAY", "FT", "FINISHED") for m in quiniela_league_matches
        )
        if quiniela_datetimes and quiniela_has_live:
            window_start = min(quiniela_datetimes) - timedelta(days=1)
            window_end = max(quiniela_datetimes) + timedelta(days=1)

    window_dates = None
    if window_start is not None:
        window_dates = {
            (window_start.date() + timedelta(days=offset)).isoformat()
            for offset in range((window_end.date() - window_start.date()).days + 1)
        }
    return today_str, window_start, window_end, window_dates


def _could_keep_external_match(match, today_str, window_dates):
    """Superconjunto barato (sin parsear) de lo que conserva el filtro de ventana."""
    if _is_live_match(match):
        return True
    if str(match.get("added") or match.get("fecha_raw") or "")[:10] == today_str:
        return True
    date_hint = _match_date_hint(match)
    return not date_hint or date_hint == today_str or (window_dates is not None and date_hint in window_dates)


def _filter_external_matches_to_jornada_window(all_league_matches, quiniela_league_matches):
    """Keep external matches that are relevant right now.

    Always keep today's matches (scheduled, live or finished today): a
    midweek Castellon game must show up in the Directo even when the
    quiniela is idle. Additionally, during the jornada window keep the
    matches inside it, as before.
    """
    today_str, window_start, window_end, window_dates = _jornada_window(quiniela_league_matches)

    def keep_external_match(match):
        # Un directo ya validado por _close_stale_live_matches es relevante
        # aunque el proveedor conserve una fecha de importación antigua.
        if is_live_status(match.get("status")):
            return True
        match_date = str(match.get("added") or match.get("fecha_raw") or "")[:10]
        if match_date == today_str:
            return True
        # Descarte barato por la cadena de fecha antes de parsear: el panel
        # trae miles de partidos de otras fechas y strptime era la mitad del
        # coste de este filtro. Es la misma fecha que parsearia
        # parse_any_match_datetime, asi que el resultado no cambia.
        date_hint = _match_date_hint(match)
        if date_hint and date_hint != today_str and (window_dates is None or date_hint not in window_dates):
            return False
        dt = parse_any_match_datetime(match)
        if dt is not None and dt.strftime("%Y-%m-%d") == today_str:
            return True
        if window_start is not None and dt is not None and window_start <= dt <= window_end:
            return True
        raw_status = str(match.get("status") or "").upper()
        raw_score = str(match.get("score") or match.get("marcador") or "").strip()
        has_score = bool(re.search(r"\d+\s*-\s*\d+", raw_score))
        looks_live = raw_status in ("LIVE", "IN PLAY", "HT", "EN JUEGO")
        return match_date == today_str and (looks_live or has_score)

    return [match for match in all_league_matches if keep_external_match(match)]


def _is_domestic_league_match(match):
    competition = (match.get("competition_name") or (match.get("competition") or {}).get("name") or "").upper()
    blocked = (
        "UEFA",
        "CHAMPIONS",
        "EUROPA LEAGUE",
        "CONFERENCE LEAGUE",
        "SUPERCUP",
        "SUPER CUP",
        "FRIENDLIES",
        "FRIENDLY",
    )
    return not any(token in competition for token in blocked)


def _duplicates_quiniela_match(match, quiniela_pairs):
    competition = (match.get("competition_name") or (match.get("competition") or {}).get("name") or "").upper()
    if competition not in (
        "LA LIGA",
        "SEGUNDA DIVISION",
        "LIGA F",
        "LIGA F MOEVE",
        "PRIMERA DIVISION FEMENINA",
    ):
        return False
    return _match_pair_key(match) in quiniela_pairs
