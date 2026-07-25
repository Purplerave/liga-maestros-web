"""Short, authenticated comments attached to a contest jornada."""

from datetime import datetime

from flask import Blueprint, jsonify, request, session

from ..db.connection import get_db
from ..middleware.csrf import valid_csrf_request
from ..middleware.rate_limit import is_rate_limited

bp = Blueprint("comments", __name__)

MAX_COMMENT_LENGTH = 240
MAX_VISIBLE_COMMENTS = 40


def _valid_jornada(raw_value):
    value = str(raw_value or "").strip()
    if not value.isdigit():
        return None
    jornada = int(value)
    return jornada if 1 <= jornada <= 999 else None


@bp.get("/api/comentarios")
def get_comments():
    jornada = _valid_jornada(request.args.get("j"))
    if jornada is None:
        return jsonify({"status": "error", "message": "Jornada invalida"}), 400

    conn = get_db()
    try:
        rows = conn.execute(
            """
            SELECT id, nombre, texto, etiqueta, created_at
            FROM comentarios_jornada
            WHERE jornada = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (jornada, MAX_VISIBLE_COMMENTS),
        ).fetchall()
    finally:
        conn.close()

    comments = [dict(row) for row in reversed(rows)]
    return jsonify({"status": "ok", "jornada": jornada, "comments": comments})


@bp.post("/api/comentarios")
def post_comment():
    user = session.get("user") or {}
    user_id = str(user.get("id") or "").strip()
    if not user_id:
        return jsonify({"status": "error", "message": "Inicia sesion para comentar"}), 401
    if not valid_csrf_request():
        return jsonify({"status": "error", "message": "Sesion no valida"}), 403
    if is_rate_limited("jornada_comment", user_id, 4):
        return jsonify({"status": "error", "message": "Espera unos segundos"}), 429

    payload = request.get_json(silent=True) or {}
    jornada = _valid_jornada(payload.get("jornada"))
    text = " ".join(str(payload.get("texto") or "").split())
    if jornada is None:
        return jsonify({"status": "error", "message": "Jornada invalida"}), 400
    if not text:
        return jsonify({"status": "error", "message": "Escribe un comentario"}), 400
    if len(text) > MAX_COMMENT_LENGTH:
        return jsonify({"status": "error", "message": f"Maximo {MAX_COMMENT_LENGTH} caracteres"}), 400

    name = " ".join(str(user.get("name") or "Participante").split())[:60]
    created_at = datetime.now().astimezone().isoformat(timespec="seconds")
    conn = get_db()
    try:
        cursor = conn.execute(
            """
            INSERT INTO comentarios_jornada
                (jornada, user_id, nombre, texto, etiqueta, created_at)
            VALUES (?, ?, ?, ?, 'Jornada', ?)
            """,
            (jornada, user_id, name, text, created_at),
        )
        conn.commit()
        comment_id = cursor.lastrowid
    finally:
        conn.close()

    return jsonify(
        {
            "status": "ok",
            "comment": {
                "id": comment_id,
                "nombre": name,
                "texto": text,
                "etiqueta": "Jornada",
                "created_at": created_at,
            },
        }
    )
