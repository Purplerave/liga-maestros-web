"""Liga data route: the main data endpoint."""
import logging
import time
import threading

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
from ..utils import build_team_contract, load_team_logos, normalize_team_key
from ..middleware.rate_limit import is_rate_limited

bp = Blueprint("liga_data", __name__)
logger = logging.getLogger(__name__)

_max_jornada_cache = {"value": None, "ts": 0.0, "lock": threading.Lock()}
_MAX_JORNADA_TTL = 5.0


def _get_cached_max_jornada(conn, ttl=_MAX_JORNADA_TTL):
    now = time.time()
    if _max_jornada_cache["value"] is not None and now - _max_jornada_cache["ts"] < ttl:
        return _max_jornada_cache["value"]
    with _max_jornada_cache["lock"]:
        if _max_jornada_cache["value"] is not None and time.time() - _max_jornada_cache["ts"] < ttl:
            return _max_jornada_cache["value"]
        row = conn.execute("SELECT MAX(jornada) FROM resultados").fetchone()
        _max_jornada_cache["value"] = row[0] if row and row[0] is not None else None
        _max_jornada_cache["ts"] = time.time()
        return _max_jornada_cache["value"]


def invalidate_max_jornada_cache():
    _max_jornada_cache["ts"] = 0.0


@bp.route("/api/liga/data")
def get_liga_data():
    if is_rate_limited("liga_data_read", request.remote_addr, 2):
        return jsonify({"status": "error", "message": "Demasiadas peticiones"}), 429
    requested_jornada = request.args.get("j", "").strip()
    conn = get_db()
    try:
        max_jornada = _get_cached_max_jornada(conn)
        if max_jornada is None:
            return jsonify({"status": "error", "message": "No hay jornadas cargadas en resultados"}), 404

        jornada = int(requested_jornada) if requested_jornada.isdigit() else max_jornada
        if jornada < 1 or jornada > max_jornada + 2:
            return jsonify({"status": "error", "message": "Jornada no disponible", "max_jornada": max_jornada}), 404

        has_matches = conn.execute(
            "SELECT 1 FROM resultados WHERE jornada = ? LIMIT 1", (jornada,)
        ).fetchone()
        if not has_matches:
            return jsonify({
                "status": "error",
                "message": "Jornada sin partidos cargados",
                "max_jornada": max_jornada,
            }), 404

        team_logos_all = load_team_logos()
        partidos = build_jornada_matches(conn, jornada, team_logos_all)
        needed = set()
        for match in partidos:
            for field in ("local", "visitante"):
                name = match.get(field) or ""
                if name and name != "-":
                    needed.add(normalize_team_key(name))
        team_logos = {k: v for k, v in team_logos_all.items() if k in needed}
        standings, standings_db = build_standings_payload(conn, partidos)
        all_league_matches = build_all_league_matches(jornada, partidos, standings_db, team_logos)
        multi_league_leagues = build_multi_league_standings(standings)
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
            "today_madrid": today_madrid(),
            "is_locked": is_locked,
            "edit_deadline": _format_dt(close_info.get("close_at")),
            "kickoff_at": _format_dt(close_info.get("first_kickoff")),
            "partidos": partidos,
            "all_league_matches": all_league_matches,
            "standings": standings,
            "multi_league_standings": multi_league_standings,
            "team_logos": team_logos,
            "team_contract": build_team_contract(),
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
