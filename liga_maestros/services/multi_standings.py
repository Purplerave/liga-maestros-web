"""Multi-league standings built from local data and an explicit external cache."""

import json
import os
import time

import config

from ..utils import normalize_team_key
from .highlightly_standings import fetch_highlightly_standings

CACHE_PATH = os.path.join(config.DATA_DIR, "MULTI_STANDINGS.json")


def _load_cache():
    if not os.path.exists(CACHE_PATH):
        return None
    try:
        with open(CACHE_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("leagues", [])
    except Exception:
        return None


def _save_cache(leagues):
    try:
        os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump({"leagues": leagues, "updated_at": time.time()}, f, ensure_ascii=False)
    except Exception:
        pass


def build_multi_league_standings(official_standings, team_logos=None):
    """Build standings without making network calls.

    La Liga + Segunda: from clasificacion table.
    Others: from the last explicitly refreshed Highlightly cache.
    """
    leagues = []
    team_logos = team_logos or {}

    # 1. Official: La Liga + Segunda
    for cat, label in [("primera", "LA LIGA"), ("segunda", "SEGUNDA DIVISION")]:
        rows = official_standings.get(cat, [])
        if not rows:
            continue
        teams = []
        for row in rows:
            gf = row.get("gf", 0) or 0
            gc = row.get("gc", 0) or 0
            teams.append(
                {
                    "n": row.get("n", ""),
                    "pos": row.get("pos", 0),
                    "pj": row.get("pj", 0),
                    "pg": row.get("pg", 0),
                    "pe": row.get("pe", 0),
                    "pp": row.get("pp", 0),
                    "gf": gf,
                    "gc": gc,
                    "dg": gf - gc,
                    "pts": row.get("pts", 0),
                    "logo": team_logos.get(normalize_team_key(row.get("n", "")), ""),
                    "form": [],
                    "streak": row.get("racha", ""),
                }
            )
        leagues.append({"name": label, "teams": teams, "source": "official"})

    # 2. External domestic leagues from the last explicit refresh.
    cached = _load_cache()
    if cached:
        existing_names = {league["name"] for league in leagues}
        allowed_names = set(config.STANDINGS_LEAGUES)
        for league in cached:
            if league["name"] in allowed_names and league["name"] not in existing_names:
                leagues.append(league)
    return leagues


def refresh_external_standings(season=2025):
    """Refresh the external cache only when called by an operator or worker."""
    external = []
    for name, lid in config.STANDINGS_LEAGUES.items():
        teams = fetch_highlightly_standings(lid, season=season)
        if teams:
            external.append({"name": name, "teams": teams, "source": "highlightly"})
    if external:
        _save_cache(external)
    return external


def refresh_spanish_standings(season=2026):
    """Fetch La Liga and Segunda standings from Highlightly and update BASE files."""
    import logging

    logger = logging.getLogger(__name__)

    spanish_leagues = {
        "primera": (config.HIGHLIGHTLY_LEAGUES.get("LA LIGA", 119924), "STANDINGS_LALIGA_BASE.json"),
        "segunda": (config.HIGHLIGHTLY_LEAGUES.get("SEGUNDA DIVISION", 120775), "STANDINGS_SEGUNDA_BASE.json"),
    }
    updated = []
    for cat, (league_id, filename) in spanish_leagues.items():
        teams = fetch_highlightly_standings(league_id, season=season)
        if not teams:
            continue
        base_teams = []
        for i, t in enumerate(teams, 1):
            base_teams.append(
                {
                    "pos": i,
                    "n": t.get("n", ""),
                    "pj": t.get("pj", 0),
                    "pg": t.get("pg", 0),
                    "pe": t.get("pe", 0),
                    "pp": t.get("pp", 0),
                    "gf": t.get("gf", 0),
                    "gc": t.get("gc", 0),
                    "pts": t.get("pts", 0),
                }
            )
        path = os.path.join(config.DATA_DIR, filename)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(base_teams, f, ensure_ascii=False, indent=2)
            logger.info("Updated %s standings: %d teams", cat, len(base_teams))
            updated.append(cat)
        except Exception:
            logger.exception("Failed to write %s", filename)
    return updated
