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
        corrections = json.load(fh).get("fixtures") or []

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
    conn.commit()
    return changed
