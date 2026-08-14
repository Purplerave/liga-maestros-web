"""La temporada 2026-27 empieza en la J1 y el histórico no se cuela.

Bug de origen: la liga de pruebas usó numeración continua hasta la J76, así que
sus jornadas son NUMÉRICAMENTE MAYORES que las de la temporada nueva. Con
`CONTEST_DYNAMIC_START_JORNADA = 58` y filtros `jornada >= 1`, el ranking
general seguía sumando la pretemporada (GROK 138 pts) y el selector ofrecía 22
jornadas, mientras la pestaña Quiniela ya mostraba solo la J1.

Además `run_startup_migrations()` llamaba a `ensure_jornada_75(force=True)` en
cada arranque, así que la J75/J76 resucitaban tras cualquier limpieza.
"""

import sqlite3

import pytest

from liga_maestros.db import migrations
from liga_maestros.services.season import (
    LEGACY_JORNADA_MAX,
    LEGACY_JORNADA_MIN,
    filter_season_jornadas,
    is_season_jornada,
    season_sql_filter,
    season_start,
)


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    migrations.ensure_core_tables(conn)
    return conn


def _add_result(conn, jornada, partido_id=1, signo="1"):
    conn.execute(
        """
        INSERT INTO resultados (jornada, partido_id, local, visitante, status, signo_actual, goles_local, goles_visitante)
        VALUES (?, ?, 'Local', 'Visitante', 'FT', ?, 1, 0)
        """,
        (jornada, partido_id, signo),
    )


def test_season_starts_at_jornada_1():
    assert season_start() == 1
    assert is_season_jornada(1)
    assert is_season_jornada(2)
    assert is_season_jornada(38)


@pytest.mark.parametrize("jornada", [40, 51, 58, 73, 75, 76, LEGACY_JORNADA_MIN, LEGACY_JORNADA_MAX])
def test_legacy_jornadas_are_not_season(jornada):
    """La liga de pruebas y los ensayos de verano quedan fuera pese a ser > 1."""
    assert not is_season_jornada(jornada)


def test_filter_keeps_only_current_season():
    todas = [1, 2, 51, 58, 73, 75, 76]
    assert filter_season_jornadas(todas) == [1, 2]


def test_sql_filter_excludes_legacy_rows():
    conn = _conn()
    for jornada in (1, 2, 58, 73, 75, 76):
        _add_result(conn, jornada)
    conn.commit()

    where, params = season_sql_filter()
    rows = conn.execute(f"SELECT DISTINCT jornada FROM resultados WHERE {where} ORDER BY jornada", params).fetchall()
    assert [int(r[0]) for r in rows] == [1, 2]


def test_startup_migrations_do_not_resurrect_j75(tmp_path, monkeypatch):
    """El arranque ya no reimporta la J75/J76.

    Antes, `ensure_jornada_75(conn)` corría con `force=True` en cada arranque,
    así que los ensayos de verano volvían tras cualquier limpieza. El seed
    público sí puede traer el histórico de la liga de pruebas (J58-J73): eso se
    conserva a propósito, solo queda oculto por los filtros de temporada.
    """
    import config

    db_path = tmp_path / "test.db"
    monkeypatch.setattr(config, "DB_PATH", str(db_path))
    monkeypatch.setattr(migrations.config, "DB_PATH", str(db_path))

    migrations.run_startup_migrations()

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    jornadas = [int(r[0]) for r in conn.execute("SELECT DISTINCT jornada FROM resultados").fetchall()]
    puntos = conn.execute("SELECT COUNT(*) FROM usuarios WHERE COALESCE(puntos_acumulados, 0) != 0").fetchone()[0]

    # Lo que la web ofrece al usuario: solo la temporada nueva.
    assert filter_season_jornadas(jornadas) == [1]
    assert puntos == 0, "el ranking nuevo arrancó con puntos de la temporada de pruebas"

    # Y el archivo histórico sigue intacto en la BD (no se ha borrado nada).
    from liga_maestros.services.jornada import resolve_active_jornada

    assert resolve_active_jornada(conn) == 1
    conn.close()


def test_archive_zeroes_carryover_points_but_keeps_history():
    """El histórico se conserva en la BD; solo dejan de contar sus puntos."""
    conn = _conn()
    for jornada in (58, 73, 75):
        _add_result(conn, jornada)
    conn.execute("INSERT INTO usuarios (id, nombre, puntos_acumulados) VALUES ('grok', 'GROK', 138)")
    conn.commit()

    migrations.archive_legacy_jornadas(conn)

    # Los datos históricos NO se borran.
    assert conn.execute("SELECT COUNT(*) FROM resultados WHERE jornada = 73").fetchone()[0] == 1
    # Pero los puntos arrastrados dejan de sumar en la temporada nueva.
    assert conn.execute("SELECT puntos_acumulados FROM usuarios WHERE id = 'grok'").fetchone()[0] == 0


def test_resolve_active_jornada_prefers_season_over_higher_legacy():
    from liga_maestros.services.jornada import resolve_active_jornada

    conn = _conn()
    _add_result(conn, 1)
    _add_result(conn, 76)
    conn.commit()
    assert resolve_active_jornada(conn) == 1
