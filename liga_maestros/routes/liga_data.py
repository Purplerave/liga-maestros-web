"""Liga data route: the main data endpoint."""
import logging

from flask import Blueprint, jsonify, request, session

import config
from ..db.connection import get_db
from ..middleware.authz import is_admin_request
from ..services.payloads.league_matches import build_all_league_matches
from ..services.payloads.matches import build_jornada_matches
from ..services.payloads.predictions import build_predictions_payload
from ..services.payloads.standings import build_standings_payload
from ..services.multi_standings import build_multi_league_standings
from ..services.teams import build_participant_contract
from ..services.ticket import compute_ticket_close_info, load_match_info_for_jornada, madrid_now, today_madrid
from ..utils import load_team_logos

bp = Blueprint("liga_data", __name__)
logger = logging.getLogger(__name__)

@bp.route("/api/liga/data")
def get_liga_data():
    requested_jornada = request.args.get("j", "")
    conn = get_db()
    try:
        max_jornada = _resolve_max_jornada(conn)
        if max_jornada is None:
            return jsonify({"status": "error", "message": "No hay jornadas cargadas en resultados"}), 404

        jornadas_disponibles = _resolve_available_jornadas(conn)
        jornada = requested_jornada or max_jornada
        team_logos = load_team_logos()
        partidos = build_jornada_matches(conn, jornada, team_logos)
        standings, standings_db = build_standings_payload(conn, partidos)
        all_league_matches = build_all_league_matches(jornada, partidos, standings_db, team_logos)
        multi_league_leagues = build_multi_league_standings(standings, team_logos)
        multi_league_standings = {"leagues": multi_league_leagues}
        jornada_liga = _detect_jornada_liga(conn)
        match_info = _load_and_repair_match_info(jornada, partidos)
        close_info = compute_ticket_close_info(partidos, source=f"api_liga_data_j{jornada}")
        is_locked = _is_ticket_locked(partidos, close_info)
        user = session.get("user") or {}
        predictions_payload = build_predictions_payload(
            conn,
            jornada,
            current_user_id=user.get("id"),
            reveal_all=is_locked,
        )

        participant_contract = predictions_payload.get("participant_contract") or build_participant_contract()
        return jsonify({
            "jornada": jornada,
            "jornada_liga": jornada_liga,
            "max_jornada": max_jornada,
            "jornadas_disponibles": jornadas_disponibles,
            "today_madrid": today_madrid(),
            "is_locked": is_locked,
            "edit_deadline": _format_dt(close_info.get("close_at")),
            "kickoff_at": _format_dt(close_info.get("first_kickoff")),
            "partidos": partidos,
            "all_league_matches": all_league_matches,
            "standings": standings,
            "multi_league_standings": multi_league_standings,
            "participant_contract": participant_contract,
            "match_info": match_info,
            "predicciones_actuales": predictions_payload["predicciones_actuales"],
            "consenso_pena": predictions_payload["consenso_pena"],
            "consenso_pleno_pena": predictions_payload["consenso_pleno_pena"],
            "ranking_maestros": predictions_payload["ranking_maestros"],
            "auth_enabled": config.GOOGLE_AUTH_ENABLED,
            "is_admin": is_admin_request(),
            "ticket_policy": {
                "max_dobles": config.MAX_DOBLES_PER_TICKET,
                "max_triples": config.MAX_TRIPLES_PER_TICKET,
            },
        })
    finally:
        conn.close()


def _resolve_max_jornada(conn):
    row = conn.execute("SELECT MAX(jornada) FROM resultados").fetchone()
    if not row or row[0] is None:
        return None
    return row[0]

def _resolve_available_jornadas(conn):
    rows = conn.execute("""
        SELECT jornada, COUNT(*) AS partidos
        FROM resultados
        GROUP BY jornada
        HAVING partidos > 0
        ORDER BY jornada DESC
    """).fetchall()
    return [int(row["jornada"]) for row in rows if row["jornada"] is not None]

def _detect_jornada_liga(conn):
    try:
        row = conn.execute("SELECT AVG(pj) as avg_pj FROM clasificacion WHERE division = 1").fetchone()
        if row and row["avg_pj"] is not None:
            return str(int(round(row["avg_pj"])))
    except Exception:
        logger.exception("No se pudo detectar la jornada de liga")
        return ""
    return ""


def _is_ticket_locked(partidos, close_info):
    close_at = close_info.get("close_at")
    close_started = bool(close_at and madrid_now() >= close_at)
    match_started = any((match.get("status") or "") in ("LIVE", "FT", "FINISHED") for match in partidos)
    return close_started or match_started


def _format_dt(value):
    return value.strftime("%Y-%m-%d %H:%M") if value else ""


def _load_and_repair_match_info(jornada, partidos):
    match_info = load_match_info_for_jornada(jornada)
    partidos_by_id = {str(match.get("id")): match for match in partidos}
    for match_id, info in match_info.items():
        detail = info.get("detalle") or ""
        if "Hypermotion" not in detail:
            continue
        match = partidos_by_id.get(str(match_id)) or {}
        detail = (
            detail
            .replace("6Âº Hypermotion", match.get("local") or "Local")
            .replace("3Âº Hypermotion", match.get("visitante") or "Visitante")
            .replace("5Âº Hypermotion", match.get("local") or "Local")
            .replace("4Âº Hypermotion", match.get("visitante") or "Visitante")
        )
        info["detalle"] = detail
    return match_info
