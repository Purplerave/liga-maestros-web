"""Security middleware: rate limiting, CSP tightening, request validation."""

import os
import time
from collections import defaultdict
from functools import wraps

from flask import g, jsonify, request

# In-memory rate limit store (per-process, good enough for single-instance deploy)
_RATE_LIMIT_STORE = defaultdict(list)
_RATE_LIMIT_LOCK = None  # Use threading.Lock if gunicorn workers > 1


def _get_client_ip():
    """Extract client IP respecting proxy headers."""
    if request.headers.get("X-Forwarded-For"):
        return request.headers.get("X-Forwarded-For").split(",")[0].strip()
    if request.headers.get("X-Real-IP"):
        return request.headers.get("X-Real-IP")
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
    """
    Rate limit decorator for Flask routes.

    Args:
        max_requests: Maximum requests allowed in window
        window_seconds: Time window in seconds
        paths: List of path prefixes to apply limit (default: ["/api/"])
    """
    if paths is None:
        paths = ["/api/"]

    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            # Check if path matches
            if not any(request.path.startswith(p) for p in paths):
                return f(*args, **kwargs)

            # Skip rate limit for health checks
            if request.path in ("/api/live/health", "/health", "/favicon.ico"):
                return f(*args, **kwargs)

            ip = _get_client_ip()
            now = time.time()
            window_start = now - window_seconds

            # Clean old entries periodically (every 100 requests)
            if len(_RATE_LIMIT_STORE) % 100 == 0:
                _clean_old_entries(window_seconds)

            # Filter timestamps in window
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

            # Add current request
            _RATE_LIMIT_STORE[ip].append(now)

            # Add rate limit headers to response
            response = f(*args, **kwargs)
            if hasattr(response, "headers"):
                response.headers["X-RateLimit-Limit"] = str(max_requests)
                response.headers["X-RateLimit-Remaining"] = str(max(0, max_requests - len(recent) - 1))
                response.headers["X-RateLimit-Reset"] = str(int(now + window_seconds))
            return response

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

        # Clean old entries periodically
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
