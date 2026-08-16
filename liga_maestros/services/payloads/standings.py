"""Build the Primera/Segunda standings payload.

The table is never produced by adding finished matches on top of the official
snapshot (that double counted every match the provider had already processed).
It is produced by ``services.standings_engine``: our own deduplicated ledger of
finished matches is compared with the provider snapshot team by team and the
more complete of the two wins. See that module for the full rationale.
"""

from ...utils import load_standings_override, normalize_team_key
from ..season_rosters import LALIGA_2026_27, SEGUNDA_2026_27
from ..standings_engine import (
    collect_finished_matches,
    collect_live_matches,
    compute_table,
    merge_rows,
    sort_table,
)

ROSTERS = {"primera": LALIGA_2026_27, "segunda": SEGUNDA_2026_27}


def build_standings_payload(conn, partidos=None, extra_matches=None):
    """Return ``(standings, standings_db)``.

    ``standings`` holds the merged, ranked table per category.
    ``standings_db`` maps a normalized team key to its row and is used
    elsewhere to work out which competition a fixture belongs to.
    """
    official = _official_rows_by_category(conn)
    finished = collect_finished_matches(conn, extra_matches=extra_matches)
    live = collect_live_matches(conn, extra_matches=extra_matches)

    standings = {}
    standings_db = {}
    for category, roster in ROSTERS.items():
        roster_keys = {normalize_team_key(name) for name in roster}
        category_matches = [
            match for match in finished if match["home_key"] in roster_keys and match["away_key"] in roster_keys
        ]
        computed = {row["key"]: row for row in compute_table(category_matches, roster)}
        official_rows = {normalize_team_key(row.get("n")): row for row in official.get(category, [])}

        rows = []
        for name in roster:
            key = normalize_team_key(name)
            row = merge_rows(official_rows.get(key), computed.get(key))
            row["n"] = name
            row["key"] = key
            row.setdefault("racha", row.get("streak") or "")
            rows.append(row)

        _annotate_live(rows, live, roster_keys)
        sort_table(rows)
        standings[category] = rows
        standings_db[category] = {row["key"]: row for row in rows}

    return standings, standings_db


def persist_standings(conn, standings):
    """Write the computed table into ``clasificacion``.

    The table is derived data, but other features (the "jornada de liga"
    indicator, exports, the admin panel) read the database directly. Writing
    the already-merged result keeps every consumer on the same numbers instead
    of letting each one recompute — and get — a different table.
    """
    updated = 0
    try:
        for category, rows in standings.items():
            division = 1 if category == "primera" else 2
            for row in rows:
                cursor = conn.execute(
                    """
                    UPDATE clasificacion
                    SET pj = ?, pg = ?, pe = ?, pp = ?, gf = ?, gc = ?, pts = ?, pos = ?, racha = ?
                    WHERE equipo = ? AND division = ?
                    """,
                    (
                        int(row.get("pj") or 0),
                        int(row.get("pg") or 0),
                        int(row.get("pe") or 0),
                        int(row.get("pp") or 0),
                        int(row.get("gf") or 0),
                        int(row.get("gc") or 0),
                        int(row.get("pts") or 0),
                        int(row.get("pos") or 0),
                        row.get("streak") or "",
                        row.get("n"),
                        division,
                    ),
                )
                updated += cursor.rowcount
        conn.commit()
    except Exception:  # pragma: no cover - persistence must never break the page
        try:
            conn.rollback()
        except Exception:
            pass
        return 0
    return updated


def matchday_played(standings):
    """How many league matchdays have actually been played (max PJ).

    Using the maximum rather than the average means a Monday-night fixture does
    not drag the whole league back to the previous matchday.
    """
    played = [int(row.get("pj") or 0) for rows in standings.values() for row in rows]
    return max(played) if played else 0


def _annotate_live(rows, live_matches, roster_keys):
    """Flag teams currently playing so the table can show a live badge.

    A live match never changes points: it is shown as extra information
    (``en_juego`` plus the provisional score) so the table stays truthful.
    """
    by_key = {row["key"]: row for row in rows}
    for match in live_matches:
        if match["home_key"] not in roster_keys or match["away_key"] not in roster_keys:
            continue
        home = by_key.get(match["home_key"])
        away = by_key.get(match["away_key"])
        if home is not None:
            home["en_juego"] = True
            home["marcador_live"] = f"{match['gh']}-{match['ga']}"
        if away is not None:
            away["en_juego"] = True
            away["marcador_live"] = f"{match['ga']}-{match['gh']}"


def _official_rows_by_category(conn):
    """Provider/official snapshot: the BASE files, falling back to the table."""
    override = load_standings_override() or {}
    official = {}
    for category in ROSTERS:
        rows = [row for row in (override.get(category) or []) if row.get("n")]
        official[category] = [
            {
                "n": row.get("n"),
                "pj": int(row.get("pj") or 0),
                "pg": int(row.get("pg") or 0),
                "pe": int(row.get("pe") or 0),
                "pp": int(row.get("pp") or 0),
                "gf": int(row.get("gf") or 0),
                "gc": int(row.get("gc") or 0),
                "pts": int(row.get("pts") or 0),
                "racha": row.get("racha") or "",
                "base_oficial": True,
            }
            for row in rows
        ]
        if official[category]:
            continue
        official[category] = _rows_from_db(conn, 1 if category == "primera" else 2)
    return official


def _rows_from_db(conn, division):
    try:
        rows = conn.execute(
            "SELECT * FROM clasificacion WHERE division = ? ORDER BY pos ASC",
            (division,),
        ).fetchall()
    except Exception:
        return []
    result = []
    for row in rows:
        keys = row.keys()
        result.append(
            {
                "n": row["equipo"],
                "pj": int(row["pj"] or 0),
                "pg": int(row["pg"] or 0),
                "pe": int(row["pe"] or 0),
                "pp": int(row["pp"] or 0),
                "gf": int(row["gf"] or 0),
                "gc": int(row["gc"] or 0),
                "pts": int(row["pts"] or 0),
                "racha": (row["racha"] if "racha" in keys else "") or "",
            }
        )
    return result
