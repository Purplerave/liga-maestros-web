import sqlite3

from tools.ops import LIVE_COLLECTOR as collector


def test_stuck_match_is_persistently_closed_with_final_sign(monkeypatch):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE resultados (
            jornada INTEGER, partido_id INTEGER, goles_local INTEGER,
            goles_visitante INTEGER, status TEXT, minuto TEXT, signo_actual TEXT
        )
        """
    )
    conn.execute(
        "INSERT INTO resultados VALUES (1, 4, 2, 1, 'IN PLAY', '90', 'X')"
    )
    conn.commit()
    stuck = [{"id": 4, "local": "A", "visitante": "B", "status": "IN PLAY", "minuto": "90"}]
    monkeypatch.setattr(collector, "detect_stuck_live_matches", lambda jornada, grace_minutes=180: stuck)
    monkeypatch.setattr(collector, "get_db", lambda: conn)
    monkeypatch.setattr(collector, "log_line", lambda message: None)

    closed = collector.close_stuck_live_matches(1)
    row = conn.execute(
        "SELECT status, minuto, signo_actual FROM resultados WHERE jornada = 1 AND partido_id = 4"
    ).fetchone()

    assert closed == stuck
    assert dict(row) == {"status": "FT", "minuto": "Finalizado", "signo_actual": "1"}
