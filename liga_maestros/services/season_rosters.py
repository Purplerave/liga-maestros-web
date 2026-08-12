"""Official 2026-27 league rosters and season-start standings helpers.

Single source of truth for Primera, Segunda and the foreign leagues shown
in the Ligas tab. Used by seed JSON, startup migrations and tests.
"""

from __future__ import annotations

import json
import os
import time

import config

SEASON_ID = "2026-27"
COMPLETED_SEASON_PJ = 30

# Names keep the existing Spanish display style so logos/aliases still match.
LALIGA_2026_27 = [
    "FC Barcelona",
    "Real Madrid",
    "Villarreal CF",
    "Atlético de Madrid",
    "Real Betis",
    "Celta",
    "Getafe CF",
    "Rayo Vallecano",
    "Valencia CF",
    "Real Sociedad",
    "RCD Espanyol de Barcelona",
    "Athletic Club",
    "Sevilla FC",
    "Deportivo Alavés",
    "Elche CF",
    "Levante UD",
    "CA Osasuna",
    "R. Racing Club",
    "RC Deportivo",
    "Málaga CF",
]

SEGUNDA_2026_27 = [
    "RCD Mallorca",
    "Girona FC",
    "Real Oviedo",
    "UD Almería",
    "UD Las Palmas",
    "CD Castellón",
    "Burgos CF",
    "SD Eibar",
    "Córdoba CF",
    "Albacete BP",
    "AD Ceuta FC",
    "FC Andorra",
    "Real Sporting",
    "Granada CF",
    "R. Sociedad B",
    "Real Valladolid CF",
    "Cádiz CF",
    "CD Leganés",
    "CD Tenerife",
    "CD Eldense",
    "CE Sabadell",
    "Celta Fortuna",
]

PREMIER_2026_27 = [
    "Arsenal",
    "Manchester City",
    "Manchester United",
    "Aston Villa",
    "Liverpool",
    "Bournemouth",
    "Sunderland",
    "Brighton",
    "Brentford",
    "Chelsea",
    "Fulham",
    "Newcastle United",
    "Everton",
    "Leeds",
    "Crystal Palace",
    "Nottingham Forest",
    "Tottenham",
    "Coventry City",
    "Ipswich Town",
    "Hull City",
]

BUNDESLIGA_2026_27 = [
    "Bayern Munich",
    "Borussia Dortmund",
    "RB Leipzig",
    "VfB Stuttgart",
    "1899 Hoffenheim",
    "Bayer Leverkusen",
    "SC Freiburg",
    "Eintracht Frankfurt",
    "FC Augsburg",
    "FSV Mainz 05",
    "Union Berlin",
    "Borussia Mönchengladbach",
    "Hamburger SV",
    "FC Koln",
    "Werder Bremen",
    "Schalke 04",
    "SV Elversberg",
    "SC Paderborn",
]

LIGUE1_2026_27 = [
    "Paris Saint Germain",
    "Lens",
    "Lille",
    "Lyon",
    "Marseille",
    "Rennes FC",
    "Monaco",
    "Strasbourg",
    "Toulouse",
    "Lorient",
    "Paris FC",
    "Stade Brestois 29",
    "Angers",
    "LE Havre AC",
    "Auxerre",
    "Nice",
    "Troyes",
    "Le Mans",
]

FOREIGN_ROSTERS = {
    "PREMIER LEAGUE": PREMIER_2026_27,
    "BUNDESLIGA": BUNDESLIGA_2026_27,
    "LIGUE 1": LIGUE1_2026_27,
}

# Logos already cached from Highlightly for clubs that stay in the league.
FOREIGN_LOGOS = {
    "Arsenal": "https://highlightly.net/soccer/images/teams/36526.png",
    "Manchester City": "https://highlightly.net/soccer/images/teams/43334.png",
    "Manchester United": "https://highlightly.net/soccer/images/teams/28867.png",
    "Aston Villa": "https://highlightly.net/soccer/images/teams/56950.png",
    "Liverpool": "https://highlightly.net/soccer/images/teams/34824.png",
    "Bournemouth": "https://highlightly.net/soccer/images/teams/30569.png",
    "Sunderland": "https://highlightly.net/soccer/images/teams/635630.png",
    "Brighton": "https://highlightly.net/soccer/images/teams/44185.png",
    "Brentford": "https://highlightly.net/soccer/images/teams/47589.png",
    "Chelsea": "https://highlightly.net/soccer/images/teams/42483.png",
    "Fulham": "https://highlightly.net/soccer/images/teams/31420.png",
    "Newcastle United": "https://highlightly.net/soccer/images/teams/29718.png",
    "Everton": "https://highlightly.net/soccer/images/teams/39079.png",
    "Leeds": "https://highlightly.net/soccer/images/teams/54397.png",
    "Crystal Palace": "https://highlightly.net/soccer/images/teams/45036.png",
    "Nottingham Forest": "https://highlightly.net/soccer/images/teams/56099.png",
    "Tottenham": "https://highlightly.net/soccer/images/teams/40781.png",
    "Bayern Munich": "https://highlightly.net/soccer/images/teams/134391.png",
    "Borussia Dortmund": "https://highlightly.net/soccer/images/teams/141199.png",
    "RB Leipzig": "https://highlightly.net/soccer/images/teams/148007.png",
    "VfB Stuttgart": "https://highlightly.net/soccer/images/teams/147156.png",
    "1899 Hoffenheim": "https://highlightly.net/soccer/images/teams/142901.png",
    "Bayer Leverkusen": "https://highlightly.net/soccer/images/teams/143752.png",
    "SC Freiburg": "https://highlightly.net/soccer/images/teams/136944.png",
    "Eintracht Frankfurt": "https://highlightly.net/soccer/images/teams/144603.png",
    "FC Augsburg": "https://highlightly.net/soccer/images/teams/145454.png",
    "FSV Mainz 05": "https://highlightly.net/soccer/images/teams/140348.png",
    "Union Berlin": "https://highlightly.net/soccer/images/teams/155666.png",
    "Borussia Mönchengladbach": "https://highlightly.net/soccer/images/teams/139497.png",
    "Hamburger SV": "https://highlightly.net/soccer/images/teams/149709.png",
    "FC Koln": "https://highlightly.net/soccer/images/teams/164176.png",
    "Werder Bremen": "https://highlightly.net/soccer/images/teams/138646.png",
    "SC Paderborn": "https://highlightly.net/soccer/images/teams/158219.png",
    "Paris Saint Germain": "https://highlightly.net/soccer/images/teams/73119.png",
    "Lens": "https://highlightly.net/soccer/images/teams/99500.png",
    "Lille": "https://highlightly.net/soccer/images/teams/68013.png",
    "Lyon": "https://highlightly.net/soccer/images/teams/68864.png",
    "Marseille": "https://highlightly.net/soccer/images/teams/69715.png",
    "Rennes FC": "https://highlightly.net/soccer/images/teams/80778.png",
    "Monaco": "https://highlightly.net/soccer/images/teams/78225.png",
    "Strasbourg": "https://highlightly.net/soccer/images/teams/81629.png",
    "Toulouse": "https://highlightly.net/soccer/images/teams/82480.png",
    "Lorient": "https://highlightly.net/soccer/images/teams/83331.png",
    "Paris FC": "https://highlightly.net/soccer/images/teams/97798.png",
    "Stade Brestois 29": "https://highlightly.net/soccer/images/teams/90990.png",
    "Angers": "https://highlightly.net/soccer/images/teams/66311.png",
    "LE Havre AC": "https://highlightly.net/soccer/images/teams/95245.png",
    "Auxerre": "https://highlightly.net/soccer/images/teams/92692.png",
    "Nice": "https://highlightly.net/soccer/images/teams/72268.png",
}


def zero_base_row(name, pos):
    return {
        "pos": pos,
        "n": name,
        "pj": 0,
        "pg": 0,
        "pe": 0,
        "pp": 0,
        "gf": 0,
        "gc": 0,
        "pts": 0,
    }


def zero_official_row(name, pos):
    row = zero_base_row(name, pos)
    row["dg"] = 0
    return row


def zero_foreign_row(name, pos):
    return {
        "n": name,
        "pos": pos,
        "pj": 0,
        "pg": 0,
        "pe": 0,
        "pp": 0,
        "gf": 0,
        "gc": 0,
        "dg": 0,
        "pts": 0,
        "logo": FOREIGN_LOGOS.get(name, ""),
        "form": [],
        "streak": "",
    }


def build_base_standings(names):
    return [zero_base_row(name, idx) for idx, name in enumerate(names, start=1)]


def build_official_standings():
    return {
        "primera": [zero_official_row(name, idx) for idx, name in enumerate(LALIGA_2026_27, start=1)],
        "segunda": [zero_official_row(name, idx) for idx, name in enumerate(SEGUNDA_2026_27, start=1)],
    }


def build_fresh_external_leagues():
    leagues = []
    for name, roster in FOREIGN_ROSTERS.items():
        leagues.append(
            {
                "name": name,
                "teams": [zero_foreign_row(team, idx) for idx, team in enumerate(roster, start=1)],
                "source": "season-reset",
                "season": SEASON_ID,
            }
        )
    return leagues


def official_names(category):
    if category == "primera":
        return list(LALIGA_2026_27)
    if category == "segunda":
        return list(SEGUNDA_2026_27)
    return list(FOREIGN_ROSTERS.get(category, []))


def official_name_set(category):
    return set(official_names(category))


def team_name_set(rows):
    return {str(row.get("n") or "").strip() for row in (rows or []) if str(row.get("n") or "").strip()}


def roster_matches(rows, expected_names):
    return team_name_set(rows) == set(expected_names)


def max_played(rows):
    played = 0
    for row in rows or []:
        try:
            played = max(played, int(row.get("pj") or 0))
        except (TypeError, ValueError):
            continue
    return played


def is_stale_external_cache(payload):
    """True when the cached foreign tables still belong to the previous season."""
    if not isinstance(payload, dict):
        return True
    if str(payload.get("season") or "") != SEASON_ID:
        return True
    leagues = payload.get("leagues") or []
    if not leagues:
        return True
    seen = {}
    for league in leagues:
        name = str(league.get("name") or "").strip()
        if name not in FOREIGN_ROSTERS:
            continue
        teams = league.get("teams") or []
        seen[name] = teams
        if max_played(teams) >= COMPLETED_SEASON_PJ:
            return True
        if not roster_matches(teams, FOREIGN_ROSTERS[name]):
            return True
    return set(seen) != set(FOREIGN_ROSTERS)


def merge_official_stats(official_names_list, calculated_teams):
    """Keep the official roster and overlay live stats for clubs that already played."""
    by_name = {str(team.get("n") or "").strip(): team for team in (calculated_teams or [])}
    merged = []
    for idx, name in enumerate(official_names_list, start=1):
        calc = by_name.get(name) or {}
        merged.append(
            {
                "pos": idx,
                "n": name,
                "pj": int(calc.get("pj") or 0),
                "pg": int(calc.get("pg") or 0),
                "pe": int(calc.get("pe") or 0),
                "pp": int(calc.get("pp") or 0),
                "gf": int(calc.get("gf") or 0),
                "gc": int(calc.get("gc") or 0),
                "pts": int(calc.get("pts") or 0),
            }
        )
    merged.sort(key=lambda row: (-row["pts"], row["gf"] - row["gc"], -row["gf"], row["n"]))
    for idx, row in enumerate(merged, start=1):
        row["pos"] = idx
    return merged


def _write_json(path, payload):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    os.replace(tmp_path, path)


def _read_json(path, default=None):
    if not path or not os.path.exists(path):
        return default
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError, TypeError):
        return default


def sync_spanish_base_files(target_dir=None):
    """Write Primera/Segunda seed files when the roster is not 2026-27."""
    target_dir = target_dir or config.SEED_DATA_DIR
    changed = []
    mapping = {
        "STANDINGS_LALIGA_BASE.json": LALIGA_2026_27,
        "STANDINGS_SEGUNDA_BASE.json": SEGUNDA_2026_27,
    }
    for filename, names in mapping.items():
        path = os.path.join(target_dir, filename)
        current = _read_json(path, [])
        if roster_matches(current, names) and max_played(current) < COMPLETED_SEASON_PJ:
            continue
        _write_json(path, build_base_standings(names))
        changed.append(filename)

    official_path = os.path.join(target_dir, "standings_oficial.json")
    official = _read_json(official_path, {}) or {}
    if not (
        roster_matches(official.get("primera"), LALIGA_2026_27)
        and roster_matches(official.get("segunda"), SEGUNDA_2026_27)
        and max_played(official.get("primera")) < COMPLETED_SEASON_PJ
        and max_played(official.get("segunda")) < COMPLETED_SEASON_PJ
    ):
        _write_json(official_path, build_official_standings())
        changed.append("standings_oficial.json")
    return changed


def sync_runtime_standings_files():
    """Copy/reset season files into DATA_DIR so production does not keep last year."""
    if not config.DATA_DIR:
        return []
    os.makedirs(config.DATA_DIR, exist_ok=True)
    changed = sync_spanish_base_files(config.SEED_DATA_DIR)
    if os.path.abspath(config.DATA_DIR) != os.path.abspath(config.SEED_DATA_DIR):
        changed.extend(sync_spanish_base_files(config.DATA_DIR))

    cache_path = os.path.join(config.DATA_DIR, "MULTI_STANDINGS.json")
    seed_cache_path = os.path.join(config.SEED_DATA_DIR, "MULTI_STANDINGS.json")
    payload = _read_json(cache_path, None)
    if is_stale_external_cache(payload):
        fresh = {"season": SEASON_ID, "leagues": build_fresh_external_leagues(), "updated_at": time.time()}
        _write_json(cache_path, fresh)
        if os.path.abspath(seed_cache_path) != os.path.abspath(cache_path):
            _write_json(seed_cache_path, fresh)
        changed.append("MULTI_STANDINGS.json")
    return changed


def replace_clasificacion_from_roster(conn):
    """Replace clasificacion when it still has the previous season's clubs.

    If the roster already matches 2026-27, leave live points untouched.
    """
    primera = build_base_standings(LALIGA_2026_27)
    segunda = build_base_standings(SEGUNDA_2026_27)
    expected = {1: set(LALIGA_2026_27), 2: set(SEGUNDA_2026_27)}
    actual = {1: set(), 2: set()}
    try:
        for row in conn.execute("SELECT equipo, division FROM clasificacion"):
            division = int(row["division"] if "division" in row.keys() else row[1])
            name = str(row["equipo"] if "equipo" in row.keys() else row[0]).strip()
            if division in actual and name:
                actual[division].add(name)
    except Exception:
        return False

    if actual[1] == expected[1] and actual[2] == expected[2]:
        return False

    conn.execute("DELETE FROM clasificacion")
    for division, rows in ((1, primera), (2, segunda)):
        for team in rows:
            conn.execute(
                """
                INSERT INTO clasificacion
                    (equipo, pj, pts, division, pos, pg, pe, pp, gf, gc, racha)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    team["n"],
                    team["pj"],
                    team["pts"],
                    division,
                    team["pos"],
                    team["pg"],
                    team["pe"],
                    team["pp"],
                    team["gf"],
                    team["gc"],
                    None,
                ),
            )
    conn.commit()
    return True
