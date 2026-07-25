from liga_maestros.services.payloads import league_matches


def test_live_payload_keeps_all_current_competitions(monkeypatch):
    monkeypatch.setattr(league_matches, "today_madrid", lambda: "2026-07-25")
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
