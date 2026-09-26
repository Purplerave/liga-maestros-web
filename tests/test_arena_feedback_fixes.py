"""Tests for new arena feedback fixes: Service-Worker-Allowed header, CSP inline fix, and Highlightly refresh window.

Antes estos tests llamaban a `create_app()` sin aislar la base de datos, con lo que
ejecutaban la cadena completa de migraciones contra `DATOS/LIGA_MAESTROS_PRO.db` y
dejaban basura real (se acumuló una jornada 999 con 20 filas en la BD de desarrollo).
Ahora usan la convención del resto del suite: `monkeypatch` sobre `config.DB_PATH`.
"""

from pathlib import Path

import config
from liga_maestros import create_app
from liga_maestros.db.connection import get_db
from liga_maestros.services.highlightly import compute_refresh_window

ROOT = Path(__file__).resolve().parents[1]
# Jornada de laboratorio. Fuera de la temporada publicada a propósito, para que
# no choque con la J9 que las migraciones siembran en la BD. Antes escribía aquí
# en la BD real (jornada 999, 20 filas basura); ahora `DB_PATH` está aislado, así
# que el temporal se tira al acabar el test.
JORNADA_TEST = 999


def _app(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "arena.db"))
    monkeypatch.setattr(config, "BOOTSTRAP_DB_PATH", str(tmp_path / "missing.db"))
    monkeypatch.setattr(config, "PRODUCTION_SEED_PATH", str(tmp_path / "missing-seed.json"))
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    monkeypatch.setenv("WEB_COLLECTOR_ENABLED", "0")
    monkeypatch.setenv("DB_BACKUP_ENABLED", "0")
    monkeypatch.setenv("ALLOW_LOCAL_ADMIN", "0")
    monkeypatch.setenv("TRUSTED_HOSTS", "localhost,127.0.0.1")
    return create_app()


def test_service_worker_allowed_header(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch)
    client = app.test_client()
    res = client.get("/static/sw.js")
    assert res.status_code == 200
    assert res.headers.get("Service-Worker-Allowed") == "/"


def test_no_inline_onclick_in_contest_js():
    content = (ROOT / "static" / "js" / "contest.js").read_text(encoding="utf-8")
    assert 'onclick="window.location.href=' not in content


def test_compute_refresh_window_all_finished(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch)
    with app.app_context():
        with get_db() as conn:
            conn.execute("DELETE FROM resultados WHERE jornada = ?", (JORNADA_TEST,))
            conn.execute(
                "INSERT OR REPLACE INTO resultados (jornada, partido_id, local, visitante, status, fecha, hora) VALUES (?, 1, 'A', 'B', 'FT', '2026-09-01', '12:00')",
                (JORNADA_TEST,),
            )
            conn.execute(
                "INSERT OR REPLACE INTO resultados (jornada, partido_id, local, visitante, status, fecha, hora) VALUES (?, 2, 'C', 'D', 'FT', '2026-09-01', '14:00')",
                (JORNADA_TEST,),
            )
            win = compute_refresh_window(conn, JORNADA_TEST)
            assert win["enabled"] is False
        with get_db() as conn:
            # La BD aislada se tira al acabar el test: nada que limpiar a mano.
            assert conn.execute("SELECT COUNT(*) FROM resultados WHERE jornada = ?", (JORNADA_TEST,)).fetchone()[0] == 2
