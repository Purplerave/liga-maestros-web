"""Explicit Highlightly standings client with shared quota protection."""

import logging
import os

import requests

import config
from .highlightly_limits import (
    record_highlightly_failure,
    record_highlightly_success,
    reserve_highlightly_calls,
)

logger = logging.getLogger(__name__)


def fetch_highlightly_standings(league_id, season=None):
    """Fetch one league table while accounting for the external API call."""
    api_key = os.getenv("HIGHLIGHTLY_API_KEY", "")
    if not api_key or not reserve_highlightly_calls(1):
        return []

    params = {"leagueId": league_id}
    if season:
        params["season"] = season
    try:
        response = requests.get(
            f"https://{config.HIGHLIGHTLY_HOST}/standings",
            params=params,
            headers={"x-rapidapi-key": api_key},
            timeout=10,
        )
        response.raise_for_status()
        record_highlightly_success()
    except requests.RequestException as exc:
        record_highlightly_failure(exc)
        logger.warning("Standings fetch failed for league %s: %s", league_id, exc)
        return []

    groups = response.json().get("groups", [])
    if not groups:
        return []

    teams = []
    for position, entry in enumerate(groups[0].get("standings", []), 1):
        total = entry.get("total", {})
        team = entry.get("team", {})
        wins = total.get("wins", 0)
        draws = total.get("draws", 0)
        goals_for = total.get("scoredGoals", 0)
        goals_against = total.get("receivedGoals", 0)
        teams.append({
            "n": team.get("name", ""),
            "pos": position,
            "pj": total.get("games", 0),
            "pg": wins,
            "pe": draws,
            "pp": total.get("loses", 0),
            "gf": goals_for,
            "gc": goals_against,
            "dg": goals_for - goals_against,
            "pts": wins * 3 + draws,
            "logo": team.get("logo", ""),
            "form": [],
            "streak": "",
        })
    return teams
