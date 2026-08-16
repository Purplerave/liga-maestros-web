"""Liga de Maestros - centralized configuration package.

Each submodule owns a domain of settings so the app stays maintainable.
Import from ``config`` directly; the package ``__init__`` re-exports the
public surface used across the codebase.
"""

from dotenv import load_dotenv
import os

# Cargar variables de entorno una sola vez.
load_dotenv()

# Directorio base del proyecto (raíz de web2.0, un nivel arriba de config/).
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Datos runtime: Render usa /var/data, si no, data/ junto al proyecto.
RENDER_DATA_DIR = "/var/data"
DEFAULT_DATA_DIR = (
    RENDER_DATA_DIR
    if os.getenv("RENDER") and os.path.isdir(RENDER_DATA_DIR)
    else os.path.join(BASE_DIR, "data")
)
DATA_DIR = os.getenv("DATA_DIR", "").strip() or DEFAULT_DATA_DIR
SEED_DATA_DIR = os.path.join(BASE_DIR, "data")


def data_path(*parts):
    """Build a path inside the runtime DATA_DIR."""
    return os.path.join(DATA_DIR, *parts)


def ensure_runtime_data_dir():
    """Create DATA_DIR and copy seed JSONs when runtime != seed."""
    import shutil

    os.makedirs(DATA_DIR, exist_ok=True)
    if os.path.abspath(DATA_DIR) == os.path.abspath(SEED_DATA_DIR):
        return
    if not os.path.isdir(SEED_DATA_DIR):
        return
    for name in os.listdir(SEED_DATA_DIR):
        src = os.path.join(SEED_DATA_DIR, name)
        dst = os.path.join(DATA_DIR, name)
        if os.path.isfile(src) and name.lower().endswith(".json") and not os.path.exists(dst):
            shutil.copy2(src, dst)


# Re-export public symbols from specialized submodules so callers can keep
# doing ``from config import X`` without touching domain modules.
from .api import (  # noqa: E402
    API_FOOTBALL_DAILY_LIMIT,
    API_FOOTBALL_DAILY_RESERVE,
    API_FOOTBALL_HOST,
    API_FOOTBALL_KEY,
    HIGHLIGHTLY_HOST,
    HIGHLIGHTLY_LEAGUES,
    HIGHLIGHTLY_RAPIDAPI_HOST,
    LIVE_SSE_ENABLED,
)
from .database import (  # noqa: E402
    BOOTSTRAP_DB_PATH,
    DB_BACKUP_DIR,
    DB_PATH,
    DEFAULT_DB_PATH,
    FIXTURE_CORRECTIONS_PATH,
    PRODUCTION_SEED_PATH,
)
from .feeds import (  # noqa: E402
    NEWS_CACHE_PATH,
    NEWS_FEEDS,
    NEWS_GENERIC_KEYWORDS,
    NEWS_REFRESH_SECONDS,
    NEWS_TEAM_KEYWORDS,
)
from .game import (  # noqa: E402
    MAX_DOBLES_PER_TICKET,
    MAX_TRIPLES_PER_TICKET,
)
from .security import (  # noqa: E402
    GOOGLE_AUTH_ENABLED,
    GOOGLE_CLIENT_KWARGS,
    GOOGLE_SERVER_METADATA_URL,
    SECRET_KEY,
    SESSION_COOKIE_HTTPONLY,
    SESSION_COOKIE_SAMESITE,
    SESSION_COOKIE_SECURE,
    TRUSTED_HOSTS,
)
from .settings import (  # noqa: E402
    ALLOW_IFRAME_EMBED,
    MAX_CONTENT_LENGTH,
    MAX_FORM_MEMORY_SIZE,
    MAX_FORM_PARTS,
    PREFERRED_URL_SCHEME,
    SLOW_REQUEST_MS,
)
from .teams import (  # noqa: E402
    STANDINGS_LEAGUES,
    TEAM_LOGO_ALIASES,
)

__all__ = [
    # Paths
    "BASE_DIR",
    "DATA_DIR",
    "DEFAULT_DATA_DIR",
    "SEED_DATA_DIR",
    "RENDER_DATA_DIR",
    "DB_PATH",
    "DEFAULT_DB_PATH",
    "BOOTSTRAP_DB_PATH",
    "PRODUCTION_SEED_PATH",
    "FIXTURE_CORRECTIONS_PATH",
    "DB_BACKUP_DIR",
    "data_path",
    "ensure_runtime_data_dir",
    # Security
    "SECRET_KEY",
    "SESSION_COOKIE_HTTPONLY",
    "SESSION_COOKIE_SAMESITE",
    "SESSION_COOKIE_SECURE",
    "TRUSTED_HOSTS",
    "PREFERRED_URL_SCHEME",
    "ALLOW_IFRAME_EMBED",
    "GOOGLE_AUTH_ENABLED",
    "GOOGLE_SERVER_METADATA_URL",
    "GOOGLE_CLIENT_KWARGS",
    # API
    "HIGHLIGHTLY_HOST",
    "HIGHLIGHTLY_RAPIDAPI_HOST",
    "HIGHLIGHTLY_LEAGUES",
    "API_FOOTBALL_HOST",
    "API_FOOTBALL_KEY",
    "API_FOOTBALL_DAILY_LIMIT",
    "API_FOOTBALL_DAILY_RESERVE",
    "LIVE_SSE_ENABLED",
    # Feeds
    "NEWS_CACHE_PATH",
    "NEWS_FEEDS",
    "NEWS_REFRESH_SECONDS",
    "NEWS_TEAM_KEYWORDS",
    "NEWS_GENERIC_KEYWORDS",
    # Game policy
    "MAX_DOBLES_PER_TICKET",
    "MAX_TRIPLES_PER_TICKET",
    # Teams
    "TEAM_LOGO_ALIASES",
    "STANDINGS_LEAGUES",
    # Request hardening
    "MAX_CONTENT_LENGTH",
    "MAX_FORM_MEMORY_SIZE",
    "MAX_FORM_PARTS",
    "SLOW_REQUEST_MS",
]
