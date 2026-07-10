"""Snake game routes: scores and leaderboard."""
from datetime import datetime
from flask import Blueprint, request, jsonify, session

from ..db.connection import get_db
from ..middleware.rate_limit import is_rate_limited
from ..db.migrations import ensure_snake_table

bp = Blueprint("snake", __name__)


@bp.route('/api/snake')
def get_snake_scores():
    user = session.get("user") or {}
    conn = get_db()
    try:
        ensure_snake_table(conn)
        rows = conn.execute("""
            SELECT nombre, score, created_at FROM snake_scores
            ORDER BY score DESC, datetime(created_at) ASC LIMIT 8
        """).fetchall()
        mine = None
        if user.get("id"):
            mine_row = conn.execute("SELECT MAX(score) AS best FROM snake_scores WHERE user_id = ?", (user.get("id"),)).fetchone()
            mine = int(mine_row["best"] or 0) if mine_row else 0
        return jsonify({"status": "ok", "auth": bool(user.get("id")), "scores": [dict(row) for row in rows], "mine": mine})
    finally:
        conn.close()


@bp.route('/api/snake', methods=['POST'])
def post_snake_score():
    user = session.get("user")
    if not user:
        return jsonify({"status": "error", "message": "Entra con Google para guardar tu puntuacion."}), 401
    if is_rate_limited("snake_score", user.get("id"), 3):
        return jsonify({"status": "error", "message": "Espera unos segundos antes de guardar otra puntuacion."}), 429
    data = request.get_json(silent=True) or {}
    try:
        score = int(data.get("score"))
    except (TypeError, ValueError):
        return jsonify({"status": "error", "message": "Puntuacion invalida."}), 400
    if score < 0 or score > 99999:
        return jsonify({"status": "error", "message": "Puntuacion fuera de rango."}), 400

    conn = get_db()
    try:
        ensure_snake_table(conn)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute("INSERT INTO snake_scores (user_id, nombre, score, created_at) VALUES (?, ?, ?, ?)", (user.get("id"), (user.get("name") or "Maestro").split(" ")[0], score, now))
        conn.commit()
        return jsonify({"status": "ok", "score": score})
    finally:
        conn.close()
