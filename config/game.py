"""Game policy limits."""

import os
from datetime import datetime
from zoneinfo import ZoneInfo

MAX_DOBLES_PER_TICKET = int(os.getenv("MAX_DOBLES_PER_TICKET", "14"))
MAX_TRIPLES_PER_TICKET = int(os.getenv("MAX_TRIPLES_PER_TICKET", "14"))


def _compute_current_season_start_year() -> int:
    """Derive season start year from Europe/Madrid date.

    Spanish season 2026-27 runs roughly Aug 2026 — May 2027.
    Override with env CURRENT_SEASON_START_YEAR for testing/admin.
    """
    forced = os.getenv("CURRENT_SEASON_START_YEAR", "").strip()
    if forced.isdigit():
        return int(forced)
    try:
        now = datetime.now(ZoneInfo("Europe/Madrid"))
    except Exception:
        now = datetime.now()
    # Season flips in July (conservative): Jan-Jun => previous year, Jul-Dec => this year
    return now.year if now.month >= 7 else now.year - 1


CURRENT_SEASON_START_YEAR = _compute_current_season_start_year()
CURRENT_SEASON_ID = f"{CURRENT_SEASON_START_YEAR}-{str(CURRENT_SEASON_START_YEAR + 1)[-2:]}"
SEASON_RESET_MARKER = f".season_reset_{CURRENT_SEASON_START_YEAR}_done"
