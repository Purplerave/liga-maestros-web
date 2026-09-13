"""Contratos de la variante ligera de ``/api/liga/data`` (``?slim=1``).

El poll del directo (``static/js/events.js``) pregunta cada 30 s por cliente.
Con la carga completa eso obliga a reconstruir en cada poll las predicciones,
el consenso de la Peña, el ranking de maestros y el trash talk: trabajo que no
cambia en una ventana de 30 s.

Cubren:
- ``?slim=1`` deja de construir los payloads de predicciones.
- La variante ligera conserva exactamente los mismos datos volátiles.
- La variante ligera no inventa ni pierde campos del contrato.
- El ETag permite responder 304 (cero bytes) cuando no hay novedades.
- El arranque en frío (503) se respeta también con ``?slim=1``.
- El frontend pide la variante ligera y sabe qué hacer con un 304.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import config
from liga_maestros import create_app
from liga_maestros.db.connection import get_db
from liga_maestros.routes import liga_data
from liga_maestros.services.ticket import madrid_now

JORNADA = 1

# Claves que solo existen en la carga completa: dependen del histórico de
# predicciones y no cambian en una ventana de 30 s.
HEAVY_KEYS = {
    "jornadas_disponibles",
    "participant_contract",
    "match_info",
    "predicciones_actuales",
    "consenso_pena",
    "consenso_pleno_pena",
    "ranking_maestros",
    "trash_talk",
    "auth_enabled",
    "live_stream_enabled",
    "is_admin",
    "ticket_policy",
}

# Claves que el poll necesita para decidir si repinta.
VOLATILE_KEYS = {
    "jornada",
    "jornada_liga",
    "max_jornada",
    "today_madrid",
    "is_locked",
    "ticket_guardado",
    "edit_deadline",
    "kickoff_at",
    "partidos",
    "all_league_matches",
    "live_matches",
    "standings",
    "multi_league_standings",
    "comentarista",
}


def _test_app(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "slim.db"))
    monkeypatch.setattr(config, "BOOTSTRAP_DB_PATH", str(tmp_path / "missing.db"))
    monkeypatch.setattr(config, "PRODUCTION_SEED_PATH", str(tmp_path / "missing-seed.json"))
    monkeypatch.setattr(config, "DB_BACKUP_DIR", str(tmp_path / "backups"))
    monkeypatch.setenv("SECRET_KEY", "slim-test-secret")
    monkeypatch.setenv("WEB_COLLECTOR_ENABLED", "0")
    monkeypatch.setenv("DB_BACKUP_ENABLED", "0")
    monkeypatch.setenv("ALLOW_LOCAL_ADMIN", "0")
    monkeypatch.setenv("TRUSTED_HOSTS", "localhost,127.0.0.1")
    return create_app()


def _seed_open_jornada(app, *, matches=15):
    """15 partidos sin empezar: la jornada mínima que el endpoint acepta."""
    kickoff = madrid_now() + timedelta(hours=6)
    fecha = kickoff.strftime("%Y-%m-%d")
    hora = kickoff.strftime("%H:%M")
    with app.app_context():
        conn = get_db()
        conn.execute("DELETE FROM resultados WHERE jornada = ?", (JORNADA,))
        for partido_id in range(1, matches + 1):
            conn.execute(
                """
                INSERT INTO resultados (jornada, partido_id, local, visitante, status, fecha, hora)
                VALUES (?, ?, ?, ?, 'NS', ?, ?)
                """,
                (JORNADA, partido_id, f"Local {partido_id}", f"Visitante {partido_id}", fecha, hora),
            )
        conn.commit()


def _spy(monkeypatch, name):
    """Sustituye un builder del módulo por un espía que cuenta llamadas."""
    original = getattr(liga_data, name)
    calls = []

    def wrapper(*args, **kwargs):
        calls.append((args, kwargs))
        return original(*args, **kwargs)

    monkeypatch.setattr(liga_data, name, wrapper)
    return calls


def test_slim_skips_prediction_builders(monkeypatch, tmp_path):
    app = _test_app(tmp_path, monkeypatch)
    _seed_open_jornada(app)
    client = app.test_client()

    predictions = _spy(monkeypatch, "build_predictions_payload")
    trash_talk = _spy(monkeypatch, "build_trash_talk")
    match_info = _spy(monkeypatch, "load_match_info_for_jornada")

    full = client.get("/api/liga/data")
    assert full.status_code == 200
    assert len(predictions) == 1
    assert len(trash_talk) == 1
    assert len(match_info) == 1

    slim = client.get("/api/liga/data?slim=1")
    assert slim.status_code == 200
    # Ni una sola llamada más: el poll no ha reconstruido nada de esto.
    assert len(predictions) == 1
    assert len(trash_talk) == 1
    assert len(match_info) == 1


def test_slim_keeps_volatile_keys_and_drops_heavy_ones(monkeypatch, tmp_path):
    app = _test_app(tmp_path, monkeypatch)
    _seed_open_jornada(app)
    client = app.test_client()

    full_payload = client.get("/api/liga/data").get_json()
    slim_payload = client.get("/api/liga/data?slim=1").get_json()

    assert slim_payload["slim"] is True
    assert "slim" not in full_payload
    assert VOLATILE_KEYS <= set(slim_payload)
    assert not HEAVY_KEYS & set(slim_payload)
    # La carga completa sigue sirviendo su contrato al completo.
    assert VOLATILE_KEYS <= set(full_payload)
    assert HEAVY_KEYS <= set(full_payload)


def test_slim_volatile_data_is_identical_to_full(monkeypatch, tmp_path):
    app = _test_app(tmp_path, monkeypatch)
    _seed_open_jornada(app)
    client = app.test_client()

    full = client.get("/api/liga/data")
    slim = client.get("/api/liga/data?slim=1")
    full_payload = full.get_json()
    slim_payload = slim.get_json()

    for key in sorted(VOLATILE_KEYS - {"comentarista"}):
        assert slim_payload[key] == full_payload[key], key
    assert len(slim.get_data()) < len(full.get_data())


def test_slim_flag_variants(monkeypatch, tmp_path):
    app = _test_app(tmp_path, monkeypatch)
    _seed_open_jornada(app)
    client = app.test_client()

    for value in ("1", "true", "TRUE", "yes", "on"):
        assert client.get(f"/api/liga/data?slim={value}").get_json().get("slim") is True, value
    for value in ("", "0", "false", "no", "off", "slim"):
        assert "slim" not in client.get(f"/api/liga/data?slim={value}").get_json(), value


def test_slim_etag_enables_304(monkeypatch, tmp_path):
    app = _test_app(tmp_path, monkeypatch)
    _seed_open_jornada(app)
    client = app.test_client()

    full = client.get("/api/liga/data")
    slim = client.get("/api/liga/data?slim=1")
    assert full.headers["ETag"] != slim.headers["ETag"]

    etag = slim.headers["ETag"]
    not_modified = client.get("/api/liga/data?slim=1", headers={"If-None-Match": etag})
    assert not_modified.status_code == 304
    # Ni un byte de payload: el poll sin novedades no cuesta transferencia.
    assert not_modified.get_data() == b""
    assert not_modified.headers["ETag"] == etag


def test_slim_keeps_cold_start_semantics(monkeypatch, tmp_path):
    app = _test_app(tmp_path, monkeypatch)
    _seed_open_jornada(app)
    client = app.test_client()
    predictions = _spy(monkeypatch, "build_predictions_payload")
    monkeypatch.setattr(liga_data, "build_jornada_matches", lambda conn, jornada, logos: [{"id": 1}] * 3)

    cold = client.get("/api/liga/data?slim=1")

    assert cold.status_code == 503
    assert cold.headers["Retry-After"] == "2"
    assert cold.headers["Cache-Control"] == "no-store"
    assert cold.get_json()["code"] == "COLD_START"
    assert len(predictions) == 0


def test_frontend_poll_requests_slim_and_handles_304():
    source = (Path(__file__).resolve().parents[1] / "static/js/events.js").read_text(encoding="utf-8")

    start = source.index("async function refreshLiveSnapshot()")
    poll = source[start:]

    assert "slim=1" in poll
    assert 'headers["If-None-Match"] = liveSnapshotEtag' in poll
    # Un 304 no es un error: se comprueba antes de mirar `response.ok`,
    # que es false para cualquier estado fuera de 2xx.
    assert poll.index("response.status === 304") < poll.index("if (!response.ok) return false;")
    # El payload ligero se mezcla sobre el completo: nunca lo sustituye.
    assert "state.data = { ...state.data, ...volatil }" in poll
    # Sin ?slim=1 (backend antiguo) el código anterior sigue funcionando igual.
    assert "state.data = freshData;" in poll


def test_slim_schema_rejects_drift_without_breaking_the_response():
    from liga_maestros.schemas import validate_liga_data_slim

    payload, error = validate_liga_data_slim({"jornada": 3, "partidos": []})
    assert error is None
    assert payload["slim"] is True
    assert payload["jornada"] == 3

    broken, error = validate_liga_data_slim({"partidos": []})
    assert error is not None
    # Ante drift se devuelve el payload original: el frontend sigue funcionando.
    assert broken == {"partidos": []}
