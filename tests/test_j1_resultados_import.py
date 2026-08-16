"""J1 resultados se aplican por partido_id aunque la fila tuviera placeholder de nombre."""

import json
import sqlite3

from liga_maestros.db.migrations import _import_j1_resultados, ensure_core_tables


def test_import_j1_resultados_fills_empty_scores_by_id(tmp_path, monkeypatch):
    results = {
        "jornada": 1,
        "resultados": [
            {"id": 1, "goles_local": 3, "goles_visitante": 0, "signo": "1", "status": "FT"},
            {"id": 8, "goles_local": 0, "goles_visitante": 0, "signo": "X", "status": "FT"},
        ],
    }
    results_path = tmp_path / "quiniela15_J1_resultados.json"
    results_path.write_text(json.dumps(results), encoding="utf-8")

    import liga_maestros.db.migrations as migrations

    monkeypatch.setattr(migrations.config, "SEED_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(migrations.config, "DATA_DIR", str(tmp_path / "missing"))

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_core_tables(conn)
    conn.execute(
        "INSERT INTO resultados (jornada, partido_id, local, visitante, status, goles_local, goles_visitante, signo_actual)"
        " VALUES (1, 1, 'Local', 'Visitante', 'NS', NULL, NULL, '-')"
    )
    conn.execute(
        "INSERT INTO resultados (jornada, partido_id, local, visitante, status, goles_local, goles_visitante, signo_actual)"
        " VALUES (1, 8, 'Real Oviedo', 'Granada', 'NS', NULL, NULL, '-')"
    )
    conn.commit()

    _import_j1_resultados(conn)

    row1 = conn.execute(
        "SELECT goles_local, goles_visitante, status, signo_actual FROM resultados WHERE partido_id=1"
    ).fetchone()
    row8 = conn.execute(
        "SELECT goles_local, goles_visitante, status, signo_actual FROM resultados WHERE partido_id=8"
    ).fetchone()
    assert tuple(row1) == (3, 0, "FT", "1")
    assert tuple(row8) == (0, 0, "FT", "X")

    conn.execute("UPDATE resultados SET goles_local=9, goles_visitante=9 WHERE partido_id=1")
    conn.commit()
    _import_j1_resultados(conn)
    row1b = conn.execute("SELECT goles_local, goles_visitante FROM resultados WHERE partido_id=1").fetchone()
    assert tuple(row1b) == (9, 9)
