"""El panel de TODOS los directos tambien vive en la vista TICKET.

La portada ya lista todos los partidos en juego (`test_cover_directo_panel.py`).
La tabla del boleto es la otra vista donde se mira el directo, y alli la franja
de un solo partido no existia: se anade el mismo panel (lista compartida en
`state.js`) con el lenguaje visual de la tabla, y el marcador pegado al partido
dentro de la propia casilla.

Ademas se fija el plegado: con jornada en curso el panel se abre; sin jornada
(un miercoles con solo Premier, o la temporada parada) arranca plegado, y la
eleccion manual del usuario manda sobre ese valor por defecto.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
UTILS = ROOT / "static" / "js" / "utils.js"
STATE = ROOT / "static" / "js" / "state.js"
TICKET = ROOT / "static" / "js" / "pages" / "ticket_page.js"

requires_node = pytest.mark.skipif(shutil.which("node") is None, reason="Node is required to exercise browser code")

_HARNESS = r"""
const fs = require("fs");
const vm = require("vm");

const memory = {};
const sandbox = {
    console,
    Map, Set, String, Number, Date, JSON, Array, Object, Boolean, RegExp, Math, parseInt, isNaN,
    URLSearchParams,
    setTimeout: () => 0,
    setInterval: () => 0,
    clearTimeout: () => {},
    localStorage: {
        getItem: key => (key in memory ? memory[key] : null),
        setItem: (key, value) => { memory[key] = String(value); },
        removeItem: key => { delete memory[key]; },
    },
    document: {
        body: { dataset: {}, classList: { toggle() {}, add() {}, remove() {}, contains() { return false; } } },
        addEventListener() {},
    },
    window: { location: { search: "" } },
};
vm.createContext(sandbox);
for (const path of [UTILS_PATH, STATE_PATH, TICKET_PATH]) {
    vm.runInContext(fs.readFileSync(path, "utf8"), sandbox, { filename: path });
}

// El servidor manda las horas en hora de Madrid: el reloj de prueba se escribe
// en esa zona para que la caducidad del directo no dependa del huso de la maquina.
const MADRID_FMT = new Intl.DateTimeFormat("en-GB", {
    timeZone: "Europe/Madrid", hour12: false,
    year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", second: "2-digit",
});
function madridClock(offsetMinutes) {
    const p = {};
    for (const part of MADRID_FMT.formatToParts(new Date(Date.now() - offsetMinutes * 60000))) p[part.type] = part.value;
    const hh = String(Number(p.hour) % 24).padStart(2, "0");
    return `${p.year}-${p.month}-${p.day} ${hh}:${p.minute}:${p.second}`;
}

function quinielaMatch(id, local, visitante, status, extra = {}) {
    const live = status !== "NS";
    const kickoff = live ? madridClock(70) : madridClock(-120);
    return Object.assign({
        id, local, visitante, status,
        fecha_raw: kickoff.slice(0, 10), hora: kickoff.slice(11, 16),
        marcador: live ? "2-1" : `${kickoff.slice(0, 10)} ${kickoff.slice(11, 16)}h`,
        goles_local: live ? 2 : null,
        goles_visitante: live ? 1 : null,
        added: kickoff,
    }, extra);
}

function externalMatch(id, home, away, extra = {}) {
    const kickoff = madridClock(60);
    return Object.assign({
        id, fixture_id: id, status: "IN PLAY", time: "54", score: "1 - 0",
        added: kickoff, scheduled: kickoff.slice(11, 16),
        competition: { name: "PREMIER LEAGUE" }, competition_name: "PREMIER LEAGUE",
        home: { name: home }, away: { name: away },
    }, extra);
}

function render(payload) {
    vm.runInContext(`Object.assign(state, { data: ${JSON.stringify(payload)}, user: null,
        my_signs: Array(15).fill("-"), server_signs: Array(15).fill("-") });`, sandbox);
    return vm.runInContext("renderTicketLivePanel()", sandbox);
}

const partidos = [];
for (let i = 1; i <= 15; i++) {
    partidos.push(quinielaMatch(i, `Equipo${i}`, `Rival${i}`, "NS"));
}
partidos[2] = quinielaMatch(3, "Levante", "Betis", "LIVE", { minuto: "63'" });
const arsenal = externalMatch(990001, "Arsenal", "Chelsea");
const levanteCopy = externalMatch(990002, "Levante", "Betis", { score: "2 - 1", time: "63" });

const results = {};

// 1. Jornada en curso: panel abierto con TODOS los directos (sin duplicar).
results.withJornada = (() => {
    const html = render({ jornada: 3, partidos, all_league_matches: [arsenal], live_matches: [arsenal, levanteCopy] });
    return {
        html,
        open: html.includes("<details class=\"lm-live-fold\" open>"),
        items: String((html.match(/ticket-live-item/g) || []).length),
        showsArsenal: /arsenal/i.test(html) && /chelsea/i.test(html),
        showsLevante: /levante/i.test(html) && /betis/i.test(html),
        slot: html.includes(">Q3<"),
        count: (html.match(/ticket-live-count">(\d+)/) || [])[1],
    };
})();

// 2. Solo futbol de fuera de la quiniela: sin jornada en curso, plegado.
results.withoutJornada = (() => {
    const quietos = partidos.map((m, i) => quinielaMatch(i + 1, `Equipo${i + 1}`, `Rival${i + 1}`, "NS"));
    const html = render({ jornada: 3, partidos: quietos, all_league_matches: [arsenal], live_matches: [arsenal] });
    return { html, open: html.includes("<details class=\"lm-live-fold\" open>"), visible: /arsenal/i.test(html) };
})();

// 3. La eleccion manual (localStorage) manda sobre el valor por defecto.
results.remembered = (() => {
    vm.runInContext("localStorage.setItem('lm-live-panel', 'closed')", sandbox);
    const conJornada = render({ jornada: 3, partidos, all_league_matches: [arsenal], live_matches: [arsenal, levanteCopy] });
    vm.runInContext("localStorage.setItem('lm-live-panel', 'open')", sandbox);
    const quietos = partidos.map((m, i) => quinielaMatch(i + 1, `Equipo${i + 1}`, `Rival${i + 1}`, "NS"));
    const sinJornada = render({ jornada: 3, partidos: quietos, all_league_matches: [arsenal], live_matches: [arsenal] });
    return {
        closedWhenAsked: !conJornada.includes("<details class=\"lm-live-fold\" open>"),
        openWhenAsked: sinJornada.includes("<details class=\"lm-live-fold\" open>"),
    };
})();

// 4. Sin ningun directo el panel no se pinta (ni un hueco vacio).
results.noLive = (() => {
    const quietos = partidos.map((m, i) => quinielaMatch(i + 1, `Equipo${i + 1}`, `Rival${i + 1}`, "NS"));
    const html = render({ jornada: 3, partidos: quietos, all_league_matches: [], live_matches: [] });
    return { empty: html === "" };
})();

console.log(JSON.stringify(results));
"""


def _run_node() -> dict:
    script = (
        _HARNESS.replace("UTILS_PATH", json.dumps(str(UTILS)))
        .replace("STATE_PATH", json.dumps(str(STATE)))
        .replace("TICKET_PATH", json.dumps(str(TICKET)))
    )
    result = subprocess.run(
        ["node", "-e", script],
        cwd=ROOT,
        check=True,
        capture_output=True,
        encoding="utf-8",
    )
    return json.loads(result.stdout.strip().splitlines()[-1])


@requires_node
def test_ticket_panel_lists_every_live_match_without_duplicates():
    payload = _run_node()["withJornada"]

    # Dos: el Levante-Betis de la quiniela (aunque el proveedor lo mande otra
    # vez) y el Arsenal-Chelsea de fuera del boleto. Sin duplicados.
    assert int(payload["items"]) == 2, f"deben salir los dos directos sin duplicar, salieron {payload['items']}"
    assert payload["showsArsenal"], "falta el directo de fuera de la quiniela"
    assert payload["showsLevante"], "falta el directo de la quiniela"
    assert payload["slot"], "la casilla de la quiniela debe marcarse con su numero"
    assert payload["count"] == "2"
    assert payload["open"], "con jornada en curso el panel se abre"


@requires_node
def test_ticket_panel_is_folded_when_no_jornada_is_playing():
    payload = _run_node()["withoutJornada"]

    assert payload["visible"], "el directo sigue estando en el DOM"
    assert not payload["open"], "sin jornada en curso el panel arranca plegado"


@requires_node
def test_ticket_panel_remembers_the_manual_toggle():
    payload = _run_node()["remembered"]

    assert payload["closedWhenAsked"], "cerrado a mano debe seguir cerrado aunque haya jornada"
    assert payload["openWhenAsked"], "abierto a mano debe seguir abierto sin jornada"


@requires_node
def test_ticket_panel_disappears_without_live_matches():
    assert _run_node()["noLive"]["empty"], "sin directos no se pinta ningun panel vacio"


def test_ticket_view_places_the_panel_on_the_side_and_the_chip_in_the_row():
    arena = (ROOT / "static" / "js" / "arena.js").read_text(encoding="utf-8")
    ticket = TICKET.read_text(encoding="utf-8")
    css = (ROOT / "static" / "css" / "pages" / "ticket.css").read_text(encoding="utf-8")

    assert "ticket-side-column" in arena and "renderTicketLivePanel()" in arena
    assert "ticket-side-column" in css
    assert "ticket-live-chip" in css and "ticketLiveChipHtml(m, score)" in ticket
    # El parche del poll tambien refresca el marcador pegado al partido.
    assert "[data-ticket-live-chip]" in ticket
