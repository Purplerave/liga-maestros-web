"""Multi-league standings built from local data and an explicit external cache."""

import json
import logging
import os
import tempfile
import time

import config

from ..utils import normalize_team_key
from .highlightly_standings import fetch_highlightly_standings

logger = logging.getLogger(__name__)

CACHE_PATH = os.path.join(config.DATA_DIR, "MULTI_STANDINGS.json")


class RefreshResult(list):
    """List-compatible refresh result with diagnostics for partial refreshes."""

    def __init__(self, values=()):
        super().__init__(values)
        self.skipped = []
        self.failures = []


def _load_cache():
    if not os.path.exists(CACHE_PATH):
        return None
    try:
        with open(CACHE_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("leagues", [])
    except Exception:
        return None


def _write_json_atomic(path, payload, *, indent=None):
    """Replace a JSON file atomically so readers never see a partial table."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    fd, temp_path = tempfile.mkstemp(
        prefix=f".{os.path.basename(path)}.", suffix=".tmp", dir=os.path.dirname(path) or "."
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=indent)
            if indent is not None:
                f.write("\n")
        os.replace(temp_path, path)
    except Exception:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise


def _save_cache(leagues):
    try:
        _write_json_atomic(
            CACHE_PATH,
            {"season": "2026-27", "leagues": leagues, "updated_at": time.time()},
        )
        return True
    except Exception:
        logger.exception("Failed to write standings cache")
        return False


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


def _issue(league, code, reason, **details):
    return {"league": league, "code": code, "reason": reason, **details}


def refresh_external_standings(season=2026):
    """Refresh the external cache only when called by an operator or worker."""
    external = RefreshResult()
    for name, lid in config.STANDINGS_LEAGUES.items():
        try:
            teams = fetch_highlightly_standings(lid, season=season)
        except Exception:
            logger.exception("Failed to fetch %s standings", name)
            external.failures.append(_issue(name, "fetch_error", "falló la consulta a Highlightly"))
            continue
        if not teams:
            external.skipped.append(_issue(name, "no_data", "Highlightly no devolvió datos (API, cuota o temporada)"))
            continue
        external.append({"name": name, "teams": teams, "source": "highlightly", "season": "2026-27"})
    if external and _save_cache(external) is False:
        external.failures.append(_issue("ligas internacionales", "write_error", "no se pudo guardar la caché"))
    return external


def _result_diagnostics(result, attribute):
    diagnostics = getattr(result, attribute, [])
    return list(diagnostics) if diagnostics else []


def refresh_all_standings(season=2026):
    """Daily full refresh: Spanish leagues (BASE files) + foreign leagues (cache).

    The returned diagnostics make omissions visible to admin callers while the
    ``spanish`` and ``external`` keys retain their original list-based contract.
    """
    spanish_result = refresh_spanish_standings(season=season)
    external_result = refresh_external_standings(season=season)
    spanish = list(spanish_result)
    external = [league["name"] for league in external_result]
    skipped = _result_diagnostics(spanish_result, "skipped") + _result_diagnostics(external_result, "skipped")
    failures = _result_diagnostics(spanish_result, "failures") + _result_diagnostics(external_result, "failures")
    updated_count = len(spanish) + len(external)

    if failures or skipped:
        status = "partial" if updated_count else "error"
    else:
        status = "ok"
    return {
        "status": status,
        "spanish": spanish,
        "external": external,
        "skipped": skipped,
        "failures": failures,
        "updated_count": updated_count,
        "expected_count": 2 + len(config.STANDINGS_LEAGUES),
    }


def _int_value(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _match_spanish_teams(category, teams):
    """Match provider rows to the official roster by canonical team key."""
    from .season_rosters import official_names

    official = official_names(category)
    official_by_key = {normalize_team_key(name): name for name in official}
    incoming_by_key = {}
    duplicates = []

    for team in teams:
        raw_name = str(team.get("n") or "").strip()
        key = normalize_team_key(raw_name)
        if key in incoming_by_key:
            duplicates.extend([str(incoming_by_key[key].get("n") or "").strip(), raw_name])
        else:
            incoming_by_key[key] = team

    expected_keys = set(official_by_key)
    incoming_keys = set(incoming_by_key)
    missing = [official_by_key[key] for key in sorted(expected_keys - incoming_keys)]
    unexpected = [str(incoming_by_key[key].get("n") or "").strip() for key in sorted(incoming_keys - expected_keys)]
    if missing or unexpected or duplicates:
        return None, {
            "missing_teams": missing,
            "unexpected_teams": unexpected,
            "duplicate_teams": sorted(set(duplicates)),
        }

    # Highlightly already returns ranking order. Keep that order and its stats,
    # but always emit the application's official presentation name.
    matched = []
    for fallback_position, team in enumerate(teams, start=1):
        key = normalize_team_key(team.get("n"))
        matched.append(
            {
                "pos": _int_value(team.get("pos"), fallback_position),
                "n": official_by_key[key],
                "pj": _int_value(team.get("pj")),
                "pg": _int_value(team.get("pg")),
                "pe": _int_value(team.get("pe")),
                "pp": _int_value(team.get("pp")),
                "gf": _int_value(team.get("gf")),
                "gc": _int_value(team.get("gc")),
                "pts": _int_value(team.get("pts")),
            }
        )
    matched.sort(key=lambda row: row["pos"])
    return matched, None


def refresh_spanish_standings(season=2026):
    """Fetch La Liga and Segunda standings from Highlightly and update BASE files."""
    spanish_leagues = {
        "primera": (
            "LA LIGA",
            config.HIGHLIGHTLY_LEAGUES.get("LA LIGA", 119924),
            "STANDINGS_LALIGA_BASE.json",
        ),
        "segunda": (
            "SEGUNDA DIVISION",
            config.HIGHLIGHTLY_LEAGUES.get("SEGUNDA DIVISION", 120775),
            "STANDINGS_SEGUNDA_BASE.json",
        ),
    }
    updated = RefreshResult()
    for category, (label, league_id, filename) in spanish_leagues.items():
        try:
            teams = fetch_highlightly_standings(league_id, season=season)
        except Exception:
            logger.exception("Failed to fetch %s standings", category)
            updated.failures.append(_issue(label, "fetch_error", "falló la consulta a Highlightly"))
            continue
        if not teams:
            updated.skipped.append(_issue(label, "no_data", "Highlightly no devolvió datos (API, cuota o temporada)"))
            continue

        base_teams, mismatch = _match_spanish_teams(category, teams)
        if mismatch:
            logger.warning(
                "Skip %s standings refresh: normalized roster mismatch (missing=%s unexpected=%s duplicates=%s)",
                category,
                mismatch["missing_teams"],
                mismatch["unexpected_teams"],
                mismatch["duplicate_teams"],
            )
            updated.skipped.append(
                _issue(
                    label,
                    "roster_mismatch",
                    "la plantilla normalizada no coincide con la oficial 2026-27",
                    **mismatch,
                )
            )
            continue

        path = os.path.join(config.DATA_DIR, filename)
        try:
            _write_json_atomic(path, base_teams, indent=2)
            logger.info("Updated %s standings: %d teams", category, len(base_teams))
            updated.append(category)
        except Exception:
            logger.exception("Failed to write %s", filename)
            updated.failures.append(_issue(label, "write_error", f"no se pudo guardar {filename}"))
    return updated
