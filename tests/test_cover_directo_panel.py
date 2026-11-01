"""Contrato de la franja EN DIRECTO de la pagina unica (cover_page.js).

La quiniela sola miraba los 15 partidos del boleto: un viernes con un
Racing - Elche de LaLiga en juego (fuera de la quiniela) la franja se quedaba
vacia y el partido no aparecia en ningun sitio. La franja kawaii se apoya en
``live_matches`` (el backend ya decide que esta en juego), por pareja de
equipos y sin duplicados, y si no hay directo no inventa ninguno.
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

// El servidor manda los horarios en hora de Madrid (no en la del navegador):
// el reloj de prueba tiene que escribirse en esa zona para reproducir el
// payload real. Si se usase la hora local, el partido se leería desplazado
// (y en Canarias o con el equipo en UTC, como futuro).
const MADRID_FMT = new Intl.DateTimeFormat("en-GB", {
    timeZone: "Europe/Madrid", hour12: false,
    year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", second: "2-digit",
});
function madridClock(atMs) {
    const p = {};
    for (const part of MADRID_FMT.formatToParts(new Date(atMs))) p[part.type] = part.value;
    const hh = String(Number(p.hour) % 24).padStart(2, "0");
    return {
        date: `${p.year}-${p.month}-${p.day}`,
        time: `${hh}:${p.minute}`,
        full: `${p.year}-${p.month}-${p.day} ${hh}:${p.minute}:${p.second}`,
    };
}
function kickoffMadrid(offsetMinutes) {
    return madridClock(Date.now() - offsetMinutes * 60000).full;
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
        added: kickoffMadrid(kickoffOffsetMin),
        scheduled: kickoffMadrid(kickoffOffsetMin).slice(11, 16),
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
        today_madrid: kickoffMadrid(30).slice(0, 10),
        is_locked: false,
        partidos,
        all_league_matches: [externalMatch(1336371187, "Alaves", "Villarreal", -60, { status: "SCHEDULED", score: "", time: "NS" }), elche],
        live_matches: [elche],
    });
    results.externalLive = {
        showsElche: /racing/i.test(html) && /elche/i.test(html),
        showsScore: html.includes("2-0") || html.includes("2 - 0"),
        showsStrip: html.includes("EN DIRECTO") && html.includes("kk-live-body"),
        countLabel: String((html.match(/kk-live-body/g) || []).length),
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
        today_madrid: kickoffMadrid(30).slice(0, 10),
        is_locked: false,
        partidos,
        all_league_matches: [],
        live_matches: [],
    });
    results.noLive = {
        emptyMessage: html.includes("Ahora mismo no hay partidos en directo"),
        oldMessage: html.includes("Sin partidos de la quiniela en directo"),
        noFakeLive: !html.includes("EN DIRECTO"),
    };
}

// 3. Partido de la quiniela en juego: se mantiene primero y sin duplicarse
//    cuando el proveedor tambien lo manda en live_matches.
{
    const partidos = [];
    for (let i = 1; i <= 15; i++) {
        partidos.push(quinielaMatch(i, `Equipo${i}`, `Rival${i}`, "2026-08-29", "17:00", "NS"));
    }
    partidos[2] = quinielaMatch(3, "Levante", "Betis", kickoffMadrid(20).slice(0, 10), kickoffMadrid(20).slice(11, 16), "LIVE");
    const proveedor = externalMatch(999, "Levante", "Betis", 20);
    const html = renderCover({
        jornada: 3,
        today_madrid: kickoffMadrid(30).slice(0, 10),
        is_locked: false,
        partidos,
        all_league_matches: [proveedor],
        live_matches: [proveedor],
    });
    results.quinielaLive = {
        shown: /levante/i.test(html) && /betis/i.test(html),
        onceInPanel: (html.match(/EN DIRECTO/g) || []).length === 1,
        countLabel: String((html.match(/kk-live-body/g) || []).length),
    };
}

// 4. Varios directos a la vez: TODOS en el panel lateral, cada uno una sola
//    vez, y la casilla de la quiniela marcada con su numero.
{
    const partidos = [];
    for (let i = 1; i <= 15; i++) {
        partidos.push(quinielaMatch(i, `Equipo${i}`, `Rival${i}`, "2026-08-29", "17:00", "NS"));
    }
    partidos[2] = quinielaMatch(3, "Levante", "Betis", kickoffMadrid(20).slice(0, 10), kickoffMadrid(20).slice(11, 16), "LIVE");
    partidos[2].minuto = "63'";
    partidos[2].goles_local = 2;
    partidos[2].goles_visitante = 1;
    const elche = externalMatch(1336376293, "Racing Santander", "Elche", 30);
    const toulouse = externalMatch(1336371187, "Toulouse", "Lille", 38, { time: "38" });
    const html = renderCover({
        jornada: 3,
        today_madrid: kickoffMadrid(30).slice(0, 10),
        is_locked: false,
        partidos,
        all_league_matches: [elche, toulouse],
        live_matches: [elche, toulouse],
    });
    results.manyLive = {
        count: String((html.match(/kk-live-body/g) || []).length),
        showsRacing: /racing/i.test(html),
        showsToulouse: /toulouse/i.test(html),
        showsLevante: /levante/i.test(html),
        quinielaSlot: html.includes(">Casilla 3<"),
        aside: html.includes("kk-live-aside"),
        layout: html.includes("kk-page has-live"),
    };
}

// 6. El marcador del proveedor debe llegar a RESULTADO aunque el registro de
//    la quiniela aún figure NS; los nombres de los equipos pueden venir largos.
{
    const partidos = [];
    for (let i = 1; i <= 15; i++) {
        partidos.push(quinielaMatch(i, `Equipo${i}`, `Rival${i}`, "2026-10-31", "14:00", "NS"));
    }
    partidos[1] = quinielaMatch(2, "Rayo", "Celta", "2026-10-31", "16:15", "NS");
    const row = {
        id: 2, local: "Rayo", visitante: "Celta", cuando: "sabado 31/10 16:15",
        is_pleno: false, has_result: false, resultado: "", en_juego: false,
        minuto: "", picks: {},
    };
    const proveedor = externalMatch(7788, "Rayo Vallecano", "Celta de Vigo", 65, {
        score: "2 - 0", time: "65",
    });
    const html = renderCover({
        jornada: 17,
        is_locked: false,
        partidos,
        live_matches: [proveedor],
        simple_view: { jornada: "17", columns: [], rows: [row], totals: {}, total_casillas: 14 },
    });
    const fila = (html.match(/<tr class="cx-sv-row" data-id="2">[\s\S]*?<\/tr>/) || [""])[0];
    results.providerLiveOnQuinielaRow = {
        resultCell: fila.includes("cx-sv-result is-live"),
        score: fila.includes("2-0"),
        minute: fila.includes("65"),
        readableSlot: html.includes(">Casilla 2<"),
    };
}

// 5. La quiniela muestra el directo una sola vez, dentro de RESULTADO:
//    marcador y minuto frescos, y un STALE no se pinta como resultado.
{
    const enJuego = quinielaMatch(1, "Levante", "Betis", kickoffMadrid(20).slice(0, 10), kickoffMadrid(20).slice(11, 16), "LIVE");
    enJuego.minuto = "63'";
    enJuego.goles_local = 2;
    enJuego.goles_visitante = 1;
    const degradado = quinielaMatch(2, "Sevilla", "Valencia", kickoffMadrid(80).slice(0, 10), kickoffMadrid(80).slice(11, 16), "STALE");
    degradado.goles_local = 1;
    degradado.goles_visitante = 0;
    const partidos = [enJuego, degradado];
    for (let i = 3; i <= 15; i++) {
        partidos.push(quinielaMatch(i, `Equipo${i}`, `Rival${i}`, "2026-08-29", "17:00", "NS"));
    }
    const simpleView = {
        jornada: "3",
        columns: [],
        rows: [
            { id: 1, local: "Levante", visitante: "Betis", cuando: "2026-08-29 17:00", is_pleno: false, has_result: false, resultado: "", en_juego: false, minuto: "", picks: {} },
            { id: 2, local: "Sevilla", visitante: "Valencia", cuando: "2026-08-29 17:00", is_pleno: false, has_result: false, resultado: "", en_juego: false, minuto: "", picks: {} },
        ],
        totals: {},
        total_casillas: 14,
    };
    const html = renderCover({
        jornada: 3,
        today_madrid: kickoffMadrid(30).slice(0, 10),
        is_locked: false,
        partidos,
        all_league_matches: [],
        live_matches: [],
        simple_view: simpleView,
    });
    const fila1 = (html.match(/<tr class="cx-sv-row" data-id="1">[\s\S]*?<\/tr>/) || [""])[0];
    const fila2 = (html.match(/<tr class="cx-sv-row" data-id="2">[\s\S]*?<\/tr>/) || [""])[0];
    results.rowLive = {
        duplicateChip: fila1.includes("cx-sv-live"),
        resultText: /cx-sv-result-val[^>]*>2-1 · 63&#039;<\/span>/.test(fila1),
        resultLive: fila1.includes("cx-sv-result is-live"),
        staleDuplicateChip: fila2.includes("cx-sv-live"),
        staleScore: fila2.includes("1-0"),
        stalePending: fila2.includes("cx-sv-result is-pending"),
    };
}

// 7. Al terminar el partido desaparece del Directo, pero el resultado queda
//    fijo en su fila de la quiniela.
{
    const partidos = [
        quinielaMatch(1, "Levante", "Atletico", "2026-08-29", "14:00", "FT"),
        quinielaMatch(2, "Rayo", "Celta", "2026-08-29", "16:15", "FINISHED"),
        quinielaMatch(3, "Betis", "Malaga", "2026-08-29", "18:30", "FT"),
    ];
    for (let i = 4; i <= 15; i++) {
        partidos.push(quinielaMatch(i, `Equipo${i}`, `Rival${i}`, "2026-08-29", "21:00", "NS"));
    }
    partidos[1].status = "FINISHED";
    const html = renderCover({
        jornada: 3,
        today_madrid: "2026-08-30",
        is_locked: true,
        partidos,
        all_league_matches: [],
        live_matches: [],
        simple_view: { jornada: "3", columns: [], rows: [], totals: {}, total_casillas: 14 },
    });
    const aside = (html.match(/<aside class="kk-live-aside"[\s\S]*?<\/aside>/) || [""])[0];
    const ticketRow = (html.match(/<tr class="cx-sv-row" data-id="1">[\s\S]*?<\/tr>/) || [""])[0];
    results.finishedMatchLifecycle = {
        goneFromLive: !aside,
        scoreStaysOnTicket: ticketRow.includes("cx-sv-result is-ft") && ticketRow.includes("1-0"),
    };
}

// 9. Un directo degradado (STALE) no se debe mostrar en el panel Directo aunque
//    conserve goles parciales.
{
    const stale = quinielaMatch(1, "Sevilla", "Valencia", "2026-08-29", "19:00", "STALE");
    stale.goles_local = 1;
    stale.goles_visitante = 0;
    const partidos = [stale];
    for (let i = 2; i <= 15; i++) {
        partidos.push(quinielaMatch(i, `Equipo${i}`, `Rival${i}`, "2026-08-29", "21:00", "NS"));
    }
    const html = renderCover({
        jornada: 3,
        today_madrid: "2026-08-30",
        is_locked: true,
        partidos,
        all_league_matches: [],
        live_matches: [],
        simple_view: { jornada: "3", columns: [], rows: [], totals: {}, total_casillas: 14 },
    });
    results.staleIsNotFinal = {
        aside: !html.includes("kk-live-aside"),
        noStaleScore: !html.includes('kk-live-score is-ft">1-0'),
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

    assert payload["externalLive"]["showsElche"], "el partido externo en juego no aparece en la franja EN DIRECTO"
    assert payload["externalLive"]["showsScore"], "el marcador del directo externo no se pinta"
    assert payload["externalLive"]["showsStrip"], "falta la franja kawaii de directo con partidos en juego"
    assert payload["externalLive"]["countLabel"] == "1", "la franja debe pintar un solo partido en juego"
    assert not payload["externalLive"]["emptyMessage"], "panel vacio pese a haber un partido en juego"


@pytest.mark.skipif(shutil.which("node") is None, reason="Node is required to exercise browser code")
def test_cover_directo_panel_empty_state_without_any_live_match():
    """Sin directos en ningun sitio, el panel lo dice sin mencionar la quiniela."""
    payload = _run_node()

    assert not payload["noLive"]["emptyMessage"], "el aviso vacio viejo del panel ha vuelto"
    assert not payload["noLive"]["oldMessage"], "el mensaje vacio ya no debe hablar solo de la quiniela"
    assert payload["noLive"]["noFakeLive"], "sin partidos en juego no debe pintarse una franja EN DIRECTO"


@pytest.mark.skipif(shutil.which("node") is None, reason="Node is required to exercise browser code")
def test_cover_directo_panel_keeps_quiniela_match_first_and_deduped():
    """Un directo de la quiniela sigue mostrandose, una sola vez."""
    payload = _run_node()

    assert payload["quinielaLive"]["shown"]
    assert payload["quinielaLive"]["onceInPanel"], "la quiniela y la copia del proveedor se pintan dos veces"
    assert payload["quinielaLive"]["countLabel"] == "1"


@pytest.mark.skipif(shutil.which("node") is None, reason="Node is required to exercise browser code")
def test_cover_directo_panel_lists_every_live_match_on_one_side():
    """El panel lateral muestra TODOS los directos, no solo el primero.

    Antes la portada pintaba un partido y un «+N»: con tres partidos en juego
    dos de ellos no estaban en ningun sitio.
    """
    payload = _run_node()
    many = payload["manyLive"]

    assert many["aside"], "falta el panel lateral de directos"
    assert many["count"] == "3", f"el panel debe listar los tres directos, hay {many['count']}"
    assert many["showsRacing"] and many["showsToulouse"], "falta un directo de fuera de la quiniela"
    assert many["showsLevante"], "el directo de la quiniela tambien va en el panel"
    assert many["quinielaSlot"], "la casilla de la quiniela debe marcarse con su numero"
    assert many["layout"], "con directos la portada debe abrir la maquetacion a dos columnas"


@pytest.mark.skipif(shutil.which("node") is None, reason="Node is required to exercise browser code")
def test_marcador_de_quiniela_aparece_una_vez_en_columna_resultado():
    """El marcador y minuto se muestran en Resultado, sin chip duplicado."""
    payload = _run_node()
    row = payload["rowLive"]

    assert not row["duplicateChip"], "el marcador no debe repetirse junto al nombre del partido"
    assert row["resultText"], "el marcador y minuto deben aparecer en la columna Resultado"
    assert row["resultLive"], "la columna de resultado debe pintarse como en directo"
    assert not row["staleDuplicateChip"], "un directo degradado (STALE) no puede pintarse en juego"
    assert not row["staleScore"], "un STALE no puede pintarse como resultado"
    assert row["stalePending"], "sin resultado verificado la casilla se queda pendiente"


@pytest.mark.skipif(shutil.which("node") is None, reason="Node is required to exercise browser code")
def test_marcador_externo_de_quiniela_aparece_en_columna_resultado():
    """Rayo/Celta del proveedor debe completar la fila aunque Q15 siga NS."""
    payload = _run_node()
    row = payload["providerLiveOnQuinielaRow"]

    assert row["resultCell"], "la columna Resultado no se marca en directo"
    assert row["score"], "falta el marcador del partido en Resultado"
    assert row["minute"], "falta el minuto del partido en Resultado"
    assert row["readableSlot"], "el panel debe explicar qué casilla de la quiniela está en juego"


@pytest.mark.skipif(shutil.which("node") is None, reason="Node is required to exercise browser code")
def test_el_final_sale_del_directo_y_permanece_en_la_quiniela():
    """Directo es efímero; el marcador final se conserva en la fila del boleto."""
    lifecycle = _run_node()["finishedMatchLifecycle"]

    assert lifecycle["goneFromLive"], "un partido terminado no debe quedarse en el panel Directo"
    assert lifecycle["scoreStaysOnTicket"], "el resultado final debe permanecer en la fila de la quiniela"


@pytest.mark.skipif(shutil.which("node") is None, reason="Node is required to exercise browser code")
def test_un_directo_degradado_no_se_pinta_como_resultado_final():
    """STALE conserva goles parciales para diagnostico, no es un marcador final."""
    stale = _run_node()["staleIsNotFinal"]

    assert stale["aside"], "un STALE no puede abrir el panel Directo"
    assert stale["noStaleScore"], "un STALE no puede pintarse como marcador definitivo"
