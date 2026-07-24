"""User routes: status, stats."""
from flask import Blueprint, request, jsonify, session

from ..db.connection import get_db
from ..services.teams import contest_aliases_for_uid, is_scored_status
from ..services.contest import build_contest_payload
from ..scoring import score_prediction
from ..middleware.csrf import get_csrf_token

bp = Blueprint("user", __name__)


@bp.route('/api/user/status')
def user_status():
    session_user = session.get('user') or {}
    user = None
    if session_user:
        user = {
            "id": session_user.get("id"),
            "name": session_user.get("name"),
            "is_admin": bool(session_user.get("is_admin")),
        }
    return jsonify({"user": user, "csrf_token": get_csrf_token() if user else None})


@bp.route('/api/user/stats')
def get_user_stats():
    uid = request.args.get('uid')
    if not uid:
        return jsonify({})
    current_user = session.get("user") or {}
    current_uid = str(current_user.get("id") or "")
    is_admin = bool(current_user.get("is_admin"))
    if not is_admin:
        email = str(current_user.get("email") or "").strip().lower()
        is_admin = bool(email and email in _admin_emails())
    if str(uid) != current_uid and not is_admin:
        return jsonify({"status": "forbidden"}), 403

    conn = get_db()
    try:
        aliases = contest_aliases_for_uid(uid)
        placeholders = ",".join("?" for _ in aliases)
        rows = conn.execute("""
            SELECT p.jornada, p.partido_id, p.signo, r.signo_actual, r.goles_local, r.goles_visitante, r.status
            FROM predicciones p
            JOIN resultados r ON p.jornada = r.jornada AND p.partido_id = r.partido_id
            WHERE p.user_id IN ({})
            ORDER BY p.jornada, p.partido_id
        """.format(placeholders), aliases).fetchall()
    finally:
        conn.close()

    total_hits = 0
    by_jornada = {}
    for row in rows:
        if not is_scored_status(row["status"]):
            continue
        real = row["signo_actual"]
        if int(row["partido_id"] or 0) == 15 and row["goles_local"] is not None and row["goles_visitante"] is not None:
            real = f"{int(row['goles_local'])}-{int(row['goles_visitante'])}"
        hit = score_prediction(row["partido_id"], row["signo"], real)
        total_hits += hit
        jornada = int(row["jornada"])
        by_jornada[jornada] = by_jornada.get(jornada, 0) + hit

    best_hits = max(by_jornada.values(), default=0)
    profile = None
    try:
        profile = build_contest_payload(None, uid).get("profile")
    except Exception:
        pass
    return jsonify({
        "total_aciertos": total_hits,
        "mejor_jornada": best_hits,
        "posicion": profile.get("position") if profile else None,
    })


def _admin_emails():
    import os
    return {email.strip().lower() for email in os.getenv("ADMIN_EMAILS", "").split(",") if email.strip()}
