"""Arcade games generic routes: scores and leaderboards."""
from datetime import datetime
from flask import Blueprint, request, jsonify, session

from ..db.connection import get_db
from ..middleware.rate_limit import is_rate_limited
from ..db.migrations import ensure_arcade_table

bp = Blueprint("arcade", __name__)

ALLOWED_GAMES = {"snake", "arkanoid", "invaders"}


@bp.route('/api/arcade/<game_id>')
def get_arcade_scores(game_id):
    if game_id not in ALLOWED_GAMES:
        return jsonify({"status": "error", "message": "Juego invalido."}), 400

    user = session.get("user") or {}
    conn = get_db()
    try:
        ensure_arcade_table(conn)
        rows = conn.execute("""
            SELECT nombre, score, created_at FROM arcade_scores
            WHERE game_id = ?
            ORDER BY score DESC, datetime(created_at) ASC LIMIT 10
        """, (game_id,)).fetchall()
        mine = None
        if user.get("id"):
            mine_row = conn.execute(
                "SELECT MAX(score) AS best FROM arcade_scores WHERE game_id = ? AND user_id = ?",
                (game_id, user.get("id"))
            ).fetchone()
            mine = int(mine_row["best"] or 0) if mine_row and mine_row["best"] is not None else 0
        return jsonify({
            "status": "ok",
            "game_id": game_id,
            "auth": bool(user.get("id")),
            "scores": [dict(row) for row in rows],
            "mine": mine
        })
    finally:
        conn.close()


@bp.route('/api/arcade/<game_id>', methods=['POST'])
def post_arcade_score(game_id):
    if game_id not in ALLOWED_GAMES:
        return jsonify({"status": "error", "message": "Juego invalido."}), 400

    user = session.get("user")
    if not user:
        return jsonify({"status": "error", "message": "Entra con Google para guardar tu puntuacion."}), 401

    if is_rate_limited(f"arcade_score_{game_id}", user.get("id"), 3):
        return jsonify({"status": "error", "message": "Espera unos segundos antes de guardar otra puntuacion."}), 429

    data = request.get_json(silent=True) or {}
    try:
        score = int(data.get("score"))
    except (TypeError, ValueError):
        return jsonify({"status": "error", "message": "Puntuacion invalida."}), 400

    if score < 0 or score > 999999:
        return jsonify({"status": "error", "message": "Puntuacion fuera de rango."}), 400

    conn = get_db()
    try:
        ensure_arcade_table(conn)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        nombre = (user.get("name") or "Maestro").split(" ")[0]
        conn.execute(
            "INSERT INTO arcade_scores (game_id, user_id, nombre, score, created_at) VALUES (?, ?, ?, ?, ?)",
            (game_id, user.get("id"), nombre, score, now)
        )
        conn.commit()
        return jsonify({"status": "ok", "game_id": game_id, "score": score})
    finally:
        conn.close()
