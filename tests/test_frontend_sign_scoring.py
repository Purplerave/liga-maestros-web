from pathlib import Path


UTILS_JS = Path(__file__).resolve().parents[1] / "static" / "js" / "utils.js"


def test_frontend_hit_rendering_uses_multiple_sign_matching():
    source = UTILS_JS.read_text(encoding="utf-8")

    assert "function standardSignMatches(sign, real)" in source
    assert 'prediction.includes(result)' in source
    assert 'return standardSignMatches(sign, real) ? "hit" : "miss";' in source
    assert "return standardSignMatches(sign, real);" in source


def test_next_match_timestamp_combines_date_and_kickoff_time():
    source = UTILS_JS.read_text(encoding="utf-8")

    assert "match.fecha_raw || match.fecha" in source
    assert "`${isoDate}T${timePart}`" in source
    assert "ts > Date.now() - graceMinutes * 60 * 1000" in source
