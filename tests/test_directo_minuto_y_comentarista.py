"""Contratos de navegador para el minuto en directo y el comentarista IA.

Cubre dos mejoras de la pestaña Directo y de la quiniela:

* **Minuto visible**: las tarjetas de Directo llevan un chip con el minuto
  ("63'", "Descanso") bajo el marcador, y la celda "Hora / resultado" de la
  quiniela muestra "2-1 · 63'" mientras el partido esta en juego. El dato
  llega con formas distintas segun el payload (``minuto_live`` en la quiniela,
  ``time`` en live_matches, "2-1 (63')" pegado al marcador), asi que la
  funcion que lo normaliza debe leerlas todas.
* **Comentarista IA en Directo**: las frases de MiMo ya no viven solo en el
  ticker de la portada; abren la pagina de Directo. Sin comentarios (no hay
  partidos en juego o la IA no tiene key) no se pinta nada de ese panel.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
UTILS = ROOT / "static" / "js" / "utils.js"
LOGOS = ROOT / "static" / "js" / "logos.js"
ARENA = ROOT / "static" / "js" / "arena.js"
LIVE = ROOT / "static" / "js" / "live.js"

requires_node = pytest.mark.skipif(
    shutil.which("node") is None, reason="Node is required to exercise browser utility functions"
)


def _run_node(script):
    result = subprocess.run(["node", "-e", script], cwd=ROOT, check=True, text=True, capture_output=True)
    return json.loads(result.stdout)


@requires_node
def test_live_minute_label_reads_every_provider_shape():
    script = f"""
        const fs = require("fs");
        const vm = require("vm");
        const context = {{ console, Map, String, Number, Date, JSON, Set, RegExp }};
        vm.createContext(context);
        vm.runInContext(fs.readFileSync({json.dumps(str(UTILS))}, "utf8"), context);
        console.log(JSON.stringify({{
            quiniela: context.liveMinuteLabel({{ status: "LIVE", minuto_live: "63" }}),
            ht: context.liveMinuteLabel({{ status: "HT", minuto_live: "" }}),
            htPorMinuto: context.liveMinuteLabel({{ status: "LIVE", minuto: "Descanso" }}),
            liveMatches: context.liveMinuteLabel({{ status: "IN PLAY", time: "45+" }}),
            incrustado: context.liveMinuteLabel({{ status: "EN JUEGO", marcador: "2-1\\u00a0(63')" }}),
            sinMinuto: context.liveMinuteLabel({{ status: "LIVE", marcador_base: "0-0" }}),
            vacio: context.liveMinuteLabel(null)
        }}));
    """
    labels = _run_node(script)

    assert labels["quiniela"] == "63'"
    assert labels["ht"] == "DESCANSO"
    assert labels["htPorMinuto"] == "DESCANSO"
    assert labels["liveMatches"] == "45'"
    assert labels["incrustado"] == "63'"
    assert labels["sinMinuto"] == ""
    assert labels["vacio"] == ""


@requires_node
def test_live_score_with_minute_builds_the_ticket_badge_text():
    script = f"""
        const fs = require("fs");
        const vm = require("vm");
        const context = {{ console, Map, String, Number, Date, JSON, Set, RegExp }};
        vm.createContext(context);
        vm.runInContext(fs.readFileSync({json.dumps(str(UTILS))}, "utf8"), context);
        console.log(JSON.stringify({{
            enJuego: context.liveScoreWithMinute({{
                status: "LIVE", marcador_base: "2-1", goles_local: 2, goles_visitante: 1, minuto_live: "63"
            }}),
            descanso: context.liveScoreWithMinute({{
                status: "HT", marcador_base: "0-0", goles_local: 0, goles_visitante: 0, minuto_live: ""
            }}),
            sinMinuto: context.liveScoreWithMinute({{
                status: "LIVE", marcador_base: "0-0", goles_local: 0, goles_visitante: 0, minuto_live: ""
            }})
        }}));
    """
    scores = _run_node(script)

    assert scores["enJuego"] == "2-1 · 63'"
    assert scores["descanso"] == "0-0 · Desc."
    assert scores["sinMinuto"] == "0-0"


@requires_node
def test_directo_card_renders_the_minute_chip_under_the_score():
    script = f"""
        const fs = require("fs");
        const vm = require("vm");
        const context = {{ console, Map, String, Number, Date, JSON, Set, RegExp, encodeURIComponent }};
        vm.createContext(context);
        vm.runInContext(fs.readFileSync({json.dumps(str(UTILS))}, "utf8"), context);
        vm.runInContext(fs.readFileSync({json.dumps(str(LOGOS))}, "utf8"), context);
        vm.runInContext(fs.readFileSync({json.dumps(str(ARENA))}, "utf8"), context);
        context.state = {{ data: {{ today_madrid: "2026-08-23" }} }};
        context.logoCache = new Map();
        context.logoAliasIndex = null;
        context.isLiveMatch = m => String(m.status || "").toUpperCase() === "LIVE";
        // Saque hace 80 minutos: un minuto 72 es coherente con el reloj real.
        // (Con el saque en el futuro o con el minuto por delante del tiempo
        // transcurrido, la web descarta el directo por congelado.)
        const kickoff = new Date(Date.now() - 80 * 60000);
        const pad = n => String(n).padStart(2, "0");
        const fecha = `${{kickoff.getFullYear()}}-${{pad(kickoff.getMonth() + 1)}}-${{pad(kickoff.getDate())}}`;
        const hora = `${{pad(kickoff.getHours())}}:${{pad(kickoff.getMinutes())}}`;
        const card = context.renderMatchCard({{
            id: "quiniela-1-3",
            local: "Celta", visitante: "Osasuna",
            status: "LIVE", marcador_base: "1-0", goles_local: 1, goles_visitante: 0,
            minuto_live: "72", fecha_raw: fecha, hora: hora
        }});
        const programada = context.renderMatchCard({{
            id: 4, local: "Celta", visitante: "Osasuna", status: "NS",
            marcador: "21:30h", fecha_raw: fecha, hora: hora
        }});
        console.log(JSON.stringify({{
            chip: card.includes('data-live-minute-label') && card.includes("72&#039;"),
            badge: card.includes("1-0"),
            programadaSinChip: !programada.includes("data-live-minute-label")
        }}));
    """
    payload = _run_node(script)

    assert payload["chip"] is True, "la tarjeta en directo debe pintar el minuto"
    assert payload["badge"] is True
    assert payload["programadaSinChip"] is True, "un partido no iniciado no lleva chip de minuto"


@requires_node
def test_directo_page_opens_with_the_ia_commentator_panel():
    script = f"""
        const fs = require("fs");
        const vm = require("vm");
        const context = {{ console, Map, String, Number, Date, JSON, Set, RegExp }};
        vm.createContext(context);
        vm.runInContext(fs.readFileSync({json.dumps(str(UTILS))}, "utf8"), context);
        vm.runInContext(fs.readFileSync({json.dumps(str(LIVE))}, "utf8"), context);
        context.state = {{
            currentFilter: "LIVE",
            data: {{
                comentarista: {{
                    comentarios: [
                        {{ texto: "Golazo del Celta para adelantarse", local: "Celta",
                           visitante: "Osasuna", minuto: "72'", marcador: "1-0" }}
                    ]
                }}
            }}
        }};
        const panel = context.directComentaristaHtml();
        context.state.data.comentarista.comentarios = [];
        const vacio = context.directComentaristaHtml();
        console.log(JSON.stringify({{
            panel: panel.includes("direct-comentarista") && panel.includes("Golazo del Celta"),
            contexto: panel.includes("CELTA") && panel.includes("72&#039;"),
            vacio: vacio === ""
        }}));
    """
    payload = _run_node(script)

    assert payload["panel"] is True, "los comentarios de la IA deben abrir la pagina de Directo"
    assert payload["contexto"] is True
    assert payload["vacio"] is True, "sin comentarios no se pinta el panel"
