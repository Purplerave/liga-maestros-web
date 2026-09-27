"""Predictions route: save user predictions."""

import logging

from flask import Blueprint, jsonify, request, session

import config

from ..db.connection import begin_immediate_with_retry, get_db, is_transient_lock_error
from ..middleware.rate_limit import is_rate_limited
from ..scoring import normalize_prediction_sign
from ..services.highlightly import Q15_EXPECTED_MATCHES
from ..services.jornada import resolve_active_jornada
from ..services.teams import is_live_scored_status, is_scored_status
from ..services.ticket import compute_ticket_close_info, madrid_now

bp = Blueprint("predictions", __name__)


class GuardadoIncompletoError(Exception):
    """La fila releida no coincide con lo enviado.

    Se distingue del error generico porque significa que la escritura se guardo a
    medias, no que la transaccion fallo: conviene registrarla aparte.
    """


class QuinielaCerradaError(Exception):
    """La jornada se cerro entre la comprobacion y la escritura.

    Se lanza DENTRO de la transaccion, con los estados releidos bajo el lock de
    escritura. Comprobarlo antes dejaba la ventana de la carrera: dos guardados
    concurrentes pasaban los dos el control y el segundo, que tomaba el lock
    despues, borraba los signos del primero.
    """

    def __init__(self, message):
        super().__init__(message)
        self.message = message


def _motivo_de_cierre(rows, close_at):
    """Mensaje de cierre si la jornada ya no admite cambios, o None si sigue abierta."""
    if close_at and madrid_now() >= close_at:
        return f"La quiniela ya esta cerrada: el cierre era el {close_at.strftime('%d/%m %H:%M')}."
    if any(is_scored_status(row["status"]) or is_live_scored_status(row["status"]) for row in rows):
        return "La quiniela ya esta cerrada: empezo el primer partido."
    return None


logger = logging.getLogger(__name__)


@bp.route("/api/predicciones/save", methods=["POST"])
def save_predictions():
    user = session.get("user")
    if not user:
        return jsonify({"status": "error", "message": "Debes iniciar sesion"}), 401
    if is_rate_limited("predicciones_save", user.get("id"), 5):
        return jsonify({"status": "error", "message": "Espera unos segundos antes de volver a guardar."}), 429

    data = request.get_json(silent=True) or {}
    uid = data.get("user_id")
    j = data.get("jornada")
    signos = data.get("signos")

    if not uid or not j or not signos:
        return jsonify({"status": "error", "message": "Datos incompletos"}), 400
    if str(uid) != str(user["id"]):
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
    if doubles > config.MAX_DOBLES_PER_TICKET or triples > config.MAX_TRIPLES_PER_TICKET:
        return jsonify({"status": "error", "message": "La quiniela supera el limite de dobles/triples permitido."}), 400
    try:
        target_jornada = int(j)
    except Exception:
        return jsonify({"status": "error", "message": "Jornada invalida."}), 400

    conn = get_db()
    try:
        active_jornada = resolve_active_jornada(conn)
        if active_jornada is None or int(active_jornada) != target_jornada:
            return jsonify({"status": "error", "message": "Solo se puede guardar la jornada activa."}), 403
        rows = conn.execute(
            "SELECT partido_id, fecha, hora, status FROM resultados WHERE jornada = ? ORDER BY partido_id",
            (target_jornada,),
        ).fetchall()
        ids = {int(row["partido_id"]) for row in rows}
        if len(rows) != Q15_EXPECTED_MATCHES or ids != set(range(1, Q15_EXPECTED_MATCHES + 1)):
            return jsonify({"status": "error", "message": "La jornada no tiene 15 partidos validos."}), 400
        close_info = compute_ticket_close_info(rows, source=f"save_predictions_j{target_jornada}")
        close_at = close_info["close_at"]
        # Comprobacion rapida antes de tomar el lock de escritura. NO es la que
        # protege: entre aqui y el BEGIN otro guardado (o el collector) puede
        # cerrar la jornada, asi que se repite dentro de la transaccion.
        motivo_cierre = _motivo_de_cierre(rows, close_at)
        if motivo_cierre:
            return jsonify({"status": "error", "message": motivo_cierre}), 403

        def escribir_y_verificar():
            """Transaccion de escritura completa: borra, inserta y relee.

            Se reintenta entera si SQLite esta bloqueado en el momento. El boleto
            va con los 15 signos en un solo POST, asi que perderlo por un lock de
            milisegundos del collector era un fallo evitible.
            """
            begin_immediate_with_retry(conn)
            # El cierre se vuelve a comprobar aqui, releendo los estados bajo el
            # lock de escritura. Es el unico sitio donde el control y la escritura
            # son atomicos: comprobarlo antes dejaba que dos guardados concurrentes
            # pasaron ambos el filtro y el ultimo machacase al primero.
            filas = conn.execute(
                "SELECT status FROM resultados WHERE jornada = ? ORDER BY partido_id",
                (target_jornada,),
            ).fetchall()
            motivo = _motivo_de_cierre(filas, close_at)
            if motivo:
                raise QuinielaCerradaError(motivo)
            conn.execute("DELETE FROM predicciones WHERE user_id = ? AND jornada = ?", (uid, target_jornada))
            insert_tuples = [
                (uid, target_jornada, i, signo) for i, signo in enumerate(normalized_signs, 1) if signo != "-"
            ]
            if insert_tuples:
                conn.executemany(
                    "INSERT INTO predicciones (user_id, jornada, partido_id, signo) VALUES (?, ?, ?, ?)",
                    insert_tuples,
                )
            saved_rows = conn.execute(
                "SELECT partido_id, signo FROM predicciones WHERE user_id = ? AND jornada = ? ORDER BY partido_id",
                (uid, target_jornada),
            ).fetchall()
            leidos = ["-"] * Q15_EXPECTED_MATCHES
            for row in saved_rows:
                idx = int(row["partido_id"]) - 1
                if 0 <= idx < Q15_EXPECTED_MATCHES:
                    leidos[idx] = row["signo"]
            if leidos != normalized_signs:
                raise GuardadoIncompletoError()
            conn.commit()
            return leidos

        intentos = 3
        for intento in range(intentos):
            try:
                saved_signs = escribir_y_verificar()
                break
            except GuardadoIncompletoError:
                conn.rollback()
                logger.error(
                    "El guardado de la quiniela de la jornada %s quedo incompleto para el usuario %s",
                    target_jornada,
                    uid,
                )
                return jsonify(
                    {"status": "error", "message": "No se pudo verificar el guardado completo de la quiniela."}
                ), 500
            except QuinielaCerradaError as cierre:
                # No se reintenta: la jornada esta cerrada, un intento mas solo
                # gastaria el lock de escritura para acabar con el mismo 403.
                conn.rollback()
                return jsonify({"status": "error", "message": cierre.message}), 403
            except Exception as exc:  # noqa: BLE001
                # `rollback()` sin transaccion abierta es un no-op, asi que se puede
                # llamar siempre: cubre tanto el lock de BEGIN como un fallo a mitad.
                conn.rollback()
                if not is_transient_lock_error(exc):
                    raise
                logger.warning(
                    "SQLite bloqueado al guardar la quiniela (intento %s/%s): %s", intento + 1, intentos, exc
                )
        else:
            return jsonify(
                {"status": "error", "message": "El sistema esta ocupado. Intentalo de nuevo en unos segundos."}
            ), 503

        return jsonify(
            {
                "status": "ok",
                "message": "Quiniela guardada correctamente",
                "jornada": target_jornada,
                "saved_count": len([sign for sign in saved_signs if sign != "-"]),
                "signos": saved_signs,
            }
        )
    except Exception:
        conn.rollback()
        logger.exception("No se pudo guardar la quiniela de la jornada %s", target_jornada)
        return jsonify({"status": "error", "message": "Error guardando la quiniela. Intentalo de nuevo."}), 500
