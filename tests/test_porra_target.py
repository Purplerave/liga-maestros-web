import sqlite3

from liga_maestros.routes.porra import _porra_target_match


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
            ("a", 1, "1"), ("b", 1, "1"), ("c", 1, "1"),
            ("a", 2, "1"), ("b", 2, "X"), ("c", 2, "2"),
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
