"""La jornada del directo debe ser la misma que la que ve el usuario.

Regresión: `resolve_jornada` hacía `SELECT MAX(jornada) FROM resultados`, así que
apuntaba al periodo de pruebas (J51-76) que sigue archivado en la BD. Resultado:
la web mostraba la J1, pero el directo, el collector, `/api/live/health` y
`/api/sync/status` perseguían la J76. Los marcadores nunca se movían y la cuota
de Highlightly se gastaba refrescando fechas de una jornada muerta.
"""

import sqlite3

from liga_maestros.db.migrations import ensure_core_tables
from liga_maestros.services.highlightly import refresh_dates_for_jornada, resolve_jornada
from liga_maestros.services.jornada import resolve_active_jornada


def _conn_with(rows):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_core_tables(conn)
    conn.executemany(
        "INSERT INTO resultados (jornada, partido_id, local, visitante, status, fecha, hora) VALUES (?,?,?,?,?,?,?)",
        rows,
    )
    return conn


def _jornada(jornada, fecha, status="NS"):
    return [(jornada, pid, f"Local{pid}", f"Visitante{pid}", status, fecha, "19:30") for pid in range(1, 16)]


def test_directo_y_ui_resuelven_la_misma_jornada_con_pruebas_archivadas():
    """Con J1 real y J75/J76 de pruebas en la BD, ambas rutas deben decir J1."""
    conn = _conn_with(_jornada(1, "2026-08-15") + _jornada(75, "2026-08-01", "FT") + _jornada(76, "2026-08-08", "FT"))

    assert resolve_active_jornada(conn) == 1
    assert resolve_jornada(conn, None) == 1
    assert resolve_jornada(conn, None) == resolve_active_jornada(conn)


def test_collector_no_refresca_fechas_de_la_temporada_de_pruebas():
    """Las fechas a refrescar salen de la jornada activa, no de la J76."""
    conn = _conn_with(_jornada(1, "2026-08-15") + _jornada(76, "2026-08-08", "FT"))

    dates = refresh_dates_for_jornada(conn, None)

    assert "2026-08-08" not in dates


def test_jornada_explicita_sigue_mandando():
    """Pedir ?j=75 explícitamente (archivo/admin) debe seguir funcionando."""
    conn = _conn_with(_jornada(1, "2026-08-15") + _jornada(75, "2026-08-01", "FT"))

    assert resolve_jornada(conn, "75") == 75
    assert resolve_jornada(conn, 75) == 75


def test_base_de_datos_vacia_no_revienta():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_core_tables(conn)

    assert resolve_jornada(conn, None) == 1
