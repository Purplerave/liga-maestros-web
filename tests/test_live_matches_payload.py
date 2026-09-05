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


def test_live_before_kickoff_is_never_shown_as_live(monkeypatch):
    """Andorra-Ceuta: LIVE minuto 90 mientras su inicio (17:00) es futuro.

    La regla antigua solo miraba `kickoff + 120 min`, asi que un inicio en el
    futuro no expiraba jamas y el partido se quedaba en directo para siempre.
    """
    monkeypatch.setattr(league_matches, "today_madrid", lambda: "2026-08-16")
    monkeypatch.setattr(
        league_matches,
        "madrid_now",
        lambda: datetime(2026, 8, 16, 15, 30, tzinfo=ZoneInfo("Europe/Madrid")),
    )
    impossible = {
        "id": 6,
        "status": "IN PLAY",
        "time": "90",
        "added": "2026-08-16 17:00:00",
        "scheduled": "17:00",
        "score": "1 - 0",
        "competition_name": "SEGUNDA DIVISION",
        "home": {"name": "Andorra"},
        "away": {"name": "Ceuta"},
    }
    monkeypatch.setattr(league_matches, "_load_external_matches", lambda: [impossible])

    liga = league_matches.build_all_league_matches("", [], {}, {})
    directo = league_matches.build_live_matches([], {})

    assert liga[0]["status"] == "SCHEDULED"
    assert liga[0]["score"] == ""
    assert directo == []
    assert impossible["status"] == "IN PLAY", "no debe mutar la cache compartida"


def test_live_with_minute_ahead_of_the_clock_is_closed_as_stale(monkeypatch):
    """Cadiz-Celta Fortuna: minuto 45 cuando solo han pasado 10 minutos."""
    monkeypatch.setattr(league_matches, "today_madrid", lambda: "2026-08-16")
    monkeypatch.setattr(
        league_matches,
        "madrid_now",
        lambda: datetime(2026, 8, 16, 19, 10, tzinfo=ZoneInfo("Europe/Madrid")),
    )
    frozen = {
        "id": 7,
        "status": "IN PLAY",
        "time": "45",
        "added": "2026-08-16 19:00:00",
        "scheduled": "19:00",
        "score": "2 - 1",
        "competition_name": "SEGUNDA DIVISION",
        "home": {"name": "Cádiz"},
        "away": {"name": "Celta Fortuna"},
    }
    monkeypatch.setattr(league_matches, "_load_external_matches", lambda: [frozen])

    liga = league_matches.build_all_league_matches("", [], {}, {})

    assert liga[0]["status"] == "STALE"
    assert liga[0]["score"] == "2 - 1", "el marcador se conserva, no se inventa un FT"
    assert league_matches.build_live_matches([], {}) == []


def test_live_without_provider_updates_for_thirty_minutes_is_closed(monkeypatch):
    monkeypatch.setattr(league_matches, "today_madrid", lambda: "2026-08-16")
    monkeypatch.setattr(
        league_matches,
        "madrid_now",
        lambda: datetime(2026, 8, 16, 20, 15, tzinfo=ZoneInfo("Europe/Madrid")),
    )
    frozen = {
        "id": 8,
        "status": "IN PLAY",
        "time": "60",
        "added": "2026-08-16 19:00:00",
        "scheduled": "19:00",
        "score": "1 - 1",
        "updated_at": "2026-08-16T19:40:00",
        "competition_name": "LA LIGA",
        "home": {"name": "Celta"},
        "away": {"name": "Osasuna"},
    }
    monkeypatch.setattr(league_matches, "_load_external_matches", lambda: [frozen])

    assert league_matches.build_all_league_matches("", [], {}, {})[0]["status"] == "STALE"


def test_same_match_from_quiniela_and_panel_is_not_duplicated_in_directo(monkeypatch):
    """El directo mostraba el mismo partido dos veces: una en su grupo real
    (LA LIGA, copia del panel externo con id numerico) y otra en FRIENDLIES
    (copia de la quiniela con id ``quiniela-*``), porque la dedup solo
    comparaba ids y cada fuente usa ids distintos para el mismo partido.
    """
    monkeypatch.setattr(league_matches, "today_madrid", lambda: "2026-08-23")
    monkeypatch.setattr(
        league_matches,
        "madrid_now",
        lambda: datetime(2026, 8, 23, 20, 0, tzinfo=ZoneInfo("Europe/Madrid")),
    )
    monkeypatch.setattr(
        league_matches,
        "_load_external_matches",
        lambda: [
            {
                "id": 777,
                "fixture_id": 777,
                "status": "IN PLAY",
                "time": "55",
                "added": "2026-08-23 19:00:00",
                "scheduled": "19:00",
                "score": "1 - 0",
                "competition_name": "LA LIGA",
                "home": {"name": "Celta"},
                "away": {"name": "Osasuna"},
            }
        ],
    )
    partidos = [
        {
            "id": 3,
            "local": "Celta",
            "visitante": "Osasuna",
            "status": "LIVE",
            "minuto": "55",
            "marcador": "1-0 (55')",
            "fecha_raw": "2026-08-23",
            "hora": "19:00",
            "logo_local": "",
            "logo_visitante": "",
        }
    ]
    standings_db = {"primera": {"CELTA DE VIGO": {}, "OSASUNA": {}}, "segunda": {}}

    matches = league_matches.build_live_matches(partidos, {}, standings_db)

    assert len(matches) == 1, "el mismo partido no puede salir dos veces en DIRECTO"
    assert matches[0]["competition_name"] == "LA LIGA", "la copia ganadora lleva su liga real, no FRIENDLIES"


def test_quiniela_live_match_keeps_its_real_competition(monkeypatch):
    """Sin standings_db el partido de la quiniela se etiquetaba FRIENDLIES y
    abria un grupo fantasma en DIRECTO; con el standings_db de la ruta debe
    conservar su liga aunque no exista copia en el panel externo."""
    monkeypatch.setattr(league_matches, "today_madrid", lambda: "2026-08-23")
    monkeypatch.setattr(
        league_matches,
        "madrid_now",
        lambda: datetime(2026, 8, 23, 20, 0, tzinfo=ZoneInfo("Europe/Madrid")),
    )
    monkeypatch.setattr(league_matches, "_load_external_matches", lambda: [])
    partidos = [
        {
            "id": 7,
            "local": "Celta",
            "visitante": "Osasuna",
            "status": "LIVE",
            "minuto": "55",
            "marcador": "1-0 (55')",
            "fecha_raw": "2026-08-23",
            "hora": "19:00",
            "logo_local": "",
            "logo_visitante": "",
        }
    ]
    standings_db = {"primera": {"CELTA DE VIGO": {}, "OSASUNA": {}}, "segunda": {}}

    matches = league_matches.build_live_matches(partidos, {}, standings_db)

    assert len(matches) == 1
    assert matches[0]["competition_name"] == "LA LIGA"


def test_genuine_live_match_with_fresh_data_stays_in_directo(monkeypatch):
    monkeypatch.setattr(league_matches, "today_madrid", lambda: "2026-08-16")
    monkeypatch.setattr(
        league_matches,
        "madrid_now",
        lambda: datetime(2026, 8, 16, 19, 50, tzinfo=ZoneInfo("Europe/Madrid")),
    )
    running = {
        "id": 9,
        "status": "IN PLAY",
        "time": "45",
        "added": "2026-08-16 19:00:00",
        "scheduled": "19:00",
        "score": "1 - 0",
        "updated_at": "2026-08-16T19:49:00",
        "competition_name": "LA LIGA",
        "home": {"name": "Celta"},
        "away": {"name": "Osasuna"},
    }
    monkeypatch.setattr(league_matches, "_load_external_matches", lambda: [running])

    assert league_matches.build_all_league_matches("", [], {}, {})[0]["status"] == "IN PLAY"
    assert len(league_matches.build_live_matches([], {})) == 1


def test_live_match_different_date_than_today_madrid_is_included(monkeypatch):
    """Un partido en directo cuyo fecha_raw/added tenga fecha diferente a today_madrid no se descarta."""
    monkeypatch.setattr(league_matches, "today_madrid", lambda: "2026-09-05")
    monkeypatch.setattr(
        league_matches,
        "madrid_now",
        lambda: datetime(2026, 8, 16, 21, 35, tzinfo=ZoneInfo("Europe/Madrid")),
    )
    partidos = [
        {
            "id": 1,
            "local": "Real Madrid",
            "visitante": "Barcelona",
            "status": "LIVE",
            "minuto": "35",
            "marcador": "1-0",
            "fecha_raw": "2026-08-16",
            "hora": "21:00",
            "logo_local": "",
            "logo_visitante": "",
        }
    ]
    matches = league_matches.build_live_matches(partidos, {})
    assert len(matches) == 1
    assert matches[0]["local"] == "Real Madrid"
