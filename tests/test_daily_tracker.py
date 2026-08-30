"""Tests for the daily league tracker (agenda, live windows, stats history)."""

import json

import config
from liga_maestros.services import daily_matches


def _sample_api_match(match_id=101, league="LA LIGA", finished=False, kickoff="2026-08-15T19:30:00.000Z"):
    return {
        "id": match_id,
        "_competition_name": league,
        "date": kickoff,
        "homeTeam": {"name": "CD Castellón", "logo": "castellon.png"},
        "awayTeam": {"name": "Real Zaragoza", "logo": "zaragoza.png"},
        "state": {
            "description": "Finished" if finished else "Not started",
            "score": {"current": "2 - 1" if finished else ""},
        },
        "league": {"name": league},
    }


def _patch_data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))


def test_agenda_fetches_once_per_day(tmp_path, monkeypatch):
    _patch_data_dir(tmp_path, monkeypatch)
    calls = []

    def fake_fetch(date_text=None):
        calls.append(date_text)
        return [_sample_api_match()]

    monkeypatch.setattr(daily_matches, "fetch_today_agenda", fake_fetch)
    monkeypatch.setattr(daily_matches, "today_madrid", lambda: "2026-08-15")

    first = daily_matches.refresh_daily_agenda()
    second = daily_matches.refresh_daily_agenda()

    assert len(calls) == 1, "The agenda must hit the API only once per day"
    assert first["date"] == "2026-08-15"
    assert second["matches"] == first["matches"]
    assert first["matches"][0]["home"] == "CD Castellón"


def test_agenda_feeds_live_panel_with_scheduled_matches(tmp_path, monkeypatch):
    _patch_data_dir(tmp_path, monkeypatch)
    monkeypatch.setattr(daily_matches, "fetch_today_agenda", lambda date_text=None: [_sample_api_match()])
    monkeypatch.setattr(daily_matches, "today_madrid", lambda: "2026-08-15")

    daily_matches.refresh_daily_agenda(force=True)

    panel = json.loads((tmp_path / "LIVE_ALL_MATCHES_V3.json").read_text(encoding="utf-8"))
    assert len(panel) == 1
    assert panel[0]["home"]["name"] == "CD Castellón"
    assert panel[0]["competition_name"] == "LA LIGA"


def test_live_window_detection(tmp_path, monkeypatch):
    _patch_data_dir(tmp_path, monkeypatch)
    from datetime import datetime
    from zoneinfo import ZoneInfo

    madrid = ZoneInfo("Europe/Madrid")

    # Kickoff at 19:30 UTC -> window open at 21:00 Madrid (UTC+2 in August).
    agenda = {
        "date": "2026-08-15",
        "matches": [{"id": 1, "kickoff": "2026-08-15T19:30:00.000Z"}],
    }

    monkeypatch.setattr(
        daily_matches,
        "madrid_now",
        lambda: datetime(2026, 8, 15, 22, 0, tzinfo=madrid),
    )
    assert daily_matches.any_live_window_open(agenda) is True

    monkeypatch.setattr(
        daily_matches,
        "madrid_now",
        lambda: datetime(2026, 8, 15, 10, 0, tzinfo=madrid),
    )
    assert daily_matches.any_live_window_open(agenda) is False

    # 3h+ after kickoff the window closes again.
    monkeypatch.setattr(
        daily_matches,
        "madrid_now",
        lambda: datetime(2026, 8, 16, 1, 40, tzinfo=madrid),
    )
    assert daily_matches.any_live_window_open(agenda) is False


def test_finished_matches_are_archived_once_with_statistics(tmp_path, monkeypatch):
    _patch_data_dir(tmp_path, monkeypatch)
    stats_calls = []

    def fake_stats(match_id):
        stats_calls.append(match_id)
        return [
            {"team": {"name": "CD Castellón"}, "statistics": [{"displayName": "Ball possession", "value": "58%"}]},
            {"team": {"name": "Real Zaragoza"}, "statistics": [{"displayName": "Ball possession", "value": "42%"}]},
        ]

    monkeypatch.setattr(daily_matches, "fetch_match_statistics", fake_stats)
    monkeypatch.setattr(daily_matches, "_update_db_match_stats", lambda record: False)

    finished = _sample_api_match(match_id=555, finished=True)
    added_first = daily_matches.archive_finished_matches([finished])
    added_second = daily_matches.archive_finished_matches([finished])

    assert added_first == 1
    assert added_second == 0, "A finished match must be archived exactly once"
    assert stats_calls == [555]

    history = daily_matches.history_path()
    lines = open(history, encoding="utf-8").read().strip().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["match_id"] == 555
    assert record["home"] == "CD Castellón"
    assert record["score"] == "2 - 1"
    assert record["statistics"][0]["statistics"][0]["value"] == "58%"


def test_unfinished_matches_are_not_archived(tmp_path, monkeypatch):
    _patch_data_dir(tmp_path, monkeypatch)
    monkeypatch.setattr(
        daily_matches,
        "fetch_match_statistics",
        lambda match_id: (_ for _ in ()).throw(AssertionError("must not fetch stats for unfinished matches")),
    )

    live = _sample_api_match(match_id=777, finished=False)
    assert daily_matches.archive_finished_matches([live]) == 0


def test_daily_tick_skips_scores_when_no_window_open(tmp_path, monkeypatch):
    _patch_data_dir(tmp_path, monkeypatch)
    monkeypatch.setattr(
        daily_matches,
        "refresh_daily_agenda",
        lambda force=False: {"date": "2026-08-15", "matches": []},
    )
    monkeypatch.setattr(daily_matches, "any_live_window_open", lambda agenda=None: False)
    monkeypatch.setattr(
        daily_matches,
        "refresh_live_scores",
        lambda: (_ for _ in ()).throw(AssertionError("must not refresh scores while idle")),
    )

    summary = daily_matches.run_daily_tick()
    assert summary["window_open"] is False
    assert summary["panel"] == 0


def test_daily_tick_refreshes_scores_when_window_open(tmp_path, monkeypatch):
    _patch_data_dir(tmp_path, monkeypatch)
    monkeypatch.setattr(
        daily_matches,
        "refresh_daily_agenda",
        lambda force=False: {"date": "2026-08-15", "matches": [{"id": 1}]},
    )
    monkeypatch.setattr(daily_matches, "any_live_window_open", lambda agenda=None: True)
    monkeypatch.setattr(daily_matches, "refresh_live_scores", lambda: 3)

    summary = daily_matches.run_daily_tick()
    assert summary["window_open"] is True
    assert summary["panel"] == 3


def test_cleanup_removes_only_old_agendas(tmp_path, monkeypatch):
    _patch_data_dir(tmp_path, monkeypatch)
    from datetime import datetime
    from zoneinfo import ZoneInfo

    monkeypatch.setattr(
        daily_matches,
        "madrid_now",
        lambda: datetime(2026, 8, 15, 12, 0, tzinfo=ZoneInfo("Europe/Madrid")),
    )

    old = tmp_path / "DAILY_AGENDA_2026-08-01.json"
    fresh = tmp_path / "DAILY_AGENDA_2026-08-14.json"
    old.write_text("{}", encoding="utf-8")
    fresh.write_text("{}", encoding="utf-8")

    daily_matches.cleanup_old_agendas(keep_days=7)

    assert not old.exists()
    assert fresh.exists()


def test_agenda_never_calls_api_without_quota(tmp_path, monkeypatch):
    _patch_data_dir(tmp_path, monkeypatch)
    monkeypatch.setenv("HIGHLIGHTLY_API_KEY", "test-key")
    monkeypatch.setattr(daily_matches, "reserve_highlightly_calls", lambda count=1: False)
    monkeypatch.setattr(daily_matches, "get_highlightly_circuit", lambda: {"open": False})
    monkeypatch.setattr(
        daily_matches.requests,
        "get",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("unreserved API call")),
    )

    assert daily_matches.fetch_today_agenda("2026-08-15") == []


def test_agenda_respects_open_circuit(tmp_path, monkeypatch):
    _patch_data_dir(tmp_path, monkeypatch)
    monkeypatch.setenv("HIGHLIGHTLY_API_KEY", "test-key")
    monkeypatch.setattr(daily_matches, "get_highlightly_circuit", lambda: {"open": True})
    monkeypatch.setattr(
        daily_matches.requests,
        "get",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("call with open circuit")),
    )

    assert daily_matches.fetch_today_agenda("2026-08-15") == []


def test_backfill_adds_finished_matches_from_recent_days_once(tmp_path, monkeypatch):
    _patch_data_dir(tmp_path, monkeypatch)
    monkeypatch.setattr(daily_matches, "today_madrid", lambda: "2026-08-17")

    def fake_api_get(path, params):
        assert params["date"] in ("2026-08-16", "2026-08-15", "2026-08-14")
        return {
            "data": [
                {
                    "id": 42,
                    "date": f"{params['date']}T17:00:00.000Z",
                    "league": {"name": "Segunda División"},
                    "homeTeam": {"name": "Castellón", "logo": None},
                    "awayTeam": {"name": "R. Sociedad B", "logo": None},
                    "state": {"description": "FINISHED", "score": {"current": "1 - 0"}},
                }
            ]
        }

    monkeypatch.setattr(daily_matches, "_api_get", fake_api_get)

    # 3 dias x 3 ligas (La Liga, Segunda, Liga F): el fake devuelve el mismo partido para todas.
    assert daily_matches.backfill_recent_spanish_matches(days=3) == 9

    panel = json.loads((tmp_path / "LIVE_ALL_MATCHES_V3.json").read_text(encoding="utf-8"))
    # Con 3 ligas el ID 42 se sobrescribe; la ultima liga que escribe gana (LIGA F)
    assert any(m["id"] == 42 and m["competition_name"] in ("SEGUNDA DIVISION", "LIGA F", "LA LIGA") for m in panel)

    # Cada fecha se rellena una sola vez.
    assert daily_matches.backfill_recent_spanish_matches(days=3) == 0
