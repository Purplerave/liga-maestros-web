import json
import os
import sqlite3

import config
from liga_maestros.db.migrations import ensure_clasificacion_zero, ensure_core_tables
from liga_maestros.services.season_rosters import (
    BUNDESLIGA_2026_27,
    LALIGA_2026_27,
    LIGUE1_2026_27,
    PREMIER_2026_27,
    SEGUNDA_2026_27,
    is_stale_external_cache,
    merge_official_stats,
    replace_clasificacion_from_roster,
)


def _names(path, key=None):
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    rows = data[key] if key else data
    return [row["n"] for row in rows]


def test_laliga_base_has_2026_27_promoted_sides():
    names = _names(os.path.join(config.SEED_DATA_DIR, "STANDINGS_LALIGA_BASE.json"))
    assert names == LALIGA_2026_27
    assert "R. Racing Club" in names
    assert "RC Deportivo" in names
    assert "Málaga CF" in names
    assert "RCD Mallorca" not in names
    assert "Girona FC" not in names
    assert "Real Oviedo" not in names
    assert len(names) == 20


def test_segunda_base_has_2026_27_promoted_and_relegated_sides():
    names = _names(os.path.join(config.SEED_DATA_DIR, "STANDINGS_SEGUNDA_BASE.json"))
    assert names == SEGUNDA_2026_27
    assert "RCD Mallorca" in names
    assert "Girona FC" in names
    assert "Real Oviedo" in names
    assert "CD Tenerife" in names
    assert "CD Eldense" in names
    assert "CE Sabadell" in names
    assert "Celta Fortuna" in names
    assert "R. Racing Club" not in names
    assert "RC Deportivo" not in names
    assert "Málaga CF" not in names
    assert "CD Mirandés" not in names
    assert "Real Zaragoza" not in names
    assert len(names) == 22


def test_foreign_cache_is_reset_for_new_season():
    with open(config.SEED_DATA_DIR + "/MULTI_STANDINGS.json", encoding="utf-8") as fh:
        payload = json.load(fh)
    assert payload["season"] == "2026-27"
    by_name = {league["name"]: league for league in payload["leagues"]}
    assert [team["n"] for team in by_name["PREMIER LEAGUE"]["teams"]] == PREMIER_2026_27
    assert [team["n"] for team in by_name["BUNDESLIGA"]["teams"]] == BUNDESLIGA_2026_27
    assert [team["n"] for team in by_name["LIGUE 1"]["teams"]] == LIGUE1_2026_27
    assert "West Ham" not in {team["n"] for team in by_name["PREMIER LEAGUE"]["teams"]}
    assert "Nantes" not in {team["n"] for team in by_name["LIGUE 1"]["teams"]}
    assert all(
        int(team["pj"]) == 0 and int(team["pts"]) == 0 for league in payload["leagues"] for team in league["teams"]
    )
    assert is_stale_external_cache(payload) is False


def test_previous_season_cache_is_detected_as_stale():
    stale = {
        "season": "2025-26",
        "leagues": [
            {
                "name": "PREMIER LEAGUE",
                "teams": [{"n": "Arsenal", "pj": 38, "pts": 85}],
            }
        ],
    }
    assert is_stale_external_cache(stale) is True


def test_clasificacion_replaces_previous_season_roster():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_core_tables(conn)
    conn.execute(
        "INSERT INTO clasificacion (equipo, pj, pts, division, pos) VALUES (?, 0, 0, 1, 18)",
        ("RCD Mallorca",),
    )
    conn.execute(
        "INSERT INTO clasificacion (equipo, pj, pts, division, pos) VALUES (?, 0, 0, 2, 1)",
        ("R. Racing Club",),
    )
    conn.commit()

    assert replace_clasificacion_from_roster(conn) is True
    primera = [
        row["equipo"] for row in conn.execute("SELECT equipo FROM clasificacion WHERE division = 1 ORDER BY pos")
    ]
    segunda = [
        row["equipo"] for row in conn.execute("SELECT equipo FROM clasificacion WHERE division = 2 ORDER BY pos")
    ]
    assert primera == LALIGA_2026_27
    assert segunda == SEGUNDA_2026_27
    assert conn.execute("SELECT SUM(pts) FROM clasificacion").fetchone()[0] == 0


def test_clasificacion_keeps_live_points_when_roster_is_already_correct():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_core_tables(conn)
    replace_clasificacion_from_roster(conn)
    conn.execute("UPDATE clasificacion SET pj = 1, pts = 3, pg = 1 WHERE equipo = 'FC Barcelona'")
    conn.commit()

    ensure_clasificacion_zero(conn)

    row = conn.execute("SELECT pj, pts, pg FROM clasificacion WHERE equipo = 'FC Barcelona'").fetchone()
    assert tuple(row) == (1, 3, 1)


def test_merge_official_stats_keeps_full_roster():
    merged = merge_official_stats(
        ["FC Barcelona", "Real Madrid"],
        [{"n": "FC Barcelona", "pj": 1, "pg": 1, "pe": 0, "pp": 0, "gf": 2, "gc": 0, "pts": 3}],
    )
    assert [row["n"] for row in merged] == ["FC Barcelona", "Real Madrid"]
    assert merged[0]["pts"] == 3
    assert merged[1]["pts"] == 0
