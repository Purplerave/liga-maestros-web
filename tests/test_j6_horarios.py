"""Horarios de J6 proporcionados para el 11-14 de septiembre de 2026."""

import sqlite3

from liga_maestros.db.migrations import ensure_core_tables, ensure_jornada_completa, load_scrape_matches
from liga_maestros.services import ticket

EXPECTED = [
    (1, "2026-09-12", "18:30"),
    (2, "2026-09-13", "16:15"),
    (3, "2026-09-12", "16:15"),
    (4, "2026-09-12", "14:00"),
    (5, "2026-09-12", "21:00"),
    (6, "2026-09-11", "21:00"),
    (7, "2026-09-14", "21:00"),
    (8, "2026-09-12", "16:15"),
    (9, "2026-09-13", "21:00"),
    (10, "2026-09-13", "16:15"),
    (11, "2026-09-13", "12:00"),
    (12, "2026-09-13", "17:00"),
    (13, "2026-09-13", "19:30"),
    (14, "2026-09-12", "16:30"),
    (15, "2026-09-13", "21:00"),
]


def test_j6_published_schedule():
    assert [(m[0], m[3], m[4]) for m in load_scrape_matches(6)] == EXPECTED


def test_j6_updates_existing_schedule_and_is_idempotent():
    with sqlite3.connect(":memory:") as conn:
        ensure_core_tables(conn)
        assert ensure_jornada_completa(conn, 6) == 15
        conn.execute("UPDATE resultados SET fecha = '2026-09-12', hora = '10:00' WHERE jornada = 6")
        assert ensure_jornada_completa(conn, 6) == 15
        rows = conn.execute(
            "SELECT partido_id, fecha, hora FROM resultados WHERE jornada = 6 ORDER BY partido_id"
        ).fetchall()
        assert rows == EXPECTED
        assert ensure_jornada_completa(conn, 6) == 0


def test_j6_ticket_closes_before_friday_match(monkeypatch):
    monkeypatch.setattr(ticket, "PREDICTION_CLOSE_MINUTES_BEFORE_KICKOFF", 15)
    rows = [{"fecha": fecha, "hora": hora} for _, fecha, hora in EXPECTED]
    info = ticket.compute_ticket_close_info(rows)
    assert info["first_kickoff"].isoformat() == "2026-09-11T21:00:00+02:00"
    assert info["close_at"].isoformat() == "2026-09-11T20:45:00+02:00"
    assert info["exact_count"] == 15
