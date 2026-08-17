"""Regresión: la clasificación nunca cuenta dos veces el mismo partido.

El fallo real: la tabla se construía sumando los partidos terminados de la
quiniela *encima* del fichero oficial. En cuanto el proveedor refrescaba
``STANDINGS_LALIGA_BASE.json`` con esa misma jornada ya contada, el equipo
aparecía con ``PJ 2`` y el doble de puntos tras haber jugado un solo partido.
"""

import sqlite3
from datetime import timedelta

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
    _panel_competition,
    collect_finished_matches,
    compute_table,
    merge_rows,
)
from liga_maestros.services.ticket import madrid_now

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


def _add_result(
    conn,
    partido_id,
    local,
    visitante,
    gh,
    ga,
    status="FT",
    jornada=1,
    fecha="2026-08-15",
    hora="19:30",
    minuto="",
):
    conn.execute(
        """
        INSERT INTO resultados
            (jornada, partido_id, local, visitante, goles_local, goles_visitante, status, fecha, hora, minuto)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (jornada, partido_id, local, visitante, gh, ga, status, fecha, hora, minuto),
    )
    conn.commit()


def _kickoff_minutes_ago(minutes):
    """Fecha/hora of a match that started ``minutes`` ago in Madrid time."""
    started = madrid_now() - timedelta(minutes=minutes)
    return started.strftime("%Y-%m-%d"), started.strftime("%H:%M")


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
    fecha, hora = _kickoff_minutes_ago(30)
    _add_result(conn, 1, HOME, AWAY, 2, 0, status="LIVE", fecha=fecha, hora=hora, minuto="30")

    row = _row(build_standings_payload(conn)[0], HOME)
    assert row["pj"] == 0, "un partido en juego no suma hasta que termina"
    assert row["pts"] == 0
    assert row["en_juego"] is True
    assert row["marcador_live"] == "2-0"


def test_finished_match_left_stuck_at_live_never_shows_a_live_score(conn, monkeypatch):
    """Sevilla ya habia terminado y la clasificacion seguia dando su marcador.

    El proveedor (o el colector caido) puede dejar la fila en LIVE despues del
    pitido final. La tabla debe cerrar ese directo con las mismas reglas que el
    resto de la web: los puntos ya estan contados y el marcador provisional
    tiene que desaparecer.
    """
    _no_official(monkeypatch)
    fecha, hora = _kickoff_minutes_ago(400)
    _add_result(conn, 1, HOME, AWAY, 2, 1, status="LIVE", fecha=fecha, hora=hora, minuto="90")

    row = _row(build_standings_payload(conn)[0], HOME)

    assert row.get("en_juego") is not True, "un partido acabado no puede seguir en juego"
    assert not row.get("marcador_live"), "el marcador en vivo debe desaparecer al terminar"


def test_live_match_from_the_panel_is_closed_when_the_provider_freezes(conn, monkeypatch):
    """Un partido que no esta en la quiniela tambien se cierra al congelarse."""
    _no_official(monkeypatch)
    frozen = madrid_now().replace(tzinfo=None) - timedelta(minutes=200)
    panel = [
        {
            "competition_name": "LA LIGA",
            "status": "LIVE",
            "local": "Real Madrid",
            "visitante": "FC Barcelona",
            "score": "1-0",
            "fecha_raw": frozen.strftime("%Y-%m-%d"),
            "hora": frozen.strftime("%H:%M"),
            "time": "90",
        }
    ]

    standings, _ = build_standings_payload(conn, extra_matches=panel)
    row = _row(standings, "Real Madrid")

    assert row.get("en_juego") is not True
    assert not row.get("marcador_live")


def test_genuine_panel_live_match_still_shows_its_provisional_score(conn, monkeypatch):
    """Un directo real fuera de la quiniela si tiene que verse en la tabla."""
    _no_official(monkeypatch)
    started = madrid_now().replace(tzinfo=None) - timedelta(minutes=25)
    panel = [
        {
            "competition_name": "LA LIGA",
            "status": "LIVE",
            "local": "Real Madrid",
            "visitante": "FC Barcelona",
            "score": "1-0",
            "fecha_raw": started.strftime("%Y-%m-%d"),
            "hora": started.strftime("%H:%M"),
            "time": "25",
        }
    ]

    standings, _ = build_standings_payload(conn, extra_matches=panel)
    row = _row(standings, "Real Madrid")

    assert row["en_juego"] is True
    assert row["marcador_live"] == "1-0"
    assert row["pj"] == 0, "un directo no suma puntos hasta que acaba"


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


def test_panel_competition_ignores_accents():
    """El panel entrega 'Segunda División' con tilde: no puede perderse."""
    assert _panel_competition({"competition_name": "Segunda División"}) == "segunda"
    assert _panel_competition({"competition": {"name": "Segunda División"}}) == "segunda"
    assert _panel_competition({"competition_name": "La Liga"}) == "primera"
    assert _panel_competition({"competition_name": "Segunda División de Chile"}) is None


def test_panel_match_with_accented_competition_feeds_the_table(conn, monkeypatch):
    """Castellón 1-0 R. Sociedad B: solo llega por el panel, con tilde en la competición.

    El partido no esta en la quiniela, asi que si el panel no se lee bien el
    Castellon se queda sin forma y sin racha (aunque el proveedor oficial le
    ponga los numeros).
    """
    _no_official(monkeypatch)
    panel = [
        {
            "competition_name": "Segunda División",
            "competition": {"name": "Segunda División"},
            "status": "FINISHED",
            "local": "Castellón",
            "visitante": "R. Sociedad B",
            "score": "1 - 0",
        }
    ]

    standings, _ = build_standings_payload(conn, extra_matches=panel)

    castellon = _row(standings, "CD Castellón", category="segunda")
    assert (castellon["pj"], castellon["pts"]) == (1, 3)
    assert castellon["form"] == ["W"]
    assert castellon["streak"] == "1W"
    sociedad_b = _row(standings, "R. Sociedad B", category="segunda")
    assert sociedad_b["form"] == ["L"]
    assert sociedad_b["streak"] == "1L"


def test_panel_match_closed_as_stale_with_a_score_still_counts(conn, monkeypatch):
    """Un directo cerrado sin confirmacion (STALE) ya es un resultado para la tabla."""
    _no_official(monkeypatch)
    panel = [
        {
            "competition_name": "Segunda División",
            "status": "STALE",
            "local": "Castellón",
            "visitante": "R. Sociedad B",
            "score": "1 - 0",
        }
    ]

    standings, _ = build_standings_payload(conn, extra_matches=panel)

    castellon = _row(standings, "CD Castellón", category="segunda")
    assert castellon["form"] == ["W"]
    assert castellon["streak"] == "1W"
    assert (castellon["pj"], castellon["pts"]) == (1, 3)
