"""Export public competition history without accounts or private activity."""
from datetime import datetime, timezone
import argparse
import json
import os
import sqlite3

import config

TABLES = (
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


def public_participant_ids():
    path = os.path.join(config.SEED_DATA_DIR, "PARTICIPANTES_MAESTROS.json")
    with open(path, "r", encoding="utf-8") as fh:
        participants = json.load(fh)
    ids = {str(item["id"]) for item in participants if item.get("id")}
    ids.update({"v260_omnisciente", "consenso"})
    return ids


def export_seed(source, output):
    conn = sqlite3.connect(source)
    conn.row_factory = sqlite3.Row
    allowed_ids = public_participant_ids()
    payload = {
        "version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "privacy": "No contiene usuarios, correos, comentarios ni actividad privada.",
        "tables": {},
    }
    try:
        for table in TABLES:
            columns = [row[1] for row in conn.execute(f'PRAGMA table_info("{table}")')]
            if not columns:
                continue
            if table == "predicciones":
                placeholders = ",".join("?" for _ in allowed_ids)
                rows = conn.execute(
                    f"SELECT * FROM predicciones WHERE user_id IN ({placeholders}) ORDER BY jornada, partido_id, user_id",
                    sorted(allowed_ids),
                ).fetchall()
            else:
                rows = conn.execute(f'SELECT * FROM "{table}"').fetchall()
            payload["tables"][table] = {
                "columns": columns,
                "rows": [[row[column] for column in columns] for row in rows],
            }
    finally:
        conn.close()

    os.makedirs(os.path.dirname(output), exist_ok=True)
    with open(output, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Genera la semilla publica de produccion.")
    parser.add_argument("--source", default=config.BOOTSTRAP_DB_PATH)
    parser.add_argument("--output", default=config.PRODUCTION_SEED_PATH)
    args = parser.parse_args()
    print(export_seed(args.source, args.output))
