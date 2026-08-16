"""Security and authentication settings."""

import os

# Core secret.
SECRET_KEY = os.getenv("SECRET_KEY", "").strip()

# Session cookies.
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = os.getenv("SESSION_COOKIE_SAMESITE", "Lax")
SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "0").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)

# Host validation.
TRUSTED_HOSTS = [
    item.strip()
    for item in os.getenv(
        "TRUSTED_HOSTS",
        "ligademaestros.alwaysdata.net,localhost,127.0.0.1",
    ).split(",")
    if item.strip()
]

# Google OAuth.
GOOGLE_AUTH_ENABLED = bool(os.getenv("GOOGLE_CLIENT_ID") and os.getenv("GOOGLE_CLIENT_SECRET"))
GOOGLE_SERVER_METADATA_URL = "https://accounts.google.com/.well-known/openid-configuration"
GOOGLE_CLIENT_KWARGS = {"scope": "openid email profile"}
