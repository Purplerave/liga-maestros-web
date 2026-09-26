"""The Jornada 9 Pavo ticket is loaded as a Peña entry with provenance."""

import json
import sqlite3
from pathlib import Path

from liga_maestros.db.migrations import ensure_core_tables, ensure_jornada_9
from liga_maestros.services.teams import build_participant_contract

EXPECTED_PAVO = ["X", "1", "X", "1", "1", "1", "1", "1", "X", "2", "1", "X", "X", "X", "0-1"]
SOURCE = "https://app.pavo-ai.work"


def test_j9_pavo_ticket_is_imported_and_registered_in_la_pena():
    payload = json.loads(Path("data/predicciones_J9.json").read_text(encoding="utf-8"))
    assert payload["pavo"]["fuente"] == SOURCE
    assert payload["pavo"]["signos"] == EXPECTED_PAVO

    contract = build_participant_contract()
    assert "pavo" in contract["pena_ids"]
    assert contract["names"]["pavo"] == "Pavo"

    with sqlite3.connect(":memory:") as conn:
        conn.row_factory = sqlite3.Row
        ensure_core_tables(conn)
        ensure_jornada_9(conn)
        rows = conn.execute(
            "SELECT signo FROM predicciones WHERE jornada = 9 AND user_id = 'pavo' ORDER BY partido_id"
        ).fetchall()

    assert [row["signo"] for row in rows] == EXPECTED_PAVO
