"""Small session-bound CSRF protection for authenticated writes."""

import hmac
import secrets

from flask import request, session


def get_csrf_token():
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


def valid_csrf_request():
    expected = str(session.get("csrf_token") or "")
    received = str(request.headers.get("X-CSRF-Token") or request.form.get("csrf_token") or "")
    if not expected or not received:
        return False
    # compare_digest con str lanza TypeError si el token trae no-ASCII: se compara en bytes.
    return hmac.compare_digest(expected.encode("utf-8"), received.encode("utf-8"))
