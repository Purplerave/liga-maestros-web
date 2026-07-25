import pytest

import config
from liga_maestros import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "comments.db"))
    monkeypatch.setattr(config, "BOOTSTRAP_DB_PATH", str(tmp_path / "missing.db"))
    monkeypatch.setattr(config, "PRODUCTION_SEED_PATH", str(tmp_path / "missing-seed.json"))
    monkeypatch.setattr(config, "DB_BACKUP_DIR", str(tmp_path / "backups"))
    monkeypatch.setenv("SECRET_KEY", "comments-test-secret")
    monkeypatch.setenv("WEB_COLLECTOR_ENABLED", "0")
    monkeypatch.setenv("DB_BACKUP_ENABLED", "0")
    return create_app().test_client()


def _login(client):
    with client.session_transaction() as session:
        session["user"] = {"id": "comment-user", "name": "Pablo"}
        session["csrf_token"] = "comment-token"


def test_comments_require_valid_jornada(client):
    response = client.get("/api/comentarios?j=no")
    assert response.status_code == 400


def test_authenticated_user_can_post_and_read_comment(client):
    _login(client)
    response = client.post(
        "/api/comentarios",
        json={"jornada": 72, "texto": "Partido muy igualado"},
        headers={"X-CSRF-Token": "comment-token"},
    )
    assert response.status_code == 200
    assert response.get_json()["comment"]["texto"] == "Partido muy igualado"

    listing = client.get("/api/comentarios?j=72")
    assert listing.status_code == 200
    assert listing.get_json()["comments"][-1]["nombre"] == "Pablo"


def test_comment_post_rejects_anonymous_user(client):
    response = client.post("/api/comentarios", json={"jornada": 72, "texto": "Hola"})
    assert response.status_code == 401
