"""Authorization helpers shared by routes."""

import hmac
import os

from flask import request, session


def _trust_proxy_headers() -> bool:
    return os.getenv("TRUST_PROXY_HEADERS", "0").strip().lower() in ("1", "true", "yes", "on")


def _digest_equal(expected: str, received: str) -> bool:
    # compare_digest con str revienta con caracteres no ASCII (TypeError -> 500).
    return hmac.compare_digest(expected.encode("utf-8"), received.encode("utf-8"))


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
    # Detras de un proxy, ProxyFix reescribe REMOTE_ADDR con el ultimo valor de
    # X-Forwarded-For, de modo que cualquier cliente podria mandar
    # "X-Forwarded-For: 127.0.0.1" y colarse como admin. Sin proxy, remote_addr
    # es la direccion real del socket y el bypass local es fiable.
    if _trust_proxy_headers():
        return False
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
    return bool(expected and received and _digest_equal(expected, received))
