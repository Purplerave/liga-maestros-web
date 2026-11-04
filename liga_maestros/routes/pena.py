"""La Peña voting routes."""

import logging
from datetime import datetime

from flask import Blueprint, jsonify, request, session

from ..db.connection import get_db
from ..middleware.rate_limit import is_rate_limited
from ..scoring import normalize_prediction_sign
from ..services.teams import is_live_scored_status, is_scored_status
from ..services.ticket import compute_ticket_close_info, madrid_now

bp = Blueprint("pena", __name__)
logger = logging.getLogger(__name__)


@bp.route("/api/pena/votar", methods=["POST"])
def votar():
    user = session.get("user")
    if not user:
        return jsonify({"status": "error", "message": "Entra con Google para votar."}), 401
    if is_rate_limited("pena_votar", user.get("id"), 10):
        return jsonify({"status": "error", "message": "Espera unos segundos."}), 429

    data = request.get_json(silent=True) or {}
    j = data.get("jornada")
    signos = data.get("signos") or data.get("boleto")

    if not j or not signos or not isinstance(signos, list) or len(signos) != 15:
        return jsonify({"status": "error", "message": "Datos incompletos"}), 400

    normalized_signs = []
    for i, signo in enumerate(signos, 1):
        normalized = normalize_prediction_sign(i, signo)
        if not normalized:
            return jsonify({"status": "error", "message": f"Signo inválido en el partido {i}."}), 400
        normalized_signs.append(normalized)
    if any(sign == "-" for sign in normalized_signs):
        return jsonify({"status": "error", "message": "Completa los 15 partidos antes de votar."}), 400

    try:
        target_jornada = int(j)
    except Exception:
        return jsonify({"status": "error", "message": "Jornada inválida."}), 400

    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT partido_id, fecha, hora, status FROM resultados WHERE jornada = ? ORDER BY partido_id",
            (target_jornada,),
        ).fetchall()
        ids = {int(row["partido_id"]) for row in rows}
        if len(rows) != 15 or ids != set(range(1, 16)):
            return jsonify({"status": "error", "message": "La jornada no está lista."}), 400
        close_info = compute_ticket_close_info(rows, source=f"pena_votar_j{target_jornada}")
        close_at = close_info["close_at"]
        if close_at and madrid_now() >= close_at:
            return jsonify({"status": "error", "message": "El plazo para votar ha cerrado."}), 403
        if any(is_scored_status(row["status"]) or is_live_scored_status(row["status"]) for row in rows):
            return jsonify({"status": "error", "message": "El plazo para votar ha cerrado."}), 403

        user_id = str(user.get("id"))
        now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
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
    j = request.args.get("j") or request.args.get("jornada")
    if not j:
        return jsonify({"status": "ok", "votos": None})
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT partido_id, signo FROM votos_pena WHERE user_id = ? AND jornada = ? ORDER BY partido_id",
            (str(user.get("id")), int(j)),
        ).fetchall()
        if not rows:
            return jsonify({"status": "ok", "votos": None})
        signos = ["-"] * 15
        for r in rows:
            idx = int(r["partido_id"]) - 1
            if 0 <= idx < 15:
                signos[idx] = r["signo"]
        return jsonify({"status": "ok", "votos": signos})
    finally:
        conn.close()


@bp.route("/api/pena/consenso")
def consenso_pena_publico():
    j = request.args.get("j") or request.args.get("jornada")
    if not j:
        return jsonify({"status": "error", "message": "Falta jornada"}), 400
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT partido_id, signo FROM votos_pena WHERE jornada = ?",
            (int(j),),
        ).fetchall()
        counts = {pid: {"1": 0, "X": 0, "2": 0} for pid in range(1, 16)}
        voters = set()
        for r in rows:
            voters.add(r["user_id"])
            pid = int(r["partido_id"])
            sign = str(r["signo"] or "").strip().upper()
            if pid >= 1 and pid <= 15 and sign in ("1", "X", "2"):
                counts[pid][sign] += 1
        total_voters = len(voters)
        result = []
        for pid in range(1, 15):
            c = counts[pid]
            total = c["1"] + c["X"] + c["2"]
            if total == 0:
                result.append({"id": pid, "p1": 0, "px": 0, "p2": 0, "ganador": "-", "total": 0})
                continue
            p1 = round((c["1"] * 100) / total)
            px = round((c["X"] * 100) / total)
            p2 = max(0, 100 - p1 - px)
            max_v = max(c["1"], c["X"], c["2"])
            tied = [s for s in ("1", "X", "2") if c[s] == max_v]
            ganador = tied[0] if len(tied) == 1 else "-"
            result.append({"id": pid, "p1": p1, "px": px, "p2": p2, "ganador": ganador, "total": total_voters, "votes": c})
        pleno_counts = {}
        for r in rows:
            if int(r["partido_id"]) == 15:
                s = str(r["signo"] or "").strip().upper()
                pleno_counts[s] = pleno_counts.get(s, 0) + 1
        return jsonify({"status": "ok", "consenso": result, "total_votantes": total_voters, "pleno": pleno_counts})
    finally:
        conn.close()
