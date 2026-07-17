"""Public identifiers and response sanitizing for provider-backed accounts."""
import hashlib
import hmac
import os


PUBLIC_USER_PREFIX = "usuario_"


def is_private_account_id(value):
    """Google subject identifiers are long decimal strings and must stay private."""
    text = str(value or "").strip()
    return len(text) >= 16 and text.isdigit()


def public_participant_id(value, current_user_id=None):
    """Return a stable opaque id, preserving the requester's own id for app state."""
    text = str(value or "").strip()
    if current_user_id and hmac.compare_digest(text, str(current_user_id).strip()):
        return text
    if not is_private_account_id(text):
        return text
    secret = os.getenv("SECRET_KEY", "").encode("utf-8")
    digest = hmac.new(secret, text.encode("utf-8"), hashlib.sha256).hexdigest()[:20]
    return f"{PUBLIC_USER_PREFIX}{digest}"


def resolve_public_participant_id(conn, value):
    """Resolve an opaque public id without ever accepting a raw provider id."""
    text = str(value or "").strip()
    if is_private_account_id(text):
        return None
    if not text.startswith(PUBLIC_USER_PREFIX):
        return text
    for row in conn.execute("SELECT id FROM usuarios"):
        candidate = str(row["id"] or "")
        if not is_private_account_id(candidate):
            continue
        if hmac.compare_digest(public_participant_id(candidate), text):
            return candidate
    return None


def publicize_identifiers(payload, current_user_id=None):
    """Copy a JSON-like payload while replacing private values under id keys."""
    if isinstance(payload, list):
        return [publicize_identifiers(item, current_user_id) for item in payload]
    if not isinstance(payload, dict):
        return payload
    result = {}
    for key, value in payload.items():
        public_key = public_participant_id(key, current_user_id) if is_private_account_id(key) else key
        if key in {"id", "user_id"} and is_private_account_id(value):
            result[public_key] = public_participant_id(value, current_user_id)
        else:
            result[public_key] = publicize_identifiers(value, current_user_id)
    return result


def publicize_mapping_keys(mapping, current_user_id=None):
    return {
        public_participant_id(key, current_user_id): value
        for key, value in (mapping or {}).items()
    }
