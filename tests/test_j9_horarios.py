"""Jornada 9 fixtures must reach both the cover and ticket payload on time."""

import sqlite3

from liga_maestros.db.migrations import ensure_core_tables, ensure_jornada_9
from liga_maestros.services.payloads.matches import build_jornada_matches

EXPECTED = [
    (1, "2026-09-26", "14:00"),
    (2, "2026-09-26", "16:15"),
    (3, "2026-09-26", "18:30"),
    (4, "2026-09-26", "18:30"),
    (5, "2026-09-27", "14:00"),
    (6, "2026-09-27", "16:15"),
    (7, "2026-09-27", "18:30"),
    (8, "2026-09-27", "18:30"),
    (9, "2026-09-27", "21:00"),
    (10, "2026-09-28", "20:30"),
    (11, "2026-09-27", "12:00"),
    (12, "2026-09-27", "12:00"),
    (13, "2026-09-27", "16:00"),
    (14, "2026-09-27", "18:00"),
    (15, "2026-09-26", "20:45"),
]


def test_j9_schedule_is_persisted_and_served_to_the_cover_and_ticket():
    with sqlite3.connect(":memory:") as conn:
        conn.row_factory = sqlite3.Row
        ensure_core_tables(conn)
        ensure_jornada_9(conn)

        payload = build_jornada_matches(conn, 9, {})

    assert len(payload) == 15
    assert [(match["id"], match["fecha_raw"], match["hora"]) for match in payload] == EXPECTED
