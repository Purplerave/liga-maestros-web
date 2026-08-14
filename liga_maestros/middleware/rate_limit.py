"""Small cross-thread/process rate limiter backed by SQLite.

The schema is created at startup, never in the request hot path. A conditional
UPSERT performs the check and reservation atomically, while stale-row cleanup is
sampled so normal requests do not scan the table every time.
"""

import logging
import time

from flask import request

from ..db.connection import get_db

logger = logging.getLogger(__name__)

_rate_limit_lock = None
_rate_limit_hits: dict[tuple[str, str], float] = {}
_last_cleanup = 0.0
_CLEANUP_INTERVAL_SECONDS = 300
_RETENTION_SECONDS = 3600


def _get_lock():
    global _rate_limit_lock
    if _rate_limit_lock is None:
        import threading

        _rate_limit_lock = threading.Lock()
    return _rate_limit_lock


def _claim_cleanup(now):
    global _last_cleanup
    with _get_lock():
        if now - _last_cleanup < _CLEANUP_INTERVAL_SECONDS:
            return False
        _last_cleanup = now
        return True


def _fallback_is_limited(scope, identity, seconds, now):
    """Keep a single-process safety net if the limiter table is unavailable."""
    key = (scope, identity)
    with _get_lock():
        last_seen = _rate_limit_hits.get(key, 0)
        if now - last_seen < seconds:
            return True
        _rate_limit_hits[key] = now
        if len(_rate_limit_hits) > 4096:
            cutoff = now - _RETENTION_SECONDS
            for stale_key, seen_at in list(_rate_limit_hits.items()):
                if seen_at < cutoff:
                    _rate_limit_hits.pop(stale_key, None)
        return False


def is_rate_limited(scope, identity, seconds):
    now = time.time()
    scope = str(scope or "default")
    identity = str(identity or request.remote_addr or "anon")
    seconds = max(0.0, float(seconds or 0))
    conn = get_db()
    try:
        cursor = conn.execute(
            """
            INSERT INTO api_rate_limit (scope, identity, last_seen)
            VALUES (?, ?, ?)
            ON CONFLICT(scope, identity) DO UPDATE SET last_seen = excluded.last_seen
            WHERE api_rate_limit.last_seen <= excluded.last_seen - ?
            """,
            (scope, identity, now, seconds),
        )
        allowed = cursor.rowcount > 0
        if allowed and _claim_cleanup(now):
            conn.execute("DELETE FROM api_rate_limit WHERE last_seen < ?", (now - _RETENTION_SECONDS,))
        conn.commit()
        return not allowed
    except Exception:
        conn.rollback()
        logger.warning("Rate limiter SQLite unavailable; using process-local fallback", exc_info=True)
        return _fallback_is_limited(scope, identity, seconds, now)
    finally:
        conn.close()
