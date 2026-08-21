"""La jornada activa no puede quedarse anclada en un NS caducado.

Un partido en NS con fecha ya pasada (aplazado sin nueva fecha o resultado
que el scraper no ha recogido) no debe mantener "abierta" una jornada cuya
quiniela ya está cerrada: la web debe promocionar a la siguiente jornada.
"""

import sqlite3
from datetime import timedelta
from zoneinfo import ZoneInfo

from liga_maestros.services.jornada import resolve_active_jornada
from liga_maestros.services.ticket import madrid_now


def _conn_with_jornada(jornada, *matches):
    """Crea una BD en memoria con una jornada de partidos (status, fecha)."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """CREATE TABLE resultados (
            jornada INTEGER, partido_id INTEGER, local TEXT, visitante TEXT,
            status TEXT, fecha DATE, hora TEXT, goles_local INTEGER,
            goles_visitante INTEGER, minuto TEXT, signo_actual TEXT
        )"""
    )
    for pid, (status, fecha) in enumerate(matches, start=1):
        conn.execute(
            "INSERT INTO resultados (jornada, partido_id, local, visitante, status, fecha, hora) "
            "VALUES (?, ?, 'Local', 'Visitante', ?, ?, '20:00')",
            (jornada, pid, status, fecha),
        )
    conn.commit()
    return conn


def _days(delta):
    return (madrid_now() + timedelta(days=delta)).strftime("%Y-%m-%d")


def test_ns_pasado_no_mantiene_la_jornada_abierta():
    conn = _conn_with_jornada(1, *([("NS", _days(-5))] * 15))
    assert resolve_active_jornada(conn) == 1  # única jornada: es el máximo


def test_promociona_a_la_siguiente_jornada_si_solo_quedan_ns_caducados():
    conn = _conn_with_jornada(1, *([("NS", _days(-5))] * 15))
    conn.execute(
        "INSERT INTO resultados (jornada, partido_id, local, visitante, status, fecha, hora) "
        "VALUES (2, 1, 'Athletic', 'Sevilla', 'NS', ?, '17:00')",
        (_days(1),),
    )
    conn.commit()
    assert resolve_active_jornada(conn) == 2


def test_ns_futuro_o_sin_fecha_mantiene_la_jornada_abierta():
    conn = _conn_with_jornada(1, *([("NS", _days(-5))] * 14), ("NS", _days(2)))
    assert resolve_active_jornada(conn) == 1

    conn2 = _conn_with_jornada(1, *([("NS", _days(-5))] * 14), ("NS", ""))
    assert resolve_active_jornada(conn2) == 1


def test_todas_cerradas_devuelve_la_ultima_jornada():
    conn = _conn_with_jornada(1, *([("FT", _days(-5))] * 15))
    conn.execute(
        "INSERT INTO resultados (jornada, partido_id, local, visitante, status, fecha, hora) "
        "VALUES (2, 1, 'Athletic', 'Sevilla', 'FT', ?, '17:00')",
        (_days(-1),),
    )
    conn.commit()
    assert resolve_active_jornada(conn) == 2


def test_zona_horaria_madrid():
    assert str(ZoneInfo("Europe/Madrid"))
