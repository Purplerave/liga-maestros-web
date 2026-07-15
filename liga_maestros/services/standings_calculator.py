"""Calculate standings from match data for any league.

No API calls needed — processes existing match data.
Supports: points, GF, GC, GD, W/D/L, form (last 5), streaks.
"""

import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
try:
    from utils import normalize_team_key
except ImportError:
    def normalize_team_key(value):
        import unicodedata
        text = unicodedata.normalize("NFD", str(value or "").upper())
        text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
        text = re.sub(r"[^A-Z0-9]+", " ", text).strip()
        return text


def _parse_score(match):
    """Extract home/away goals from a match dict. Returns (home_goals, away_goals) or (None, None)."""
    gh = match.get("goles_local")
    ga = match.get("goles_visitante")
    if gh is not None and ga is not None:
        try:
            return int(gh), int(ga)
        except (ValueError, TypeError):
            pass

    score_text = match.get("marcador") or match.get("score") or match.get("scores", {}).get("score") or ""
    m = re.search(r"(\d+)\s*[-–]\s*(\d+)", str(score_text))
    if m:
        return int(m.group(1)), int(m.group(2))
    return None, None


def _team_name(match, side):
    """Get team name from match for 'home' or 'away'."""
    if side == "home":
        return (
            match.get("local")
            or match.get("home_name")
            or (match.get("home") or {}).get("name")
            or ""
        )
    return (
        match.get("visitante")
        or match.get("away_name")
        or (match.get("away") or {}).get("name")
        or ""
    )


def _competition_name(match):
    """Get competition name from match."""
    return (
        match.get("competition_name")
        or (match.get("competition") or {}).get("name")
        or "Desconocida"
    )


def _is_finished(match):
    """Check if a match is finished."""
    status = str(match.get("status") or "").upper()
    return status in ("FT", "FINISHED", "TERMINADO", "FIN")


def _match_sort_key(match):
    """Sort key for matches: chronological by added/scheduled."""
    added = match.get("added") or match.get("fecha_raw") or ""
    return str(added)[:19]


def calculate_standings_from_matches(all_matches):
    """Calculate standings for all leagues from a list of matches.

    Args:
        all_matches: list of match dicts (any source: quiniela, highlightly, etc.)

    Returns:
        dict: {
            "leagues": [
                {
                    "name": "LA LIGA",
                    "teams": [
                        {
                            "n": "Real Madrid",
                            "pos": 1,
                            "pj": 10, "pg": 8, "pe": 1, "pp": 1,
                            "gf": 25, "gc": 8, "dg": 17,
                            "pts": 25,
                            "form": ["W", "W", "D", "W", "L"],  # last 5
                            "streak": "3W",  # current streak
                            "last5_pts": 13,
                        },
                        ...
                    ]
                },
                ...
            ]
        }
    """
    # Group matches by competition
    by_competition = defaultdict(list)
    for match in all_matches:
        comp = _competition_name(match)
        if not comp or comp.upper() in ("FRIENDLIES", "FRIENDLIES CLUBS", "FRIENDLIES WOMEN"):
            continue
        if not _is_finished(match):
            continue
        by_competition[comp].append(match)

    leagues = []
    for comp_name, matches in sorted(by_competition.items()):
        if len(matches) < 3:  # skip leagues with too few matches
            continue

        # Sort chronologically
        matches.sort(key=_match_sort_key)

        # Calculate team stats
        teams = defaultdict(lambda: {
            "n": "", "pj": 0, "pg": 0, "pe": 0, "pp": 0,
            "gf": 0, "gc": 0, "results": [],
        })

        for match in matches:
            home_name = _team_name(match, "home")
            away_name = _team_name(match, "away")
            gh, ga = _parse_score(match)
            if gh is None or ga is None or not home_name or not away_name:
                continue

            home_key = normalize_team_key(home_name)
            away_key = normalize_team_key(away_name)
            if not home_key or not away_key:
                continue

            home = teams[home_key]
            away = teams[away_key]
            if not home["n"]:
                home["n"] = home_name
            if not away["n"]:
                away["n"] = away_name

            home["pj"] += 1
            away["pj"] += 1
            home["gf"] += gh
            home["gc"] += ga
            away["gf"] += ga
            away["gc"] += gh

            if gh > ga:
                home["pg"] += 1
                home["pts"] = home.get("pts", 0) + 3
                home["results"].append((3, gh, ga))
                away["pp"] += 1
                away["results"].append((0, ga, gh))
            elif gh < ga:
                away["pg"] += 1
                away["pts"] = away.get("pts", 0) + 3
                away["results"].append((3, ga, gh))
                home["pp"] += 1
                home["results"].append((0, gh, ga))
            else:
                home["pe"] += 1
                home["pts"] = home.get("pts", 0) + 1
                home["results"].append((1, gh, ga))
                away["pe"] += 1
                away["pts"] = away.get("pts", 0) + 1
                away["results"].append((1, ga, gh))

        # Build final team list with form and streaks
        team_list = []
        for name, stats in teams.items():
            dg = stats["gf"] - stats["gc"]
            pts = stats.get("pts", 0)

            # Form: last 5 results as W/D/L
            last5 = stats["results"][-5:]
            form = []
            for r_pts, _, _ in last5:
                if r_pts == 3:
                    form.append("W")
                elif r_pts == 1:
                    form.append("D")
                else:
                    form.append("L")
            last5_pts = sum(r[0] for r in last5)

            # Current streak
            streak = _calc_streak(stats["results"])

            team_list.append({
                "n": name,
                "pj": stats["pj"],
                "pg": stats["pg"],
                "pe": stats["pe"],
                "pp": stats["pp"],
                "gf": stats["gf"],
                "gc": stats["gc"],
                "dg": dg,
                "pts": pts,
                "form": form,
                "streak": streak,
                "last5_pts": last5_pts,
            })

        # Sort: points, goal diff, goals for, name
        team_list.sort(key=lambda t: (-t["pts"], -t["dg"], -t["gf"], t["n"]))

        # Assign positions
        for idx, team in enumerate(team_list, 1):
            team["pos"] = idx

        if len(team_list) >= 3:
            leagues.append({
                "name": comp_name,
                "teams": team_list,
                "total_matches": len(matches),
            })

    # Sort leagues: Spanish leagues first, then by number of teams
    def league_sort_key(league):
        name = league["name"].upper()
        if "LA LIGA" in name:
            return (0, -len(league["teams"]))
        if "SEGUNDA" in name:
            return (1, -len(league["teams"]))
        return (2, -len(league["teams"]))

    leagues.sort(key=league_sort_key)

    return {"leagues": leagues}


def _calc_streak(results):
    """Calculate current streak from results list (chronological)."""
    if not results:
        return ""
    last = results[-1]
    pts = last[0]
    if pts == 3:
        symbol = "W"
    elif pts == 1:
        symbol = "D"
    else:
        symbol = "L"
    count = 0
    for r in reversed(results):
        if r[0] == pts:
            count += 1
        else:
            break
    return f"{count}{symbol}" if count > 1 else symbol
