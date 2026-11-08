"""Standings endpoint used by the Next.js frontend."""

from flask import Blueprint, current_app, jsonify, request

from ..db.connection import get_db
from ..services.payloads.predictions import build_predictions_payload

bp = Blueprint("standings_modern", __name__, url_prefix="/api/modern/standings")


@bp.get("/", strict_slashes=False)
def get_all_standings():
    conn = get_db()
    jornada = request.args.get("jornada", "1")

    try:
        payload = build_predictions_payload(conn, jornada)
    except Exception:
        current_app.logger.exception("No se pudo construir la clasificación moderna")
        return jsonify({"status": "error", "message": "No se pudo cargar la clasificación"}), 500

    names = (payload.get("participant_contract") or {}).get("names") or {}
    ranking = payload.get("ranking_maestros") or {}
    data = []
    for participant_id, stats in ranking.items():
        bonus = int(stats.get("bonus") or 0)
        total_points = int(stats.get("total") or 0)
        data.append(
            {
                "id": participant_id,
                "name": names.get(participant_id) or participant_id,
                "hits": max(0, total_points - bonus),
                "points": total_points,
            }
        )
    data.sort(key=lambda row: (-row["points"], -row["hits"], row["name"].casefold()))
    return jsonify({"status": "success", "data": data})
