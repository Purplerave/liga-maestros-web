"""Midweek Directo: external matches of today must show without the quiniela."""

from liga_maestros.services.payloads import league_matches


def _castellon_today(status="IN PLAY", score="1-0"):
    return {
        "id": 900,
        "fixture_id": 900,
        "status": status,
        "score": score,
        "added": "2026-08-15 19:30:00",
        "fecha_raw": "2026-08-15",
        "hora": "19:30",
        "competition_name": "SEGUNDA DIVISION",
        "competition": {"name": "SEGUNDA DIVISION"},
        "home": {"name": "CD Castellón"},
        "away": {"name": "Real Zaragoza"},
        "local": "CD Castellón",
        "visitante": "Real Zaragoza",
    }


def test_todays_external_match_shows_without_any_quiniela(monkeypatch):
    """A Tuesday Castellon game appears even with zero quiniela matches."""
    monkeypatch.setattr(league_matches, "today_madrid", lambda: "2026-08-15")
    monkeypatch.setattr(league_matches, "_load_external_matches", lambda: [_castellon_today()])

    result = league_matches.build_all_league_matches("", [], {}, {})

    assert len(result) == 1
    assert result[0]["local"] == "CD Castellón"


def test_todays_scheduled_match_shows_before_kickoff(monkeypatch):
    """Even before kickoff (SCHEDULED), today's fixture is listed."""
    monkeypatch.setattr(league_matches, "today_madrid", lambda: "2026-08-15")
    monkeypatch.setattr(
        league_matches,
        "_load_external_matches",
        lambda: [_castellon_today(status="SCHEDULED", score="")],
    )

    result = league_matches.build_all_league_matches("", [], {}, {})

    assert len(result) == 1
    assert result[0]["status"] == "SCHEDULED"


def test_old_external_matches_do_not_leak_outside_windows(monkeypatch):
    """Stale matches from past days stay hidden when nothing is active."""
    monkeypatch.setattr(league_matches, "today_madrid", lambda: "2026-08-20")
    monkeypatch.setattr(league_matches, "_load_external_matches", lambda: [_castellon_today()])

    result = league_matches.build_all_league_matches("", [], {}, {})

    assert result == []


def test_champions_matches_are_still_excluded(monkeypatch):
    monkeypatch.setattr(league_matches, "today_madrid", lambda: "2026-08-15")
    match = _castellon_today()
    match["competition_name"] = "UEFA CHAMPIONS LEAGUE"
    match["competition"] = {"name": "UEFA CHAMPIONS LEAGUE"}
    monkeypatch.setattr(league_matches, "_load_external_matches", lambda: [match])

    result = league_matches.build_all_league_matches("", [], {}, {})

    assert result == []
