"""Regression tests: a partial jornada must self-heal to 15 matches.

Bug: ensure_jornada_75() skipped all work when ANY row of the jornada already
existed in `resultados`, so a partially imported jornada stayed incomplete
forever and the "Quiniela" tab rendered '-'/'Pendiente' placeholders.
"""

import sqlite3

from liga_maestros.db import migrations
from liga_maestros.services.payloads import matches as matches_payload


def _fresh_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    migrations.ensure_core_tables(conn)
    return conn


def _insert_match(conn, partido_id, local="-", visitante="-", fecha="", hora="", status="NS"):
    conn.execute(
        """
        INSERT INTO resultados (jornada, partido_id, local, visitante, status, fecha, hora)
        VALUES (75, ?, ?, ?, ?, ?, ?)
        """,
        (partido_id, local, visitante, status, fecha, hora),
    )
    conn.commit()


def _j75_rows(conn):
    return conn.execute("SELECT * FROM resultados WHERE jornada = 75 ORDER BY partido_id").fetchall()


def test_empty_db_imports_full_j75():
    conn = _fresh_conn()
    migrations.ensure_jornada_75(conn)
    rows = _j75_rows(conn)
    assert len(rows) == 15
    assert rows[0]["local"] == "VPS Vaasa"
    assert rows[0]["visitante"] == "Inter Turku"
    assert rows[0]["fecha"] == "2026-08-02"
    assert rows[14]["local"] == "AIK"


def test_partial_jornada_is_completed():
    conn = _fresh_conn()
    for pid in range(1, 6):
        _insert_match(conn, pid, local="VPS Vaasa" if pid == 1 else f"Equipo {pid}", visitante="Rival")

    changed = migrations.ensure_jornada_completa(conn, 75, fallback_matches=migrations.J75_FALLBACK_MATCHES)
    rows = _j75_rows(conn)

    assert changed >= 10
    assert len(rows) == 15
    assert {int(r["partido_id"]) for r in rows} == set(range(1, 16))
    assert rows[9]["local"] == "Aalesunds FK"
    assert rows[14]["visitante"] == "Orgryte IS"


def test_empty_placeholder_rows_are_backfilled():
    conn = _fresh_conn()
    for pid in range(1, 16):
        _insert_match(conn, pid)

    migrations.ensure_jornada_completa(conn, 75, fallback_matches=migrations.J75_FALLBACK_MATCHES)
    rows = _j75_rows(conn)

    assert len(rows) == 15
    assert all(r["local"] and r["local"] != "-" for r in rows)
    assert all(r["fecha"] for r in rows)


def test_results_backfill_covers_uncovered_finished_matches():
    """Production case: VPS/TPS rows stuck NS after the jornada ended."""
    conn = _fresh_conn()
    for pid in range(1, 16):
        _insert_match(conn, pid, local=f"Local {pid}", visitante=f"Visita {pid}", fecha="2026-08-01", hora="14:00")
    for pid in range(3, 16):  # el directo cubrio 3-15
        conn.execute(
            "UPDATE resultados SET goles_local = 1, goles_visitante = 0, status = 'FT' WHERE jornada = 75 AND partido_id = ?",
            (pid,),
        )
    conn.commit()

    migrations.ensure_jornada_75(conn)
    uncovered = conn.execute(
        "SELECT goles_local, goles_visitante, status, signo_actual FROM resultados WHERE jornada = 75 AND partido_id IN (1, 2)"
    ).fetchall()

    assert tuple(uncovered[0]) == (0, 1, "FT", "2")
    assert tuple(uncovered[1]) == (3, 0, "FT", "1")
    # los que ya estaban cubiertos NO se tocan
    row3 = conn.execute(
        "SELECT goles_local, goles_visitante FROM resultados WHERE jornada = 75 AND partido_id = 3"
    ).fetchone()
    assert tuple(row3) == (1, 0)


def test_duplicate_rows_are_deduplicated_keeping_results():
    conn = _fresh_conn()
    # Duplicado: fila vacia + fila con resultado real
    _insert_match(conn, 5)
    conn.execute(
        """
        INSERT INTO resultados (jornada, partido_id, local, visitante, status, fecha, hora, goles_local, goles_visitante)
        VALUES (75, 5, 'IF Gnistan', 'KuPS Kuopio', 'FT', '2026-08-01', '18:00', 1, 2)
        """
    )
    conn.commit()

    migrations.ensure_jornada_completa(conn, 75, fallback_matches=migrations.J75_FALLBACK_MATCHES)
    rows = conn.execute("SELECT * FROM resultados WHERE jornada = 75 AND partido_id = 5").fetchall()

    assert len(rows) == 1
    assert rows[0]["local"] == "IF Gnistan"
    assert rows[0]["goles_local"] == 1
    assert rows[0]["status"] == "FT"
    assert len(_j75_rows(conn)) == 15


def test_finished_matches_are_never_touched():
    conn = _fresh_conn()
    for pid in range(1, 16):
        _insert_match(conn, pid, local=f"Local {pid}", visitante=f"Visita {pid}", fecha="2026-08-01", hora="14:00")
    conn.execute(
        "UPDATE resultados SET goles_local = 2, goles_visitante = 1, status = 'FT' WHERE jornada = 75 AND partido_id = 3"
    )
    conn.commit()

    migrations.ensure_jornada_completa(conn, 75, fallback_matches=migrations.J75_FALLBACK_MATCHES)
    row = conn.execute("SELECT * FROM resultados WHERE jornada = 75 AND partido_id = 3").fetchone()

    assert row["local"] == "Local 3"
    assert row["visitante"] == "Visita 3"
    assert row["goles_local"] == 2
    assert row["status"] == "FT"


def test_ticket_payload_backfills_missing_matches_from_scrape():
    conn = _fresh_conn()
    for pid in range(1, 6):
        conn.execute(
            """
            INSERT INTO resultados (jornada, partido_id, local, visitante, status, fecha, hora)
            VALUES (75, ?, ?, ?, 'NS', ?, ?)
            """,
            (pid, f"Local {pid}", f"Visita {pid}", "2026-08-01", "14:00"),
        )
    conn.commit()

    partidos = matches_payload.build_jornada_matches(conn, 75, {})

    assert len(partidos) == 15
    assert partidos[9]["local"] == "Aalesunds FK"
    assert partidos[14]["local"] == "AIK"
    assert all(p["local"] != "-" for p in partidos)


def test_ticket_payload_without_scrape_keeps_placeholders(monkeypatch):
    conn = _fresh_conn()
    conn.execute(
        "INSERT INTO resultados (jornada, partido_id, local, visitante, status) VALUES (99, 1, 'A', 'B', 'NS')"
    )
    conn.commit()

    partidos = matches_payload.build_jornada_matches(conn, 99, {})

    assert len(partidos) == 15
    assert partidos[0]["local"] == "A"
    assert partidos[1]["local"] == "-"
    assert partidos[1]["marcador"] == "Pendiente"
