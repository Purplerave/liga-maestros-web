"""Authorization helpers shared by routes."""

import hmac
import os

from flask import request, session


def is_admin_request():
    user = session.get("user") or {}
    if user.get("is_admin") is True:
        return True
    # Compatibility for sessions created before email was removed from cookies.
    email = str(user.get("email") or "").strip().lower()
    admin_emails = {item.strip().lower() for item in os.getenv("ADMIN_EMAILS", "").split(",") if item.strip()}
    if email and email in admin_emails:
        return True
    allow_local = os.getenv("ALLOW_LOCAL_ADMIN", "0").strip().lower() in ("1", "true", "yes", "on")
    if not allow_local:
        return False
    # Only use real remote_addr, never X-Forwarded-For for admin bypass.
    is_local = request.remote_addr in ("127.0.0.1", "::1", "localhost")
    return is_local


def is_admin_or_service_request():
    """Authorize an admin session or an explicitly configured service secret.

    Service credentials are accepted only in a header. Query-string secrets
    leak into browser history, access logs and proxy telemetry, so they are
    deliberately ignored. There is no default credential: a missing
    ``ADMIN_API_SECRET`` fails closed.
    """
    if is_admin_request():
        return True

    expected = os.getenv("ADMIN_API_SECRET", "").strip()
    received = request.headers.get("X-Admin-Secret", "").strip()
    return bool(expected and received and hmac.compare_digest(expected, received))
