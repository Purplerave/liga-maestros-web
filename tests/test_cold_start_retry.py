"""Contracts for the retryable first load of the live data payload."""

from pathlib import Path

import pytest

import config
from liga_maestros import create_app
from liga_maestros.routes import liga_data
from liga_maestros.workers import web_collector


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


def test_liga_data_sirve_el_snapshot_mientras_arranca_el_collector(monkeypatch, tmp_path):
    """Un arranque lento no puede dejar la portada en «Reintentando (n/4)».

    Antes: cualquier peticion que llegase antes de la primera pasada del
    collector recibia un 503 `cold_start`. En produccion esa pasada (scrape Q15
    + highlightly + agenda) dura mas que los 4 reintentos del navegador, asi
    que la portada se quedaba sin datos. Ahora el lector espera un margen corto
    y sirve el ultimo snapshot persistido.
    """
    app = _test_app(tmp_path, monkeypatch)
    monkeypatch.setattr(web_collector, "collector_startup_pending", lambda: True)
    monkeypatch.setattr(web_collector, "collector_startup_stale", lambda: False)
    esperas = []
    monkeypatch.setattr(
        web_collector, "wait_for_collector_startup", lambda timeout=None: esperas.append(timeout) or True
    )

    response = app.test_client().get("/api/liga/data?first=1")

    assert response.status_code == 200
    assert esperas, "la primera pintura debe esperar al arranque, no rendirse"


def test_liga_data_espera_y_luego_sirve_si_la_pasada_no_termina(monkeypatch, tmp_path):
    app = _test_app(tmp_path, monkeypatch)
    monkeypatch.setattr(web_collector, "collector_startup_pending", lambda: True)
    monkeypatch.setattr(web_collector, "collector_startup_stale", lambda: False)
    monkeypatch.setattr(web_collector, "wait_for_collector_startup", lambda timeout=None: False)

    response = app.test_client().get("/api/liga/data?slim=1")

    assert response.status_code == 200
    assert response.get_json()["slim"] is True


def test_liga_data_no_hace_esperar_al_poll_automatico(monkeypatch, tmp_path):
    app = _test_app(tmp_path, monkeypatch)
    monkeypatch.setattr(web_collector, "collector_startup_pending", lambda: True)
    monkeypatch.setattr(web_collector, "collector_startup_stale", lambda: False)
    monkeypatch.setattr(
        web_collector,
        "wait_for_collector_startup",
        lambda timeout=None: pytest.fail("el poll automatico no debe bloquearse"),
    )

    response = app.test_client().get("/api/liga/data?auto=1&slim=1")

    assert response.status_code == 503
    assert response.headers["Retry-After"] == "1"
    assert response.get_json()["code"] == "COLD_START"


def test_liga_data_no_hace_esperar_al_reintento_del_navegador(monkeypatch, tmp_path):
    app = _test_app(tmp_path, monkeypatch)
    monkeypatch.setattr(web_collector, "collector_startup_pending", lambda: True)
    monkeypatch.setattr(web_collector, "collector_startup_stale", lambda: False)
    monkeypatch.setattr(
        web_collector, "wait_for_collector_startup", lambda timeout=None: pytest.fail("el reintento no espera")
    )

    response = app.test_client().get("/api/liga/data", headers={"X-Liga-Retry": "1"})

    assert response.status_code == 503


def test_liga_data_sirve_si_la_primera_pasada_esta_atascada(monkeypatch, tmp_path):
    """Pasado el margen se sirve el snapshot, no un 503 eterno."""
    app = _test_app(tmp_path, monkeypatch)
    monkeypatch.setattr(web_collector, "collector_startup_pending", lambda: True)
    monkeypatch.setattr(web_collector, "collector_startup_stale", lambda: True)
    monkeypatch.setattr(
        web_collector,
        "wait_for_collector_startup",
        lambda timeout=None: pytest.fail("no hay que esperar a una pasada atascada"),
    )

    response = app.test_client().get("/api/liga/data?first=1")

    assert response.status_code == 200


def test_pwa_foreground_resume_revalidates_data_and_checks_worker_updates():
    root = Path(__file__).resolve().parents[1]
    source = (root / "static/js/events.js").read_text(encoding="utf-8")

    assert 'window.addEventListener("pageshow"' in source
    assert 'window.addEventListener("online", () => refreshAfterPwaResume())' in source
    assert "if (event.persisted) refreshAfterPwaResume()" in source
    assert 'document.addEventListener("visibilitychange", handlePwaVisibilityChange)' in source
    assert "refreshData({ auto: true })" in source
    assert "registration?.update()" in source
    assert "PWA_RESUME_REFRESH_DEDUPE_MS" in source
    assert "pwaResumeRefreshPending = true" in source
    assert "if (state.data) refreshAfterPwaResume()" in source


def test_frontend_retries_cold_start_and_honours_retry_after():
    source = (Path(__file__).resolve().parents[1] / "static/js/quantum_final.js").read_text(encoding="utf-8")

    assert "fetchLigaDataWithRetry" in source
    assert "response.status !== 503" in source
    assert 'payload?.status === "cold_start"' in source
    assert 'response.headers.get("Retry-After")' in source
    assert "maxAttempts = 3" in source
    assert "fetchLigaDataWithRetry(" in source
    assert "/api/liga/data?j=" in source
    # La carga tiene tope de espera propio y el reintento se marca como
    # automatico para que el backend no lo retenga tras el arranque.
    assert "fetchWithTimeout" in source
    assert '"X-Liga-Retry": "1"' in source
