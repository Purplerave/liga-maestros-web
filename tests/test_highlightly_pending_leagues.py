"""Regresión: resultados finales que se caen de la página genérica de Highlightly.

El panel genérico `/matches?limit=100` está paginado. En un día con muchos
partidos, un partido de Segunda que acaba de terminar se sale de la primera
página, así que la fila conservaba el último marcador en directo: Ceuta-R.
Sociedad B quedó 1-1 en `STALE` y se puntuó como X. Cuando la jornada activa
tiene un resultado sin confirmar (STALE, sin goles o sin estado final),
`fetch_highlightly_matches` debe consultar explícitamente las ligas de la
quiniela y fusionar la respuesta.

La segunda parte del fix es el cruce de nombres: la fila guarda "Ceuta" y el
proveedor devuelve "AD Ceuta FC", así que ni con el partido en el feed se
actualizaba la fila.
"""

import sqlite3

import config
from liga_maestros.db import migrations
from liga_maestros.services import highlightly

FECHA = "2026-08-30"
HORA = "14:00"
RECENT = 60 * 24  # horas: la jornada se cerro "hace poco" respecto a la fecha del partido


def _patch_env(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "pro.db"))
    monkeypatch.setenv("HIGHLIGHTLY_API_KEY", "test-key")
    # El .env local deja el refresco apagado y la constante se lee al importar.
    monkeypatch.setattr(highlightly, "HIGHLIGHTLY_REFRESH_ENABLED", True)


def _seed(conn, monkeypatch, tmp_path, status, goles_local, goles_visitante):
    migrations.ensure_core_tables(conn)
    migrations.ensure_jornada_completa(conn, 3)
    conn.execute(
        """
        UPDATE resultados
        SET local = 'Ceuta', visitante = 'R. Sociedad B', fecha = ?, hora = ?,
            status = ?, goles_local = ?, goles_visitante = ?, minuto = 'Sin datos'
        WHERE jornada = 3 AND partido_id = 1
        """,
        (FECHA, HORA, status, goles_local, goles_visitante),
    )
    conn.execute("DELETE FROM resultados WHERE jornada = 3 AND partido_id <> 1")
    # El test se centra en el paso masculino: Liga F se comprueba en test_liga_f_live.
    monkeypatch.setattr(highlightly, "_quiniela_has_feminine_matches_on_date", lambda *a, **k: False)
    conn.commit()


def _finished_ceuta():
    return {
        "id": 778899,
        "date": "2026-08-30T12:00:00.000Z",
        "league": {"name": "Segunda División"},
        "homeTeam": {"name": "AD Ceuta FC", "logo": None},
        "awayTeam": {"name": "R. Sociedad B", "logo": None},
        "state": {"description": "Finished", "score": {"current": "2 - 1"}},
    }


def _patch_feed(monkeypatch, calls):
    def fake_get_matches(params, headers):
        calls.append(dict(params))
        if "leagueId" in params:
            return [_finished_ceuta()]
        # Página genérica truncada: el partido ya no aparece.
        return []

    monkeypatch.setattr(highlightly, "_highlightly_get_matches", fake_get_matches)


def test_stale_match_triggers_explicit_second_division_call(tmp_path, monkeypatch):
    _patch_env(monkeypatch, tmp_path)
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    _seed(conn, monkeypatch, tmp_path, "STALE", 1, 1)
    monkeypatch.setattr(highlightly, "HIGHLIGHTLY_PENDING_WINDOW_HOURS", RECENT)
    calls = []
    _patch_feed(monkeypatch, calls)

    matches = highlightly.fetch_highlightly_matches(FECHA, conn=conn, jornada=3, max_calls=4)
    conn.close()

    assert [m["id"] for m in matches] == [778899]
    league_ids = [c.get("leagueId") for c in calls if "leagueId" in c]
    assert config.HIGHLIGHTLY_LEAGUES["SEGUNDA DIVISION"] in league_ids, (
        "con un resultado sin confirmar debe consultarse Segunda de forma explicita"
    )


def test_no_extra_call_when_result_is_already_confirmed(tmp_path, monkeypatch):
    _patch_env(monkeypatch, tmp_path)
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    _seed(conn, monkeypatch, tmp_path, "FT", 2, 1)
    monkeypatch.setattr(highlightly, "HIGHLIGHTLY_PENDING_WINDOW_HOURS", RECENT)
    calls = []
    _patch_feed(monkeypatch, calls)

    highlightly.fetch_highlightly_matches(FECHA, conn=conn, jornada=3, max_calls=4)
    conn.close()

    assert len(calls) == 1, "con el resultado ya confirmado solo cabe la pagina generica"
    assert all("leagueId" not in c for c in calls)


def test_pending_window_ignores_long_finished_rows(tmp_path, monkeypatch):
    _patch_env(monkeypatch, tmp_path)
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    _seed(conn, monkeypatch, tmp_path, "STALE", 1, 1)
    # 2 horas de margen: la fila lleva semanas sin confirmar.
    monkeypatch.setattr(highlightly, "HIGHLIGHTLY_PENDING_WINDOW_HOURS", 2)
    calls = []
    _patch_feed(monkeypatch, calls)

    highlightly.fetch_highlightly_matches(FECHA, conn=conn, jornada=3, max_calls=4)
    conn.close()

    assert len(calls) == 1, "fuera de la ventana no se gastan llamadas extra"
    assert all("leagueId" not in c for c in calls)


def test_pending_call_respects_refresh_budget(tmp_path, monkeypatch):
    _patch_env(monkeypatch, tmp_path)
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    _seed(conn, monkeypatch, tmp_path, "STALE", 1, 1)
    monkeypatch.setattr(highlightly, "HIGHLIGHTLY_PENDING_WINDOW_HOURS", RECENT)
    calls = []
    _patch_feed(monkeypatch, calls)

    # max_calls=1: la pagina generica agota el presupuesto de la pasada.
    highlightly.fetch_highlightly_matches(FECHA, conn=conn, jornada=3, max_calls=1)
    conn.close()

    assert all("leagueId" not in c for c in calls), "no se puede pasar el presupuesto de la pasada"


def test_refresh_writes_the_confirmed_final_score(tmp_path, monkeypatch):
    _patch_env(monkeypatch, tmp_path)
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    _seed(conn, monkeypatch, tmp_path, "STALE", 1, 1)
    monkeypatch.setattr(highlightly, "HIGHLIGHTLY_PENDING_WINDOW_HOURS", RECENT)
    conn.close()
    _patch_feed(monkeypatch, [])
    monkeypatch.setattr(highlightly, "refresh_dates_for_jornada", lambda conn, jornada=None: [FECHA])

    updates = highlightly.refresh_current_matches_from_highlightly(force=True, jornada=3)

    check = sqlite3.connect(config.DB_PATH)
    check.row_factory = sqlite3.Row
    row = check.execute(
        "SELECT status, goles_local, goles_visitante, minuto, signo_actual FROM resultados"
        " WHERE jornada = 3 AND partido_id = 1"
    ).fetchone()
    check.close()

    assert updates >= 1
    assert row["status"] == "FT"
    assert (row["goles_local"], row["goles_visitante"]) == (2, 1)
    assert row["minuto"] == "Finalizado"
    assert row["signo_actual"] == "1", "2-1 local es signo 1, no la X del marcador parcial"


def test_core_lookup_matches_legal_form_variants():
    feed = {}
    core_feed = {}
    match = _finished_ceuta()
    feed[("AD CEUTA FC", "R SOCIEDAD B")] = (match, False)
    feed[("R SOCIEDAD B", "AD CEUTA FC")] = (match, True)
    home_core = highlightly._core_team_key("AD Ceuta FC")
    away_core = highlightly._core_team_key("R. Sociedad B")
    assert home_core == ("CEUTA",)
    core_feed[(home_core, away_core)] = [(match, False)]
    core_feed[(away_core, home_core)] = [(match, True)]

    found = highlightly._find_feed_item(feed, "Ceuta", "R. Sociedad B", core_feed)

    assert found is not None
    assert found[0]["id"] == 778899


def test_core_lookup_refuses_ambiguous_pair():
    match = _finished_ceuta()
    other = dict(match, id=778900)
    home_core = highlightly._core_team_key("AD Ceuta FC")
    away_core = highlightly._core_team_key("R. Sociedad B")
    core_feed = {
        (home_core, away_core): [(match, False)],
        (away_core, home_core): [(match, True), (other, True)],
    }

    assert highlightly._find_feed_item({}, "Ceuta", "R. Sociedad B", core_feed) is None
