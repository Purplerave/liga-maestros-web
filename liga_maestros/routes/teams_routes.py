"""Teams routes: canonical team data, available leagues."""
from flask import Blueprint, jsonify
from ..utils import build_team_contract

bp = Blueprint("teams_routes", __name__)


@bp.route('/api/teams/canonical')
def teams_canonical():
    return jsonify({"status": "ok", "contract": build_team_contract()})


@bp.route('/api/ligas/disponibles')
def get_ligas_disponibles():
    return jsonify({"ligas": ["LA LIGA", "SEGUNDA DIVISION", "PREMIER LEAGUE", "BUNDESLIGA", "LIGUE 1"]})
