"""Build league/directo match payloads for the newspaper pages."""
import json
import os
import re
from datetime import timedelta

import config
from ...services.ticket import today_madrid
from ...utils import normalize_team_key, parse_any_match_datetime


def build_all_league_matches(jornada, partidos, standings_db, team_logos):
    def logo_for(team_name):
        return team_logos.get(normalize_team_key(team_name), "")

    all_league_matches = _load_external_matches()
    quiniela_league_matches = _build_quiniela_league_matches(jornada, partidos, standings_db)
    quiniela_pairs = {
        (normalize_team_key(m.get("local")), normalize_team_key(m.get("visitante")))
        for m in quiniela_league_matches
    }

    all_league_matches = _filter_external_matches_to_jornada_window(all_league_matches, quiniela_league_matches)
    all_league_matches = [
        match for match in all_league_matches
        if _is_domestic_league_match(match) and not _duplicates_quiniela_match(match, quiniela_pairs)
    ]
    all_league_matches = quiniela_league_matches + all_league_matches

    for match in all_league_matches:
        home_name = match.get("local") or match.get("home_name") or (match.get("home") or {}).get("name")
        away_name = match.get("visitante") or match.get("away_name") or (match.get("away") or {}).get("name")
        match["home_logo"] = match.get("home_logo") or (match.get("home") or {}).get("logo") or logo_for(home_name)
        match["away_logo"] = match.get("away_logo") or (match.get("away") or {}).get("logo") or logo_for(away_name)

    return all_league_matches


def _load_external_matches():
    candidate_match_paths = [
        os.path.join(config.DATA_DIR, "LIVE_ALL_MATCHES_V3.json"),
        os.path.join(config.BASE_DIR, "LIVE_ALL_MATCHES_V3.json"),
        os.path.join(config.DATA_DIR, "LIVE_ALL_MATCHES.json"),
    ]
    extra_panel_path = os.getenv("LIVE_ALL_MATCHES_EXTRA_PATH", "").strip()
    if extra_panel_path:
        candidate_match_paths.insert(0, extra_panel_path)
    for path in candidate_match_paths:
        if not os.path.exists(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as fh:
                loaded_matches = json.load(fh)
            if loaded_matches:
                return loaded_matches
        except Exception:
            pass
    return []


def _build_quiniela_league_matches(jornada, partidos, standings_db):
    quiniela_league_matches = []
    for match in partidos:
        comp = _infer_match_competition(match, standings_db)
        fecha = match.get("fecha_raw") or ""
        hora = match.get("hora") or ""
        quiniela_league_matches.append({
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
        })
    return quiniela_league_matches


def _infer_match_competition(match, standings_db):
    home_key = normalize_team_key(match.get("local"))
    away_key = normalize_team_key(match.get("visitante"))
    if "HYPERMOTION" in home_key or "HYPERMOTION" in away_key:
        return "SEGUNDA DIVISION"
    if home_key in standings_db.get("primera", {}) and away_key in standings_db.get("primera", {}):
        return "LA LIGA"
    if home_key in standings_db.get("segunda", {}) and away_key in standings_db.get("segunda", {}):
        return "SEGUNDA DIVISION"
    return "FRIENDLIES"


def _filter_external_matches_to_jornada_window(all_league_matches, quiniela_league_matches):
    # Si no hay partidos de quiniela, no mostrar externos
    if not quiniela_league_matches:
        return []

    # Verificar si hay partidos de quiniela en vivo o terminados
    quiniela_has_live = any(
        str(m.get("status") or "").upper() in ("LIVE", "IN PLAY", "FT", "FINISHED")
        for m in quiniela_league_matches
    )

    # Si no hay partidos en vivo/terminados en la quiniela, no mostrar externos
    if not quiniela_has_live:
        return []

    quiniela_datetimes = [dt for dt in (parse_any_match_datetime(m) for m in quiniela_league_matches) if dt]
    if not quiniela_datetimes:
        return []

    window_start = min(quiniela_datetimes) - timedelta(days=1)
    window_end = max(quiniela_datetimes) + timedelta(days=1)
    today_str = today_madrid()

    def keep_external_match(match):
        dt = parse_any_match_datetime(match)
        if dt and window_start <= dt <= window_end:
            return True
        raw_status = str(match.get("status") or "").upper()
        raw_score = str(match.get("score") or match.get("marcador") or "").strip()
        match_date = str(match.get("added") or match.get("fecha_raw") or "")[:10]
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
    if competition not in ("LA LIGA", "SEGUNDA DIVISION"):
        return False
    home = match.get("local") or match.get("home_name") or (match.get("home") or {}).get("name")
    away = match.get("visitante") or match.get("away_name") or (match.get("away") or {}).get("name")
    return (normalize_team_key(home), normalize_team_key(away)) in quiniela_pairs
