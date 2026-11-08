from flask import Blueprint, jsonify, request
from ..services.payloads import matches, standings
from ..db.connection import get_db

bp = Blueprint('api_modern', __name__, url_prefix='/api/modern')

@bp.route('/jornada/<jornada>')
def get_jornada(jornada):
    conn = get_db()
    # Team logos would normally be passed here from a service
    data = matches.build_jornada_matches(conn, jornada, {}) 
    return jsonify({"status": "success", "data": data})

@bp.route('/standings')
def get_standings():
    conn = get_db()
    # data = standings.build_standings(conn)
    return jsonify({"status": "success", "data": []})
