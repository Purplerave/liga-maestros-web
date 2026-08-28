"""Security middleware: rate limiting, CSP tightening, request validation."""

import os
import threading
import time
from collections import defaultdict
from functools import wraps

from flask import g, jsonify, request

# In-memory rate limit store (per-process, good enough for single-instance deploy)
# Lock needed: gunicorn --workers 1 --threads 8 ya es multi-thread.
_RATE_LIMIT_STORE = defaultdict(list)
_RATE_LIMIT_LOCK = threading.Lock()


def _get_client_ip():
    """IP real ya corregida por ProxyFix (x_for=1); no parsear X-Forwarded-For a mano."""
    return request.remote_addr or "unknown"


def _clean_old_entries(window_seconds):
    """Remove entries older than window to prevent memory growth."""
    now = time.time()
    cutoff = now - window_seconds
    for ip, timestamps in _RATE_LIMIT_STORE.items():
        _RATE_LIMIT_STORE[ip] = [ts for ts in timestamps if ts > cutoff]
    # Remove empty
    empty_ips = [ip for ip, ts in _RATE_LIMIT_STORE.items() if not ts]
    for ip in empty_ips:
        del _RATE_LIMIT_STORE[ip]


def rate_limit(max_requests: int = 120, window_seconds: int = 60, paths=None):
    """Decorator legacy — mantenido por compatibilidad. Usar init_rate_limiter global."""
    # Nota: código muerto en uso actual (grep: 0 callers). Se conserva para no romper imports,
    # pero el limitador real es init_rate_limiter.
    if paths is None:
        paths = ["/api/"]

    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            return f(*args, **kwargs)

        return wrapped

    return decorator


def init_rate_limiter(app):
    """Initialize rate limiter as a global before_request handler."""

    @app.before_request
    def apply_rate_limit():
        # Apply to all /api/* routes
        if not request.path.startswith("/api/"):
            return None
        # Skip health checks
        if request.path in ("/api/live/health", "/health", "/favicon.ico"):
            return None

        ip = _get_client_ip()
        now = time.time()
        window_seconds = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))
        max_requests = int(os.getenv("RATE_LIMIT_MAX_REQUESTS", "120"))
        window_start = now - window_seconds

        with _RATE_LIMIT_LOCK:
            if len(_RATE_LIMIT_STORE) % 100 == 0:
                _clean_old_entries(window_seconds)
            recent = [ts for ts in _RATE_LIMIT_STORE[ip] if ts > window_start]
            _RATE_LIMIT_STORE[ip] = recent
            if len(recent) >= max_requests:
                retry_after = int(window_seconds - (now - recent[0])) + 1
                response = jsonify(
                    {
                        "status": "error",
                        "error": "Rate limit exceeded",
                        "retry_after": retry_after,
                    }
                )
                response.status_code = 429
                response.headers["Retry-After"] = str(retry_after)
                response.headers["X-RateLimit-Limit"] = str(max_requests)
                response.headers["X-RateLimit-Remaining"] = "0"
                response.headers["X-RateLimit-Reset"] = str(int(now + window_seconds))
                return response
            _RATE_LIMIT_STORE[ip].append(now)

        # Add headers to response via after_request
        g.rate_limit_info = {
            "limit": max_requests,
            "remaining": max(0, max_requests - len(recent) - 1),
            "reset": int(now + window_seconds),
        }
        return None

    @app.after_request
    def add_rate_limit_headers(response):
        if hasattr(g, "rate_limit_info"):
            info = g.rate_limit_info
            response.headers["X-RateLimit-Limit"] = str(info["limit"])
            response.headers["X-RateLimit-Remaining"] = str(info["remaining"])
            response.headers["X-RateLimit-Reset"] = str(info["reset"])
        return response
