"""La quiniela15 dice que el partido ha acabado, pero no lo dice con palabras.

No existe ningun "finalizado" en su HTML: mientras corre, el marcador parpadea
(`blink_me`) y la celda de minuto dice "min. 67'"; al acabar desaparecen ambos y
solo queda el marcador. Antes se deducia el final por reloj (2h30 despues del
saque, `FULL_MATCH_WINDOW`) y la fila se quedaba STALE con el ultimo marcador en
vivo, que es como Ceuta-R. Sociedad B se puntuo 1-1 siendo 3-1.
"""

import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools" / "scrapers"))

from SCRAPE_QUINIELA15_DIRECTO import (  # noqa: E402
    parse_main_row,
    q15_row_is_scheduled_placeholder,
    q15_row_live_markup,
    status_for_q15,
)

from tools.ops import LIVE_COLLECTOR as collector  # noqa: E402

MADRID = ZoneInfo("Europe/Madrid")

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


def _j9_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """CREATE TABLE resultados (
            jornada INTEGER, partido_id INTEGER, local TEXT, visitante TEXT,
            goles_local INTEGER, goles_visitante INTEGER, status TEXT,
            fecha TEXT, hora TEXT, minuto TEXT, signo_actual TEXT, updated_at TEXT
        )"""
    )
    filas = [
        (9, 1, "Ceuta", "R. Sociedad B", None, None, "NS", "2026-09-26", "14:00"),
        (9, 2, "Granada", "Andorra FC", None, None, "NS", "2026-09-26", "16:15"),
    ]
    conn.executemany(
        """INSERT INTO resultados
           (jornada, partido_id, local, visitante, goles_local, goles_visitante, status, fecha, hora)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        filas,
    )
    conn.commit()
    return conn


def test_j9_ceuta_llega_a_la_bd_como_final(monkeypatch):
    """El recorrido entero: HTML real de la J9 -> parseo -> tabla resultados.

    Es el test que habria pillado el incidente: con el parser viejo la fila
    terminada llegaba como STALE y se puntuaba con el ultimo marcador en vivo.
    """
    conn = _j9_db()
    monkeypatch.setattr(collector, "get_db", lambda: conn)
    monkeypatch.setattr(collector, "log_line", lambda message: None)
    monkeypatch.setattr(collector, "madrid_now", lambda: datetime(2026, 9, 26, 18, 0, tzinfo=MADRID))

    ceuta = _row(1, "Ceuta", "R. Sociedad B", "<td><span> 3 - 1 </span></td>", "1")
    granada = _row(2, "Granada", "Andorra", '<td><span class="blink_me text-red-600"> 0 - 1 </span></td>', "min. 26'")
    matches = [parse_main_row(BeautifulSoup(html, "html.parser").find("tr")) for html in (ceuta, granada)]

    updates = collector.apply_q15_results_to_db(9, {"matches": matches})

    assert updates == 2
    p1 = conn.execute("SELECT * FROM resultados WHERE partido_id = 1").fetchone()
    assert (p1["goles_local"], p1["goles_visitante"], p1["status"], p1["minuto"], p1["signo_actual"]) == (
        3,
        1,
        "FT",
        "Finalizado",
        "1",
    )
    p2 = conn.execute("SELECT * FROM resultados WHERE partido_id = 2").fetchone()
    assert (p2["goles_local"], p2["goles_visitante"], p2["status"], p2["minuto"]) == (0, 1, "LIVE", "26'")
