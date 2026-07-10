"""Authorization helpers shared by routes."""
import os

from flask import request, session


def is_admin_request():
    user = session.get("user") or {}
    email = str(user.get("email") or "").strip().lower()
    allow_local = os.getenv("ALLOW_LOCAL_ADMIN", "0").strip().lower() in ("1", "true", "yes", "on")
    is_local = request.remote_addr in ("127.0.0.1", "::1", "localhost")
    admin_emails = {item.strip().lower() for item in os.getenv("ADMIN_EMAILS", "").split(",") if item.strip()}
    return (allow_local and is_local) or (email and email in admin_emails)

