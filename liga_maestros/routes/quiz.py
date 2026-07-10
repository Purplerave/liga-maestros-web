"""Quiz routes: Reto 10 LaLiga."""
from datetime import datetime

from flask import Blueprint, request, jsonify, session

from ..services.quiz import (
    get_quiz_preguntas, submit_quiz_respuestas,
    get_quiz_ranking_jornada, get_quiz_ranking_temporada,
    get_quiz_ranking_mensual, get_user_quiz_stats,
)

bp = Blueprint("quiz", __name__)


def _quiz_session_key(jornada):
    return f"quiz_attempt_{int(jornada)}"


@bp.route('/api/quiz/preguntas')
def quiz_preguntas():
    jornada = request.args.get("j", "").strip()
    if not jornada.isdigit():
        return jsonify({"status": "error", "message": "Jornada invalida"}), 400
    preguntas = get_quiz_preguntas(int(jornada))
    if not preguntas:
        return jsonify({"status": "ok", "disponible": False, "message": "Sin preguntas para esta jornada"})
    
    user = session.get("user") or {}
    session[_quiz_session_key(int(jornada))] = {
        "started_at": datetime.utcnow().isoformat(timespec="milliseconds"),
        "question_ids": [int(p["id"]) for p in preguntas],
    }
    return jsonify({
        "status": "ok",
        "disponible": True,
        "jornada": int(jornada),
        "total": len(preguntas),
        "preguntas": [{
            "id": p["id"],
            "tipo": p["tipo"],
            "enunciado": p["enunciado"],
            "opcion_a": p["opcion_a"],
            "opcion_b": p["opcion_b"],
            "opcion_c": p["opcion_c"],
            "tema": p["tema"],
            "dificultad": p["dificultad"],
        } for p in preguntas],
        "auth": bool(user.get("id")),
    })


@bp.route('/api/quiz/submit', methods=['POST'])
def quiz_submit():
    user = session.get("user")
    if not user:
        return jsonify({"status": "error", "message": "Entra con Google para participar."}), 401
    
    data = request.get_json(silent=True) or {}
    jornada = data.get("jornada")
    respuestas = data.get("respuestas")
    try:
        jornada = int(jornada)
        client_tiempo_ms = int(data.get("tiempo_total_ms", 0))
    except (TypeError, ValueError):
        return jsonify({"status": "error", "message": "Datos incompletos."}), 400
    
    if not jornada or not isinstance(respuestas, list):
        return jsonify({"status": "error", "message": "Datos incompletos."}), 400
    
    attempt = session.get(_quiz_session_key(jornada)) or {}
    try:
        started_at = datetime.fromisoformat(str(attempt.get("started_at")))
        tiempo_ms = max(0, int((datetime.utcnow() - started_at).total_seconds() * 1000))
    except (TypeError, ValueError):
        tiempo_ms = max(client_tiempo_ms, 180000)

    result = submit_quiz_respuestas(
        jornada=jornada,
        user_id=user["id"],
        nombre=(user.get("name") or "Maestro").split(" ")[0],
        respuestas=respuestas,
        tiempo_total_ms=tiempo_ms,
        expected_question_ids=attempt.get("question_ids"),
    )
    
    if "error" in result:
        return jsonify({"status": "error", "message": result["error"]}), 400
    
    return jsonify({"status": "ok", **result})


@bp.route('/api/quiz/ranking')
def quiz_ranking():
    tipo = request.args.get("tipo", "jornada")
    
    if tipo == "jornada":
        jornada = request.args.get("j", "").strip()
        if not jornada.isdigit():
            return jsonify({"status": "error", "message": "Jornada invalida"}), 400
        ranking = get_quiz_ranking_jornada(int(jornada))
        return jsonify({"status": "ok", "tipo": "jornada", "jornada": int(jornada), "ranking": ranking})
    
    elif tipo == "temporada":
        ranking = get_quiz_ranking_temporada()
        return jsonify({"status": "ok", "tipo": "temporada", "ranking": ranking})
    
    elif tipo == "mensual":
        mes = request.args.get("mes", "").strip()
        if not mes:
            from datetime import datetime
            mes = datetime.now().strftime("%Y-%m")
        ranking = get_quiz_ranking_mensual(mes)
        return jsonify({"status": "ok", "tipo": "mensual", "mes": mes, "ranking": ranking})
    
    return jsonify({"status": "error", "message": "Tipo de ranking invalido"}), 400


@bp.route('/api/quiz/mi-historial')
def quiz_mi_historial():
    user = session.get("user")
    if not user:
        return jsonify({"status": "error", "message": "No hay sesion."}), 401
    stats = get_user_quiz_stats(user["id"])
    return jsonify({"status": "ok", **stats})
