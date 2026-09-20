import json
from pathlib import Path

from app import app
from liga_maestros.db import get_db
from liga_maestros.db.migrations import _import_jornada_resultados, ensure_jornada_completa


def test_j8_resultados_imported_into_db():
    with get_db() as conn:
        ensure_jornada_completa(conn, 8)
        _import_jornada_resultados(conn, 8)
        row = conn.execute(
            "SELECT local, visitante, status, goles_local, goles_visitante, signo_actual FROM resultados WHERE jornada = 8 AND partido_id = 15"
        ).fetchone()
        assert row is not None
        assert row["local"] == "Atlético de Madrid"
        assert row["visitante"] == "Real Madrid"
        assert row["status"] == "LIVE"
        assert row["goles_local"] == 0
        assert row["goles_visitante"] == 0
        assert row["signo_actual"] == "0-0"


def test_api_liga_data_contains_real_madrid_live_and_quiniela():
    client = app.test_client()
    res = client.get("/api/liga/data")
    assert res.status_code == 200
    data = res.get_json()
    assert int(data.get("jornada")) == 8

    # Match 15 on the ticket (Pleno al 15)
    partidos = data.get("partidos", [])
    assert len(partidos) == 15
    p15 = next((p for p in partidos if p["id"] == 15), None)
    assert p15 is not None
    assert p15["local"] == "Atlético de Madrid"
    assert p15["visitante"] == "Real Madrid"
    assert p15["status"] == "LIVE"
    assert p15["fecha_raw"] == "2026-09-20"
    assert p15["goles_local"] == 0
    assert p15["goles_visitante"] == 0
    assert p15["signo_actual"] == "0-0"
    assert p15["signo"] == "0-0"
    assert "0-0" in p15["marcador"]

    # Match in live_matches (Directo)
    live = data.get("live_matches", [])
    madrid_live = next(
        (m for m in live if "Real Madrid" in (m.get("visitante") or "") or "Real Madrid" in (m.get("local") or "")),
        None,
    )
    assert madrid_live is not None
    assert madrid_live["local"] == "Atlético de Madrid"
    assert madrid_live["visitante"] == "Real Madrid"
    assert madrid_live["status"] == "LIVE"
    assert madrid_live["competition_name"] == "LA LIGA"

    # Match in all_league_matches
    all_league = data.get("all_league_matches", [])
    madrid_league = [
        m for m in all_league if "Real Madrid" in (m.get("local") or "") or "Real Madrid" in (m.get("visitante") or "")
    ]
    # Both Real Madrid (F) and the Madrid derby
    assert len(madrid_league) >= 2


def test_api_q15_directo_defaults_to_active_jornada():
    client = app.test_client()
    res = client.get("/api/q15/directo")
    assert res.status_code == 200
    data = res.get_json()
    matches = data.get("matches", [])
    assert len(matches) == 15
    m15 = next((m for m in matches if m["id"] == 15), None)
    assert m15 is not None
    assert m15["local"] == "Atlético de Madrid"
    assert m15["visitante"] == "Real Madrid"
    assert m15["status"] == "LIVE"
    assert m15["score_home"] == 0
    assert m15["score_away"] == 0
