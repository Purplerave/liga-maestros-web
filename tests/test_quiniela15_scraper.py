"""Snapshot tests for the Quiniela15 scraper.

The scraper depends on quiniela15.com's DOM. If they change their markup we
want to know from a red test locally/in CI — not from a broken jornada on
Sunday morning. The fixture in tests/data/quiniela15_snapshot.html mirrors the
structure the parser expects (rows with 9+ cells, `matchinfo` detail rows,
Q15/LAE/APU percent blocks, "Marcador Q15" score probabilities for match 15,
Hypermotion placeholders, and the Cierre/Jornada headers).

If the real site changes: update the fixture to match the new markup, fix the
parser, and keep these tests green.
"""

import importlib.util
import sys
from datetime import datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRAPER_PATH = ROOT / "tools" / "scrapers" / "SCRAPE_QUINIELA15_PROXIMA.py"
FIXTURE_PATH = Path(__file__).resolve().parent / "data" / "quiniela15_snapshot.html"


def _load_scraper():
    spec = importlib.util.spec_from_file_location("scrape_quiniela15_proxima", SCRAPER_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def scraper():
    return _load_scraper()


@pytest.fixture(scope="module")
def payload(scraper):
    html = FIXTURE_PATH.read_text(encoding="utf-8")
    original_fetch = scraper.fetch_html
    scraper.fetch_html = lambda url=None: html
    try:
        return scraper.scrape_quiz("https://fixture.local/pronostico-quiniela")
    finally:
        scraper.fetch_html = original_fetch


def test_snapshot_extracts_exactly_15_matches(payload):
    assert len(payload["partidos"]) == 15
    assert [p["num"] for p in payload["partidos"]] == list(range(1, 16))


def test_snapshot_detects_jornada_and_cierre(payload):
    assert payload["jornada"] == 75
    assert "13:00" in payload["cierre"]


def test_snapshot_parses_teams_and_forces(payload):
    first = payload["partidos"][0]
    assert first["local"] == "Real Madrid"
    assert first["visitante"] == "FC Barcelona"
    assert first["fuerza_local"] == 2.0
    assert first["fuerza_visitante"] == -1.0


def test_snapshot_parses_percent_blocks(payload):
    first = payload["partidos"][0]
    assert first["q15"] == {"1": 55, "X": 25, "2": 20}
    assert first["lae"] == {"1": 50, "X": 28, "2": 22}
    assert first["apu"] == {"1": 52, "X": 26, "2": 22}


def test_snapshot_parses_match_15_score_probabilities(payload):
    pleno = payload["partidos"][14]
    assert pleno["num"] == 15
    assert pleno["marcadores_q15"], "Match 15 must expose 'Marcador Q15' score probabilities"
    assert pleno["marcadores_q15"][0] == {"score": "1-0", "pct": 22}
    assert pleno["comunidad"] == "1-0"


def test_snapshot_parses_schedule_rows(payload):
    horarios = payload["horarios"]
    assert len(horarios) == 15
    first = horarios["1"]
    assert first["hora"] == "21:00"
    assert first["fecha"].endswith("-08-16")


def test_snapshot_base_signs_cover_all_matches(payload):
    signs = payload["q15_base_signs"]
    assert len(signs) == 15
    for sign in signs[:14]:
        assert sign in {"1", "X", "2"}
    # Match 15 keeps the raw system score.
    assert signs[14] == "1-0"


def test_scraper_fails_loudly_when_matches_are_missing(scraper):
    """A DOM change that drops matches must raise, never emit partial data."""
    html = FIXTURE_PATH.read_text(encoding="utf-8")
    # Simulate quiniela15.com renaming their table cells: drop every data row.
    broken = html.replace("<td>", "<div>").replace("</td>", "</div>")
    original_fetch = scraper.fetch_html
    scraper.fetch_html = lambda url=None: broken
    try:
        with pytest.raises(RuntimeError):
            scraper.scrape_quiz("https://fixture.local/broken")
    finally:
        scraper.fetch_html = original_fetch


def test_scraper_fails_loudly_when_jornada_header_disappears(scraper):
    html = FIXTURE_PATH.read_text(encoding="utf-8").replace("Jornada 75", "Fecha 75")
    original_fetch = scraper.fetch_html
    scraper.fetch_html = lambda url=None: html
    try:
        with pytest.raises(RuntimeError):
            scraper.scrape_quiz("https://fixture.local/no-jornada")
    finally:
        scraper.fetch_html = original_fetch


def test_hypermotion_placeholder_resolution(scraper):
    position_map = {1: "Sporting Gijón", 2: "Real Zaragoza"}
    assert scraper.resolve_hypermotion_placeholder("1º Hypermotion", position_map) == "Sporting Gijón"
    assert scraper.resolve_hypermotion_placeholder("2ª Hypermotion", position_map) == "Real Zaragoza"
    assert scraper.resolve_hypermotion_placeholder("Real Madrid", position_map) == "Real Madrid"
    # Unknown position falls back to the raw placeholder instead of crashing.
    assert scraper.resolve_hypermotion_placeholder("9º Hypermotion", position_map) == "9º Hypermotion"


def test_detail_datetime_handles_midnight_edge_case(scraper):
    now = datetime(2026, 8, 15)
    fecha, hora = scraper.parse_detail_datetime("La Liga · sábado 16 agosto 24:00h · Estadio", now=now)
    assert hora == "00:00"
    assert fecha == "2026-08-17"


def test_detail_datetime_handles_year_rollover(scraper):
    # Scraping in December for a January match must land in the next year.
    now = datetime(2026, 12, 28)
    fecha, hora = scraper.parse_detail_datetime("La Liga · domingo 3 enero 18:00h · Estadio", now=now)
    assert fecha == "2027-01-03"
    assert hora == "18:00"
