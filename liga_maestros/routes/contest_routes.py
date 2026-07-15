"""Contest routes: rankings, profiles, awards."""
from flask import Blueprint, request, jsonify, session
from ..services.contest import build_contest_payload
from ..services.teams import canonical_contest_id

bp = Blueprint("contest_routes", __name__)


@bp.route('/api/concurso')
def get_contest():
    user = session.get('user') or {}
    jornada = request.args.get("j") or None
    if jornada and not str(jornada).isdigit():
        jornada = None
    try:
        payload = build_contest_payload(jornada, user.get("id"))
    except Exception:
        payload = {"jornada": None, "galardones": {"jornadas": [], "meses": []}, "profile": None, "rows": []}
    return jsonify(payload)


@bp.route('/api/concurso/perfil/<uid>')
def get_contest_profile(uid):
    jornada = request.args.get("j") or None
    target = canonical_contest_id(uid)
    profile_payload = build_contest_payload(jornada, target)
    profile = profile_payload.get("profile")
    if not profile:
        return jsonify({"status": "error", "message": "Perfil no encontrado"}), 404
    profile.pop("is_user", None)
    return jsonify({"status": "ok", "profile": profile})
