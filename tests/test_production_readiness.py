import json
import sqlite3

import config
from flask import jsonify
from liga_maestros import create_app
from liga_maestros.db.backups import create_backup, verify_backup
from liga_maestros.db.connection import ClosingConnection
from liga_maestros.db.migrations import (
    ensure_core_tables,
    ensure_porra_table,
    ensure_quiz_tables,
    ensure_snake_table,
    run_startup_migrations,
)
from liga_maestros.db.seed import apply_fixture_corrections
from liga_maestros.routes.legal import delete_user_data


def test_fresh_database_creates_core_schema_and_imports_public_seed(tmp_path, monkeypatch):
    db_path = tmp_path / "production.db"
    seed_path = tmp_path / "seed.json"
    seed_path.write_text(json.dumps({
        "version": 1,
        "tables": {
            "resultados": {
                "columns": ["jornada", "partido_id", "local", "visitante", "status"],
                "rows": [[99, 1, "Local", "Visitante", "SCHEDULED"]],
            },
            "predicciones": {
                "columns": ["user_id", "jornada", "partido_id", "signo"],
                "rows": [["programa", 99, 1, "1"]],
            },
        },
    }), encoding="utf-8")

    monkeypatch.setattr(config, "DB_PATH", str(db_path))
    monkeypatch.setattr(config, "BOOTSTRAP_DB_PATH", str(tmp_path / "missing.db"))
    monkeypatch.setattr(config, "PRODUCTION_SEED_PATH", str(seed_path))
    run_startup_migrations()

    conn = sqlite3.connect(db_path)
    try:
        assert conn.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM comentarios_jornada").fetchone()[0] == 0
        assert conn.execute("SELECT local FROM resultados").fetchone()[0] == "Local"
        assert conn.execute("SELECT user_id FROM predicciones").fetchone()[0] == "programa"
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        conn.close()


def test_repository_seed_contains_no_private_account_tables():
    with open(config.PRODUCTION_SEED_PATH, "r", encoding="utf-8") as fh:
        payload = json.load(fh)
    tables = payload["tables"]
    assert "usuarios" not in tables
    assert "comentarios_jornada" not in tables
    assert "porra_entries" not in tables
    prediction_ids = {str(row[0]) for row in tables["predicciones"]["rows"]}
    assert prediction_ids
    assert not any(user_id.isdigit() for user_id in prediction_ids)


def test_fixture_corrections_update_only_the_expected_placeholder(tmp_path):
    corrections_path = tmp_path / "fixture_corrections.json"
    corrections_path.write_text(json.dumps({"fixtures": [{
        "jornada": 73,
        "partido_id": 15,
        "old_local": "Ganador Semifinal 1",
        "old_visitante": "Ganador Semifinal 2",
        "local": "España",
        "visitante": "Argentina",
    }]}), encoding="utf-8")

    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE resultados (jornada INTEGER, partido_id INTEGER, local TEXT, visitante TEXT)")
    conn.execute("INSERT INTO resultados VALUES (73, 15, 'Ganador Semifinal 1', 'Ganador Semifinal 2')")

    assert apply_fixture_corrections(conn, str(corrections_path)) == 1
    assert conn.execute("SELECT local, visitante FROM resultados").fetchone() == ("España", "Argentina")
    assert apply_fixture_corrections(conn, str(corrections_path)) == 0


def test_fixture_corrections_can_update_public_master_predictions(tmp_path):
    corrections_path = tmp_path / "fixture_corrections.json"
    corrections_path.write_text(json.dumps({"predictions": [{
        "jornada": 73,
        "user_id": "copilot",
        "signos": ["1", "X2", "-"],
    }]}), encoding="utf-8")

    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE resultados (jornada INTEGER, partido_id INTEGER, local TEXT, visitante TEXT)")
    conn.execute("CREATE TABLE predicciones (user_id TEXT, jornada INTEGER, partido_id INTEGER, signo TEXT)")
    conn.execute("CREATE UNIQUE INDEX ux_test_predictions ON predicciones(user_id, jornada, partido_id)")
    conn.execute("INSERT INTO resultados VALUES (73, 1, 'Local', 'Visitante')")
    conn.execute("INSERT INTO predicciones VALUES ('copilot', 73, 1, '2')")

    assert apply_fixture_corrections(conn, str(corrections_path)) == 3
    assert conn.execute(
        "SELECT signo FROM predicciones WHERE user_id = 'copilot' AND jornada = 73 ORDER BY partido_id"
    ).fetchall() == [("1",), ("X2",), ("-",)]
    assert apply_fixture_corrections(conn, str(corrections_path)) == 0


def test_backup_is_created_and_passes_integrity_check(tmp_path, monkeypatch):
    db_path = tmp_path / "source.db"
    backup_dir = tmp_path / "backups"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE sample (value TEXT)")
    conn.execute("INSERT INTO sample VALUES ('ok')")
    conn.commit()
    conn.close()

    monkeypatch.setattr(config, "DB_PATH", str(db_path))
    monkeypatch.setattr(config, "DB_BACKUP_DIR", str(backup_dir))
    monkeypatch.setenv("DB_BACKUP_RETENTION", "3")
    backup = create_backup("test")

    assert verify_backup(backup)
    copy = sqlite3.connect(backup)
    try:
        assert copy.execute("SELECT value FROM sample").fetchone()[0] == "ok"
    finally:
        copy.close()


def test_account_deletion_removes_all_owned_activity():
    conn = sqlite3.connect(":memory:", factory=ClosingConnection)
    ensure_core_tables(conn)
    ensure_porra_table(conn)
    ensure_snake_table(conn)
    ensure_quiz_tables(conn)
    conn.execute("CREATE TABLE api_rate_limit (scope TEXT, identity TEXT, last_seen REAL)")
    conn.execute("INSERT INTO usuarios (id, nombre, email) VALUES ('u1', 'User', 'user@example.test')")
    conn.execute("INSERT INTO predicciones VALUES ('u1', 1, 1, '1')")
    conn.execute("INSERT INTO comentarios_jornada (jornada, user_id, nombre, texto, etiqueta, created_at) VALUES (1, 'u1', 'User', 'Hola', 'Bar', 'now')")
    conn.execute("INSERT INTO porra_entries (jornada, partido_id, user_id, nombre, goles_local, goles_visitante, created_at, updated_at) VALUES (1, 1, 'u1', 'User', 1, 0, 'now', 'now')")
    conn.execute("INSERT INTO snake_scores (user_id, nombre, score, created_at) VALUES ('u1', 'User', 10, 'now')")
    conn.execute("INSERT INTO quiz_participaciones (jornada, user_id, nombre, respuestas, created_at) VALUES (1, 'u1', 'User', '[]', 'now')")
    conn.execute("INSERT INTO api_rate_limit VALUES ('test', 'u1', 0)")
    conn.commit()

    conn.execute("BEGIN IMMEDIATE")
    deleted = delete_user_data(conn, "u1")
    conn.commit()

    assert deleted["usuarios"] == 1
    for table in (
        "usuarios",
        "predicciones",
        "comentarios_jornada",
        "porra_entries",
        "snake_scores",
        "quiz_participaciones",
        "api_rate_limit",
    ):
        assert conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0
    conn.close()


def test_authenticated_writes_require_session_csrf(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "csrf.db"))
    monkeypatch.setattr(config, "BOOTSTRAP_DB_PATH", str(tmp_path / "missing.db"))
    monkeypatch.setattr(config, "PRODUCTION_SEED_PATH", str(tmp_path / "missing-seed.json"))
    monkeypatch.setenv("SECRET_KEY", "csrf-test-secret")
    monkeypatch.setenv("WEB_COLLECTOR_ENABLED", "0")
    monkeypatch.setenv("DB_BACKUP_ENABLED", "0")
    app = create_app()

    @app.post("/_test/write")
    def test_write():
        return jsonify({"status": "ok"})

    client = app.test_client()
    with client.session_transaction() as flask_session:
        flask_session["user"] = {"id": "u1", "name": "User", "email": "user@example.test"}
        flask_session["csrf_token"] = "known-token"

    assert client.post("/_test/write").status_code == 403
    response = client.post("/_test/write", headers={"X-CSRF-Token": "known-token"})
    assert response.status_code == 200


def test_user_status_never_exposes_email(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "status.db"))
    monkeypatch.setattr(config, "BOOTSTRAP_DB_PATH", str(tmp_path / "missing.db"))
    monkeypatch.setattr(config, "PRODUCTION_SEED_PATH", str(tmp_path / "missing-seed.json"))
    monkeypatch.setenv("SECRET_KEY", "status-test-secret")
    monkeypatch.setenv("WEB_COLLECTOR_ENABLED", "0")
    monkeypatch.setenv("DB_BACKUP_ENABLED", "0")
    app = create_app()
    client = app.test_client()

    assert client.get("/api/user/status").get_json() == {"csrf_token": None, "user": None}
    with client.session_transaction() as flask_session:
        flask_session["user"] = {
            "id": "u1",
            "name": "User",
            "email": "private@example.test",
            "is_admin": False,
        }
    payload = client.get("/api/user/status").get_json()
    assert payload["user"] == {"id": "u1", "name": "User", "is_admin": False}
    assert "private@example.test" not in json.dumps(payload)
    assert client.get("/api/user/status").headers["Cache-Control"] == "no-store, private"


def test_user_stats_are_private_to_account_owner(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "stats.db"))
    monkeypatch.setattr(config, "BOOTSTRAP_DB_PATH", str(tmp_path / "missing.db"))
    monkeypatch.setattr(config, "PRODUCTION_SEED_PATH", str(tmp_path / "missing-seed.json"))
    monkeypatch.setenv("SECRET_KEY", "stats-test-secret")
    monkeypatch.setenv("WEB_COLLECTOR_ENABLED", "0")
    monkeypatch.setenv("DB_BACKUP_ENABLED", "0")
    app = create_app()
    client = app.test_client()
    with client.session_transaction() as flask_session:
        flask_session["user"] = {"id": "u1", "name": "User", "is_admin": False}

    assert client.get("/api/user/stats?uid=u2").status_code == 403
