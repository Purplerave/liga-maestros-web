"""Rendimiento de ``/api/liga/data`` con un panel externo grande.

El panel ``LIVE_ALL_MATCHES_V3.json`` acumula todos los partidos que ha visto
el proveedor (varios MB a mitad de temporada). Medido en local con 6.000
partidos, cada peticion lo parseaba tres veces y normalizaba nombres y fechas
de miles de partidos de otras jornadas que nunca podian cruzar.

Cubren:
- El panel se parsea una vez por version del fichero y nadie puede ensuciar
  la copia cacheada.
- Los partidos fuera de +-1 dia de la jornada no se procesan, con el mismo
  resultado.
- Un partido viejo del mismo emparejamiento (la ida del derbi) ya no tapa el
  marcador en directo del de hoy.
- ``/api/liga/data`` sale comprimido con gzip y conserva el 304 por ETag.
"""

from __future__ import annotations

import gzip
import json
from datetime import timedelta

import pytest

import config
from liga_maestros.services.payloads import league_matches
from liga_maestros.services.ticket import madrid_now


@pytest.fixture
def panel(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.setattr(config, "DATA_DIR", str(data_dir))
    monkeypatch.setattr(config, "BASE_DIR", str(tmp_path))
    monkeypatch.delenv("LIVE_ALL_MATCHES_EXTRA_PATH", raising=False)
    monkeypatch.setitem(league_matches._EXTERNAL_CACHE, "key", None)
    monkeypatch.setitem(league_matches._EXTERNAL_CACHE, "matches", [])
    path = data_dir / "LIVE_ALL_MATCHES_V3.json"

    def write(matches):
        path.write_text(json.dumps(matches), encoding="utf-8")
        return path

    return write


class _CountingJson:
    def __init__(self):
        self.loads = 0

    def load(self, fh):
        self.loads += 1
        return json.load(fh)

    def __getattr__(self, name):
        return getattr(json, name)


def test_el_panel_se_parsea_una_vez_por_version_del_fichero(panel, monkeypatch):
    counter = _CountingJson()
    monkeypatch.setattr(league_matches, "json", counter)
    panel([{"id": 1, "local": "A", "visitante": "B", "status": "FT"}])

    first = league_matches._load_external_matches()
    second = league_matches._load_external_matches()
    assert counter.loads == 1
    assert first == second == [{"id": 1, "local": "A", "visitante": "B", "status": "FT"}]

    # Nueva version del fichero (otro tamaño): se vuelve a leer.
    panel([{"id": 1, "local": "A", "visitante": "B", "status": "FT"}, {"id": 2, "local": "C", "visitante": "D"}])
    assert len(league_matches._load_external_matches()) == 2
    assert counter.loads == 2


def test_los_lectores_no_ensucian_la_copia_cacheada(panel):
    panel([{"id": 1, "local": "A", "visitante": "B", "status": "LIVE"}])

    copy = league_matches._load_external_matches()
    copy[0]["status"] = "STALE"
    copy[0]["home_logo"] = "x.png"

    assert league_matches._load_external_matches() == [{"id": 1, "local": "A", "visitante": "B", "status": "LIVE"}]


def test_un_panel_ilegible_no_rompe_nada(panel):
    path = panel([])
    path.write_text("{no es json", encoding="utf-8")
    assert league_matches._load_external_matches() == []


def _provider(local, visitante, when, status, score, **extra):
    return {
        "local": local,
        "visitante": visitante,
        "fecha_raw": when.strftime("%Y-%m-%d"),
        "hora": when.strftime("%H:%M"),
        "status": status,
        "score": score,
        **extra,
    }


def test_la_ida_del_derbi_ya_no_tapa_el_marcador_en_directo(panel):
    """Mismo emparejamiento meses antes: antes ganaba el final viejo y se perdia el directo."""
    now = madrid_now().replace(tzinfo=None)
    kickoff = now - timedelta(minutes=30)
    panel(
        [
            _provider("Sevilla", "Betis", kickoff, "LIVE", "1-0", time="30'", updated_at=now.isoformat()),
            _provider("Sevilla", "Betis", now - timedelta(days=200), "FT", "2-2"),
        ]
    )
    partidos = [
        {
            "id": 15,
            "local": "Sevilla",
            "visitante": "Betis",
            "fecha_raw": kickoff.strftime("%Y-%m-%d"),
            "hora": kickoff.strftime("%H:%M"),
            "status": "NS",
        }
    ]

    merged = league_matches.apply_verified_provider_scores(partidos)

    assert merged[0]["goles_local"] == 1
    assert merged[0]["goles_visitante"] == 0
    assert merged[0]["status"] == "LIVE"


def test_los_partidos_de_otras_fechas_no_se_procesan(panel, monkeypatch):
    now = madrid_now().replace(tzinfo=None)
    kickoff = now - timedelta(minutes=30)
    old = [_provider(f"Equipo {i}", f"Rival {i}", now - timedelta(days=30 + i % 200), "FT", "1-1") for i in range(800)]
    panel([*old, _provider("Sevilla", "Betis", kickoff, "LIVE", "1-0", time="30'", updated_at=now.isoformat())])
    calls = []
    original = league_matches.normalize_team_key

    def counting(*args, **kwargs):
        calls.append(args)
        return original(*args, **kwargs)

    monkeypatch.setattr(league_matches, "normalize_team_key", counting)
    partidos = [
        {
            "id": 15,
            "local": "Sevilla",
            "visitante": "Betis",
            "fecha_raw": kickoff.strftime("%Y-%m-%d"),
            "hora": kickoff.strftime("%H:%M"),
            "status": "NS",
        }
    ]

    merged = league_matches.apply_verified_provider_scores(partidos)

    assert merged[0]["goles_local"] == 1
    # 2 nombres del proveedor + 2 de la casilla; no 1.600 del historico.
    assert len(calls) <= 8


def test_el_filtro_de_ventana_da_lo_mismo_sin_parsear_el_historico(panel, monkeypatch):
    now = madrid_now().replace(tzinfo=None)
    today = now.strftime("%Y-%m-%d")
    quiniela = [
        {"local": "A", "visitante": "B", "fecha_raw": today, "hora": "12:00", "status": "FT"},
    ]
    yesterday = now - timedelta(days=1)
    matches = [
        _provider("Hoy", "Tarde", now.replace(hour=12, minute=0), "NS", ""),
        _provider("Ayer", "Noche", yesterday.replace(hour=21, minute=0), "FT", "2-0"),
        _provider("Mes", "Pasado", now - timedelta(days=40), "FT", "0-0"),
        {"local": "Sin", "visitante": "Fecha", "status": "FT", "score": "1-0"},
        _provider("En", "Juego", now - timedelta(days=3), "LIVE", "1-1"),
    ]
    parsed = []
    original = league_matches.parse_any_match_datetime

    def counting(match):
        parsed.append(match.get("local"))
        return original(match)

    monkeypatch.setattr(league_matches, "parse_any_match_datetime", counting)

    kept = league_matches._filter_external_matches_to_jornada_window(matches, quiniela)

    assert [m["local"] for m in kept] == ["Hoy", "Ayer", "En"]
    assert "Mes" not in parsed  # descartado por la cadena de fecha, sin strptime


# ---------------------------------------------------------------------------
# gzip + ETag en /api/liga/data
# ---------------------------------------------------------------------------


def test_la_api_sale_comprimida_y_conserva_el_304(tmp_path, monkeypatch):
    from test_liga_data_slim import _seed_open_jornada, _test_app

    app = _test_app(tmp_path, monkeypatch)
    _seed_open_jornada(app)
    client = app.test_client()

    plain = client.get("/api/liga/data?slim=1")
    packed = client.get("/api/liga/data?slim=1", headers={"Accept-Encoding": "gzip, deflate, br"})

    assert "Content-Encoding" not in plain.headers
    assert packed.headers["Content-Encoding"] == "gzip"
    assert len(packed.data) < len(plain.data) / 3
    unpacked = json.loads(gzip.decompress(packed.data))
    assert unpacked["partidos"] == plain.get_json()["partidos"]
    for response in (plain, packed):
        assert "Accept-Encoding" in response.headers["Vary"]
        assert "Cookie" in response.headers["Vary"]
        assert response.headers["Cache-Control"] == "private, no-cache, must-revalidate"

    # Cada codificacion lleva su validador.
    assert packed.headers["ETag"] != plain.headers["ETag"]
    cached = client.get(
        "/api/liga/data?slim=1", headers={"Accept-Encoding": "gzip", "If-None-Match": packed.headers["ETag"]}
    )
    assert cached.status_code == 304
    assert cached.headers["ETag"] == packed.headers["ETag"]
    assert "Accept-Encoding" in cached.headers["Vary"]
    # El ETag comprimido no valida la representacion sin comprimir.
    assert client.get("/api/liga/data?slim=1", headers={"If-None-Match": packed.headers["ETag"]}).status_code == 200
    # Y el poll sin gzip sigue teniendo su 304 de siempre.
    plain_cached = client.get("/api/liga/data?slim=1", headers={"If-None-Match": plain.headers["ETag"]})
    assert plain_cached.status_code == 304


@pytest.mark.parametrize("quiniela_status", ["FT", "NS"])
def test_el_prefiltro_es_un_superconjunto_exacto_del_filtro_de_ventana(quiniela_status):
    """Panel aleatorio: con y sin prefiltro el Directo conserva exactamente lo mismo."""
    import random

    rng = random.Random(20261122)
    now = madrid_now().replace(tzinfo=None)
    quiniela = [
        {
            "local": "A",
            "visitante": "B",
            "fecha_raw": (now - timedelta(days=1)).strftime("%Y-%m-%d"),
            "hora": "18:30",
            "status": quiniela_status,
        },
        {"local": "C", "visitante": "D", "fecha_raw": now.strftime("%Y-%m-%d"), "hora": "21:00", "status": "NS"},
    ]
    statuses = ["LIVE", "HT", "IN PLAY", "FT", "FINISHED", "NS", "SCHEDULED", "STALE", ""]
    matches = []
    for i in range(3000):
        when = now + timedelta(days=rng.choice([0, 0, -1, -2, 1, 2, -3, -40, 30]), minutes=rng.randint(-600, 600))
        match = {"id": i, "local": f"L{i}", "visitante": f"V{i}", "status": rng.choice(statuses)}
        shape = rng.random()
        if shape < 0.5:
            match.update(fecha_raw=when.strftime("%Y-%m-%d"), hora=when.strftime("%H:%M"))
        elif shape < 0.7:
            match["added"] = when.strftime("%Y-%m-%d %H:%M:%S")
        elif shape < 0.8:
            other = when + timedelta(days=rng.choice([-1, 1, 5]))
            match.update(fecha_raw=when.strftime("%Y-%m-%d"), added=other.strftime("%Y-%m-%d %H:%M"))
        elif shape < 0.9:
            match["date"] = when.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        if rng.random() < 0.5:
            match["score"] = f"{rng.randint(0, 4)}-{rng.randint(0, 4)}"
        if rng.random() < 0.5:
            match["time"] = f"{rng.randint(1, 95)}'"
        if rng.random() < 0.5:
            match["updated_at"] = (now - timedelta(minutes=rng.randint(0, 90))).isoformat()
        matches.append(match)

    full = league_matches._filter_external_matches_to_jornada_window(
        league_matches._close_stale_live_matches([dict(m) for m in matches]), quiniela
    )
    today_str, _, _, window_dates = league_matches._jornada_window(quiniela)
    candidates = [dict(m) for m in matches if league_matches._could_keep_external_match(m, today_str, window_dates)]
    fast = league_matches._filter_external_matches_to_jornada_window(
        league_matches._close_stale_live_matches(candidates), quiniela
    )

    assert [m["id"] for m in fast] == [m["id"] for m in full]
    assert len(candidates) < len(matches)  # y de verdad descarta
