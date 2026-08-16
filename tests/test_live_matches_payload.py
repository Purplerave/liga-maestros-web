from datetime import datetime
from zoneinfo import ZoneInfo

from liga_maestros.services.payloads import league_matches


def test_live_payload_keeps_all_current_competitions(monkeypatch):
    monkeypatch.setattr(league_matches, "today_madrid", lambda: "2026-07-25")
    monkeypatch.setattr(
        league_matches,
        "madrid_now",
        lambda: datetime(2026, 7, 25, 19, 59, tzinfo=ZoneInfo("Europe/Madrid")),
    )
    monkeypatch.setattr(
        league_matches,
        "_load_external_matches",
        lambda: [
            {
                "id": 1,
                "status": "IN PLAY",
                "added": "2026-07-25 18:00:00",
                "competition_name": "Premier League",
                "home": {"name": "A"},
                "away": {"name": "B"},
            },
            {
                "id": 2,
                "status": "HT",
                "added": "2026-07-25 19:00:00",
                "competition_name": "UEFA Champions League",
                "home": {"name": "C"},
                "away": {"name": "D"},
            },
            {
                "id": 3,
                "status": "IN PLAY",
                "added": "2026-07-24 19:00:00",
                "competition_name": "Old League",
                "home": {"name": "E"},
                "away": {"name": "F"},
            },
        ],
    )

    matches = league_matches.build_live_matches([], {})

    assert [match["id"] for match in matches] == [1, 2]
    assert {match["competition_name"] for match in matches} == {
        "Premier League",
        "UEFA Champions League",
    }


def test_stale_live_snapshot_is_closed_in_liga_and_removed_from_directo(monkeypatch):
    monkeypatch.setattr(league_matches, "today_madrid", lambda: "2026-08-15")
    monkeypatch.setattr(
        league_matches,
        "madrid_now",
        lambda: datetime(2026, 8, 15, 21, 31, tzinfo=ZoneInfo("Europe/Madrid")),
    )
    stale = {
        "id": 44,
        "status": "IN PLAY",
        "added": "2026-08-15 19:30:00",
        "scheduled": "19:30",
        "score": "2 - 1",
        "competition_name": "LA LIGA",
        "home": {"name": "A"},
        "away": {"name": "B"},
    }
    monkeypatch.setattr(league_matches, "_load_external_matches", lambda: [stale])

    liga = league_matches.build_all_league_matches("", [], {}, {})
    directo = league_matches.build_live_matches([], {})

    assert liga[0]["status"] == "STALE"
    assert liga[0]["score"] == "2 - 1"
    assert directo == []
    assert stale["status"] == "IN PLAY", "payload normalization must not mutate the shared cache"


def test_recent_live_snapshot_remains_live(monkeypatch):
    monkeypatch.setattr(league_matches, "today_madrid", lambda: "2026-08-15")
    monkeypatch.setattr(
        league_matches,
        "madrid_now",
        lambda: datetime(2026, 8, 15, 21, 0, tzinfo=ZoneInfo("Europe/Madrid")),
    )
    match = {
        "id": 45,
        "status": "HT",
        "added": "2026-08-15 19:30:00",
        "competition_name": "SEGUNDA DIVISION",
        "home": {"name": "A"},
        "away": {"name": "B"},
    }
    monkeypatch.setattr(league_matches, "_load_external_matches", lambda: [match])

    assert league_matches.build_live_matches([], {})[0]["status"] == "HT"
