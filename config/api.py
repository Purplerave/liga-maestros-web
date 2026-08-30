"""External API configuration."""

import os

# Highlightly.
HIGHLIGHTLY_HOST = "soccer.highlightly.net"
HIGHLIGHTLY_RAPIDAPI_HOST = "football-highlights-api.p.rapidapi.com"

# Liga F IDs: Highlightly may use different IDs per season / naming.
# Allow override via env and provide sensible defaults (best-effort).
# If the ID is wrong the collector still falls back to leagueName queries.
_LIGA_F_ID = int(os.getenv("HIGHLIGHTLY_LIGA_F_ID", "121144"))
_LIGA_F_MOEVE_ID = int(os.getenv("HIGHLIGHTLY_LIGA_F_MOEVE_ID", str(_LIGA_F_ID)))
_LIGA_F_ALT_ID = int(os.getenv("HIGHLIGHTLY_LIGA_F_ALT_ID", "12316"))

HIGHLIGHTLY_LEAGUES = {
    "LA LIGA": 119924,
    "SEGUNDA DIVISION": 120775,
    "PREMIER LEAGUE": 33973,
    "BUNDESLIGA": 67162,
    "LIGUE 1": 52695,
    "UEFA CHAMPIONS LEAGUE": 2486,
    "LIGA F": _LIGA_F_ID,
    "LIGA F MOEVE": _LIGA_F_MOEVE_ID,
    "PRIMERA DIVISION FEMENINA": _LIGA_F_ID,
    # Alternative naming that some providers use
    "LIGA F FEMENINA": _LIGA_F_ALT_ID,
}

# API-FOOTBALL / API-SPORTS: fallback only, not the live engine.
API_FOOTBALL_HOST = os.getenv("API_FOOTBALL_HOST", "v3.football.api-sports.io")
API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY", "")
API_FOOTBALL_DAILY_LIMIT = int(os.getenv("API_FOOTBALL_DAILY_LIMIT", "100"))
API_FOOTBALL_DAILY_RESERVE = int(os.getenv("API_FOOTBALL_DAILY_RESERVE", "10"))

# Feature flags. SSE bloquea 1 thread por cliente en gunicorn sync (--threads 8);
# mantener 0 por defecto y habilitar solo con gevent/eventlet.
LIVE_SSE_ENABLED = os.getenv("LIVE_SSE_ENABLED", "0").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)
