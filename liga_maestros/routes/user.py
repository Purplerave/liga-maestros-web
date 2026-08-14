"""User routes: status, stats."""

from flask import Blueprint, jsonify, request, session

from ..db.connection import get_db
from ..middleware.csrf import get_csrf_token
from ..scoring import score_prediction
from ..services.contest import build_contest_payload
from ..services.engagement import (
    build_post_jornada_summary,
    build_share_card_payload,
    compute_quiniela_streak,
)
from ..services.jornada import current_season_sql
from ..services.teams import contest_aliases_for_uid, is_scored_status

bp = Blueprint("user", __name__)


@bp.route("/api/user/status")
def user_status():
    session_user = session.get("user") or {}
    user = None
    if session_user:
        user = {
            "id": session_user.get("id"),
            "name": session_user.get("name"),
            "is_admin": bool(session_user.get("is_admin")),
        }
    return jsonify({"user": user, "csrf_token": get_csrf_token() if user else None})


@bp.route("/api/user/stats")
def get_user_stats():
    uid = request.args.get("uid")
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
    aliases = contest_aliases_for_uid(uid)
    placeholders = ",".join("?" for _ in aliases)
    # Solo la temporada publicada: las jornadas de pruebas no alimentan
    # total de aciertos ni mejor jornada.
    rows = conn.execute(
        f"""
        SELECT p.jornada, p.partido_id, p.signo, r.signo_actual, r.goles_local, r.goles_visitante, r.status
        FROM predicciones p
        JOIN resultados r ON p.jornada = r.jornada AND p.partido_id = r.partido_id
        WHERE p.user_id IN ({placeholders}) AND {current_season_sql("p.jornada")}
        ORDER BY p.jornada, p.partido_id
    """,
        aliases,
    ).fetchall()

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
    streak = compute_quiniela_streak(conn, uid)
    return jsonify(
        {
            "total_aciertos": total_hits,
            "mejor_jornada": best_hits,
            "posicion": profile.get("position") if profile else None,
            "racha_actual": streak.get("racha_actual", 0),
            "racha_max": streak.get("racha_max", 0),
            "ultima_jornada": streak.get("ultima_jornada"),
            "jornadas_jugadas": streak.get("jornadas_jugadas", 0),
        }
    )


@bp.route("/api/user/post-jornada-summary")
def post_jornada_summary():
    """Resumen emocional post-jornada: tú vs maestros IA + racha."""
    user = session.get("user") or {}
    uid = request.args.get("uid") or user.get("id")
    if not uid:
        return jsonify({"status": "error", "message": "Usuario no identificado"}), 401
    current_uid = str(user.get("id") or "")
    is_admin = bool(user.get("is_admin"))
    if str(uid) != current_uid and not is_admin:
        return jsonify({"status": "forbidden"}), 403

    jornada = request.args.get("jornada", type=int)
    conn = get_db()
    summary = build_post_jornada_summary(conn, str(uid), jornada)
    if not summary:
        return jsonify({"status": "not_found", "message": "Sin jornada puntuada aún"}), 404
    return jsonify(summary)


@bp.route("/api/share-card")
def share_card():
    """Payload para tarjeta compartible (cliente o render servidor)."""
    user = session.get("user") or {}
    uid = request.args.get("uid") or user.get("id")
    if not uid:
        return jsonify({"status": "error", "message": "Usuario no identificado"}), 401
    current_uid = str(user.get("id") or "")
    is_admin = bool(user.get("is_admin"))
    if str(uid) != current_uid and not is_admin:
        return jsonify({"status": "forbidden"}), 403

    jornada = request.args.get("jornada", type=int)
    conn = get_db()
    payload = build_share_card_payload(conn, str(uid), jornada)
    if not payload:
        return jsonify({"status": "not_found", "message": "Sin datos para la tarjeta"}), 404
    return jsonify(payload)


def _admin_emails():
    import os

    return {email.strip().lower() for email in os.getenv("ADMIN_EMAILS", "").split(",") if email.strip()}
