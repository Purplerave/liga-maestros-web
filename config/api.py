"""External API configuration."""

import os

# Highlightly.
HIGHLIGHTLY_HOST = "soccer.highlightly.net"
HIGHLIGHTLY_RAPIDAPI_HOST = "football-highlights-api.p.rapidapi.com"
HIGHLIGHTLY_LEAGUES = {
    "LA LIGA": 119924,
    "SEGUNDA DIVISION": 120775,
    "PREMIER LEAGUE": 33973,
    "BUNDESLIGA": 67162,
    "LIGUE 1": 52695,
    "UEFA CHAMPIONS LEAGUE": 2486,
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
