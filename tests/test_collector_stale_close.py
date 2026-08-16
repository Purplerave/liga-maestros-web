import sqlite3
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from tools.ops import LIVE_COLLECTOR as collector

MADRID = ZoneInfo("Europe/Madrid")
NOW = datetime(2026, 8, 16, 15, 30, tzinfo=MADRID)


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE resultados (
            jornada INTEGER, partido_id INTEGER, local TEXT, visitante TEXT,
            goles_local INTEGER, goles_visitante INTEGER, status TEXT,
            fecha TEXT, hora TEXT, minuto TEXT, signo_actual TEXT, updated_at TEXT
        )
        """
    )
    return conn


@pytest.fixture
def collector_db(monkeypatch):
    conn = _conn()
    monkeypatch.setattr(collector, "get_db", lambda: conn)
    monkeypatch.setattr(collector, "log_line", lambda message: None)
    monkeypatch.setattr(collector, "madrid_now", lambda: NOW)
    return conn


def _insert(conn, **over):
    row = {
        "jornada": 1,
        "partido_id": 6,
        "local": "Andorra",
        "visitante": "Ceuta",
        "goles_local": None,
        "goles_visitante": None,
        "status": "LIVE",
        "fecha": "2026-08-16",
        "hora": "17:00",
        "minuto": "90",
        "signo_actual": "-",
        "updated_at": None,
    }
    row.update(over)
    conn.execute(
        "INSERT INTO resultados VALUES (:jornada, :partido_id, :local, :visitante, :goles_local,"
        " :goles_visitante, :status, :fecha, :hora, :minuto, :signo_actual, :updated_at)",
        row,
    )
    conn.commit()


def _read(conn, partido_id=6):
    return dict(
        conn.execute(
            "SELECT status, minuto, signo_actual, goles_local FROM resultados WHERE partido_id = ?",
            (partido_id,),
        ).fetchone()
    )


def test_live_match_before_its_kickoff_is_reset_not_finalised(collector_db):
    """Andorra-Ceuta: LIVE minuto 90 con inicio futuro a las 17:00."""
    _insert(collector_db, goles_local=1, goles_visitante=0)

    closed = collector.close_stuck_live_matches(1)

    assert [item["reason"] for item in closed] == ["live_antes_del_inicio"]
    assert _read(collector_db) == {
        "status": "NS",
        "minuto": "",
        "signo_actual": "-",
        "goles_local": None,
    }


def test_second_stuck_match_is_also_closed(collector_db):
    """Cadiz-Celta Fortuna: LIVE minuto 45 con inicio futuro a las 19:00."""
    _insert(collector_db, partido_id=7, local="Cádiz", visitante="Celta Fortuna", hora="19:00", minuto="45")

    collector.close_stuck_live_matches(1)

    assert _read(collector_db, 7)["status"] == "NS"


def test_match_without_updates_for_thirty_minutes_is_closed_as_stale(collector_db):
    _insert(
        collector_db,
        hora="14:30",
        minuto="45",
        goles_local=1,
        goles_visitante=1,
        updated_at=(NOW - timedelta(minutes=31)).isoformat(timespec="seconds"),
    )

    closed = collector.close_stuck_live_matches(1)

    assert [item["reason"] for item in closed] == ["sin_actualizacion_30min"]
    # Score preserved, no official sign invented.
    assert _read(collector_db) == {
        "status": "STALE",
        "minuto": "Sin datos",
        "signo_actual": "-",
        "goles_local": 1,
    }


def test_stuck_match_past_the_full_window_is_finalised_with_final_sign(collector_db):
    _insert(
        collector_db,
        hora="13:00",
        minuto="90",
        goles_local=2,
        goles_visitante=1,
        status="IN PLAY",
        updated_at=(NOW - timedelta(minutes=5)).isoformat(timespec="seconds"),
    )

    closed = collector.close_stuck_live_matches(1)

    assert len(closed) == 1
    assert _read(collector_db) == {
        "status": "FT",
        "minuto": "Finalizado",
        "signo_actual": "1",
        "goles_local": 2,
    }


def test_recently_updated_live_match_is_left_running(collector_db):
    _insert(
        collector_db,
        hora="14:45",
        minuto="40",
        goles_local=0,
        goles_visitante=0,
        updated_at=(NOW - timedelta(minutes=2)).isoformat(timespec="seconds"),
    )

    assert collector.close_stuck_live_matches(1) == []
    assert _read(collector_db)["status"] == "LIVE"


def test_finished_and_scheduled_rows_are_never_rewritten(collector_db):
    _insert(collector_db, partido_id=1, status="FT", minuto="Finalizado", goles_local=1, goles_visitante=0)
    _insert(collector_db, partido_id=2, status="NS", minuto="", hora="21:30")

    assert collector.close_stuck_live_matches(1) == []
    assert _read(collector_db, 1)["status"] == "FT"
    assert _read(collector_db, 2)["status"] == "NS"


def test_legacy_rows_without_updated_at_column_are_still_closed(monkeypatch):
    """Databases predating the freshness column must not crash the collector."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE resultados (
            jornada INTEGER, partido_id INTEGER, local TEXT, visitante TEXT,
            goles_local INTEGER, goles_visitante INTEGER, status TEXT,
            fecha TEXT, hora TEXT, minuto TEXT, signo_actual TEXT
        )
        """
    )
    conn.execute(
        "INSERT INTO resultados VALUES (1, 6, 'Andorra', 'Ceuta', 1, 0, 'LIVE', '2026-08-16', '17:00', '90', '1')"
    )
    conn.commit()
    monkeypatch.setattr(collector, "get_db", lambda: conn)
    monkeypatch.setattr(collector, "log_line", lambda message: None)
    monkeypatch.setattr(collector, "madrid_now", lambda: NOW)

    collector.close_stuck_live_matches(1)

    assert conn.execute("SELECT status FROM resultados").fetchone()["status"] == "NS"


def test_provider_snapshot_cannot_reopen_an_impossible_live_state(collector_db):
    """A Q15 pass reporting LIVE 90' before kickoff must be discarded."""
    _insert(collector_db, status="NS", minuto="", goles_local=None, goles_visitante=None)
    payload = {
        "matches": [
            {
                "id": 6,
                "local": "Andorra",
                "visitante": "Ceuta",
                "status": "LIVE",
                "minute": "90",
                "score_home": 1,
                "score_away": 0,
            }
        ]
    }

    updates = collector.apply_q15_results_to_db(1, payload)

    assert updates == 0
    assert _read(collector_db)["status"] == "NS"


def test_provider_snapshot_of_a_real_live_match_is_applied_and_stamped(collector_db):
    _insert(collector_db, status="NS", minuto="", hora="14:45")
    payload = {
        "matches": [
            {
                "id": 6,
                "local": "Andorra",
                "visitante": "Ceuta",
                "status": "LIVE",
                "minute": "40",
                "score_home": 1,
                "score_away": 0,
            }
        ]
    }

    assert collector.apply_q15_results_to_db(1, payload) == 1
    row = collector_db.execute("SELECT status, minuto, updated_at FROM resultados").fetchone()
    assert row["status"] == "LIVE"
    assert row["updated_at"]


def test_unchanged_snapshot_refreshes_the_freshness_stamp(collector_db):
    """A quiet 0-0 still counts as 'the provider confirmed it just now'."""
    stale_stamp = (NOW - timedelta(minutes=29)).isoformat(timespec="seconds")
    _insert(
        collector_db, status="LIVE", hora="14:45", minuto="40", goles_local=0, goles_visitante=0, updated_at=stale_stamp
    )
    payload = {
        "matches": [
            {
                "id": 6,
                "local": "Andorra",
                "visitante": "Ceuta",
                "status": "LIVE",
                "minute": "40",
                "score_home": 0,
                "score_away": 0,
            }
        ]
    }

    collector.apply_q15_results_to_db(1, payload)

    assert collector_db.execute("SELECT updated_at FROM resultados").fetchone()["updated_at"] != stale_stamp
    assert collector.close_stuck_live_matches(1) == []
