"""Tests for the admin-only 'refresh everything now' endpoint."""

from pathlib import Path

import config
from liga_maestros import create_app


def _test_app(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "refresh.db"))
    monkeypatch.setattr(config, "BOOTSTRAP_DB_PATH", str(tmp_path / "missing.db"))
    monkeypatch.setattr(config, "PRODUCTION_SEED_PATH", str(tmp_path / "missing-seed.json"))
    monkeypatch.setattr(config, "DB_BACKUP_DIR", str(tmp_path / "backups"))
    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SECRET_KEY", "refresh-all-test-secret")
    monkeypatch.setenv("WEB_COLLECTOR_ENABLED", "0")
    monkeypatch.setenv("DB_BACKUP_ENABLED", "0")
    monkeypatch.setenv("ALLOW_LOCAL_ADMIN", "0")
    monkeypatch.setenv("TRUSTED_HOSTS", "localhost,127.0.0.1")
    return create_app()


def _patch_refreshers(monkeypatch, calls):
    from liga_maestros.services import daily_matches, highlightly, multi_standings

    monkeypatch.setattr(
        multi_standings,
        "refresh_all_standings",
        lambda season: calls.append("standings") or {"spanish": ["primera"], "external": ["PREMIER LEAGUE"]},
    )
    monkeypatch.setattr(
        daily_matches,
        "refresh_daily_agenda",
        lambda force=False: calls.append("agenda") or {"date": "2026-08-15", "matches": [{"id": 1}, {"id": 2}]},
    )
    monkeypatch.setattr(daily_matches, "refresh_live_scores", lambda: calls.append("scores") or 2)
    monkeypatch.setattr(
        highlightly,
        "trigger_highlightly_refresh_async",
        lambda force=False, jornada=None: calls.append("quiniela") or True,
    )


def test_refresh_all_requires_admin(tmp_path, monkeypatch):
    app = _test_app(tmp_path, monkeypatch)
    client = app.test_client()

    # Anonymous: forbidden.
    assert client.post("/api/admin/refresh-all").status_code == 403

    # Regular signed-in user: forbidden too.
    with client.session_transaction() as flask_session:
        flask_session["user"] = {"id": "1", "name": "User", "is_admin": False}
        flask_session["csrf_token"] = "tok"
    response = client.post("/api/admin/refresh-all", headers={"X-CSRF-Token": "tok"})
    assert response.status_code == 403


def test_refresh_all_runs_every_refresher_for_admin(tmp_path, monkeypatch):
    app = _test_app(tmp_path, monkeypatch)
    calls = []
    _patch_refreshers(monkeypatch, calls)

    client = app.test_client()
    with client.session_transaction() as flask_session:
        flask_session["user"] = {"id": "1", "name": "Admin", "is_admin": True}
        flask_session["csrf_token"] = "tok"

    response = client.post("/api/admin/refresh-all", headers={"X-CSRF-Token": "tok"})

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "ok"
    assert calls == ["standings", "agenda", "scores", "quiniela"]
    summary = payload["summary"]
    assert summary["standings"]["spanish"] == ["primera"]
    assert summary["agenda_matches"] == 2
    assert summary["panel_matches"] == 2
    assert summary["quiniela_refresh_started"] is True


def test_refresh_all_survives_partial_failures(tmp_path, monkeypatch):
    """One refresher blowing up must not abort the rest."""
    app = _test_app(tmp_path, monkeypatch)
    calls = []
    _patch_refreshers(monkeypatch, calls)

    from liga_maestros.services import multi_standings

    def boom(season):
        raise RuntimeError("api down")

    monkeypatch.setattr(multi_standings, "refresh_all_standings", boom)

    client = app.test_client()
    with client.session_transaction() as flask_session:
        flask_session["user"] = {"id": "1", "name": "Admin", "is_admin": True}
        flask_session["csrf_token"] = "tok"

    response = client.post("/api/admin/refresh-all", headers={"X-CSRF-Token": "tok"})

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "partial"
    assert payload["summary"]["standings"] == "error"
    assert payload["failures"] == [{"component": "standings", "reason": "falló la actualización de clasificaciones"}]
    assert "Actualización parcial" in payload["message"]
    # The remaining refreshers still ran.
    assert "agenda" in calls
    assert "scores" in calls
    assert "quiniela" in calls


def test_refresh_all_exposes_skipped_leagues_as_partial(tmp_path, monkeypatch):
    app = _test_app(tmp_path, monkeypatch)
    calls = []
    _patch_refreshers(monkeypatch, calls)

    from liga_maestros.services import multi_standings

    monkeypatch.setattr(
        multi_standings,
        "refresh_all_standings",
        lambda season: {
            "status": "partial",
            "spanish": ["primera"],
            "external": ["PREMIER LEAGUE"],
            "skipped": [
                {
                    "league": "SEGUNDA DIVISION",
                    "code": "roster_mismatch",
                    "reason": "la plantilla normalizada no coincide con la oficial 2026-27",
                }
            ],
            "failures": [],
            "updated_count": 2,
            "expected_count": 5,
        },
    )

    client = app.test_client()
    with client.session_transaction() as flask_session:
        flask_session["user"] = {"id": "1", "name": "Admin", "is_admin": True}
        flask_session["csrf_token"] = "tok"

    response = client.post("/api/admin/refresh-all", headers={"X-CSRF-Token": "tok"})

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "partial"
    assert payload["skipped"][0]["component"] == "standings"
    assert payload["skipped"][0]["league"] == "SEGUNDA DIVISION"
    assert "Omitidos: SEGUNDA DIVISION" in payload["message"]


def test_refresh_all_toast_warns_on_partial_results():
    source = (Path(__file__).resolve().parents[1] / "static" / "js" / "quantum_final.js").read_text(encoding="utf-8")

    assert 'payload.status !== "ok"' in source
    assert "payload.skipped" in source
    assert "payload.failures" in source
    assert 'showToast(`${payload.message || "Actualización parcial."}${completed}`, "error")' in source


def test_liga_data_exposes_is_admin_flag(tmp_path, monkeypatch):
    app = _test_app(tmp_path, monkeypatch)
    client = app.test_client()

    anonymous_response = client.get("/api/liga/data")
    assert anonymous_response.status_code == 200
    assert anonymous_response.get_json()["is_admin"] is False

    with client.session_transaction() as flask_session:
        flask_session["user"] = {
            "id": "1",
            "name": "Admin",
            "is_admin": True,
        }

    admin_response = client.get("/api/liga/data")
    assert admin_response.status_code == 200
    assert admin_response.get_json()["is_admin"] is True
