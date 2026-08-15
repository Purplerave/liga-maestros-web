"""Concurrency and automatic-close end-to-end tests.

Covers the two operational risks flagged for a SQLite-backed deployment:

1. Concurrency: many users signing their quiniela at the same time while the
   live collector writes to `resultados` must never surface
   "database is locked" errors to users (WAL + busy_timeout + BEGIN IMMEDIATE).

2. Automatic close: the moment the first match kicks off (status flips to a
   live/scored value, or the close time passes), saving must be rejected.
"""

import sqlite3
import threading
from datetime import timedelta

import config
from liga_maestros import create_app
from liga_maestros.db.connection import get_db
from liga_maestros.services.ticket import madrid_now

JORNADA = 1
NUM_USERS = 20
VALID_SIGNS = ["1", "X", "2", "1", "X", "2", "1", "X", "2", "1", "X", "2", "1", "X", "1-0"]


def _test_app(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "concurrency.db"))
    monkeypatch.setattr(config, "BOOTSTRAP_DB_PATH", str(tmp_path / "missing.db"))
    monkeypatch.setattr(config, "PRODUCTION_SEED_PATH", str(tmp_path / "missing-seed.json"))
    monkeypatch.setattr(config, "DB_BACKUP_DIR", str(tmp_path / "backups"))
    monkeypatch.setenv("SECRET_KEY", "concurrency-test-secret")
    monkeypatch.setenv("WEB_COLLECTOR_ENABLED", "0")
    monkeypatch.setenv("DB_BACKUP_ENABLED", "0")
    monkeypatch.setenv("ALLOW_LOCAL_ADMIN", "0")
    monkeypatch.setenv("TRUSTED_HOSTS", "localhost,127.0.0.1")
    return create_app()


def _seed_open_jornada(app, *, kickoff_offset_hours=6):
    """Insert 15 not-started matches whose first kickoff is far in the future."""
    kickoff = madrid_now() + timedelta(hours=kickoff_offset_hours)
    fecha = kickoff.strftime("%Y-%m-%d")
    hora = kickoff.strftime("%H:%M")
    with app.app_context():
        conn = get_db()
        conn.execute("DELETE FROM resultados WHERE jornada = ?", (JORNADA,))
        for partido_id in range(1, 16):
            conn.execute(
                """
                INSERT INTO resultados (jornada, partido_id, local, visitante, status, fecha, hora)
                VALUES (?, ?, ?, ?, 'NS', ?, ?)
                """,
                (JORNADA, partido_id, f"Local {partido_id}", f"Visitante {partido_id}", fecha, hora),
            )
        conn.commit()


def _signed_client(app, user_id):
    client = app.test_client()
    with client.session_transaction() as flask_session:
        flask_session["user"] = {"id": user_id, "name": f"User {user_id}", "is_admin": False}
        flask_session["csrf_token"] = f"csrf-{user_id}"
    return client


def _save_ticket(client, user_id, signs=None):
    return client.post(
        "/api/predicciones/save",
        json={"user_id": user_id, "jornada": JORNADA, "signos": signs or VALID_SIGNS},
        headers={"X-CSRF-Token": f"csrf-{user_id}"},
    )


def test_twenty_simultaneous_signings_with_collector_writes(tmp_path, monkeypatch):
    """20 users sign at once while a collector thread hammers `resultados`."""
    app = _test_app(tmp_path, monkeypatch)
    _seed_open_jornada(app)

    user_ids = [f"11661234567890123{i:04d}" for i in range(NUM_USERS)]
    clients = {uid: _signed_client(app, uid) for uid in user_ids}

    results = {}
    errors = []
    start_barrier = threading.Barrier(NUM_USERS + 1)
    collector_stop = threading.Event()

    def sign(uid):
        try:
            start_barrier.wait(timeout=30)
            response = _save_ticket(clients[uid], uid)
            results[uid] = (response.status_code, response.get_json())
        except Exception as exc:  # pragma: no cover - only on failure
            errors.append((uid, repr(exc)))

    def collector():
        """Simulate the live collector updating match stats concurrently."""
        conn = sqlite3.connect(config.DB_PATH, timeout=10)
        conn.execute("PRAGMA busy_timeout = 10000")
        try:
            start_barrier.wait(timeout=30)
            tick = 0
            while not collector_stop.is_set() and tick < 200:
                tick += 1
                # Touch stats columns only: kickoff must stay in the future
                # and status must stay NS so the window remains open.
                conn.execute(
                    "UPDATE resultados SET posesion_h = ?, tiros_h = ? WHERE jornada = ? AND partido_id = ?",
                    (tick % 100, tick % 30, JORNADA, (tick % 15) + 1),
                )
                conn.commit()
        except Exception as exc:  # pragma: no cover - only on failure
            errors.append(("collector", repr(exc)))
        finally:
            conn.close()

    threads = [threading.Thread(target=sign, args=(uid,)) for uid in user_ids]
    collector_thread = threading.Thread(target=collector)
    for thread in threads:
        thread.start()
    collector_thread.start()
    for thread in threads:
        thread.join(timeout=60)
    collector_stop.set()
    collector_thread.join(timeout=60)

    assert not errors, f"Unexpected exceptions under concurrency: {errors}"
    assert len(results) == NUM_USERS

    locked = [
        (uid, status, payload)
        for uid, (status, payload) in results.items()
        if status >= 500 or "locked" in str(payload).lower()
    ]
    assert not locked, f"'database is locked' style failures: {locked}"

    ok = [uid for uid, (status, _) in results.items() if status == 200]
    assert len(ok) == NUM_USERS, f"Only {len(ok)}/{NUM_USERS} signings succeeded: {results}"

    # Every user must have exactly 15 rows persisted.
    with app.app_context():
        conn = get_db()
        for uid in user_ids:
            count = conn.execute(
                "SELECT COUNT(*) FROM predicciones WHERE user_id = ? AND jornada = ?",
                (uid, JORNADA),
            ).fetchone()[0]
            assert count == 15, f"User {uid} persisted {count}/15 predictions"


def test_double_save_by_same_user_is_consistent(tmp_path, monkeypatch):
    """Two racing saves from the same user must end with one clean ticket."""
    app = _test_app(tmp_path, monkeypatch)
    _seed_open_jornada(app)
    uid = "116612345678901234567"

    alternative = list(VALID_SIGNS)
    alternative[0] = "2"

    outcome = {}
    barrier = threading.Barrier(2)

    def save(tag, signs):
        client = _signed_client(app, uid)
        barrier.wait(timeout=30)
        response = _save_ticket(client, uid, signs)
        outcome[tag] = response.status_code

    threads = [
        threading.Thread(target=save, args=("a", VALID_SIGNS)),
        threading.Thread(target=save, args=("b", alternative)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)

    # Rate limiting may reject one of the two (429) but nothing may 500.
    assert all(status in (200, 429) for status in outcome.values()), outcome
    assert 200 in outcome.values()

    with app.app_context():
        conn = get_db()
        rows = conn.execute(
            "SELECT partido_id, COUNT(*) FROM predicciones WHERE user_id = ? AND jornada = ? GROUP BY partido_id",
            (uid, JORNADA),
        ).fetchall()
        assert len(rows) == 15
        assert all(row[1] == 1 for row in rows), "Duplicated prediction rows after racing saves"


def test_signing_rejected_after_first_whistle_status(tmp_path, monkeypatch):
    """E2E: first match flips to LIVE -> save endpoint must refuse."""
    app = _test_app(tmp_path, monkeypatch)
    _seed_open_jornada(app)
    uid = "116612345678901234567"
    client = _signed_client(app, uid)

    assert _save_ticket(client, uid).status_code == 200

    with app.app_context():
        conn = get_db()
        conn.execute(
            "UPDATE resultados SET status = 'LIVE', minuto = \"1'\" WHERE jornada = ? AND partido_id = 1",
            (JORNADA,),
        )
        conn.commit()

    # Clear the per-user save rate limit window before retrying.
    with app.app_context():
        conn = get_db()
        conn.execute("DELETE FROM api_rate_limit")
        conn.commit()
    response = _save_ticket(client, uid)
    assert response.status_code == 403
    assert "cerrada" in response.get_json()["message"].lower()


def test_signing_rejected_after_finished_match(tmp_path, monkeypatch):
    app = _test_app(tmp_path, monkeypatch)
    _seed_open_jornada(app)
    uid = "116612345678901234567"
    client = _signed_client(app, uid)

    with app.app_context():
        conn = get_db()
        conn.execute(
            "UPDATE resultados SET status = 'FT', goles_local = 2, goles_visitante = 0 "
            "WHERE jornada = ? AND partido_id = 1",
            (JORNADA,),
        )
        conn.commit()

    response = _save_ticket(client, uid)
    assert response.status_code == 403


def test_signing_rejected_when_close_time_passed(tmp_path, monkeypatch):
    """Even with all matches still NS, a past kickoff time closes the ticket."""
    app = _test_app(tmp_path, monkeypatch)
    _seed_open_jornada(app, kickoff_offset_hours=-1)
    uid = "116612345678901234567"
    client = _signed_client(app, uid)

    response = _save_ticket(client, uid)
    assert response.status_code == 403
    assert "cerrada" in response.get_json()["message"].lower()
