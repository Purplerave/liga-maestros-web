from liga_maestros.services import multi_standings
from liga_maestros.services import highlightly_standings


def test_official_standings_include_only_relevant_logo_data(monkeypatch):
    monkeypatch.setattr(multi_standings, "_load_cache", lambda: [])
    monkeypatch.setattr(
        multi_standings,
        "fetch_highlightly_standings",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("network call")),
    )

    standings = {
        "primera": [{
            "n": "Atletico Madrid",
            "pos": 1,
            "pj": 1,
            "pg": 1,
            "pe": 0,
            "pp": 0,
            "gf": 2,
            "gc": 0,
            "pts": 3,
        }],
        "segunda": [],
    }
    logos = {"ATLETICO MADRID": "/static/img/team_logos/ATLETICO_MADRID.png"}

    leagues = multi_standings.build_multi_league_standings(standings, logos)

    assert len(leagues) == 1
    assert leagues[0]["teams"][0]["logo"] == logos["ATLETICO MADRID"]


def test_external_standings_refresh_is_explicit(monkeypatch):
    monkeypatch.setattr(multi_standings.config, "STANDINGS_LEAGUES", {"PREMIER LEAGUE": 1})
    monkeypatch.setattr(
        multi_standings,
        "fetch_highlightly_standings",
        lambda league_id, season: [{"n": "Liverpool", "logo": "logo.png"}],
    )
    saved = []
    monkeypatch.setattr(multi_standings, "_save_cache", saved.append)

    result = multi_standings.refresh_external_standings(season=2026)

    assert result[0]["name"] == "PREMIER LEAGUE"
    assert saved == [result]


def test_cached_international_competitions_are_not_exposed(monkeypatch):
    monkeypatch.setattr(
        multi_standings,
        "_load_cache",
        lambda: [
            {"name": "PREMIER LEAGUE", "teams": [{"n": "Liverpool"}]},
            {"name": "UEFA CHAMPIONS LEAGUE", "teams": [{"n": "Arsenal"}]},
        ],
    )
    monkeypatch.setattr(
        multi_standings.config,
        "STANDINGS_LEAGUES",
        {"PREMIER LEAGUE": 1},
    )

    leagues = multi_standings.build_multi_league_standings({})

    assert [league["name"] for league in leagues] == ["PREMIER LEAGUE"]


def test_standings_client_never_calls_api_without_reserved_quota(monkeypatch):
    monkeypatch.setenv("HIGHLIGHTLY_API_KEY", "test-key")
    monkeypatch.setattr(highlightly_standings, "reserve_highlightly_calls", lambda count: False)
    monkeypatch.setattr(
        highlightly_standings.requests,
        "get",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("unreserved API call")),
    )

    assert highlightly_standings.fetch_highlightly_standings(1, season=2026) == []


def test_standings_client_records_success_and_normalizes_rows(monkeypatch):
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"groups": [{"standings": [{
                "team": {"name": "Liverpool", "logo": "logo.png"},
                "total": {
                    "games": 3,
                    "wins": 2,
                    "draws": 1,
                    "loses": 0,
                    "scoredGoals": 7,
                    "receivedGoals": 2,
                },
            }]}]}

    successes = []
    monkeypatch.setenv("HIGHLIGHTLY_API_KEY", "test-key")
    monkeypatch.setattr(highlightly_standings, "reserve_highlightly_calls", lambda count: count == 1)
    monkeypatch.setattr(highlightly_standings, "record_highlightly_success", lambda: successes.append(True))
    monkeypatch.setattr(highlightly_standings.requests, "get", lambda *args, **kwargs: Response())

    rows = highlightly_standings.fetch_highlightly_standings(1, season=2026)

    assert successes == [True]
    assert rows == [{
        "n": "Liverpool",
        "pos": 1,
        "pj": 3,
        "pg": 2,
        "pe": 1,
        "pp": 0,
        "gf": 7,
        "gc": 2,
        "dg": 5,
        "pts": 7,
        "logo": "logo.png",
        "form": [],
        "streak": "",
    }]
