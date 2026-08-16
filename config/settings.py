"""Request hardening and observability defaults."""

import os

MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", str(64 * 1024)))
MAX_FORM_MEMORY_SIZE = int(os.getenv("MAX_FORM_MEMORY_SIZE", str(32 * 1024)))
MAX_FORM_PARTS = int(os.getenv("MAX_FORM_PARTS", "50"))
SLOW_REQUEST_MS = max(1.0, float(os.getenv("SLOW_REQUEST_MS", "750")))
PREFERRED_URL_SCHEME = os.getenv("PREFERRED_URL_SCHEME", "https")
ALLOW_IFRAME_EMBED = os.getenv("ALLOW_IFRAME_EMBED", "0").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)
