import json

import config
from liga_maestros import create_app
from liga_maestros.db.backups import minimize_backup_personal_data
from liga_maestros.db.connection import get_db
from liga_maestros.services.payloads.predictions import _filter_public_predictions
from liga_maestros.services.privacy import (
    PUBLIC_USER_PREFIX,
    public_participant_id,
    publicize_identifiers,
    resolve_public_participant_id,
)

PRIVATE_ID = "116612345678901234567"
OTHER_PRIVATE_ID = "111223456789012345678"


def _test_app(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "security.db"))
    monkeypatch.setattr(config, "BOOTSTRAP_DB_PATH", str(tmp_path / "missing.db"))
    monkeypatch.setattr(config, "PRODUCTION_SEED_PATH", str(tmp_path / "missing-seed.json"))
    monkeypatch.setattr(config, "DB_BACKUP_DIR", str(tmp_path / "backups"))
    monkeypatch.setenv("SECRET_KEY", "security-test-secret")
    monkeypatch.setenv("WEB_COLLECTOR_ENABLED", "0")
    monkeypatch.setenv("DB_BACKUP_ENABLED", "0")
    monkeypatch.setenv("ALLOW_LOCAL_ADMIN", "0")
    monkeypatch.setenv("TRUSTED_HOSTS", "localhost,127.0.0.1,ligademaestros.alwaysdata.net")
    return create_app()


def _insert_scored_prediction(conn, user_id, jornada=73, partido_id=1):
    conn.execute(
        """
        INSERT INTO resultados
            (jornada, partido_id, local, visitante, goles_local, goles_visitante,
             status, fecha, hora, minuto, signo_actual)
        VALUES (?, ?, 'Local', 'Visitante', 1, 0, 'FT', '2026-07-01', '18:00', 'FT', '1')
        """,
        (jornada, partido_id),
    )
    conn.execute(
        "INSERT INTO predicciones (user_id, jornada, partido_id, signo) VALUES (?, ?, ?, ?)",
        (user_id, jornada, partido_id, "1"),
    )


def test_provider_ids_are_stable_and_opaque(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "privacy-test-secret")
    public_id = public_participant_id(PRIVATE_ID)
    assert public_id.startswith(PUBLIC_USER_PREFIX)
    assert PRIVATE_ID not in public_id
    assert public_id == public_participant_id(PRIVATE_ID)
    assert public_participant_id(PRIVATE_ID, PRIVATE_ID) == PRIVATE_ID


def test_public_id_resolver_rejects_raw_provider_ids(tmp_path, monkeypatch):
    app = _test_app(tmp_path, monkeypatch)
    with app.app_context():
        conn = get_db()
        conn.execute(
            "INSERT INTO usuarios (id, nombre, email) VALUES (?, ?, ?)", (PRIVATE_ID, "Pablo", "private@example.test")
        )
        conn.commit()
        token = public_participant_id(PRIVATE_ID)
        assert resolve_public_participant_id(conn, PRIVATE_ID) is None
        assert resolve_public_participant_id(conn, token) == PRIVATE_ID
        conn.close()


def test_public_payload_hides_other_provider_ids(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "privacy-test-secret")
    payload = {
        "rows": [{"id": PRIVATE_ID, "name": "Pablo"}],
        "ranking": {OTHER_PRIVATE_ID: {"total": 10}},
    }
    public = publicize_identifiers(payload)
    serialized = json.dumps(public)
    assert PRIVATE_ID not in serialized
    assert OTHER_PRIVATE_ID not in serialized


def test_prediction_payload_preserves_owner_but_hides_other_accounts(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "privacy-test-secret")
    preds = {
        PRIVATE_ID: {"signos": ["1"] * 15},
        OTHER_PRIVATE_ID: {"signos": ["2"] * 15},
        "programa": {"signos": ["X"] * 15},
    }
    contract = {"visible_ai_columns": [{"id": "programa"}], "hidden_ids": [], "pena_ids": []}
    public = _filter_public_predictions(preds, contract, PRIVATE_ID, reveal_all=True)
    assert PRIVATE_ID in public
    assert OTHER_PRIVATE_ID not in public
    assert public_participant_id(OTHER_PRIVATE_ID) in public
    assert "programa" in public


def test_security_headers_host_validation_and_request_limits(tmp_path, monkeypatch):
    app = _test_app(tmp_path, monkeypatch)

    @app.post("/_security/echo")
    def echo_body():
        from flask import request

        return {"size": len(request.get_data())}

    client = app.test_client()
    response = client.get("/")
    assert response.status_code == 200
    csp = response.headers["Content-Security-Policy"]
    assert "script-src 'self'" in csp
    assert "object-src 'none'" in csp
    assert "frame-ancestors 'none'" in csp
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert client.get("/", headers={"Host": "attacker.invalid"}).status_code == 400
    assert client.post("/_security/echo", data=b"x" * (65 * 1024)).status_code == 413


def test_csp_never_allows_inline_scripts(tmp_path, monkeypatch):
    """Regression guard: script-src must never include 'unsafe-inline'.

    Inline scripts defeat the whole point of the CSP against XSS. All JS must
    live in external files under static/js/ or juegos/.
    """
    app = _test_app(tmp_path, monkeypatch)
    client = app.test_client()
    for path in ("/", "/juegos/arkanoid.html"):
        response = client.get(path)
        csp = response.headers.get("Content-Security-Policy", "")
        script_src = next(
            (directive.strip() for directive in csp.split(";") if directive.strip().startswith("script-src")),
            "",
        )
        assert script_src, f"Missing script-src directive for {path}"
        assert "'unsafe-inline'" not in script_src, f"script-src allows inline scripts on {path}: {script_src}"


def test_shipped_html_has_no_inline_scripts():
    """No template or game page may embed executable inline <script> blocks."""
    import re
    from pathlib import Path

    root = Path(config.BASE_DIR)
    offenders = []
    for html_path in list(root.glob("templates/**/*.html")) + list(root.glob("juegos/**/*.html")):
        content = html_path.read_text(encoding="utf-8", errors="replace")
        for match in re.finditer(r"<script\b([^>]*)>", content, flags=re.I):
            attrs = match.group(1)
            if "src=" in attrs:
                continue
            # JSON-LD and other data blocks are not executable.
            if re.search(r"type\s*=\s*[\"'](application/(ld\+json|json))[\"']", attrs, flags=re.I):
                continue
            offenders.append(str(html_path.relative_to(root)))
            break
    assert not offenders, f"Inline executable <script> found in: {offenders}"


def test_authenticated_api_responses_are_not_cached(tmp_path, monkeypatch):
    app = _test_app(tmp_path, monkeypatch)
    client = app.test_client()
    with client.session_transaction() as flask_session:
        flask_session["user"] = {"id": PRIVATE_ID, "name": "Pablo", "is_admin": False}
    response = client.get("/api/user/status")
    assert response.headers["Cache-Control"] == "no-store, private"


def test_public_health_does_not_disclose_api_budget_or_circuit(tmp_path, monkeypatch):
    app = _test_app(tmp_path, monkeypatch)
    payload = app.test_client().get("/api/live/health").get_json()
    assert payload["status"] == "ok"
    assert "api_usage" not in payload
    assert "highlightly_circuit" not in payload
    assert "collector" not in payload


def test_public_contest_endpoint_never_exposes_provider_ids(tmp_path, monkeypatch):
    app = _test_app(tmp_path, monkeypatch)
    with app.app_context():
        conn = get_db()
        conn.execute(
            "INSERT INTO usuarios (id, nombre, email) VALUES (?, ?, ?)",
            (PRIVATE_ID, "Pablo", None),
        )
        # Jornada de la temporada publicada: las de pruebas (51-76) ya no
        # alimentan el concurso.
        _insert_scored_prediction(conn, PRIVATE_ID, jornada=1)
        conn.commit()
        conn.close()

    response = app.test_client().get("/api/concurso?j=1")
    assert response.status_code == 200
    assert PRIVATE_ID not in response.get_data(as_text=True)
    assert PUBLIC_USER_PREFIX in response.get_data(as_text=True)


def test_public_liga_payload_never_exposes_provider_ids(tmp_path, monkeypatch):
    app = _test_app(tmp_path, monkeypatch)
    with app.app_context():
        conn = get_db()
        conn.execute(
            "INSERT INTO usuarios (id, nombre, email) VALUES (?, ?, ?)",
            (PRIVATE_ID, "Pablo", None),
        )
        _insert_scored_prediction(conn, PRIVATE_ID)
        conn.commit()
        conn.close()

    response = app.test_client().get("/api/liga/data?j=73")
    assert response.status_code == 200
    assert PRIVATE_ID not in response.get_data(as_text=True)
    payload = response.get_json()
    assert "team_contract" not in payload
    assert "team_logos" not in payload


def test_raw_provider_profile_url_is_rejected_but_opaque_url_works(tmp_path, monkeypatch):
    app = _test_app(tmp_path, monkeypatch)
    with app.app_context():
        conn = get_db()
        conn.execute(
            "INSERT INTO usuarios (id, nombre, email) VALUES (?, ?, ?)",
            (PRIVATE_ID, "Pablo", None),
        )
        conn.commit()
        conn.close()

    client = app.test_client()
    assert client.get(f"/api/concurso/perfil/{PRIVATE_ID}").status_code == 404
    opaque_id = public_participant_id(PRIVATE_ID)
    response = client.get(f"/api/concurso/perfil/{opaque_id}")
    assert response.status_code == 200
    assert PRIVATE_ID not in response.get_data(as_text=True)


def test_authenticated_writes_require_session_csrf_token(tmp_path, monkeypatch):
    app = _test_app(tmp_path, monkeypatch)
    client = app.test_client()
    with client.session_transaction() as flask_session:
        flask_session["user"] = {"id": PRIVATE_ID, "name": "Pablo", "is_admin": False}

    payload = {"user_id": PRIVATE_ID, "jornada": 73, "signos": ["1"] * 15}
    rejected = client.post("/api/predicciones/save", json=payload)
    assert rejected.status_code == 403

    status = client.get("/api/user/status").get_json()
    accepted = client.post(
        "/api/predicciones/save",
        json=payload,
        headers={"X-CSRF-Token": status["csrf_token"]},
    )
    assert accepted.status_code != 403


def test_runtime_and_repository_files_are_not_publicly_served(tmp_path, monkeypatch):
    app = _test_app(tmp_path, monkeypatch)
    client = app.test_client()
    sensitive_paths = (
        "/.env",
        "/.git/config",
        "/requirements.txt",
        "/config.py",
        "/DATOS/LIGA_MAESTROS_PRO.db",
        "/data/backups/",
        "/server_stderr.log",
        "/static/%2e%2e/.env",
        "/juegos/%2e%2e/.env",
        "/static/%2e%2e%2fDATOS%2fLIGA_MAESTROS_PRO.db",
    )

    for path in sensitive_paths:
        response = client.get(path)
        assert response.status_code == 404, path


def test_startup_removes_stored_emails(tmp_path, monkeypatch):
    app = _test_app(tmp_path, monkeypatch)
    with app.app_context():
        conn = get_db()
        conn.execute(
            "INSERT INTO usuarios (id, nombre, email) VALUES (?, ?, ?)", (PRIVATE_ID, "Pablo", "private@example.test")
        )
        conn.commit()
        from liga_maestros.db.migrations import minimize_stored_personal_data

        minimize_stored_personal_data(conn)
        assert conn.execute("SELECT email FROM usuarios WHERE id = ?", (PRIVATE_ID,)).fetchone()[0] is None
        conn.close()


def test_retained_backups_are_scrubbed_of_emails(tmp_path, monkeypatch):
    import sqlite3

    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    backup = backup_dir / "liga_maestros_20260717T120000Z_test.db"
    conn = sqlite3.connect(backup)
    conn.execute("CREATE TABLE usuarios (id TEXT PRIMARY KEY, email TEXT)")
    conn.execute("INSERT INTO usuarios VALUES (?, ?)", (PRIVATE_ID, "private@example.test"))
    conn.commit()
    conn.close()
    monkeypatch.setattr(config, "DB_BACKUP_DIR", str(backup_dir))

    assert minimize_backup_personal_data() == 1
    conn = sqlite3.connect(backup)
    assert conn.execute("SELECT email FROM usuarios").fetchone()[0] is None
    conn.close()


def test_admin_endpoints_fail_closed_and_ignore_query_secrets(tmp_path, monkeypatch):
    monkeypatch.delenv("ADMIN_API_SECRET", raising=False)
    monkeypatch.setenv("ADMIN_SECRET", "legacy-secret-must-not-authorize")
    app = _test_app(tmp_path, monkeypatch)
    client = app.test_client()

    requests = (
        ("post", "/api/admin/reset-standings?secret=legacy-secret-must-not-authorize"),
        ("post", "/api/admin/reset-j75?secret=legacy-secret-must-not-authorize"),
        ("post", "/api/admin/setup-j76?secret=legacy-secret-must-not-authorize"),
        ("post", "/api/admin/sync-scrape?secret=legacy-secret-must-not-authorize"),
        ("get", "/api/admin/debug-files?secret=legacy-secret-must-not-authorize"),
    )
    for method, path in requests:
        response = getattr(client, method)(path, headers={"X-Admin-Secret": "legacy-secret-must-not-authorize"})
        assert response.status_code == 403, path
        assert response.headers["Cache-Control"] == "no-store, private"


def test_admin_session_writes_still_require_csrf(tmp_path, monkeypatch):
    app = _test_app(tmp_path, monkeypatch)
    client = app.test_client()
    with client.session_transaction() as flask_session:
        flask_session["user"] = {"id": PRIVATE_ID, "name": "Admin", "is_admin": True}

    response = client.post("/api/admin/sync-scrape")
    assert response.status_code == 403
    assert response.get_json()["error"] == "Solicitud de seguridad caducada."


def test_admin_service_secret_is_header_only_and_diagnostics_are_minimal(tmp_path, monkeypatch):
    app = _test_app(tmp_path, monkeypatch)
    monkeypatch.setenv("ADMIN_API_SECRET", "configured-test-service-secret")
    client = app.test_client()

    assert client.get("/api/admin/debug-files?secret=configured-test-service-secret").status_code == 403
    response = client.get(
        "/api/admin/debug-files",
        headers={"X-Admin-Secret": "configured-test-service-secret"},
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "ok"
    assert set(payload["files"]) == {"runtime", "seed"}
    serialized = json.dumps(payload)
    assert config.BASE_DIR not in serialized
    assert config.DATA_DIR not in serialized


def test_live_stream_is_opt_in_on_synchronous_deployments(tmp_path, monkeypatch):
    app = _test_app(tmp_path, monkeypatch)
    monkeypatch.setattr(config, "LIVE_SSE_ENABLED", False)

    response = app.test_client().get("/api/live/stream?j=73")
    assert response.status_code == 503
    assert response.headers["Retry-After"] == "120"
    assert response.get_json()["status"] == "disabled"


def test_responses_include_request_diagnostics(tmp_path, monkeypatch):
    app = _test_app(tmp_path, monkeypatch)
    response = app.test_client().get("/health")

    assert response.status_code == 200
    assert len(response.headers["X-Request-ID"]) == 16
    assert response.headers["Server-Timing"].startswith("app;dur=")


def test_rate_limiter_schema_is_migrated_and_reservation_is_atomic(tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor

    from liga_maestros.middleware import rate_limit

    app = _test_app(tmp_path, monkeypatch)
    monkeypatch.setattr(rate_limit.time, "time", lambda: 1_800_000_000.0)
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: rate_limit.is_rate_limited("test_scope", "u1", 5), range(8)))

    assert results.count(False) == 1
    assert results.count(True) == 7

    with app.app_context():
        conn = get_db()
        row = conn.execute(
            "SELECT last_seen FROM api_rate_limit WHERE scope = ? AND identity = ?",
            ("test_scope", "u1"),
        ).fetchone()
        assert row["last_seen"] == 1_800_000_000.0
        indexes = {item[1] for item in conn.execute("PRAGMA index_list(api_rate_limit)")}
        assert "idx_rate_limit_last_seen" in indexes
        conn.close()
