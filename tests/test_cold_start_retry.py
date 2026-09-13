"""Contracts for the retryable first load of the live data payload."""

from pathlib import Path

import config
from liga_maestros import create_app
from liga_maestros.routes import liga_data


def _test_app(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "cold-start.db"))
    monkeypatch.setattr(config, "BOOTSTRAP_DB_PATH", str(tmp_path / "missing.db"))
    monkeypatch.setattr(config, "PRODUCTION_SEED_PATH", str(tmp_path / "missing-seed.json"))
    monkeypatch.setenv("SECRET_KEY", "cold-start-test-secret")
    monkeypatch.setenv("WEB_COLLECTOR_ENABLED", "0")
    monkeypatch.setenv("DB_BACKUP_ENABLED", "0")
    return create_app()


def test_liga_data_returns_retryable_cold_start(monkeypatch, tmp_path):
    app = _test_app(tmp_path, monkeypatch)
    monkeypatch.setattr(liga_data, "_resolve_max_jornada", lambda conn: None)

    response = app.test_client().get("/api/liga/data")

    assert response.status_code == 503
    assert response.headers["Retry-After"] == "2"
    assert response.headers["Cache-Control"] == "no-store"
    assert response.get_json() == {
        "status": "cold_start",
        "code": "COLD_START",
        "message": "Los datos de la jornada aún se están preparando.",
    }


def test_frontend_retries_cold_start_and_honours_retry_after():
    source = (Path(__file__).resolve().parents[1] / "static/js/quantum_final.js").read_text(encoding="utf-8")

    assert "fetchLigaDataWithRetry" in source
    assert "response.status !== 503" in source
    assert 'payload?.status === "cold_start"' in source
    assert 'response.headers.get("Retry-After")' in source
    assert "maxAttempts = 3" in source
    assert "fetchLigaDataWithRetry(`/api/liga/data" in source
