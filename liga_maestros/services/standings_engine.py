"""Single source of truth for the Primera/Segunda tables.

Why this module exists
----------------------
The classification used to be built by *adding* the finished quiniela matches
on top of the official base file. That is only correct while the provider has
not counted those matches yet: as soon as Highlightly refreshes
``STANDINGS_*_BASE.json`` the same match was applied twice and a team that had
played one match appeared with ``PJ 2`` and double points.

The rule here is different and cannot double count:

1. We keep our **own ledger of finished matches** (one entry per fixture,
   deduplicated by team pair) built from the results table plus the live panel.
2. We compute a full table from that ledger.
3. We merge it with the official provider snapshot **per team, choosing the
   more complete row** (the one with more matches played) instead of summing.

So during a matchday our own ledger leads (it updates the moment a match ends),
and once the provider catches up its authoritative numbers take over. Neither
path can inflate ``PJ``.
"""

from __future__ import annotations

import logging
import os

import config

from ..utils import normalize_team_key, parse_score_text, safe_read_json
from .jornada import CURRENT_SEASON_MAX_JORNADA

logger = logging.getLogger(__name__)

FINISHED_STATUSES = ("FT", "FINISHED", "TERMINADO", "AET", "PEN", "AWARDED")
LIVE_STATUSES = ("LIVE", "IN PLAY", "HT", "HALF TIME BREAK", "EN JUEGO", "1H", "2H", "ET")

LEAGUE_CATEGORY = {
    "LA LIGA": "primera",
    "LALIGA": "primera",
    "PRIMERA DIVISION": "primera",
    "SEGUNDA DIVISION": "segunda",
    "SEGUNDA": "segunda",
    "LALIGA HYPERMOTION": "segunda",
}


def is_finished_status(status):
    return str(status or "").strip().upper() in FINISHED_STATUSES


def is_live_status(status):
    return str(status or "").strip().upper() in LIVE_STATUSES


def _empty_row(name):
    return {
        "n": name,
        "pj": 0,
        "pg": 0,
        "pe": 0,
        "pp": 0,
        "gf": 0,
        "gc": 0,
        "pts": 0,
        "results": [],
    }


def _apply(row, gf, gc, when):
    row["pj"] += 1
    row["gf"] += gf
    row["gc"] += gc
    if gf > gc:
        row["pg"] += 1
        row["pts"] += 3
        outcome = "W"
    elif gf < gc:
        row["pp"] += 1
        outcome = "L"
    else:
        row["pe"] += 1
        row["pts"] += 1
        outcome = "D"
    row["results"].append((when, outcome))


def _streak(outcomes):
    if not outcomes:
        return ""
    last = outcomes[-1]
    count = 0
    for item in reversed(outcomes):
        if item != last:
            break
        count += 1
    return f"{count}{last}"


# ---------------------------------------------------------------------------
# Ledger of finished matches
# ---------------------------------------------------------------------------


def _match_entry(home, away, gh, ga, when, source):
    home_key = normalize_team_key(home)
    away_key = normalize_team_key(away)
    if not home_key or not away_key or home_key == away_key:
        return None
    if gh is None or ga is None:
        return None
    try:
        gh, ga = int(gh), int(ga)
    except (TypeError, ValueError):
        return None
    return {
        "key": f"{home_key}|{away_key}",
        "home_key": home_key,
        "away_key": away_key,
        "home": str(home or "").strip(),
        "away": str(away or "").strip(),
        "gh": gh,
        "ga": ga,
        "when": str(when or ""),
        "source": source,
    }


def collect_finished_matches(conn, extra_matches=None):
    """Every finished league match we know about, deduplicated by fixture.

    ``resultados`` (the quiniela, 15 matches per jornada) is the trusted source;
    the live panel adds the rest of the matchday for La Liga and Segunda.
    A fixture is identified by its team pair, which is unique per season, so the
    same match can never be counted twice even if both sources report it.
    """
    entries = {}

    try:
        rows = conn.execute(
            f"""
            SELECT jornada, partido_id, local, visitante, goles_local, goles_visitante,
                   status, fecha
            FROM resultados
            WHERE jornada BETWEEN 1 AND {int(CURRENT_SEASON_MAX_JORNADA)}
            ORDER BY jornada ASC, partido_id ASC
            """  # noqa: S608 - the bound is an internal int constant
        ).fetchall()
    except Exception:
        logger.exception("No se pudieron leer los resultados para la clasificación")
        rows = []

    for row in rows:
        row = dict(row)
        if not is_finished_status(row.get("status")):
            continue
        entry = _match_entry(
            row.get("local"),
            row.get("visitante"),
            row.get("goles_local"),
            row.get("goles_visitante"),
            row.get("fecha"),
            "quiniela",
        )
        if entry:
            entries.setdefault(entry["key"], entry)

    for match in list(extra_matches or []) + _load_panel_matches():
        entry = _panel_entry(match)
        if entry:
            entries.setdefault(entry["key"], entry)

    return list(entries.values())


def _load_panel_matches():
    for path in (
        os.path.join(config.DATA_DIR, "LIVE_ALL_MATCHES_V3.json"),
        os.path.join(config.BASE_DIR, "LIVE_ALL_MATCHES_V3.json"),
        os.path.join(config.DATA_DIR, "LIVE_ALL_MATCHES.json"),
    ):
        if not os.path.exists(path):
            continue
        data = safe_read_json(path, None)
        if isinstance(data, list) and data:
            return data
    return []


def _panel_competition(match):
    raw = match.get("competition_name") or (match.get("competition") or {}).get("name") or ""
    return LEAGUE_CATEGORY.get(str(raw).strip().upper())


def _panel_entry(match, allow_live=False):
    if not isinstance(match, dict):
        return None
    if not _panel_competition(match):
        return None
    status = match.get("status")
    if not (is_finished_status(status) or (allow_live and is_live_status(status))):
        return None
    home = match.get("local") or match.get("home_name") or (match.get("home") or {}).get("name")
    away = match.get("visitante") or match.get("away_name") or (match.get("away") or {}).get("name")
    gh = match.get("goles_local")
    ga = match.get("goles_visitante")
    if gh is None or ga is None:
        gh, ga = parse_score_text(
            match.get("score") or match.get("marcador") or (match.get("scores") or {}).get("score")
        )
    entry = _match_entry(home, away, gh, ga, match.get("added") or match.get("fecha_raw"), "panel")
    if entry:
        entry["live"] = bool(not is_finished_status(status))
    return entry


def collect_live_matches(conn, extra_matches=None):
    """Matches being played right now, with their provisional score."""
    entries = {}
    try:
        rows = conn.execute(
            f"""
            SELECT local, visitante, goles_local, goles_visitante, status, fecha
            FROM resultados
            WHERE jornada BETWEEN 1 AND {int(CURRENT_SEASON_MAX_JORNADA)}
            """  # noqa: S608 - the bound is an internal int constant
        ).fetchall()
    except Exception:
        rows = []
    for row in rows:
        row = dict(row)
        if not is_live_status(row.get("status")):
            continue
        entry = _match_entry(
            row.get("local"),
            row.get("visitante"),
            row.get("goles_local"),
            row.get("goles_visitante"),
            row.get("fecha"),
            "quiniela",
        )
        if entry:
            entry["live"] = True
            entries.setdefault(entry["key"], entry)

    for match in list(extra_matches or []) + _load_panel_matches():
        entry = _panel_entry(match, allow_live=True)
        if entry and entry.get("live"):
            entries.setdefault(entry["key"], entry)
    return list(entries.values())


# ---------------------------------------------------------------------------
# Table computation
# ---------------------------------------------------------------------------


def compute_table(matches, roster_names):
    """Build a table for one category from a list of finished matches."""
    by_key = {normalize_team_key(name): name for name in roster_names}
    rows = {key: _empty_row(name) for key, name in by_key.items()}

    ordered = sorted(matches, key=lambda m: (str(m.get("when") or ""), m.get("key") or ""))
    for match in ordered:
        home_key, away_key = match["home_key"], match["away_key"]
        if home_key not in rows or away_key not in rows:
            continue
        _apply(rows[home_key], match["gh"], match["ga"], match["when"])
        _apply(rows[away_key], match["ga"], match["gh"], match["when"])

    table = []
    for key, row in rows.items():
        outcomes = [outcome for _, outcome in row.pop("results")]
        row["dg"] = row["gf"] - row["gc"]
        row["form"] = outcomes[-5:]
        row["streak"] = _streak(outcomes)
        row["key"] = key
        table.append(row)
    return table


def sort_table(rows):
    rows.sort(
        key=lambda row: (
            -int(row.get("pts") or 0),
            -(int(row.get("gf") or 0) - int(row.get("gc") or 0)),
            -int(row.get("gf") or 0),
            str(row.get("n") or ""),
        )
    )
    for idx, row in enumerate(rows, start=1):
        row["pos"] = idx
    return rows


def merge_rows(official_row, local_row):
    """Pick the more complete of the two rows. Never sums them.

    ``official_row`` is the provider snapshot, ``local_row`` the table computed
    from our own ledger. Whichever has played more matches is the one that
    reflects reality best right now; the form/streak always comes from our
    ledger because the provider does not send it.
    """
    official_pj = int((official_row or {}).get("pj") or 0)
    local_pj = int((local_row or {}).get("pj") or 0)
    base = dict(official_row or {}) if official_pj >= local_pj else dict(local_row or {})
    source = "oficial" if official_pj >= local_pj else "calculada"
    if local_row:
        base["form"] = local_row.get("form") or []
        base["streak"] = local_row.get("streak") or ""
    base["gf"] = int(base.get("gf") or 0)
    base["gc"] = int(base.get("gc") or 0)
    base["dg"] = base["gf"] - base["gc"]
    base["source"] = source
    base["pj_oficial"] = official_pj
    base["pj_calculada"] = local_pj
    return base
