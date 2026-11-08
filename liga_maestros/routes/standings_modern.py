from flask import Blueprint, jsonify
from ..services.payloads import standings
from ..db.connection import get_db

bp = Blueprint('standings_modern', __name__, url_prefix='/api/modern/standings')

@bp.route('/')
def get_all_standings():
    conn = get_db()
    try:
        # We use the existing service but ensure it's optimized
        data = standings.build_standings(conn) 
        return jsonify({"status": "success", "data": data})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
