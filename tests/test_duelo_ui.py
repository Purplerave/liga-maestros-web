"""El marcador del duelo y la barra de la Peña, atados al HTML y al JS reales.

Fallos que vigila este modulo (todos llegaron en el rediseño de La Peña):

* el marcador se metio dentro de la topbar, que mide 66px y tiene
  ``overflow: hidden``: el tercer hijo del grid se quedaba fuera de pantalla;
* un contador que se repinta cada segundo no puede ser una region ``aria-live``;
* ``duelo.js`` pintaba el marcador pero nadie lo llamaba: se quedaba en 0-0;
* el atajo de teclado ``R`` se anunciaba como "Actualizard" (typo);
* ``renderFixtureSchedule`` desaparecio y el horario del boleto se quedo en
  blanco sin que ningun test lo notara.
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

TEMPLATE = ROOT / "templates" / "liga_index.html"
DUELO_JS = ROOT / "static" / "js" / "pages" / "duelo.js"
TICKET_JS = ROOT / "static" / "js" / "pages" / "ticket_page.js"
EVENTS_JS = ROOT / "static" / "js" / "events.js"
QUANTUM_JS = ROOT / "static" / "js" / "quantum_final.js"
COMPONENTS_CSS = ROOT / "static" / "css" / "themes" / "newspaper" / "components.css"


def _topbar(html):
    inicio = html.index('<header class="topbar-shell">')
    return html[inicio : html.index("</header>", inicio)]


def test_el_marcador_del_duelo_vive_dentro_de_la_topbar():
    html = TEMPLATE.read_text(encoding="utf-8")
    topbar = _topbar(html)

    assert 'id="duelo-scorebar"' in topbar
    # Los tres bloques del marcador, en orden.
    assert topbar.index("duelo-maestros") < topbar.index("duelo-countdown") < topbar.index("duelo-pena")
    # Y no se duplica fuera de ella.
    assert html.count('id="duelo-scorebar"') == 1


def test_el_marcador_no_es_una_region_viva_con_contador():
    html = TEMPLATE.read_text(encoding="utf-8")
    etiqueta = re.search(r'<div id="duelo-scorebar"[^>]*>', html).group(0)

    # Un nodo que cambia cada segundo con aria-live = lector de pantalla
    # anunciando la cuenta atras sin parar.
    assert "aria-live" not in etiqueta
    assert 'role="group"' in etiqueta
    # Sigue teniendo nombre accesible.
    assert "aria-label=" in etiqueta


def test_la_topbar_da_sitio_al_marcador():
    css = COMPONENTS_CSS.read_text(encoding="utf-8")
    regla = re.search(r"\.topbar-shell:has\(\.duelo-scorebar\)\s*\{([^}]*)\}", css)

    assert regla, "falta la regla que abre la celda del marcador en la topbar"
    assert "grid-template-columns" in regla.group(1)
    # Contexto + marcador + filtros + acciones.
    assert regla.group(1).count("auto") >= 2


def test_el_atajo_de_actualizar_no_esta_escrito_a_mano():
    html = TEMPLATE.read_text(encoding="utf-8")

    assert "Actualizard" not in html
    assert 'title="Actualizar (R)"' in html
    assert 'aria-label="Actualizar"' in html


@pytest.mark.parametrize("archivo", [DUELO_JS, EVENTS_JS, QUANTUM_JS])
def test_hydrate_duelo_existe_y_se_llama(archivo):
    texto = archivo.read_text(encoding="utf-8")

    if archivo is DUELO_JS:
        assert "function hydrateDuelo(" in texto
        assert "function updateDueloScore(" in texto
        assert "function startDueloCountdown(" in texto
    else:
        assert "hydrateDuelo" in texto, f"{archivo.name} no refresca el marcador del duelo"


def test_duelo_js_no_pide_el_pleno_sin_las_catorce_previas():
    js = DUELO_JS.read_text(encoding="utf-8")

    # El pleno solo paga con las 14 previas acertadas (misma regla que el
    # backend): el marcador no puede sumarlo por su cuenta.
    assert "previasResueltas === 14" in js
    assert "previas === 14" in js
    # Un empate del consenso es "-" y no puntua.
    assert 'ganador === "-"' in js or "ganador" in js
    # La hora de cierre es hora de pared de Madrid, no UTC.
    assert "madridWallClockToMs" in js


def test_el_horario_del_boleto_sigue_teniendo_su_render():
    """`fixtureScheduleParts` sin `renderFixtureSchedule` = celda vacia."""
    ticket = TICKET_JS.read_text(encoding="utf-8")

    assert "function renderFixtureSchedule(match)" in ticket
    assert "function renderMatchDetailGrid(m, c)" in ticket
    # Y se usa en el repintado del directo ademas de en el render inicial.
    assert ticket.count("renderFixtureSchedule(") >= 3
