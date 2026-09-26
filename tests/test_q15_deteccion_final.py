"""La quiniela15 dice que el partido ha acabado, pero no lo dice con palabras.

No existe ningun "finalizado" en su HTML: mientras corre, el marcador parpadea
(`blink_me`) y la celda de minuto dice "min. 67'"; al acabar desaparecen ambos y
solo queda el marcador. Antes se deducia el final por reloj (2h30 despues del
saque, `FULL_MATCH_WINDOW`) y la fila se quedaba STALE con el ultimo marcador en
vivo, que es como Ceuta-R. Sociedad B se puntuo 1-1 siendo 3-1.
"""

import sys
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools" / "scrapers"))

from SCRAPE_QUINIELA15_DIRECTO import (  # noqa: E402
    parse_main_row,
    q15_row_is_scheduled_placeholder,
    q15_row_live_markup,
    status_for_q15,
)

HEAD = (
    '<tr><td class="tnum">{}</td><td>{} (1700.0) - {} (1600.0)</td>{}<td>{}</td><td>1</td><td>50% | 25% | 25%</td></tr>'
)


def _row(index, home, away, score_html, minute_text):
    return HEAD.format(index, home, away, score_html, minute_text)


def test_finished_match_is_ft_without_any_final_word():
    # Ceuta 3-1: marcador plano, sin parpadeo y sin minuto.
    row = _row(1, "Ceuta", "R. Sociedad B", "<td><span> 3 - 1 </span></td>", "1")
    soup = BeautifulSoup(row, "html.parser")
    tr = soup.find("tr")

    assert q15_row_live_markup(tr) is False
    assert status_for_q15(3, 1, "", tr.get_text(" ", strip=True)) == "FT"


def test_live_match_is_live_by_blink_and_minute():
    row = _row(2, "Granada", "Andorra", '<td><span class="blink_me text-red-600"> 0 - 1 </span></td>', "min. 25'")
    soup = BeautifulSoup(row, "html.parser")
    tr = soup.find("tr")

    assert q15_row_live_markup(tr) is True
    assert status_for_q15(0, 1, "25'", tr.get_text(" ", strip=True)) == "LIVE"
    # Aunque el minuto se pierda, el parpadeo sigue delatando el directo.
    assert status_for_q15(0, 1, "", "", live_markup=True) == "LIVE"


def test_scheduled_match_is_not_a_result():
    row = (
        '<tr><td class="tnum">3</td><td>Celta Fortuna (1500.0) - Sabadell (1500.0)</td>'
        '<td colspan="2"><span class="matchdate">sabado</span>'
        '<span class="matchdate">26 sept 18:30h</span></td><td>1</td><td>33% | 33% | 34%</td></tr>'
    )
    tr = BeautifulSoup(row, "html.parser").find("tr")

    assert q15_row_is_scheduled_placeholder(tr) is True
    assert status_for_q15(None, None, "", "", scheduled_placeholder=True) == "NS"


def test_parse_main_row_reads_a_finished_match():
    row = _row(1, "Ceuta", "R. Sociedad B", "<td><span> 3 - 1 </span></td>", "1")
    parsed = parse_main_row(BeautifulSoup(row, "html.parser").find("tr"))

    assert parsed["id"] == 1
    assert (parsed["score_home"], parsed["score_away"]) == (3, 1)
    assert parsed["status"] == "FT"
    assert parsed["signo"] == "1"


def test_parse_main_row_keeps_a_live_match_live():
    row = _row(2, "Granada", "Andorra", '<td><span class="blink_me text-red-600"> 0 - 1 </span></td>', "min. 25'")
    parsed = parse_main_row(BeautifulSoup(row, "html.parser").find("tr"))

    assert parsed["status"] == "LIVE"
    assert parsed["minute"] == "25'"


@pytest.mark.parametrize(
    "score_home,score_away,minute,expected",
    [
        (3, 1, "", "FT"),
        (0, 1, "67'", "LIVE"),
        (1, 0, "Descanso", "HT"),
        (None, None, "", "NS"),
    ],
)
def test_status_for_q15_matrix(score_home, score_away, minute, expected):
    assert status_for_q15(score_home, score_away, minute, "") == expected
