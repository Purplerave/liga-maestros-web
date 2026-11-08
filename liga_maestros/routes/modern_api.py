"""Match endpoints used by the Next.js frontend."""

from flask import Blueprint, jsonify

from ..db.connection import get_db
from ..services.payloads.matches import build_jornada_matches

bp = Blueprint("api_modern", __name__, url_prefix="/api/modern")


@bp.get("/jornada/<jornada>")
def get_jornada(jornada):
    conn = get_db()
    from .liga_data import load_team_logos

    data = build_jornada_matches(conn, jornada, load_team_logos())
    return jsonify({"status": "success", "data": data})
