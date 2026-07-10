import time
from flask import request
from ..db.connection import get_db

_rate_limit_lock = None
_rate_limit_hits = {}


def _get_lock():
    global _rate_limit_lock
    if _rate_limit_lock is None:
        import threading
        _rate_limit_lock = threading.Lock()
    return _rate_limit_lock


def is_rate_limited(scope, identity, seconds):
    now = time.time()
    identity = str(identity or request.remote_addr or "anon")
    conn = get_db()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS api_rate_limit (
                scope TEXT NOT NULL,
                identity TEXT NOT NULL,
                last_seen REAL NOT NULL,
                PRIMARY KEY (scope, identity)
            )
        """)
        conn.commit()
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT last_seen FROM api_rate_limit WHERE scope = ? AND identity = ?",
            (scope, identity)
        ).fetchone()
        if row and now - float(row["last_seen"] or 0) < seconds:
            conn.rollback()
            return True
        conn.execute("""
            INSERT INTO api_rate_limit (scope, identity, last_seen)
            VALUES (?, ?, ?)
            ON CONFLICT(scope, identity) DO UPDATE SET last_seen = excluded.last_seen
        """, (scope, identity, now))
        conn.execute("DELETE FROM api_rate_limit WHERE last_seen < ?", (now - 3600,))
        conn.commit()
        return False
    except Exception:
        conn.rollback()
        lock = _get_lock()
        key = (scope, identity)
        with lock:
            last_seen = _rate_limit_hits.get(key, 0)
            if now - last_seen < seconds:
                return True
            _rate_limit_hits[key] = now
            return False
    finally:
        conn.close()
