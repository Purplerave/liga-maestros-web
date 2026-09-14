"""Contratos de la primera pintura de ``/api/liga/data`` (``?first=1``).

Lo mínimo para firmar la quiniela en el móvil: partidos, bloqueo,
deadlines y política del boleto. Sin predicciones, ranking, trash talk,
standings ni comentarista: eso llega después con la carga completa.

Cubren:
- ``?first=1`` no construye los payloads pesados.
- La primera pintura trae exactamente lo necesario para firmar.
- La variante valida contra schema sin drift.
"""

from __future__ import annotations

from test_liga_data_slim import _seed_open_jornada, _spy, _test_app

FIRST_KEYS = {
    "first",
    "jornada",
    "max_jornada",
    "today_madrid",
    "is_locked",
    "ticket_guardado",
    "edit_deadline",
    "kickoff_at",
    "partidos",
    "ticket_policy",
}

DROPPED_KEYS = {
    "predicciones_actuales",
    "consenso_pena",
    "consenso_pleno_pena",
    "ranking_maestros",
    "trash_talk",
    "standings",
    "multi_league_standings",
    "comentarista",
    "match_info",
}


def test_first_skips_heavy_builders(monkeypatch, tmp_path):
    app = _test_app(tmp_path, monkeypatch)
    _seed_open_jornada(app)
    client = app.test_client()

    predictions = _spy(monkeypatch, "build_predictions_payload")

    first = client.get("/api/liga/data?first=1")
    assert first.status_code == 200
    assert len(predictions) == 0


def test_first_brings_signing_keys_only(monkeypatch, tmp_path):
    app = _test_app(tmp_path, monkeypatch)
    _seed_open_jornada(app)
    client = app.test_client()

    payload = client.get("/api/liga/data?first=1").get_json()
    assert payload["first"] is True
    assert set(payload) == FIRST_KEYS
    assert len(payload["partidos"]) == 15
    assert payload["ticket_policy"]["max_dobles"] >= 1
    assert not (DROPPED_KEYS & set(payload))
