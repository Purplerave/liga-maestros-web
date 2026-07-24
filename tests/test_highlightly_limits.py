from liga_maestros.services import highlightly_limits


def test_usage_payload_preserves_daily_reserve(monkeypatch):
    monkeypatch.setattr(highlightly_limits, "HIGHLIGHTLY_DAILY_CALL_LIMIT", 100)
    monkeypatch.setattr(highlightly_limits, "HIGHLIGHTLY_DAILY_CALL_RESERVE", 10)

    payload = highlightly_limits.highlightly_usage_payload("2026-07-24", 84)

    assert payload == {
        "date": "2026-07-24",
        "calls": 84,
        "limit": 100,
        "reserve": 10,
        "remaining": 16,
        "usable_remaining": 6,
    }


def test_circuit_opens_and_success_resets_it(tmp_path, monkeypatch):
    monkeypatch.setattr(highlightly_limits.config, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(highlightly_limits, "HIGHLIGHTLY_CIRCUIT_FAILURE_LIMIT", 3)
    monkeypatch.setattr(highlightly_limits, "HIGHLIGHTLY_CIRCUIT_COOLDOWN_SECONDS", 60)
    monkeypatch.setattr(highlightly_limits, "HIGHLIGHTLY_CIRCUIT_MAX_COOLDOWN_SECONDS", 300)

    for _ in range(3):
        highlightly_limits.record_highlightly_failure(RuntimeError("api unavailable"))

    opened = highlightly_limits.get_highlightly_circuit()
    assert opened["open"] is True
    assert opened["failures"] == 3
    assert opened["calls_since_last_success"] == 3

    highlightly_limits.record_highlightly_success()

    reset = highlightly_limits.get_highlightly_circuit()
    assert reset["open"] is False
    assert reset["failures"] == 0
    assert reset["calls_since_last_success"] == 0
