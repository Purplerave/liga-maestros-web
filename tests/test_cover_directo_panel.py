"""Contrato del panel EN DIRECTO de la portada (cover_page.js).

La portada solo miraba los 15 partidos de la quiniela: un viernes con un
Racing - Elche de LaLiga en juego (fuera de la quiniela) el panel se quedaba
en «0 PARTIDOS» y el partido no aparecia en ningun sitio. El panel debe
reforzararse con los directos de hoy que el backend sirve en ``live_matches``
(por pareja de equipos, quiniela primero y sin duplicados).
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
UTILS = ROOT / "static" / "js" / "utils.js"
STATE = ROOT / "static" / "js" / "state.js"
COVER = ROOT / "static" / "js" / "pages" / "cover_page.js"

HARNESS = r"""
const fs = require("fs");
const vm = require("vm");

const sandbox = {
    console,
    Map, Set, String, Number, Date, JSON, Array, Object, Boolean, RegExp, Math, parseInt,
    URLSearchParams,
    setTimeout: () => 0,
    setInterval: () => 0,
    clearTimeout: () => {},
    document: {
        body: { dataset: {}, classList: { toggle() {}, add() {}, remove() {}, contains() { return false; } } },
        createElement: () => ({ classList: { add() {}, remove() {} }, style: {}, setAttribute() {}, appendChild() {} }),
        getElementById: () => null,
        querySelectorAll: () => [],
    },
    window: { location: { search: "" } },
};
vm.createContext(sandbox);
for (const path of [UTILS_PATH, STATE_PATH, COVER_PATH]) {
    vm.runInContext(fs.readFileSync(path, "utf8"), sandbox, { filename: path });
}
vm.runInContext(`
    globalThis.__renderCoverWith = function (data) {
        Object.assign(state, {
            data,
            user: null,
            my_signs: Array(15).fill("-"),
            server_signs: Array(15).fill("-"),
            currentFilter: "ALL",
        });
        globalThis.__lastCoverHtml = renderNewspaperCoverPageV3();
    };
`, sandbox);

// Kickoff "now - offsetMinutes" en hora LOCAL (parseMatchTimestamp pega la
// cadena con new Date(...), que la interpreta en la zona del navegador).
function kickoffLocal(offsetMinutes) {
    const d = new Date(Date.now() - offsetMinutes * 60000);
    const pad = n => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

function quinielaMatch(id, local, visitante, fecha, hora, status) {
    return {
        id, local, visitante, status,
        fecha_raw: fecha, hora,
        marcador: status === "NS" ? `${fecha} ${hora}h` : "1-0",
        goles_local: status === "NS" ? null : 1,
        goles_visitante: status === "NS" ? null : 0,
        added: `${fecha} ${hora}:00`,
    };
}

function externalMatch(id, home, away, kickoffOffsetMin, { status = "IN PLAY", score = "2 - 0", time = "24" } = {}) {
    return {
        id,
        fixture_id: id,
        status,
        time,
        score,
        added: kickoffLocal(kickoffOffsetMin),
        scheduled: kickoffLocal(kickoffOffsetMin).slice(11, 16),
        competition: { name: "LA LIGA" },
        competition_name: "LA LIGA",
        country: "Spain",
        country_code: "ES",
        home: { name: home, logo: "" },
        away: { name: away, logo: "" },
    };
}

function renderCover(data) {
    // `state` es un const lexico dentro de state.js: no se puede reemplazar
    // desde fuera del contexto, hay que mutarlo dentro.
    sandbox.__renderCoverWith(data);
    return sandbox.__lastCoverHtml;
}

const results = {};
"""

CASES = r"""
// 1. Viernes: quiniela parada (todo NS), Elche jugando fuera de la quiniela.
{
    const partidos = [];
    for (let i = 1; i <= 15; i++) {
        partidos.push(quinielaMatch(i, `Equipo${i}`, `Rival${i}`, "2026-08-29", "17:00", "NS"));
    }
    const elche = externalMatch(1336376293, "Racing Santander", "Elche", 30);
    const html = renderCover({
        jornada: 3,
        today_madrid: kickoffLocal(30).slice(0, 10),
        is_locked: false,
        partidos,
        all_league_matches: [externalMatch(1336371187, "Alaves", "Villarreal", -60, { status: "SCHEDULED", score: "", time: "NS" }), elche],
        live_matches: [elche],
    });
    results.externalLive = {
        showsElche: html.includes("RACING") && html.includes("ELCHE"),
        showsScore: html.includes("2-0"),
        showsComp: html.includes("LALIGA"),
        showsLink: html.includes("VER DIRECTO COMPLETO"),
        countLabel: (html.match(/cx-pn-meta">(\d+) PARTIDO/) || [])[1] || "",
        emptyMessage: html.includes("Ahora mismo no hay partidos en directo"),
    };
}

// 2. Sin ningun directo: mensaje vacio nuevo.
{
    const partidos = [];
    for (let i = 1; i <= 15; i++) {
        partidos.push(quinielaMatch(i, `Equipo${i}`, `Rival${i}`, "2026-08-29", "17:00", "NS"));
    }
    const html = renderCover({
        jornada: 3,
        today_madrid: kickoffLocal(30).slice(0, 10),
        is_locked: false,
        partidos,
        all_league_matches: [],
        live_matches: [],
    });
    results.noLive = {
        emptyMessage: html.includes("Ahora mismo no hay partidos en directo"),
        oldMessage: html.includes("Sin partidos de la quiniela en directo"),
        linkHidden: !html.includes("VER DIRECTO COMPLETO"),
    };
}

// 3. Partido de la quiniela en juego: se mantiene primero y sin duplicarse
//    cuando el proveedor tambien lo manda en live_matches.
{
    const partidos = [];
    for (let i = 1; i <= 15; i++) {
        partidos.push(quinielaMatch(i, `Equipo${i}`, `Rival${i}`, "2026-08-29", "17:00", "NS"));
    }
    partidos[2] = quinielaMatch(3, "Levante", "Betis", kickoffLocal(20).slice(0, 10), kickoffLocal(20).slice(11, 16), "LIVE");
    const proveedor = externalMatch(999, "Levante", "Betis", 20);
    const html = renderCover({
        jornada: 3,
        today_madrid: kickoffLocal(30).slice(0, 10),
        is_locked: false,
        partidos,
        all_league_matches: [proveedor],
        live_matches: [proveedor],
    });
    results.quinielaLive = {
        shown: html.includes("LEVANTE") && html.includes("BETIS"),
        onceInPanel: (html.match(/cx-live-card/g) || []).length === 1,
        countLabel: (html.match(/cx-pn-meta">(\d+) PARTIDO/) || [])[1] || "",
    };
}

console.log(JSON.stringify(results));
"""


def _run_node() -> dict:
    script = (
        HARNESS.replace("UTILS_PATH", json.dumps(str(UTILS)))
        .replace("STATE_PATH", json.dumps(str(STATE)))
        .replace("COVER_PATH", json.dumps(str(COVER)))
        + CASES
    )
    result = subprocess.run(
        ["node", "-e", script],
        cwd=ROOT,
        check=True,
        capture_output=True,
        encoding="utf-8",
    )
    return json.loads(result.stdout.strip().splitlines()[-1])


@pytest.mark.skipif(shutil.which("node") is None, reason="Node is required to exercise browser code")
def test_cover_directo_panel_shows_non_quiniela_live_match():
    """Racing - Elche (fuera de la quiniela) debe verse en el panel EN DIRECTO."""
    payload = _run_node()

    assert payload["externalLive"]["showsElche"], "el partido externo en juego no aparece en la portada"
    assert payload["externalLive"]["showsScore"], "el marcador del directo externo no se pinta"
    assert payload["externalLive"]["showsComp"], "falta la etiqueta de competicion del directo externo"
    assert payload["externalLive"]["showsLink"], "sin enlace al directo completo habiendo partidos en juego"
    assert payload["externalLive"]["countLabel"] == "1", "el contador del panel no cuenta el directo externo"
    assert not payload["externalLive"]["emptyMessage"], "panel vacio pese a haber un partido en juego"


@pytest.mark.skipif(shutil.which("node") is None, reason="Node is required to exercise browser code")
def test_cover_directo_panel_empty_state_without_any_live_match():
    """Sin directos en ningun sitio, el panel lo dice sin mencionar la quiniela."""
    payload = _run_node()

    assert payload["noLive"]["emptyMessage"]
    assert not payload["noLive"]["oldMessage"], "el mensaje vacio ya no debe hablar solo de la quiniela"
    assert payload["noLive"]["linkHidden"]


@pytest.mark.skipif(shutil.which("node") is None, reason="Node is required to exercise browser code")
def test_cover_directo_panel_keeps_quiniela_match_first_and_deduped():
    """Un directo de la quiniela sigue mostrandose, una sola vez."""
    payload = _run_node()

    assert payload["quinielaLive"]["shown"]
    assert payload["quinielaLive"]["onceInPanel"], "la quiniela y la copia del proveedor se pintan dos veces"
    assert payload["quinielaLive"]["countLabel"] == "1"
