"""Multi-league standings: direct API calls, no circuit breaker drama."""

import json
import logging
import os
import time

import requests

import config

logger = logging.getLogger(__name__)

CACHE_PATH = os.path.join(config.DATA_DIR, "MULTI_STANDINGS.json")
CACHE_TTL = 3600


def _get_standings_from_api(league_id, season=2025):
    """Single direct call to Highlightly standings endpoint."""
    api_key = os.getenv("HIGHLIGHTLY_API_KEY", "")
    if not api_key:
        return []
    url = f"https://{config.HIGHLIGHTLY_HOST}/standings"
    params = {"leagueId": league_id, "season": season}
    headers = {"x-rapidapi-key": api_key}
    try:
        r = requests.get(url, params=params, headers=headers, timeout=10)
        r.raise_for_status()
        data = r.json()
        groups = data.get("groups", [])
        if not groups:
            return []
        teams = []
        for idx, entry in enumerate(groups[0].get("standings", []), 1):
            total = entry.get("total", {})
            team = entry.get("team", {})
            wins = total.get("wins", 0)
            draws = total.get("draws", 0)
            gf = total.get("scoredGoals", 0)
            gc = total.get("receivedGoals", 0)
            teams.append({
                "n": team.get("name", ""),
                "pos": idx,
                "pj": total.get("games", 0),
                "pg": wins,
                "pe": draws,
                "pp": total.get("loses", 0),
                "gf": gf,
                "gc": gc,
                "dg": gf - gc,
                "pts": wins * 3 + draws,
                "logo": team.get("logo", ""),
                "form": [],
                "streak": "",
            })
        return teams
    except Exception as exc:
        logger.warning("Standings fetch failed for league %s: %s", league_id, exc)
        return []


def _load_cache():
    if not os.path.exists(CACHE_PATH):
        return None
    try:
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if time.time() - data.get("updated_at", 0) > CACHE_TTL:
            return None
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


def build_multi_league_standings(official_standings):
    """Build standings for all leagues.

    La Liga + Segunda: from clasificacion table.
    Others: from Highlightly API (4 calls).
    """
    leagues = []

    # 1. Official: La Liga + Segunda
    for cat, label in [("primera", "LA LIGA"), ("segunda", "SEGUNDA DIVISION")]:
        rows = official_standings.get(cat, [])
        if not rows:
            continue
        teams = []
        for row in rows:
            gf = row.get("gf", 0) or 0
            gc = row.get("gc", 0) or 0
            teams.append({
                "n": row.get("n", ""),
                "pos": row.get("pos", 0),
                "pj": row.get("pj", 0),
                "pg": row.get("pg", 0),
                "pe": row.get("pe", 0),
                "pp": row.get("pp", 0),
                "gf": gf, "gc": gc, "dg": gf - gc,
                "pts": row.get("pts", 0),
                "form": [],
                "streak": row.get("racha", ""),
            })
        leagues.append({"name": label, "teams": teams, "source": "official"})

    # 2. External: Premier, Bundesliga, Ligue 1, Champions
    cached = _load_cache()
    if cached:
        existing_names = {l["name"] for l in leagues}
        for l in cached:
            if l["name"] not in existing_names:
                leagues.append(l)
        return leagues

    external = []
    for name, lid in config.STANDINGS_LEAGUES.items():
        teams = _get_standings_from_api(lid, season=2025)
        if teams:
            external.append({"name": name, "teams": teams, "source": "highlightly"})

    if external:
        _save_cache(external)
        existing_names = {l["name"] for l in leagues}
        for l in external:
            if l["name"] not in existing_names:
                leagues.append(l)

    return leagues
