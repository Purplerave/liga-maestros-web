"""Predictions route: save user predictions."""
import os
from flask import Blueprint, request, jsonify, session

from ..db.connection import get_db
from ..scoring import normalize_prediction_sign
from ..services.ticket import compute_ticket_close_info, madrid_now
from ..services.highlightly import Q15_EXPECTED_MATCHES
from ..services.teams import is_scored_status, is_live_scored_status
from ..middleware.rate_limit import is_rate_limited

bp = Blueprint("predictions", __name__)

MAX_DOBLES_PER_TICKET = int(os.getenv("MAX_DOBLES_PER_TICKET", "14"))
MAX_TRIPLES_PER_TICKET = int(os.getenv("MAX_TRIPLES_PER_TICKET", "14"))


@bp.route('/api/predicciones/save', methods=['POST'])
def save_predictions():
    user = session.get('user')
    if not user:
        return jsonify({"status": "error", "message": "Debes iniciar sesion"}), 401
    if is_rate_limited("predicciones_save", user.get("id"), 5):
        return jsonify({"status": "error", "message": "Espera unos segundos antes de volver a guardar."}), 429

    data = request.get_json(silent=True) or {}
    uid = data.get('user_id')
    j = data.get('jornada')
    signos = data.get('signos')

    if not uid or not j or not signos:
        return jsonify({"status": "error", "message": "Datos incompletos"}), 400
    if str(uid) != str(user['id']):
        return jsonify({"status": "error", "message": "No autorizado"}), 403
    if not isinstance(signos, list) or len(signos) != Q15_EXPECTED_MATCHES:
        return jsonify({"status": "error", "message": "La quiniela debe tener 15 signos."}), 400

    normalized_signs = []
    for i, signo in enumerate(signos, 1):
        normalized = normalize_prediction_sign(i, signo)
        if not normalized:
            return jsonify({"status": "error", "message": f"Signo invalido en el partido {i}."}), 400
        normalized_signs.append(normalized)
    if any(sign == "-" for sign in normalized_signs):
        return jsonify({"status": "error", "message": "Completa los 15 partidos antes de guardar."}), 400
    doubles = sum(1 for sign in normalized_signs[:14] if len(sign) == 2)
    triples = sum(1 for sign in normalized_signs[:14] if len(sign) == 3)
    if doubles > MAX_DOBLES_PER_TICKET or triples > MAX_TRIPLES_PER_TICKET:
        return jsonify({"status": "error", "message": "La quiniela supera el limite de dobles/triples permitido."}), 400
    try:
        target_jornada = int(j)
    except Exception:
        return jsonify({"status": "error", "message": "Jornada invalida."}), 400

    conn = get_db()
    transaction_started = False
    try:
        max_jornada = conn.execute("SELECT MAX(jornada) FROM resultados").fetchone()[0]
        if max_jornada is None or int(max_jornada) != target_jornada:
            return jsonify({"status": "error", "message": "Solo se puede guardar la jornada activa."}), 403
        rows = conn.execute("SELECT partido_id, fecha, hora, status FROM resultados WHERE jornada = ? ORDER BY partido_id", (target_jornada,)).fetchall()
        ids = {int(row["partido_id"]) for row in rows}
        if len(rows) != Q15_EXPECTED_MATCHES or ids != set(range(1, Q15_EXPECTED_MATCHES + 1)):
            return jsonify({"status": "error", "message": "La jornada no tiene 15 partidos validos."}), 400
        close_info = compute_ticket_close_info(rows, source=f"save_predictions_j{target_jornada}")
        first_kickoff = close_info["first_kickoff"]
        close_at = close_info["close_at"]
        already_closed = bool(close_at and madrid_now() >= close_at)
        already_closed = already_closed or any(is_scored_status(row["status"]) or is_live_scored_status(row["status"]) for row in rows)
        if already_closed:
            if close_at:
                close_label = close_at.strftime("%d/%m %H:%M")
                message = f"La quiniela ya esta cerrada: el cierre era el {close_label}."
            else:
                message = "La quiniela ya esta cerrada: empezo el primer partido."
            return jsonify({"status": "error", "message": message}), 403

        conn.execute("BEGIN IMMEDIATE")
        transaction_started = True
        conn.execute("DELETE FROM predicciones WHERE user_id = ? AND jornada = ?", (uid, target_jornada))
        for i, signo in enumerate(normalized_signs, 1):
            if signo != "-":
                conn.execute("INSERT OR REPLACE INTO predicciones (user_id, jornada, partido_id, signo) VALUES (?, ?, ?, ?)", (uid, target_jornada, i, signo))
        saved_rows = conn.execute("SELECT partido_id, signo FROM predicciones WHERE user_id = ? AND jornada = ? ORDER BY partido_id", (uid, target_jornada)).fetchall()
        saved_signs = ["-"] * Q15_EXPECTED_MATCHES
        for row in saved_rows:
            idx = int(row["partido_id"]) - 1
            if 0 <= idx < Q15_EXPECTED_MATCHES:
                saved_signs[idx] = row["signo"]
        if saved_signs != normalized_signs:
            conn.rollback()
            return jsonify({"status": "error", "message": "No se pudo verificar el guardado completo de la quiniela."}), 500
        conn.commit()
        return jsonify({"status": "ok", "message": "Quiniela guardada correctamente", "jornada": target_jornada, "saved_count": len([sign for sign in saved_signs if sign != "-"]), "signos": saved_signs})
    except Exception as exc:
        if transaction_started:
            conn.rollback()
        return jsonify({"status": "error", "message": "Error guardando la quiniela. Intentalo de nuevo."}), 500
    finally:
        conn.close()
