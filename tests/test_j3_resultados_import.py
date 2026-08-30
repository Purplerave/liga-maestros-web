"""El importador generico de resultados aplica marcadores oficiales por
partido_id para cualquier jornada (no solo J1). Regresion del fix Liga F:
Eibar (F) 1-0 Espanyol (F) de la J3 no salia en la quiniela."""

import json

from liga_maestros.db.migrations import _import_jornada_resultados, ensure_core_tables


def _write_results(tmp_path, jornada, resultados):
    path = tmp_path / f"quiniela15_J{jornada}_resultados.json"
    path.write_text(
        json.dumps({"jornada": jornada, "resultados": resultados}), encoding="utf-8"
    )


def test_import_j3_resultados_fills_eibar_femenino(tmp_path, monkeypatch):
    import liga_maestros.db.migrations as migrations

    _write_results(
        tmp_path,
        3,
        [
            {
                "id": 12,
                "local": "Eibar (F)",
                "visitante": "Espanyol (F)",
                "goles_local": 1,
                "goles_visitante": 0,
                "signo": "1",
                "status": "FT",
            }
        ],
    )
    monkeypatch.setattr(migrations.config, "SEED_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(migrations.config, "DATA_DIR", str(tmp_path / "missing"))

    import sqlite3

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_core_tables(conn)
    conn.execute(
        "INSERT INTO resultados (jornada, partido_id, local, visitante, status, goles_local, goles_visitante, signo_actual)"
        " VALUES (3, 12, 'Eibar (F)', 'Espanyol (F)', 'NS', NULL, NULL, '-')"
    )
    conn.commit()

    applied = _import_jornada_resultados(conn, 3)
    assert applied == 1

    row = conn.execute(
        "SELECT goles_local, goles_visitante, status, signo_actual FROM resultados"
        " WHERE jornada=3 AND partido_id=12"
    ).fetchone()
    assert tuple(row) == (1, 0, "FT", "1")


def test_import_jornada_resultados_idempotent_and_never_overwrites_live(tmp_path, monkeypatch):
    import liga_maestros.db.migrations as migrations
    import sqlite3

    _write_results(
        tmp_path,
        3,
        [
            {"id": 12, "goles_local": 1, "goles_visitante": 0, "signo": "1", "status": "FT"},
        ],
    )
    monkeypatch.setattr(migrations.config, "SEED_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(migrations.config, "DATA_DIR", str(tmp_path / "missing"))

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_core_tables(conn)
    # El panel en vivo ya capturo el partido con un marcador: no se debe tocar.
    conn.execute(
        "INSERT INTO resultados (jornada, partido_id, local, visitante, status, goles_local, goles_visitante, signo_actual)"
        " VALUES (3, 12, 'Eibar (F)', 'Espanyol (F)', 'FT', 2, 1, '1')"
    )
    conn.commit()

    applied = _import_jornada_resultados(conn, 3)
    assert applied == 0
    row = conn.execute(
        "SELECT goles_local, goles_visitante FROM resultados WHERE jornada=3 AND partido_id=12"
    ).fetchone()
    assert tuple(row) == (2, 1)

    # Repetir la importacion no aplica cambios nuevos (idempotente).
    assert _import_jornada_resultados(conn, 3) == 0


def test_import_jornada_resultados_missing_file_is_noop(tmp_path, monkeypatch):
    import liga_maestros.db.migrations as migrations
    import sqlite3

    monkeypatch.setattr(migrations.config, "SEED_DATA_DIR", str(tmp_path / "vacio"))
    monkeypatch.setattr(migrations.config, "DATA_DIR", str(tmp_path / "missing"))

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_core_tables(conn)
    assert _import_jornada_resultados(conn, 99) == 0
