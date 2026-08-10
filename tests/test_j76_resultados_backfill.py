"""Regression tests: J76 results backfill + Nordic team-name normalization.

Bug: partido 5 (Lillestrom SK - Rosenborg, jugado el 09/08/2026) se quedo
sin resultado en la pestana Quiniela. El directo de Quiniela15 escribe
"Lillestrøm SK" (con ø, que NFD no descompone) y el saneo de nombres lo
convertia en "LILLESTR M SK", que no casaba con la BD ("LILLESTROM SK").
El control de coherencia de nombres descartaba el partido en las dos rutas
de resultados (directo Q15 y Highlightly), asi que el marcador nunca se
aplicaba.

Ademas, la migracion ensure_jornada_76() ahora respalda los resultados
verificados de data/quiniela15_J76_resultados.json (igual que la J75) para
los partidos que el directo no cubrio.
"""

import sqlite3

from liga_maestros.db import migrations

J76_FIXTURE = [
    (1, "Sandefjord", "KFUM Oslo", "2026-08-07", "19:00"),
    (2, "Valerenga", "Bodo-Glimt", "2026-08-08", "14:00"),
    (3, "Viking", "Sarpsborg", "2026-08-08", "16:00"),
    (4, "Start", "Fredrikstad", "2026-08-08", "18:00"),
    (5, "Lillestrom SK", "Rosenborg", "2026-08-09", "14:30"),
    (6, "Ham-Kam", "Aalesunds FK", "2026-08-09", "17:00"),
    (7, "Kristiansund", "Molde FK", "2026-08-09", "19:15"),
    (8, "Orgryte IS", "AIK", "2026-08-08", "15:00"),
    (9, "Mjallby", "Elfsborg", "2026-08-08", "17:30"),
    (10, "Hammarby", "Hacken", "2026-08-09", "14:00"),
    (11, "Malmoe", "Degerfors IF", "2026-08-09", "14:00"),
    (12, "Halmstad", "GAIS Goteborg", "2026-08-09", "16:30"),
    (13, "IFK Goteborg", "Kalmar FF", "2026-08-09", "16:30"),
    (14, "Sirius", "Brommapojkarna", "2026-08-10", "19:00"),
    (15, "Vasteras SK FK", "Djurgardens", "2026-08-10", "19:00"),
]


def _fresh_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    migrations.ensure_core_tables(conn)
    return conn


def _insert_full_j76(conn, result_ids=frozenset()):
    """Insert the J76 fixture; rows in result_ids get a fake FT result."""
    for partido_id, local, visitante, fecha, hora in J76_FIXTURE:
        if partido_id in result_ids:
            conn.execute(
                """
                INSERT INTO resultados (jornada, partido_id, local, visitante,
                    goles_local, goles_visitante, status, fecha, hora, minuto, signo_actual)
                VALUES (76, ?, ?, ?, 9, 9, 'FT', ?, ?, 'Finalizado', 'X')
                """,
                (partido_id, local, visitante, fecha, hora),
            )
        else:
            conn.execute(
                """
                INSERT INTO resultados (jornada, partido_id, local, visitante,
                    goles_local, goles_visitante, status, fecha, hora, minuto, signo_actual)
                VALUES (76, ?, ?, ?, NULL, NULL, 'NS', ?, ?, '', '-')
                """,
                (partido_id, local, visitante, fecha, hora),
            )
    conn.commit()


def _row(conn, partido_id):
    return conn.execute(
        "SELECT * FROM resultados WHERE jornada = 76 AND partido_id = ?", (partido_id,)
    ).fetchone()


def test_backfill_fills_stuck_match_without_touching_existing_results():
    """Production scenario: match 5 is stuck at NS while 1-4 and 6-13 are FT."""
    conn = _fresh_conn()
    already_ft = {1, 2, 3, 4, 6, 7, 8, 9, 10, 11, 12, 13}
    _insert_full_j76(conn, result_ids=already_ft)

    migrations.ensure_jornada_76(conn)

    row5 = _row(conn, 5)
    assert row5["goles_local"] == 0
    assert row5["goles_visitante"] == 2
    assert row5["status"] == "FT"
    assert row5["signo_actual"] == "2"

    # Los resultados ya presentes NO se sobrescriben (9-9 fake se mantiene).
    row1 = _row(conn, 1)
    assert row1["goles_local"] == 9
    assert row1["status"] == "FT"

    # Los partidos pendientes (14 y 15) siguen NS.
    for pid in (14, 15):
        assert _row(conn, pid)["status"] == "NS"
    conn.close()


def test_backfill_keeps_matches_without_result_file_entry_untouched():
    conn = _fresh_conn()
    _insert_full_j76(conn, result_ids=frozenset())
    migrations.ensure_jornada_76(conn)

    row5 = _row(conn, 5)
    assert row5["goles_local"] == 0
    assert row5["goles_visitante"] == 2
    assert row5["status"] == "FT"
    for pid in (14, 15):
        assert _row(conn, pid)["status"] == "NS"
    conn.close()


def test_backfill_is_idempotent():
    conn = _fresh_conn()
    _insert_full_j76(conn, result_ids=frozenset())
    migrations.ensure_jornada_76(conn)
    migrations.ensure_jornada_76(conn)

    row5 = _row(conn, 5)
    assert (row5["goles_local"], row5["goles_visitante"]) == (0, 2)
    assert row5["status"] == "FT"
    conn.close()
