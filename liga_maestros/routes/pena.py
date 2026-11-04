"""La Peña voting routes."""

import logging
from datetime import UTC, datetime

from flask import Blueprint, jsonify, request, session

from ..db.connection import get_db
from ..middleware.rate_limit import is_rate_limited
from ..scoring import normalize_prediction_sign
from ..services.payloads.predictions import _official_prediction_ids
from ..services.teams import build_participant_contract, canonical_contest_id, is_live_scored_status, is_scored_status
from ..services.ticket import compute_ticket_close_info, madrid_now

bp = Blueprint("pena", __name__)
logger = logging.getLogger(__name__)

# Ventana anti-flood entre votos de la misma cuenta. Hay que poder corregir el
# boleto varias veces seguidas (se guarda partido a partido desde el movil),
# pero no aceptar un POST por clic.
VOTO_COOLDOWN_SECONDS = 2


def _jornada_solicitada():
    """Jornada pedida en el cuerpo o en la query, o ``None`` si no es un entero."""
    raw = request.args.get("j") or request.args.get("jornada")
    if raw is None:
        data = request.get_json(silent=True) or {}
        raw = data.get("jornada")
    if raw is None or isinstance(raw, bool):
        return None
    try:
        return int(str(raw).strip())
    except (TypeError, ValueError):
        return None


def _jornada_abierta(conn, jornada):
    """Devuelve ``(rows, error)``: filas de la jornada o la respuesta de error."""
    rows = conn.execute(
        "SELECT partido_id, fecha, hora, status FROM resultados WHERE jornada = ? ORDER BY partido_id",
        (jornada,),
    ).fetchall()
    if not rows:
        return None, (jsonify({"status": "error", "message": "La jornada no existe."}), 404)
    ids = {int(row["partido_id"]) for row in rows}
    if len(rows) != 15 or ids != set(range(1, 16)):
        return None, (jsonify({"status": "error", "message": "La jornada no está lista."}), 400)
    close_info = compute_ticket_close_info(rows, source=f"pena_votar_j{jornada}")
    close_at = close_info["close_at"]
    if close_at and madrid_now() >= close_at:
        return None, (jsonify({"status": "error", "message": "El plazo para votar ha cerrado."}), 403)
    if any(is_scored_status(row["status"]) or is_live_scored_status(row["status"]) for row in rows):
        return None, (jsonify({"status": "error", "message": "El plazo para votar ha cerrado."}), 403)
    return rows, None


@bp.route("/api/pena/votar", methods=["POST"])
def votar():
    user = session.get("user")
    if not user:
        return jsonify({"status": "error", "message": "Entra con Google para votar."}), 401
    if is_rate_limited("pena_votar", user.get("id"), VOTO_COOLDOWN_SECONDS):
        return jsonify({"status": "error", "message": "Espera unos segundos."}), 429

    data = request.get_json(silent=True) or {}
    signos = data.get("signos") or data.get("boleto")
    target_jornada = _jornada_solicitada()
    if target_jornada is None:
        return jsonify({"status": "error", "message": "Jornada inválida."}), 400
    if not isinstance(signos, list) or len(signos) != 15:
        return jsonify({"status": "error", "message": "Datos incompletos"}), 400

    normalized_signs = []
    for i, signo in enumerate(signos, 1):
        normalized = normalize_prediction_sign(i, signo)
        if not normalized:
            return jsonify({"status": "error", "message": f"Signo inválido en el partido {i}."}), 400
        normalized_signs.append(normalized)
    if any(sign == "-" for sign in normalized_signs):
        return jsonify({"status": "error", "message": "Completa los 15 partidos antes de votar."}), 400

    user_id = str(user.get("id"))
    conn = get_db()
    try:
        _rows, error = _jornada_abierta(conn, target_jornada)
        if error:
            return error

        now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        for i, signo in enumerate(normalized_signs, 1):
            conn.execute(
                """INSERT INTO votos_pena (user_id, jornada, partido_id, signo, updated_at)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(user_id, jornada, partido_id)
                   DO UPDATE SET signo=excluded.signo, updated_at=excluded.updated_at""",
                (user_id, target_jornada, i, signo, now),
            )
        conn.commit()
        return jsonify({"status": "ok", "message": "Voto guardado correctamente"})
    except Exception:
        conn.rollback()
        logger.exception("Error guardando voto de La Peña")
        return jsonify({"status": "error", "message": "Error al guardar el voto."}), 500
    finally:
        conn.close()


@bp.route("/api/pena/mis-votos")
def mis_votos():
    user = session.get("user")
    if not user:
        return jsonify({"status": "ok", "votos": None})
    target_jornada = _jornada_solicitada()
    if target_jornada is None:
        return jsonify({"status": "ok", "votos": None})
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT partido_id, signo FROM votos_pena WHERE user_id = ? AND jornada = ? ORDER BY partido_id",
            (str(user.get("id")), target_jornada),
        ).fetchall()
        if not rows:
            return jsonify({"status": "ok", "votos": None})
        signos = ["-"] * 15
        for row in rows:
            idx = int(row["partido_id"]) - 1
            if 0 <= idx < 15:
                signos[idx] = row["signo"]
        return jsonify({"status": "ok", "votos": signos})
    finally:
        conn.close()


@bp.route("/api/pena/consenso")
def consenso_pena_publico():
    target_jornada = _jornada_solicitada()
    if target_jornada is None:
        return jsonify({"status": "error", "message": "Falta jornada"}), 400
    # Los maestros y las columnas ocultas nunca son La Peña, aunque su cuenta
    # vote: el consenso es de las personas.
    excluidos = _official_prediction_ids(build_participant_contract())
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT user_id, partido_id, signo FROM votos_pena WHERE jornada = ?",
            (target_jornada,),
        ).fetchall()
        counts = {pid: {"1": 0, "X": 0, "2": 0} for pid in range(1, 16)}
        voters = set()
        pleno_counts = {}
        for row in rows:
            uid = canonical_contest_id(row["user_id"])
            if str(uid).lower() in excluidos:
                continue
            voters.add(uid)
            pid = int(row["partido_id"])
            sign = str(row["signo"] or "").strip().upper()
            if 1 <= pid <= 14 and sign in ("1", "X", "2"):
                counts[pid][sign] += 1
            elif pid == 15 and sign:
                pleno_counts[sign] = pleno_counts.get(sign, 0) + 1
        total_voters = len(voters)
        result = []
        for pid in range(1, 15):
            c = counts[pid]
            # El total es el de ESE partido: con el numero de votantes globales,
            # un partido sin votos salia con porcentajes de otro.
            total = c["1"] + c["X"] + c["2"]
            if total == 0:
                result.append({"id": pid, "p1": 0, "px": 0, "p2": 0, "ganador": "-", "total": 0, "votes": c})
                continue
            p1 = round((c["1"] * 100) / total)
            px = round((c["X"] * 100) / total)
            p2 = max(0, 100 - p1 - px)
            max_v = max(c["1"], c["X"], c["2"])
            tied = [s for s in ("1", "X", "2") if c[s] == max_v]
            result.append(
                {
                    "id": pid,
                    "p1": p1,
                    "px": px,
                    "p2": p2,
                    "ganador": tied[0] if len(tied) == 1 else "-",
                    "total": total,
                    "votes": c,
                }
            )
        return jsonify(
            {
                "status": "ok",
                "consenso": result,
                "total_votantes": total_voters,
                "pleno": pleno_counts,
            }
        )
    finally:
        conn.close()
