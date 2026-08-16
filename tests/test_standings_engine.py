"""Regresión: la clasificación nunca cuenta dos veces el mismo partido.

El fallo real: la tabla se construía sumando los partidos terminados de la
quiniela *encima* del fichero oficial. En cuanto el proveedor refrescaba
``STANDINGS_LALIGA_BASE.json`` con esa misma jornada ya contada, el equipo
aparecía con ``PJ 2`` y el doble de puntos tras haber jugado un solo partido.
"""

import sqlite3

import pytest

from liga_maestros.db.migrations import ensure_core_tables
from liga_maestros.services.payloads import standings as standings_payload
from liga_maestros.services.payloads.standings import (
    build_standings_payload,
    matchday_played,
    persist_standings,
)
from liga_maestros.services.season_rosters import LALIGA_2026_27, SEGUNDA_2026_27
from liga_maestros.services.standings_engine import (
    collect_finished_matches,
    compute_table,
    merge_rows,
)

HOME = "Deportivo Alavés"
AWAY = "Getafe CF"


@pytest.fixture
def conn():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    ensure_core_tables(connection)
    for division, roster in ((1, LALIGA_2026_27), (2, SEGUNDA_2026_27)):
        for pos, name in enumerate(roster, start=1):
            connection.execute(
                """
                INSERT INTO clasificacion (equipo, pj, pts, division, pos, pg, pe, pp, gf, gc, racha)
                VALUES (?, 0, 0, ?, ?, 0, 0, 0, 0, 0, '')
                """,
                (name, division, pos),
            )
    connection.commit()
    return connection


def _add_result(conn, partido_id, local, visitante, gh, ga, status="FT", jornada=1):
    conn.execute(
        """
        INSERT INTO resultados
            (jornada, partido_id, local, visitante, goles_local, goles_visitante, status, fecha, hora, minuto)
        VALUES (?, ?, ?, ?, ?, ?, ?, '2026-08-15', '19:30', '')
        """,
        (jornada, partido_id, local, visitante, gh, ga, status),
    )
    conn.commit()


def _row(standings, name, category="primera"):
    return next(row for row in standings[category] if row["n"] == name)


def _no_official(monkeypatch, official=None):
    monkeypatch.setattr(standings_payload, "load_standings_override", lambda: official or {})


def test_finished_match_is_counted_once(conn, monkeypatch):
    _no_official(monkeypatch)
    _add_result(conn, 1, HOME, AWAY, 3, 0)

    standings, _ = build_standings_payload(conn)

    assert _row(standings, HOME)["pj"] == 1
    assert _row(standings, HOME)["pts"] == 3
    assert _row(standings, AWAY)["pj"] == 1
    assert _row(standings, AWAY)["pts"] == 0


def test_provider_snapshot_does_not_double_count(conn, monkeypatch):
    """El bug original: proveedor + cálculo local sumaban el mismo partido."""
    _add_result(conn, 1, HOME, AWAY, 3, 0)
    official = {
        "primera": [{"n": HOME, "pj": 1, "pg": 1, "pe": 0, "pp": 0, "gf": 3, "gc": 0, "pts": 3}],
        "segunda": [],
    }
    _no_official(monkeypatch, official)

    standings, _ = build_standings_payload(conn)

    row = _row(standings, HOME)
    assert row["pj"] == 1, "un partido jugado no puede figurar como dos"
    assert row["pts"] == 3
    assert row["gf"] == 3


def test_provider_ahead_of_local_ledger_wins(conn, monkeypatch):
    """Si el proveedor ya cuenta más jornadas que nuestro registro, manda él."""
    _add_result(conn, 1, HOME, AWAY, 3, 0)
    official = {
        "primera": [{"n": HOME, "pj": 3, "pg": 3, "pe": 0, "pp": 0, "gf": 7, "gc": 1, "pts": 9}],
        "segunda": [],
    }
    _no_official(monkeypatch, official)

    row = _row(build_standings_payload(conn)[0], HOME)
    assert (row["pj"], row["pts"]) == (3, 9)
    assert row["source"] == "oficial"


def test_local_ledger_wins_while_provider_lags(conn, monkeypatch):
    """Durante la jornada el proveedor va por detrás: mandan los resultados."""
    _add_result(conn, 1, HOME, AWAY, 3, 0)
    official = {
        "primera": [{"n": HOME, "pj": 0, "pg": 0, "pe": 0, "pp": 0, "gf": 0, "gc": 0, "pts": 0}],
        "segunda": [],
    }
    _no_official(monkeypatch, official)

    row = _row(build_standings_payload(conn)[0], HOME)
    assert (row["pj"], row["pts"]) == (1, 3)
    assert row["source"] == "calculada"


def test_live_match_does_not_award_points(conn, monkeypatch):
    _no_official(monkeypatch)
    _add_result(conn, 1, HOME, AWAY, 2, 0, status="LIVE")

    row = _row(build_standings_payload(conn)[0], HOME)
    assert row["pj"] == 0, "un partido en juego no suma hasta que termina"
    assert row["pts"] == 0
    assert row["en_juego"] is True
    assert row["marcador_live"] == "2-0"


def test_duplicate_sources_are_deduplicated(conn):
    """El mismo partido desde la quiniela y desde el panel cuenta una vez."""
    _add_result(conn, 1, HOME, AWAY, 3, 0)
    panel = [
        {
            "competition_name": "LA LIGA",
            "status": "FT",
            "local": HOME,
            "visitante": AWAY,
            "score": "3-0",
        }
    ]

    matches = collect_finished_matches(conn, extra_matches=panel)

    assert len(matches) == 1


def test_panel_adds_non_quiniela_matches(conn, monkeypatch):
    """Un partido de liga que no está en la quiniela también cuenta."""
    _no_official(monkeypatch)
    panel = [
        {
            "competition_name": "LA LIGA",
            "status": "FT",
            "local": "Real Madrid",
            "visitante": "FC Barcelona",
            "score": "2-1",
        }
    ]

    standings, _ = build_standings_payload(conn, extra_matches=panel)

    assert _row(standings, "Real Madrid")["pts"] == 3
    assert _row(standings, "FC Barcelona")["pts"] == 0


def test_table_is_sorted_and_positions_assigned(conn, monkeypatch):
    _no_official(monkeypatch)
    _add_result(conn, 1, HOME, AWAY, 5, 0)
    _add_result(conn, 2, "Real Madrid", "Valencia CF", 1, 0)

    standings, _ = build_standings_payload(conn)
    primera = standings["primera"]

    assert primera[0]["n"] == HOME  # mismos puntos, mejor diferencia de goles
    assert primera[1]["n"] == "Real Madrid"
    assert [row["pos"] for row in primera] == list(range(1, len(primera) + 1))


def test_full_roster_is_always_present(conn, monkeypatch):
    _no_official(monkeypatch)
    _add_result(conn, 1, HOME, AWAY, 3, 0)

    standings, _ = build_standings_payload(conn)

    assert len(standings["primera"]) == len(LALIGA_2026_27)
    assert len(standings["segunda"]) == len(SEGUNDA_2026_27)


def test_matchday_played_uses_max_not_average(conn, monkeypatch):
    """Un partido aplazado no debe retrasar la jornada de toda la liga."""
    _no_official(monkeypatch)
    _add_result(conn, 1, HOME, AWAY, 3, 0)

    standings, _ = build_standings_payload(conn)
    assert matchday_played(standings) == 1


def test_persist_writes_the_same_numbers(conn, monkeypatch):
    _no_official(monkeypatch)
    _add_result(conn, 1, HOME, AWAY, 3, 0)

    standings, _ = build_standings_payload(conn)
    persist_standings(conn, standings)

    row = conn.execute("SELECT pj, pts, pg, gf, racha FROM clasificacion WHERE equipo = ?", (HOME,)).fetchone()
    assert (row["pj"], row["pts"], row["pg"], row["gf"]) == (1, 3, 1, 3)
    assert row["racha"] == "1W"


def test_form_and_streak_track_recent_results(conn, monkeypatch):
    _no_official(monkeypatch)
    _add_result(conn, 1, HOME, AWAY, 3, 0, jornada=1)
    _add_result(conn, 1, HOME, "Real Madrid", 2, 0, jornada=2)

    row = _row(build_standings_payload(conn)[0], HOME)
    assert row["form"] == ["W", "W"]
    assert row["streak"] == "2W"
    assert row["pj"] == 2


def test_merge_rows_never_sums():
    merged = merge_rows(
        {"n": "X", "pj": 1, "pts": 3, "gf": 3, "gc": 0},
        {"n": "X", "pj": 1, "pts": 3, "gf": 3, "gc": 0, "form": ["W"], "streak": "1W"},
    )
    assert merged["pj"] == 1
    assert merged["pts"] == 3
    assert merged["form"] == ["W"]


def test_compute_table_ignores_teams_outside_the_roster():
    matches = [
        {
            "key": "A|B",
            "home_key": "UNKNOWN TEAM",
            "away_key": "OTHER TEAM",
            "gh": 1,
            "ga": 0,
            "when": "2026-08-15",
        }
    ]
    table = compute_table(matches, LALIGA_2026_27)
    assert all(row["pj"] == 0 for row in table)
