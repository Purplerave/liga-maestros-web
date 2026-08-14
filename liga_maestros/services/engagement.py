"""Engagement helpers: rachas de quiniela, resumen post-jornada y tarjeta compartible.

P0 de la auditoría de enganche (2026-08-14).
"""

from __future__ import annotations

from ..scoring import score_prediction
from .jornada import current_season_sql
from .teams import (
    build_participant_contract,
    canonical_contest_id,
    contest_aliases_for_uid,
    is_scored_status,
    public_contest_name,
)

# Maestros IA principales para el veredicto post-jornada
CORE_AI_IDS = ("chatgpt", "claude", "gemini", "grok")


def compute_quiniela_streak(conn, user_id: str) -> dict:
    """Racha de participación/aciertos en la quiniela principal.

    - racha_actual: jornadas consecutivas (hacia atrás desde la última jugada) con ≥1 predicción puntuada.
    - racha_max: mejor racha histórica de participación.
    - ultima_jornada: última jornada en la que participó.
    """
    aliases = contest_aliases_for_uid(user_id)
    if not aliases:
        return {"racha_actual": 0, "racha_max": 0, "ultima_jornada": None, "jornadas_jugadas": 0}

    placeholders = ",".join("?" for _ in aliases)
    # Las rachas se miden sobre la temporada publicada; el periodo de
    # pruebas (jornadas 51-76) queda fuera.
    rows = conn.execute(
        f"""
        SELECT DISTINCT p.jornada
        FROM predicciones p
        WHERE p.user_id IN ({placeholders}) AND {current_season_sql("p.jornada")}
        ORDER BY p.jornada ASC
        """,
        aliases,
    ).fetchall()
    jornadas = [int(r["jornada"]) for r in rows]
    if not jornadas:
        return {"racha_actual": 0, "racha_max": 0, "ultima_jornada": None, "jornadas_jugadas": 0}

    scored = []
    for j in jornadas:
        has_scored = conn.execute(
            """
            SELECT 1 FROM resultados
            WHERE jornada = ? AND signo_actual IS NOT NULL AND signo_actual != '-'
            LIMIT 1
            """,
            (j,),
        ).fetchone()
        if has_scored:
            scored.append(j)

    if not scored:
        return {
            "racha_actual": 0,
            "racha_max": 0,
            "ultima_jornada": jornadas[-1],
            "jornadas_jugadas": len(jornadas),
        }

    racha_max = 1
    current = 1
    for i in range(1, len(scored)):
        if scored[i] == scored[i - 1] + 1:
            current += 1
            racha_max = max(racha_max, current)
        else:
            current = 1

    racha_actual = 1
    for i in range(len(scored) - 1, 0, -1):
        if scored[i] == scored[i - 1] + 1:
            racha_actual += 1
        else:
            break

    return {
        "racha_actual": racha_actual,
        "racha_max": max(racha_max, racha_actual),
        "ultima_jornada": scored[-1],
        "jornadas_jugadas": len(jornadas),
    }


def _hits_for_user(conn, user_id: str, jornada: int) -> int:
    aliases = contest_aliases_for_uid(user_id)
    if not aliases:
        return 0
    placeholders = ",".join("?" for _ in aliases)
    rows = conn.execute(
        f"""
        SELECT p.partido_id, p.signo, r.signo_actual, r.goles_local, r.goles_visitante, r.status
        FROM predicciones p
        JOIN resultados r ON p.jornada = r.jornada AND p.partido_id = r.partido_id
        WHERE p.user_id IN ({placeholders}) AND p.jornada = ?
        """,
        (*aliases, jornada),
    ).fetchall()
    hits = 0
    for row in rows:
        if not is_scored_status(row["status"]):
            continue
        real = row["signo_actual"]
        if int(row["partido_id"] or 0) == 15 and row["goles_local"] is not None and row["goles_visitante"] is not None:
            real = f"{int(row['goles_local'])}-{int(row['goles_visitante'])}"
        hits += score_prediction(row["partido_id"], row["signo"], real)
    return hits


def build_post_jornada_summary(conn, user_id: str, jornada: int | None = None) -> dict | None:
    """Resumen emocional post-jornada: tú vs maestros IA + racha."""
    aliases = contest_aliases_for_uid(user_id)
    if not aliases:
        return None

    if jornada is None:
        placeholders = ",".join("?" for _ in aliases)
        row = conn.execute(
            f"""
            SELECT MAX(p.jornada) AS j
            FROM predicciones p
            JOIN resultados r ON p.jornada = r.jornada AND p.partido_id = r.partido_id
            WHERE p.user_id IN ({placeholders})
              AND {current_season_sql("p.jornada")}
              AND r.signo_actual IS NOT NULL AND r.signo_actual != '-'
            """,
            aliases,
        ).fetchone()
        if not row or row["j"] is None:
            return None
        jornada = int(row["j"])

    human_hits = _hits_for_user(conn, user_id, jornada)
    ai_scores = {}
    for ai_id in CORE_AI_IDS:
        ai_scores[ai_id] = _hits_for_user(conn, ai_id, jornada)

    verdicts = []
    beaten = 0
    for ai_id, ai_hits in ai_scores.items():
        label = public_contest_name(ai_id, {})
        diff = human_hits - ai_hits
        if diff >= 2:
            verdicts.append(f"🔥 Has destrozado a {label}")
            beaten += 1
        elif diff > 0:
            verdicts.append(f"✅ Le has ganado a {label}")
            beaten += 1
        elif diff == 0:
            verdicts.append(f"🤝 Empate técnico con {label}")
        elif diff <= -2:
            verdicts.append(f"😤 {label} te ha pasado por encima")
        else:
            verdicts.append(f"🤖 {label} te ha ganado esta vez")

    streak = compute_quiniela_streak(conn, user_id)
    headline = (
        f"Le ganaste a {beaten} de {len(CORE_AI_IDS)} maestros IA"
        if beaten
        else "Esta jornada los maestros IA te han ganado el duelo"
    )
    if beaten == len(CORE_AI_IDS):
        headline = "🧠 Cerebro de silicio: les has ganado a todos"

    return {
        "jornada": jornada,
        "human_hits": human_hits,
        "ai_scores": ai_scores,
        "verdicts": verdicts,
        "headline": headline,
        "beaten_ais": beaten,
        "racha": streak,
        "share_text": (
            f"Jornada {jornada}: {human_hits} aciertos. "
            f"{headline}. Racha: {streak.get('racha_actual', 0)}. #LigaDeMaestros"
        ),
    }


def build_share_card_payload(conn, user_id: str, jornada: int | None = None) -> dict | None:
    """Datos listos para renderizar una tarjeta compartible (cliente o servidor)."""
    summary = build_post_jornada_summary(conn, user_id, jornada)
    if not summary:
        return None

    contract = build_participant_contract()
    display_name = None
    try:
        row = conn.execute("SELECT nombre FROM usuarios WHERE id = ?", (user_id,)).fetchone()
        if row:
            display_name = (row["nombre"] or "").split()[0][:16]
    except Exception:
        pass
    if not display_name:
        display_name = public_contest_name(canonical_contest_id(user_id), {})

    return {
        "user": {"id": public_contest_name(canonical_contest_id(user_id), {}), "name": display_name},
        "jornada": summary["jornada"],
        "scores": {
            "human": summary["human_hits"],
            **summary["ai_scores"],
        },
        "verdict": summary["headline"],
        "verdicts": summary["verdicts"],
        "racha": summary["racha"],
        "share_text": summary["share_text"],
        "format_hints": {
            "stories": {"w": 1080, "h": 1920},
            "og": {"w": 1200, "h": 630},
        },
        "participant_contract": {
            "ai_ids": list(CORE_AI_IDS),
            "labels": {aid: public_contest_name(aid, {}) for aid in CORE_AI_IDS},
        },
    }
