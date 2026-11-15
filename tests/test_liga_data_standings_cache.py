"""Regression tests for first-load standings freshness."""

import sqlite3

from liga_maestros.routes import liga_data


def _connection():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE resultados (
            jornada INTEGER,
            partido_id INTEGER,
            local TEXT,
            visitante TEXT,
            goles_local INTEGER,
            goles_visitante INTEGER,
            status TEXT,
            fecha TEXT,
            hora TEXT,
            minuto TEXT,
            updated_at TEXT
        )
        """
    )
    conn.execute(
        """
        INSERT INTO resultados
            (jornada, partido_id, local, visitante, goles_local, goles_visitante,
             status, fecha, hora, minuto, updated_at)
        VALUES (1, 1, 'Local', 'Visitante', 0, 0, 'FT', '2026-11-14', '18:00', '', '2026-11-14T18:00:00')
        """
    )
    conn.commit()
    return conn


def _reset_cache(monkeypatch):
    monkeypatch.setattr(liga_data, "_STANDINGS_CACHE", {"data": None, "expires": 0, "key": None})


def test_same_match_ids_with_new_score_rebuild_standings(monkeypatch):
    conn = _connection()
    _reset_cache(monkeypatch)
    calls = []

    def build(_conn, matches):
        calls.append(matches[0]["goles_local"])
        return {"primera": [{"gf": matches[0]["goles_local"]}]}, {"primera": {}}

    monkeypatch.setattr(liga_data, "build_standings_payload", build)
    monkeypatch.setattr(liga_data, "persist_standings", lambda *_args: None)

    before = [{"id": 1, "local": "Local", "visitante": "Visitante", "goles_local": 0, "status": "FT"}]
    first = liga_data._get_standings_cached(conn, before, {}, jornada="1")[0]
    cached = liga_data._get_standings_cached(conn, before, {}, jornada="1")[0]
    assert cached == first
    assert calls == [0]

    conn.execute(
        "UPDATE resultados SET goles_local = 2, updated_at = '2026-11-14T18:01:00' WHERE jornada = 1 AND partido_id = 1"
    )
    conn.commit()
    after = [{**before[0], "goles_local": 2}]
    second = liga_data._get_standings_cached(conn, after, {}, jornada="1")[0]

    assert calls == [0, 2]
    assert first["primera"][0]["gf"] == 0
    assert second["primera"][0]["gf"] == 2
    conn.close()


def test_same_match_ids_in_a_different_jornada_do_not_reuse_standings(monkeypatch):
    conn = _connection()
    _reset_cache(monkeypatch)
    calls = []

    def build(_conn, matches):
        calls.append(matches[0]["id"])
        return {"primera": [{"gf": len(calls)}]}, {"primera": {}}

    monkeypatch.setattr(liga_data, "build_standings_payload", build)
    monkeypatch.setattr(liga_data, "persist_standings", lambda *_args: None)
    matches = [{"id": 1, "local": "Local", "visitante": "Visitante", "goles_local": 0, "status": "NS"}]

    liga_data._get_standings_cached(conn, matches, {}, jornada="1")
    second = liga_data._get_standings_cached(conn, matches, {}, jornada="2")[0]

    assert len(calls) == 2
    assert second["primera"][0]["gf"] == 2
    conn.close()


def test_change_in_standings_source_file_rebuilds_payload(monkeypatch, tmp_path):
    conn = _connection()
    _reset_cache(monkeypatch)
    source_file = tmp_path / "standings.json"
    source_file.write_text("old", encoding="utf-8")
    monkeypatch.setattr(liga_data, "runtime_data_path", lambda _filename: str(source_file))
    calls = []

    def build(_conn, _matches):
        calls.append(len(calls) + 1)
        return {"primera": [{"gf": calls[-1]}]}, {"primera": {}}

    monkeypatch.setattr(liga_data, "build_standings_payload", build)
    monkeypatch.setattr(liga_data, "persist_standings", lambda *_args: None)
    matches = [{"id": 1, "local": "Local", "visitante": "Visitante", "goles_local": 0, "status": "NS"}]

    liga_data._get_standings_cached(conn, matches, {}, jornada="1")
    liga_data._get_standings_cached(conn, matches, {}, jornada="1")
    assert calls == [1]
    source_file.write_text("official standings updated", encoding="utf-8")
    second = liga_data._get_standings_cached(conn, matches, {}, jornada="1")[0]

    assert calls == [1, 2]
    assert second["primera"][0]["gf"] == 2
    conn.close()
