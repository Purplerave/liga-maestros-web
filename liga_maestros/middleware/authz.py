"""Authorization helpers shared by routes."""
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
    # Only use real remote_addr, never X-Forwarded-For for admin bypass
    is_local = request.remote_addr in ("127.0.0.1", "::1", "localhost")
    return is_local

