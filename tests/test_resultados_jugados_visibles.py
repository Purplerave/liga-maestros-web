"""Resultados que "no aparecian": boleto equivocado y abreviaturas del club.

Dos averias distintas dejaban partidos ya jugados sin marcador en la quiniela:

1. **Boleto equivocado.** La app numera por concurso (J1, J2, J3...) y SELAE
   numera por boleto. En la temporada 2026/27 la J17 se juega con el boleto
   SELAE **18**. El colector pedia ``/resultados-quiniela/17``, un boleto ya
   jugado y con otros quince equipos; el cruce los descartaba todos
   (``q15_team_mismatch_skipped``) y la jornada se quedaba sin resultados
   aunque el directo si viera los partidos.

2. **Abreviatura del club.** El boleto escribe "Atletico" (y "Atletico (F)")
   donde el proveedor publica "Atletico Madrid"/"At. Madrid" y "Atletico
   Madrid Women". Sin alias propio, las dos identidades eran equipos distintos
   y el resultado del Levante - Atletico de la J17 no cruzaba nunca.
"""

import json
import re
import sqlite3
from pathlib import Path

import pytest

from liga_maestros.services import boleto_numero
from liga_maestros.services.payloads.matches import build_jornada_matches
from liga_maestros.utils import normalize_team_key, team_keys_compatible

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def _j17_fixture():
    payload = json.loads((DATA / "quiniela15_J17_scrape.json").read_text(encoding="utf-8"))
    return payload["partidos"]


# ---------------------------------------------------------------------------
# (1) el numero de boleto
# ---------------------------------------------------------------------------


def test_la_jornada_17_se_juega_con_el_boleto_selae_18():
    """El dato vive en el seed, no en el codigo."""
    seed = json.loads((DATA / "quiniela15_J17_scrape.json").read_text(encoding="utf-8"))
    assert seed["boleto"]["nombre"] == "SELAE 18"
    assert seed["boleto"]["selae"] == 18


def test_resolver_devuelve_el_boleto_declarado_en_los_datos():
    boleto_numero.clear_cache()
    assert boleto_numero.resolve_boleto_number(17) == 18


def test_resolver_cae_al_numero_de_jornada_cuando_no_hay_dato():
    """Comportamiento historico para las jornadas que no declaran boleto."""
    boleto_numero.clear_cache()
    for jornada in (1, 2, 3, 4, 6, 7, 8, 9, 11, 12, 16, 75, 76):
        assert boleto_numero.resolve_boleto_number(jornada) == jornada


def test_resolver_nunca_lanza_ante_una_jornada_rara():
    """Entrada invalida -> None; fuera de rango -> se deja pasar tal cual."""
    boleto_numero.clear_cache()
    assert boleto_numero.resolve_boleto_number("17") == 18
    assert boleto_numero.resolve_boleto_number(None) is None
    assert boleto_numero.resolve_boleto_number("diecisiete") is None
    assert boleto_numero.resolve_boleto_number(999999) == 999999


@pytest.mark.parametrize(
    "metadata, expected",
    [
        ({"boleto": {"selae": 18}}, 18),
        ({"boleto": {"selae": "18"}}, 18),
        ({"boleto": {"numero": 21}}, 21),
        ({"boleto": {"nombre": "SELAE 21"}}, 21),
        ({"boleto": {"nombre": "SELAE 18", "selae": 21}}, 21),
        ({"boleto": {"nombre": "boleto sin numero"}}, None),
        ({"boleto": {"selae": 0}}, None),
        ({"boleto": {"selae": 1000}}, None),
        ({"boleto": "SELAE 18"}, None),
        ({}, None),
        (None, None),
    ],
)
def test_lectura_del_numero_de_boleto(metadata, expected):
    """Un dato raro se ignora: mejor el numero de jornada que una URL inventada."""
    assert boleto_numero._from_boleto_metadata(metadata) == expected


def test_el_scraper_pide_el_boleto_resuelto_y_no_la_jornada_interna(monkeypatch):
    """Guarda contra el fallo real: la URL llevaba el numero interno."""
    import SCRAPE_QUINIELA15_DIRECTO as scraper

    pedidas = []
    monkeypatch.setattr(scraper, "fetch_page", lambda url, attempts=3: pedidas.append(url) or _FakeResponse())
    payload = scraper.scrape(17)

    assert pedidas == ["https://www.quiniela15.com/resultados-quiniela/18"]
    # La jornada interna sigue siendo la de la app: el boleto es solo la URL.
    assert payload["jornada"] == 17
    assert payload["boleto"] == 18


class _FakeResponse:
    text = ""


# ---------------------------------------------------------------------------
# (2) abreviaturas del club
# ---------------------------------------------------------------------------


def test_atletico_a_secas_es_el_mismo_equipo_que_atletico_madrid():
    """J17: el boleto escribe "Atletico", el proveedor "Atletico Madrid"."""
    for canto in ("Atlético Madrid", "At. Madrid", "Atlético de Madrid", "Atletico Madrid"):
        assert team_keys_compatible("Atlético", canto), canto
    assert normalize_team_key("Atlético") == normalize_team_key("At. Madrid")


def test_atletico_femenino_cruza_con_sus_variantes_del_proveedor():
    for canto in ("Atlético Madrid (F)", "At. Madrid (F)", "Atlético Madrid Women", "Atletico Madrid Femenino"):
        assert team_keys_compatible("Atlético (F)", canto), canto


def test_el_genero_sigue_siendo_infranqueable():
    """El alias nuevo no puede mezclar el Atletico masculino con el femenino."""
    assert not team_keys_compatible("Atlético", "Atlético (F)")
    assert not team_keys_compatible("Atlético", "Atlético Madrid Women")
    assert not team_keys_compatible("Atlético", "Madrid CFF (F)")
    assert not team_keys_compatible("Atlético (F)", "Atlético Madrid")


def test_el_marcador_del_levante_atletico_entra_en_la_jornada_17():
    """De punta a punta: cruce de equipos -> fila con resultado en el boleto.

    El proveedor publica "Atlético Madrid" donde el boleto dice "Atlético"; si
    el cruce falla, la fila 1 se queda en NS sin marcador (el sintoma
    reportado: "hay partidos ya jugados y no veo el resultado").
    """
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE resultados (
            jornada INTEGER, partido_id INTEGER, local TEXT, visitante TEXT,
            goles_local INTEGER, goles_visitante INTEGER, status TEXT,
            fecha TEXT, hora TEXT, minuto TEXT, signo_actual TEXT, updated_at TEXT
        )
        """
    )
    partidos = _j17_fixture()
    for partido in partidos:
        conn.execute(
            "INSERT INTO resultados (jornada, partido_id, local, visitante, status, fecha, hora)"
            " VALUES (17, ?, ?, ?, 'NS', ?, ?)",
            (partido["num"], partido["local"], partido["visitante"], partido["fecha"], partido["hora"]),
        )
    # El resultado llega con el nombre del proveedor, no con el del boleto.
    conn.execute(
        "UPDATE resultados SET goles_local = 0, goles_visitante = 2, status = 'FT',"
        " signo_actual = '2' WHERE jornada = 17 AND partido_id = 1"
    )
    conn.commit()

    casilla_1 = build_jornada_matches(conn, "17", {})[0]

    assert casilla_1["local"] == "Levante"
    assert team_keys_compatible("Atlético Madrid", casilla_1["visitante"])
    assert casilla_1["status"] == "FT"
    assert (casilla_1["goles_local"], casilla_1["goles_visitante"]) == (0, 2)
    assert casilla_1["marcador"] == "0-2"


def test_el_nombre_del_boleto_no_se_reescribe():
    """El arreglo es de identidad, no de presentacion: la fila sigue diciendo "Atletico"."""
    nombres = {(p["local"], p["visitante"]) for p in _j17_fixture()}
    assert ("Levante", "Atlético") in nombres
    assert not re.search(r"Atlético Madrid", json.dumps(_j17_fixture(), ensure_ascii=False))
