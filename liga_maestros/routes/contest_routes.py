"""Contest routes: rankings, profiles, awards."""
from flask import Blueprint, request, jsonify, session
from ..services.contest import build_contest_payload
from ..services.teams import canonical_contest_id
from ..services.privacy import publicize_identifiers, resolve_public_participant_id
from ..db.connection import get_db

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
    return jsonify(publicize_identifiers(payload, user.get("id")))


@bp.route('/api/concurso/perfil/<uid>')
def get_contest_profile(uid):
    jornada = request.args.get("j") or None
    conn = get_db()
    try:
        resolved = resolve_public_participant_id(conn, uid)
    finally:
        conn.close()
    if not resolved:
        return jsonify({"status": "error", "message": "Perfil no encontrado"}), 404
    target = canonical_contest_id(resolved)
    profile_payload = build_contest_payload(jornada, target)
    profile = profile_payload.get("profile")
    if not profile:
        return jsonify({"status": "error", "message": "Perfil no encontrado"}), 404
    profile = dict(profile)
    profile.pop("is_user", None)
    current_user = (session.get("user") or {}).get("id")
    return jsonify({"status": "ok", "profile": publicize_identifiers(profile, current_user)})
