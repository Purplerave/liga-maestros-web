"""Quiz service: Reto 10 LaLiga - scoring, ranking, validation."""
import json
from datetime import datetime

from ..db.connection import get_db


def ensure_quiz_tables(conn):
    from ..db.migrations import ensure_quiz_tables as _ensure
    _ensure(conn)


def get_quiz_preguntas(jornada):
    """Devuelve las 10 preguntas activas de una jornada."""
    conn = get_db()
    try:
        ensure_quiz_tables(conn)
        rows = conn.execute("""
            SELECT id, jornada, tipo, enunciado, opcion_a, opcion_b, opcion_c,
                   respuesta_correcta, explicacion, dificultad, tema
            FROM quiz_preguntas
            WHERE jornada = ? AND activa = 1
            ORDER BY id ASC
        """, (jornada,)).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def submit_quiz_respuestas(jornada, user_id, nombre, respuestas, tiempo_total_ms=0, expected_question_ids=None):
    """
    Guarda las respuestas del usuario y devuelve el resultado.
    
    respuestas: lista de dicts [{"pregunta_id": int, "respuesta": str}, ...]
    """
    conn = get_db()
    try:
        ensure_quiz_tables(conn)
        
        existing = conn.execute(
            "SELECT id FROM quiz_participaciones WHERE user_id = ? AND jornada = ?",
            (user_id, jornada)
        ).fetchone()
        if existing:
            return {"error": "Ya has participado en el Reto 10 de esta jornada."}
        
        preguntas = conn.execute(
            "SELECT id, respuesta_correcta, dificultad FROM quiz_preguntas WHERE jornada = ? AND activa = 1",
            (jornada,)
        ).fetchall()
        preguntas_map = {int(p["id"]): p for p in preguntas}
        expected_ids = [int(p["id"]) for p in preguntas]
        if expected_question_ids and [int(pid) for pid in expected_question_ids] != expected_ids:
            return {"error": "El intento del quiz no coincide con las preguntas actuales."}
        if len(respuestas) != len(expected_ids):
            return {"error": "Debes responder exactamente todas las preguntas del reto."}

        seen_ids = []
        normalized_answers = []
        for resp in respuestas:
            try:
                pid = int(resp.get("pregunta_id", 0))
            except (TypeError, ValueError):
                return {"error": "Respuesta invalida."}
            respuesta_user = str(resp.get("respuesta", "")).strip().upper()
            if respuesta_user not in ("A", "B", "C"):
                return {"error": "Respuesta invalida."}
            seen_ids.append(pid)
            normalized_answers.append({"pregunta_id": pid, "respuesta": respuesta_user})

        if len(set(seen_ids)) != len(seen_ids):
            return {"error": "No se admiten preguntas duplicadas."}
        if sorted(seen_ids) != sorted(expected_ids):
            return {"error": "Las respuestas no corresponden a este reto."}
        
        aciertos = 0
        puntos_total = 0
        racha = 0
        racha_max = 0
        detalle = []
        
        tiempo_total_ms = max(0, min(int(tiempo_total_ms or 0), 60 * 60 * 1000))

        for resp in normalized_answers:
            pid = resp["pregunta_id"]
            respuesta_user = resp["respuesta"]
            pregunta = preguntas_map.get(pid)
            
            if not pregunta:
                detalle.append({"pregunta_id": pid, "correcta": False, "puntos": 0})
                continue
            
            correcta = str(pregunta["respuesta_correcta"]).strip().upper()
            es_correcta = respuesta_user == correcta
            dificultad = int(pregunta["dificultad"] or 1)
            
            if es_correcta:
                aciertos += 1
                racha += 1
                puntos = 100 if dificultad <= 1 else 150
                if racha >= 5:
                    puntos += 50
                puntos_total += puntos
                racha_max = max(racha_max, racha)
            else:
                racha = 0
                puntos = 0
            
            detalle.append({
                "pregunta_id": pid,
                "respuesta": respuesta_user,
                "correcta": es_correcta,
                "puntos": puntos,
            })
        
        if aciertos == len(preguntas) and len(preguntas) > 0:
            puntos_total += 300
        
        bonus_rapidez = min(30, max(0, int((180000 - tiempo_total_ms) / 6000)))
        puntos_total += bonus_rapidez
        
        participation_bonus = 25
        puntos_total += participation_bonus
        
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute("""
            INSERT INTO quiz_participaciones
            (jornada, user_id, nombre, respuestas, aciertos, total_preguntas, puntos, tiempo_total_ms, racha_max, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            jornada, user_id, nombre,
            json.dumps(detalle, ensure_ascii=False),
            aciertos, len(preguntas), puntos_total, tiempo_total_ms, racha_max, now,
        ))
        conn.commit()
        
        ranking = get_quiz_ranking_jornada(jornada)
        position = None
        for idx, entry in enumerate(ranking, 1):
            if entry["user_id"] == user_id:
                position = idx
                break
        
        return {
            "aciertos": aciertos,
            "total": len(preguntas),
            "puntos": puntos_total,
            "bonus_rapidez": bonus_rapidez,
            "bonus_perfecto": 300 if aciertos == len(preguntas) and len(preguntas) > 0 else 0,
            "bonus_participacion": participation_bonus,
            "racha_max": racha_max,
            "posicion_jornada": position,
            "detalle": detalle,
        }
    finally:
        conn.close()


def get_quiz_ranking_jornada(jornada):
    conn = get_db()
    try:
        rows = conn.execute("""
            SELECT user_id, nombre, aciertos, total_preguntas, puntos, tiempo_total_ms, racha_max
            FROM quiz_participaciones
            WHERE jornada = ?
            ORDER BY puntos DESC, tiempo_total_ms ASC
        """, (jornada,)).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_quiz_ranking_temporada():
    conn = get_db()
    try:
        rows = conn.execute("""
            SELECT user_id, nombre,
                   SUM(puntos) AS puntos_totales,
                   COUNT(*) AS jornadas_participadas,
                   SUM(aciertos) AS aciertos_totales,
                   SUM(total_preguntas) AS total_preguntas,
                   MAX(racha_max) AS mejor_racha,
                   ROUND(AVG(puntos), 0) AS media_puntos
            FROM quiz_participaciones
            GROUP BY user_id
            ORDER BY puntos_totales DESC
        """).fetchall()
        result = []
        for idx, row in enumerate(rows, 1):
            entry = dict(row)
            entry["posicion"] = idx
            entry["hit_rate"] = round((entry["aciertos_totales"] / entry["total_preguntas"]) * 100, 1) if entry["total_preguntas"] else 0
            result.append(entry)
        return result
    finally:
        conn.close()


def get_quiz_ranking_mensual(anio_mes):
    conn = get_db()
    try:
        rows = conn.execute("""
            SELECT user_id, nombre,
                   SUM(puntos) AS puntos_totales,
                   COUNT(*) AS jornadas_participadas,
                   SUM(aciertos) AS aciertos_totales,
                   SUM(total_preguntas) AS total_preguntas
            FROM quiz_participaciones
            WHERE substr(created_at, 1, 7) = ?
            GROUP BY user_id
            ORDER BY puntos_totales DESC
        """, (anio_mes,)).fetchall()
        result = []
        for idx, row in enumerate(rows, 1):
            entry = dict(row)
            entry["posicion"] = idx
            entry["hit_rate"] = round((entry["aciertos_totales"] / entry["total_preguntas"]) * 100, 1) if entry["total_preguntas"] else 0
            result.append(entry)
        return result
    finally:
        conn.close()


def get_user_quiz_stats(user_id):
    conn = get_db()
    try:
        rows = conn.execute("""
            SELECT jornada, aciertos, total_preguntas, puntos, racha_max, created_at
            FROM quiz_participaciones
            WHERE user_id = ?
            ORDER BY jornada DESC
        """, (user_id,)).fetchall()
        
        if not rows:
            return {"participaciones": 0, "puntos_totales": 0, "mejor_jornada": None, "media_aciertos": 0}
        
        participaciones = len(rows)
        puntos_totales = sum(int(r["puntos"]) for r in rows)
        mejor = max(rows, key=lambda r: int(r["puntos"]))
        media_aciertos = round(sum(int(r["aciertos"]) for r in rows) / participaciones, 1)
        
        return {
            "participaciones": participaciones,
            "puntos_totales": puntos_totales,
            "mejor_jornada": {
                "jornada": mejor["jornada"],
                "aciertos": mejor["aciertos"],
                "puntos": mejor["puntos"],
            },
            "media_aciertos": media_aciertos,
            "historial": [dict(r) for r in rows[:12]],
        }
    finally:
        conn.close()
