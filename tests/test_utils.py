import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("SECRET_KEY", "test-secret-key")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils import (
    clean_team_key,
    highlightly_status,
    news_relevance_score,
    normalize_news_text,
    normalize_team_key,
    parse_rfc822_to_iso,
    parse_score_text,
    safe_read_json,
    safe_write_json,
    short_team_name,
    signo_for_match,
    strip_html,
    team_token,
)


class TestCleanTeamKey:
    def test_strips_accents(self):
        assert clean_team_key("ATLÉTICO") == "ATLETICO"

    def test_removes_suffixes(self):
        assert clean_team_key("FC BARCELONA") == "BARCELONA"
        assert clean_team_key("RCD ESPANYOL") == "ESPANYOL"
        assert clean_team_key("CD LEGANÉS") == "LEGANES"

    def test_normalizes_whitespace(self):
        assert clean_team_key("  Real   Madrid  ") == "REAL MADRID"

    def test_empty_and_none(self):
        assert clean_team_key("") == ""
        assert clean_team_key(None) == ""

    def test_transliterates_non_decomposable_latin_letters(self):
        # NFD no descompone ø/æ/ß: sin transliteracion, "LILLESTRØM SK" se
        # convertia en "LILLESTR M SK" y el partido no casaba con la BD.
        assert clean_team_key("LILLESTRØM SK") == "LILLESTROM SK"
        assert clean_team_key("BODØ/GLIMT") == "BODO GLIMT"
        assert clean_team_key("BRANN Æ") == "BRANN AE"
        assert clean_team_key("STRAßE") == "STRASSE"
        assert clean_team_key("DJURGÅRDENS") == "DJURGARDENS"

    def test_transliteration_keeps_accents_working(self):
        # Los acentos que NFD si descompone siguen limpiandose igual.
        assert clean_team_key("MJÄLLBY") == "MJALLBY"
        assert clean_team_key("HÄCKEN") == "HACKEN"
        assert clean_team_key("GAIS GÖTEBORG") == "GAIS GOTEBORG"


class TestNormalizeTeamKey:
    def test_known_alias(self):
        assert normalize_team_key("BETIS") == "REAL BETIS"
        assert normalize_team_key("AT MADRID") == "ATLETICO MADRID"

    def test_passthrough(self):
        assert normalize_team_key("OSASUNA") == "OSASUNA"

    def test_equivalence_db_vs_q15_directo_names(self):
        # Regresion: el directo de Quiniela15 usa "Lillestrøm SK" (con ø) y la
        # BD guarda "Lillestrom SK". Ambos deben normalizar a la misma clave o
        # el resultado del partido se descarta silenciosamente.
        assert normalize_team_key("Lillestrom SK") == normalize_team_key("Lillestrøm SK")
        assert normalize_team_key("Bodo-Glimt") == normalize_team_key("Bodø/Glimt")
        assert normalize_team_key("Djurgardens") == normalize_team_key("Djurgårdens")
        assert normalize_team_key("Vasteras SK FK") == normalize_team_key("Västerås SK FK")


class TestShortTeamName:
    def test_known_short_names(self):
        assert short_team_name("ATLETICO MADRID") == "AT. MADRID"
        assert short_team_name("REAL MADRID") == "R. MADRID"
        assert short_team_name("BARCELONA") == "BARCA"

    def test_strips_common_words(self):
        result = short_team_name("REAL SOCIEDAD")
        assert "REAL" not in result


class TestTeamToken:
    def test_two_char_token(self):
        token = team_token("BARCELONA")
        assert len(token) == 2
        assert token.isalnum()


class TestSignoForMatch:
    def test_home_win(self):
        assert signo_for_match(1, 2, 1) == "1"

    def test_away_win(self):
        assert signo_for_match(1, 1, 2) == "2"

    def test_draw(self):
        assert signo_for_match(1, 1, 1) == "X"

    def test_pleno(self):
        assert signo_for_match(15, 3, 1) == "3-1"

    def test_none_goals(self):
        assert signo_for_match(1, None, 1) == "-"
        assert signo_for_match(1, 1, None) == "-"

    def test_invalid_partido_id(self):
        assert signo_for_match("abc", 1, 1) == "-"


class TestParseScoreText:
    def test_valid(self):
        assert parse_score_text("2 - 1") == (2, 1)

    def test_no_match(self):
        assert parse_score_text("abc") == (None, None)

    def test_empty(self):
        assert parse_score_text("") == (None, None)


class TestParseRfc822ToIso:
    def test_valid_rfc822(self):
        result = parse_rfc822_to_iso("Mon, 04 Jul 2026 12:00:00 +0200")
        assert "2026-07-04" in result

    def test_empty(self):
        assert parse_rfc822_to_iso("") == ""

    def test_none(self):
        assert parse_rfc822_to_iso(None) == ""

    def test_invalid(self):
        assert parse_rfc822_to_iso("not a date") == ""


class TestHighlightlyStatus:
    def test_finished(self):
        status, minute = highlightly_status({"description": "FINISHED"})
        assert status == "FT"

    def test_live(self):
        status, minute = highlightly_status({"description": "FIRST HALF", "clock": "45"})
        assert status == "LIVE"
        assert "45" in minute

    def test_half_time(self):
        status, minute = highlightly_status({"description": "HALF TIME"})
        assert status == "LIVE"
        assert minute == "HT"

    def test_not_started(self):
        status, minute = highlightly_status({})
        assert status == "NS"


class TestSafeWriteReadJson:
    def test_write_and_read(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.json")
            data = {"key": "value", "number": 42}
            assert safe_write_json(path, data) is True
            result = safe_read_json(path, {})
            assert result == data

    def test_read_missing(self):
        result = safe_read_json("/nonexistent/path.json", {"default": True})
        assert result == {"default": True}

    def test_write_creates_dirs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "sub", "dir", "test.json")
            assert safe_write_json(path, {"test": True})
            assert os.path.exists(path)


class TestStripHtml:
    def test_strips_tags(self):
        assert strip_html("<b>hello</b>") == "hello"

    def test_normalizes_whitespace(self):
        assert strip_html("<p>  hello   world  </p>") == "hello world"

    def test_empty(self):
        assert strip_html("") == ""


class TestNormalizeNewsText:
    def test_lowercases_and_strips(self):
        result = normalize_news_text("  HELLO  WORLD  ")
        assert result == "hello world"

    def test_removes_accents(self):
        result = normalize_news_text("MADRILEÑO")
        assert "ñ" not in result


class TestNewsRelevanceScore:
    def test_team_keyword(self):
        score = news_relevance_score("El Barcelona ficha a un nuevo jugador")
        assert score >= 4

    def test_generic_keyword(self):
        score = news_relevance_score("Lesión grave del delantero")
        assert score >= 2

    def test_no_relevance(self):
        score = news_relevance_score("El tiempo hoy en Madrid")
        assert score == 0
