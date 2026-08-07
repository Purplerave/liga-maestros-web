import sqlite3
from datetime import timedelta

from liga_maestros.routes.porra import (
    _porra_is_locked,
    _porra_target_match,
    check_and_award_porra_points,
)
from liga_maestros.services.ticket import madrid_now


def porra_connection():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE resultados (
            jornada INTEGER, partido_id INTEGER, local TEXT, visitante TEXT,
            fecha TEXT, hora TEXT, status TEXT, goles_local INTEGER, goles_visitante INTEGER
        );
        CREATE TABLE predicciones (
            user_id TEXT, jornada INTEGER, partido_id INTEGER, signo TEXT
        );
        CREATE TABLE porra_entries (
            jornada INTEGER, partido_id INTEGER, user_id TEXT, nombre TEXT,
            goles_local INTEGER, goles_visitante INTEGER, created_at TEXT, updated_at TEXT
        );
    """)
    conn.executemany(
        "INSERT INTO resultados VALUES (73, ?, ?, ?, '2099-07-18', ?, 'NS', NULL, NULL)",
        [(1, "Favorito", "Rival", "14:00"), (2, "Igualado", "Visitante", "16:00")],
    )
    return conn


def test_porra_chooses_most_divided_upcoming_match():
    conn = porra_connection()
    conn.executemany(
        "INSERT INTO predicciones VALUES (?, 73, ?, ?)",
        [
            ("a", 1, "1"),
            ("b", 1, "1"),
            ("c", 1, "1"),
            ("a", 2, "1"),
            ("b", 2, "X"),
            ("c", 2, "2"),
        ],
    )

    assert _porra_target_match(conn, 73)["partido_id"] == 2
    conn.close()


def test_porra_keeps_match_that_already_has_entries():
    conn = porra_connection()
    conn.execute(
        "INSERT INTO porra_entries VALUES (73, 1, 'u1', 'Pablo', 2, 1, '2099-07-17 10:00:00', '2099-07-17 10:00:00')"
    )

    assert _porra_target_match(conn, 73)["partido_id"] == 1
    conn.close()


def test_porra_excludes_pleno_al_15():
    conn = porra_connection()
    conn.execute(
        "INSERT INTO resultados VALUES (73, 15, 'Espana', 'Argentina', '2099-07-19', '21:00', 'NS', NULL, NULL)"
    )
    conn.execute(
        "INSERT INTO porra_entries VALUES (73, 1, 'u1', 'Pablo', 2, 1, '2099-07-17 10:00:00', '2099-07-17 10:00:00')"
    )

    assert _porra_target_match(conn, 73)["partido_id"] == 1
    conn.close()


def test_porra_does_not_keep_finished_match_with_entries():
    conn = porra_connection()
    conn.execute("UPDATE resultados SET status = 'FT' WHERE partido_id = 1")
    conn.execute(
        "INSERT INTO porra_entries VALUES (73, 1, 'u1', 'Pablo', 2, 1, '2099-07-17 10:00:00', '2099-07-17 10:00:00')"
    )

    assert _porra_target_match(conn, 73)["partido_id"] == 2
    conn.close()


def test_user_can_select_any_open_match_including_pleno():
    conn = porra_connection()
    conn.execute(
        "INSERT INTO resultados VALUES (73, 15, 'Espana', 'Argentina', '2099-07-19', '21:00', 'NS', NULL, NULL)"
    )

    selected = _porra_target_match(conn, 73, partido_id=15)

    assert selected["partido_id"] == 15
    assert _porra_is_locked(selected) is False
    conn.close()


def test_exact_score_awards_one_extra_point_once():
    conn = porra_connection()
    conn.execute("CREATE TABLE usuarios (id TEXT PRIMARY KEY, puntos_acumulados INTEGER DEFAULT 0)")
    conn.execute(
        "CREATE TABLE porra_puntos (jornada INTEGER, partido_id INTEGER, user_id TEXT, puntos INTEGER, UNIQUE(jornada, partido_id, user_id))"
    )
    conn.execute("INSERT INTO usuarios VALUES ('u1', 7)")
    conn.execute(
        "INSERT INTO porra_entries VALUES (73, 1, 'u1', 'Pablo', 2, 1, '2099-07-17 10:00:00', '2099-07-17 10:00:00')"
    )
    conn.execute("UPDATE resultados SET status = 'FT', goles_local = 2, goles_visitante = 1 WHERE partido_id = 1")

    assert check_and_award_porra_points(conn, 73) == 1
    assert conn.execute("SELECT puntos_acumulados FROM usuarios WHERE id = 'u1'").fetchone()[0] == 8
    assert check_and_award_porra_points(conn, 73) == 0
    assert conn.execute("SELECT puntos_acumulados FROM usuarios WHERE id = 'u1'").fetchone()[0] == 8
    conn.close()


def test_porra_is_locked_after_kickoff():
    past = madrid_now() - timedelta(minutes=1)
    match = {"fecha": past.strftime("%Y-%m-%d"), "hora": past.strftime("%H:%M"), "status": "NS"}
    assert _porra_is_locked(match) is True


def test_porra_is_locked_when_match_is_live_or_finished():
    assert _porra_is_locked({"fecha": "2099-01-01", "hora": "12:00", "status": "LIVE"}) is True
    assert _porra_is_locked({"fecha": "2099-01-01", "hora": "12:00", "status": "FT"}) is True
