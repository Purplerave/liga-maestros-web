"""Tests for new arena feedback fixes: Service-Worker-Allowed header, CSP inline fix, and Highlightly refresh window."""

from liga_maestros import create_app
from liga_maestros.db.connection import get_db
from liga_maestros.services.highlightly import compute_refresh_window


def test_service_worker_allowed_header(monkeypatch, tmp_path):
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    app = create_app()
    client = app.test_client()
    res = client.get("/static/sw.js")
    assert res.status_code == 200
    assert res.headers.get("Service-Worker-Allowed") == "/"


def test_no_inline_onclick_in_contest_js():
    with open("static/js/contest.js", encoding="utf-8") as f:
        content = f.read()
    assert 'onclick="window.location.href=' not in content


def test_compute_refresh_window_all_finished(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    app = create_app()
    with app.app_context():
        with get_db() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO resultados (jornada, partido_id, local, visitante, status, fecha, hora) VALUES (999, 1, 'A', 'B', 'FT', '2026-09-01', '12:00')"
            )
            conn.execute(
                "INSERT OR REPLACE INTO resultados (jornada, partido_id, local, visitante, status, fecha, hora) VALUES (999, 2, 'C', 'D', 'FT', '2026-09-01', '14:00')"
            )
            win = compute_refresh_window(conn, 999)
            assert win["enabled"] is False
