"""Public, repeatable seed import for empty production databases."""
import json
import os

import config


PUBLIC_SEED_TABLES = (
    "equipos",
    "equipo_aliases",
    "equipos_aliases",
    "clasificacion",
    "resultados",
    "consenso",
    "historico",
    "predicciones",
    "quiz_preguntas",
)


def _table_columns(conn, table):
    return {row[1] for row in conn.execute(f'PRAGMA table_info("{table}")')}


def import_public_seed_if_empty(conn, seed_path=None):
    """Import public competition data once; never imports accounts or comments."""
    seed_path = seed_path or config.PRODUCTION_SEED_PATH
    count = conn.execute("SELECT COUNT(*) FROM resultados").fetchone()[0]
    if count or not seed_path or not os.path.exists(seed_path):
        return False

    with open(seed_path, "r", encoding="utf-8") as fh:
        payload = json.load(fh)

    tables = payload.get("tables") or {}
    conn.execute("BEGIN IMMEDIATE")
    try:
        for table in PUBLIC_SEED_TABLES:
            block = tables.get(table) or {}
            columns = block.get("columns") or []
            rows = block.get("rows") or []
            if not columns or not rows:
                continue
            available = _table_columns(conn, table)
            if not set(columns).issubset(available):
                missing = sorted(set(columns) - available)
                raise RuntimeError(f"Semilla incompatible en {table}: {missing}")
            quoted = ", ".join(f'"{column}"' for column in columns)
            placeholders = ", ".join("?" for _ in columns)
            conn.executemany(
                f'INSERT INTO "{table}" ({quoted}) VALUES ({placeholders})',
                rows,
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return True


def apply_fixture_corrections(conn, corrections_path=None):
    """Apply verified late fixture names to existing persistent databases."""
    corrections_path = corrections_path or config.FIXTURE_CORRECTIONS_PATH
    if not corrections_path or not os.path.exists(corrections_path):
        return 0

    with open(corrections_path, "r", encoding="utf-8") as fh:
        payload = json.load(fh)
    corrections = payload.get("fixtures") or []

    changed = 0
    for item in corrections:
        jornada = int(item["jornada"])
        partido_id = int(item["partido_id"])
        old_local = str(item.get("old_local") or "")
        old_visitante = str(item.get("old_visitante") or "")
        local = str(item["local"])
        visitante = str(item["visitante"])
        cursor = conn.execute(
            """
            UPDATE resultados
               SET local = ?, visitante = ?
             WHERE jornada = ? AND partido_id = ?
               AND local = ? AND visitante = ?
            """,
            (local, visitante, jornada, partido_id, old_local, old_visitante),
        )
        changed += cursor.rowcount

    prediction_corrections = payload.get("predictions") or []
    for item in prediction_corrections:
        jornada = int(item["jornada"])
        user_id = str(item["user_id"]).strip().lower()
        jornada_exists = conn.execute(
            "SELECT 1 FROM resultados WHERE jornada = ? LIMIT 1",
            (jornada,),
        ).fetchone()
        if not jornada_exists:
            continue
        signs = list(item.get("signos") or [])[:15]
        for partido_id, raw_sign in enumerate(signs, start=1):
            sign = str(raw_sign or "-").strip().upper()
            current = conn.execute(
                "SELECT signo FROM predicciones WHERE user_id = ? AND jornada = ? AND partido_id = ?",
                (user_id, jornada, partido_id),
            ).fetchone()
            current_sign = current[0] if current else None
            if current_sign == sign:
                continue
            conn.execute(
                "INSERT OR REPLACE INTO predicciones (user_id, jornada, partido_id, signo) VALUES (?, ?, ?, ?)",
                (user_id, jornada, partido_id, sign),
            )
            changed += 1
    conn.commit()
    return changed
