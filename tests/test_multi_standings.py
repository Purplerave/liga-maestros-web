import json

from liga_maestros.services import highlightly_standings, multi_standings
from liga_maestros.services.season_rosters import LALIGA_2026_27, SEGUNDA_2026_27
from liga_maestros.utils import normalize_team_key


def test_official_standings_include_only_relevant_logo_data(monkeypatch):
    monkeypatch.setattr(multi_standings, "_load_cache", lambda: [])
    monkeypatch.setattr(
        multi_standings,
        "fetch_highlightly_standings",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("network call")),
    )

    standings = {
        "primera": [
            {
                "n": "Atletico Madrid",
                "pos": 1,
                "pj": 1,
                "pg": 1,
                "pe": 0,
                "pp": 0,
                "gf": 2,
                "gc": 0,
                "pts": 3,
            }
        ],
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

    assert result[0].get("season") == "2026-27"

    assert result[0]["name"] == "PREMIER LEAGUE"
    assert saved == [result]


def test_refresh_all_standings_covers_spanish_and_foreign_leagues(monkeypatch):
    """Daily refresh must update Spanish BASE files AND the foreign cache."""
    monkeypatch.setattr(multi_standings, "refresh_spanish_standings", lambda season: ["primera", "segunda"])
    monkeypatch.setattr(
        multi_standings,
        "refresh_external_standings",
        lambda season: [
            {"name": "PREMIER LEAGUE", "teams": []},
            {"name": "BUNDESLIGA", "teams": []},
            {"name": "LIGUE 1", "teams": []},
        ],
    )

    summary = multi_standings.refresh_all_standings(season=2026)

    assert summary["spanish"] == ["primera", "segunda"]
    assert summary["external"] == ["PREMIER LEAGUE", "BUNDESLIGA", "LIGUE 1"]


def _provider_row(name, pos, **stats):
    return {
        "n": name,
        "pos": pos,
        "pj": 0,
        "pg": 0,
        "pe": 0,
        "pp": 0,
        "gf": 0,
        "gc": 0,
        "pts": 0,
        **stats,
    }


def test_spanish_refresh_matches_all_provider_names_and_keeps_official_display_names(tmp_path, monkeypatch):
    """Highlightly aliases must not make either complete Spanish league get discarded."""
    primera_variants = {
        "FC Barcelona": "Barcelona",
        "Villarreal CF": "Villarreal",
        "Atlético de Madrid": "Atletico Madrid",
        "Celta": "Celta Vigo",
        "Getafe CF": "Getafe",
        "Valencia CF": "Valencia",
        "RCD Espanyol de Barcelona": "Espanyol",
        "Athletic Club": "Athletic Bilbao",
        "Sevilla FC": "Sevilla",
        "Deportivo Alavés": "Alaves",
        "Elche CF": "Elche",
        "Levante UD": "Levante",
        "CA Osasuna": "Osasuna",
        "R. Racing Club": "Racing Santander",
        "RC Deportivo": "Deportivo La Coruña",
        "Málaga CF": "Malaga",
    }
    segunda_variants = {
        "RCD Mallorca": "Mallorca",
        "Girona FC": "Girona",
        "Real Oviedo": "Oviedo",
        "UD Almería": "Almeria",
        "UD Las Palmas": "Las Palmas",
        "CD Castellón": "Castellon",
        "Burgos CF": "Burgos",
        "SD Eibar": "Eibar",
        "Córdoba CF": "Cordoba",
        "Albacete BP": "Albacete Balompie",
        "AD Ceuta FC": "Ceuta",
        "FC Andorra": "Andorra",
        "Real Sporting": "Sporting Gijon",
        "Granada CF": "Granada",
        "R. Sociedad B": "Real Sociedad II",
        "Real Valladolid CF": "Real Valladolid",
        "Cádiz CF": "Cadiz",
        "CD Leganés": "Leganes",
        "CD Tenerife": "Tenerife",
        "CD Eldense": "Eldense",
        "CE Sabadell": "Sabadell",
        "Celta Fortuna": "Celta de Vigo B",
    }

    primera = [_provider_row(primera_variants.get(name, name), pos) for pos, name in enumerate(LALIGA_2026_27, 1)]
    segunda_by_official = {
        name: _provider_row(segunda_variants.get(name, name), pos) for pos, name in enumerate(SEGUNDA_2026_27, 1)
    }
    segunda_by_official["CD Castellón"].update(pj=1, pg=1, gf=1, gc=0, pts=3)
    segunda_by_official["R. Sociedad B"].update(pj=1, pp=1, gf=0, gc=1, pts=0)
    # Reproduce provider ranking order after Castellón's 0-1 win.
    segunda = [segunda_by_official["CD Castellón"]]
    segunda.extend(row for name, row in segunda_by_official.items() if name not in {"CD Castellón", "R. Sociedad B"})
    segunda.append(segunda_by_official["R. Sociedad B"])
    for pos, row in enumerate(segunda, 1):
        row["pos"] = pos

    assert {normalize_team_key(row["n"]) for row in primera} == {normalize_team_key(name) for name in LALIGA_2026_27}
    assert {normalize_team_key(row["n"]) for row in segunda} == {normalize_team_key(name) for name in SEGUNDA_2026_27}

    monkeypatch.setattr(multi_standings.config, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(
        multi_standings.config,
        "HIGHLIGHTLY_LEAGUES",
        {"LA LIGA": 101, "SEGUNDA DIVISION": 202},
    )
    monkeypatch.setattr(
        multi_standings,
        "fetch_highlightly_standings",
        lambda league_id, season: primera if league_id == 101 else segunda,
    )

    result = multi_standings.refresh_spanish_standings(season=2026)

    assert result == ["primera", "segunda"]
    assert result.skipped == []
    assert result.failures == []
    with open(tmp_path / "STANDINGS_SEGUNDA_BASE.json", encoding="utf-8") as fh:
        saved = json.load(fh)
    by_name = {row["n"]: row for row in saved}
    assert set(by_name) == set(SEGUNDA_2026_27)
    assert "Real Sociedad II" not in by_name
    assert "Celta de Vigo B" not in by_name
    assert by_name["CD Castellón"] == {
        "pos": 1,
        "n": "CD Castellón",
        "pj": 1,
        "pg": 1,
        "pe": 0,
        "pp": 0,
        "gf": 1,
        "gc": 0,
        "pts": 3,
    }


def test_spanish_refresh_reports_roster_mismatch_instead_of_overwriting_file(tmp_path, monkeypatch):
    path = tmp_path / "STANDINGS_SEGUNDA_BASE.json"
    path.write_text('[{"n": "datos anteriores", "pts": 9}]', encoding="utf-8")
    invalid_segunda = [_provider_row(name, pos) for pos, name in enumerate(SEGUNDA_2026_27, 1)]
    invalid_segunda[-1]["n"] = "Equipo desconocido"

    monkeypatch.setattr(multi_standings.config, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(
        multi_standings.config,
        "HIGHLIGHTLY_LEAGUES",
        {"LA LIGA": 101, "SEGUNDA DIVISION": 202},
    )
    monkeypatch.setattr(
        multi_standings,
        "fetch_highlightly_standings",
        lambda league_id, season: [] if league_id == 101 else invalid_segunda,
    )

    result = multi_standings.refresh_spanish_standings(season=2026)

    assert result == []
    assert {item["code"] for item in result.skipped} == {"no_data", "roster_mismatch"}
    mismatch = next(item for item in result.skipped if item["code"] == "roster_mismatch")
    assert mismatch["league"] == "SEGUNDA DIVISION"
    assert mismatch["unexpected_teams"] == ["Equipo desconocido"]
    assert "Celta Fortuna" in mismatch["missing_teams"]
    assert json.loads(path.read_text(encoding="utf-8"))[0]["pts"] == 9


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
            return {
                "groups": [
                    {
                        "standings": [
                            {
                                "team": {"name": "Liverpool", "logo": "logo.png"},
                                "total": {
                                    "games": 3,
                                    "wins": 2,
                                    "draws": 1,
                                    "loses": 0,
                                    "scoredGoals": 7,
                                    "receivedGoals": 2,
                                },
                            }
                        ]
                    }
                ]
            }

    successes = []
    monkeypatch.setenv("HIGHLIGHTLY_API_KEY", "test-key")
    monkeypatch.setattr(highlightly_standings, "reserve_highlightly_calls", lambda count: count == 1)
    monkeypatch.setattr(highlightly_standings, "record_highlightly_success", lambda: successes.append(True))
    monkeypatch.setattr(highlightly_standings.requests, "get", lambda *args, **kwargs: Response())

    rows = highlightly_standings.fetch_highlightly_standings(1, season=2026)

    assert successes == [True]
    assert rows == [
        {
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
        }
    ]
