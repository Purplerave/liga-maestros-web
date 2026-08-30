"""Regresiones del directo de Liga F en la quiniela.

El panel generico de Highlightly (/matches?limit=100) se pagina y, en dias
con muchos partidos, los de Liga F pueden quedar fuera de la primera pagina,
con lo que la quiniela nunca los ve en directo. `fetch_highlightly_matches`
debe, cuando la jornada activa tiene un partido femenino en esa fecha,
consultar Liga F explicitamente por nombre y fusionarlo. Tambien se cubre el
fix de porra: `refresh_current_matches_from_highlightly` verificaba puntos con
una conexion ya cerrada y por eso jamas otorgaba puntos desde el directo.
"""

import sqlite3

import config
from liga_maestros.db import migrations
from liga_maestros.services import highlightly


def _seed_j3(conn):
    migrations.ensure_core_tables(conn)
    migrations.ensure_jornada_completa(conn, 3)
    conn.commit()


def _patch_env(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "pro.db"))
    monkeypatch.setenv("HIGHLIGHTLY_API_KEY", "test-key")


def _sample_match(match_id, league="Liga F", desc="Second half", clock="67", score="1 - 0"):
    return {
        "id": match_id,
        "date": "2026-08-30T19:00:00.000Z",
        "league": {"name": league},
        "homeTeam": {"name": "Real Madrid Femenino", "logo": None},
        "awayTeam": {"name": "Atlético Madrid Femenino", "logo": None},
        "state": {"description": desc, "clock": clock, "score": {"current": score}},
    }


def test_liga_f_is_explicitly_fetched_when_generic_list_lacks_it(tmp_path, monkeypatch):
    _patch_env(tmp_path, monkeypatch)
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    _seed_j3(conn)

    calls = []

    def fake_get_matches(params, headers):
        calls.append(dict(params))
        # Pagina generica truncada: no trae Liga F.
        if "leagueName" not in params:
            return []
        return [_sample_match(991)]

    monkeypatch.setattr(highlightly, "_highlightly_get_matches", fake_get_matches)

    matches = highlightly.fetch_highlightly_matches("2026-08-30", conn=conn, jornada=3, max_calls=5)
    conn.close()

    assert [m["id"] for m in matches] == [991]
    assert matches[0]["_competition_name"] == "LIGA F"
    assert any("leagueName" in c for c in calls), "debe consultar Liga F por nombre"


def test_liga_f_merge_is_deduped_by_id(tmp_path, monkeypatch):
    _patch_env(tmp_path, monkeypatch)
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    _seed_j3(conn)

    calls = []

    def fake_get_matches(params, headers):
        calls.append(dict(params))
        # Tanto la pagina generica como la consulta por nombre devuelven el
        # mismo partido: el merge no debe duplicarlo.
        return [_sample_match(992, league="Liga F")]

    monkeypatch.setattr(highlightly, "_highlightly_get_matches", fake_get_matches)

    matches = highlightly.fetch_highlightly_matches("2026-08-30", conn=conn, jornada=3, max_calls=5)
    conn.close()

    assert [m["id"] for m in matches] == [992]
    assert len(calls) == 2, "consulta generica + consulta explicita por nombre de Liga F"


def test_no_liga_f_query_when_quiniela_has_no_feminine_on_date(tmp_path, monkeypatch):
    _patch_env(tmp_path, monkeypatch)
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    _seed_j3(conn)

    calls = []

    def fake_get_matches(params, headers):
        calls.append(dict(params))
        return [_sample_match(993, league="La Liga")]

    monkeypatch.setattr(highlightly, "_highlightly_get_matches", fake_get_matches)

    # 2026-08-31 solo tiene partidos masculinos en la J3 (Osasuna-Getafe, Barcelona-Rayo).
    matches = highlightly.fetch_highlightly_matches("2026-08-31", conn=conn, jornada=3, max_calls=5)
    conn.close()

    assert len(calls) == 1
    assert all("leagueName" not in c for c in calls)


def test_refresh_awards_porra_points_with_open_connection(tmp_path, monkeypatch):
    _patch_env(tmp_path, monkeypatch)
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    _seed_j3(conn)
    conn.close()

    from liga_maestros.routes import porra

    def fake_get_matches(params, headers):
        if params.get("leagueName"):
            return []
        return [
            {
                "id": 5001,
                "date": "2026-08-29T15:00:00.000Z",
                "league": {"name": "La Liga"},
                "homeTeam": {"name": "Levante UD", "logo": None},
                "awayTeam": {"name": "Real Betis", "logo": None},
                "state": {"description": "Finished", "score": {"current": "2 - 1"}},
            }
        ]

    monkeypatch.setattr(highlightly, "_highlightly_get_matches", fake_get_matches)
    monkeypatch.setattr(highlightly, "refresh_dates_for_jornada", lambda conn, jornada=None: ["2026-08-29"])

    seen = {}

    def fake_porra(porra_conn, jornada):
        # La conexion debe estar abierta: si no, falla aqui y se traga el error.
        assert porra_conn.execute("SELECT 1").fetchone() is not None
        seen["jornada"] = jornada
        return 0

    monkeypatch.setattr(porra, "check_and_award_porra_points", fake_porra)

    updates = highlightly.refresh_current_matches_from_highlightly(force=True, jornada=3)

    assert updates >= 1
    assert seen.get("jornada") == 3
