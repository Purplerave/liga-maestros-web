"""Regresiones de la portada: datos reales, clasificación y carga del directo."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(not shutil.which("node"), reason="Node.js no disponible")


def run_node(script):
    result = subprocess.run(
        ["node", "-e", script], cwd=ROOT, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def cover_render(payload, cached=None, live_match=None):
    # Mismo runtime clásico de la página, sin depender de un navegador instalado.
    script = r"""
const fs = require('fs');
const vm = require('vm');
const input = JSON.parse(INPUT);
const cached = JSON.parse(CACHED);
const match = JSON.parse(MATCH);
const storage = { getItem() { return null; }, setItem() {} };
const sandbox = {
    console, URLSearchParams, Date, setTimeout, clearTimeout, setInterval, clearInterval,
    document: { body: { classList: { add() {}, remove() {}, toggle() {} } },
        getElementById() { return null; }, querySelectorAll() { return []; },
        addEventListener() {} },
    window: { location: { search: '', pathname: '/' }, history: {}, localStorage: storage },
    localStorage: storage,
    requestAnimationFrame() {}, cancelAnimationFrame() {},
    input, cached, match,
};
vm.createContext(sandbox);
for (const file of ['static/js/utils.js', 'static/js/state.js', 'static/js/pages/cover_page.js']) {
    vm.runInContext(fs.readFileSync(file, 'utf8'), sandbox, { filename: file });
}
vm.runInContext(`
    state.data = input;
    state.jornada = String(input.jornada);
    state.q15Directo = cached;
    state.q15DirectoJornada = String(input.jornada);
    globalThis.result = {
        html: renderNewspaperCoverPageV3(),
        events: match ? kawaiiLiveEventsHtml(match) : null,
        item: match ? kawaiiLiveItemHtml(match) : null,
    };
`, sandbox);
console.log(JSON.stringify(sandbox.result));
"""
    script = (
        script.replace("JSON.parse(INPUT)", f"JSON.parse({json.dumps(json.dumps(payload))})")
        .replace("JSON.parse(CACHED)", f"JSON.parse({json.dumps(json.dumps(cached))})")
        .replace("JSON.parse(MATCH)", f"JSON.parse({json.dumps(json.dumps(live_match))})")
    )
    return run_node(script)


def competition_payload():
    columns = [
        {"id": "a", "name": "Alfa"},
        {"id": "b", "name": "Beta"},
        {"id": "c", "name": "Gamma"},
        {"id": "d", "name": "Delta & Co"},
    ]
    rows = []
    for index in range(1, 16):
        result = index <= 6 or index == 15
        pleno = index == 15
        rows.append({
            "id": index,
            "local": "Osasuna" if index == 2 else f"Local {index}",
            "visitante": "Athletic Club" if index == 2 else f"Visitante {index}",
            "fecha": "2026-11-07",
            "hora": "17:30",
            "cuando": "sabado 07/11 17:30",
            "resultado": ("2-0" if pleno else "1-0") if result else "",
            "has_result": result,
            "status": "FT" if result else "NS",
            "is_pleno": pleno,
            "picks": {
                "a": {"signo": "0-0" if pleno else "2", "hit": False if result else None},
                "b": {"signo": "2-0" if pleno else "1", "hit": True if result else None},
                "c": {"signo": "0-0" if pleno else "1", "hit": index <= 3 if result else None},
                "d": {"signo": "0-0" if pleno else "1", "hit": index <= 2 if result else None},
            },
        })
    return {
        "jornada": 19,
        "max_jornada": 19,
        "is_locked": False,
        "partidos": [{"id": 2, "local": "Osasuna", "visitante": "Athletic Club", "status": "NS"}],
        "live_matches": [],
        "simple_view": {
            "jornada": 19,
            "columns": columns,
            "rows": rows,
            "totals": {"a": {"aciertos": 0, "jugados": 6}, "b": {"aciertos": 6, "jugados": 6},
                       "c": {"aciertos": 3, "jugados": 6}, "d": {"aciertos": 2, "jugados": 6}},
            "total_casillas": 14,
            "pleno": {"b": {"acierto": True}},
            "competition_ranking": {
                "jornadas": [19, 17],
                "rows": [
                    {"id": "a", "name": "Alfa", "por_jornada": {"17": 5, "19": 0}, "total": 5},
                    {"id": "b", "name": "Beta", "por_jornada": {"17": 1, "19": 6}, "total": 7},
                    {"id": "c", "name": "Gamma", "por_jornada": {"17": 3, "19": 3}, "total": 6},
                    {"id": "d", "name": "Delta & Co", "por_jornada": {"19": 2}, "total": 2},
                ],
            },
        },
    }


def test_clasificacion_usa_puntuacion_jornadas_aciertos_y_movimiento_real():
    soup = BeautifulSoup(cover_render(competition_payload())["html"], "html.parser")
    assert len(soup.select(".cx-sv-body .cx-sv-row")) == 14
    assert len(soup.select(".cx-sv-pleno .is-pleno")) == 1
    assert [el.get_text(strip=True) for el in soup.select("th.cx-sv-col")] == [
        "Alfa", "Beta", "Gamma", "Delta & Co"
    ]
    assert soup.select_one(".lm-live-fold").has_attr("open")
    assert "has-live" not in soup.select_one(".kk-page")["class"]
    assert "SIN PARTIDOS EN JUEGO" in soup.select_one(".kk-live-aside").get_text(" ")
    rows = soup.select("tbody .cp-st-row")
    assert [row.select_one(".cp-st-name").get_text(strip=True) for row in rows] == [
        "Beta", "Gamma", "Alfa", "Delta & Co"
    ]
    assert [row.select_one(".cp-st-pts").get_text(strip=True) for row in rows] == ["7", "6", "5", "2"]
    assert [row.select_one(".cp-st-rounds").get_text(strip=True) for row in rows] == ["2", "2", "2", "1"]
    assert [row.select_one(".cp-st-hits").get_text(strip=True) for row in rows] == ["6", "3", "0", "2"]
    assert [row.select_one(".cp-st-trend").get_text(strip=True) for row in rows] == ["▲ 2", "=", "▼ 2", "—"]
    assert "Sube 2 puestos" in rows[0].select_one(".cp-st-trend span")["title"]
    assert "Sin posición anterior" in rows[3].select_one(".cp-st-trend span")["title"]
    assert "PLENO EXACTO: Beta" in soup.select_one(".cp-stats-foot").get_text(" ", strip=True)
    assert "J17 — J19 2" in soup.select(".cp-cmp-serie")[-1].get_text(" ", strip=True)
    assert "desplázate horizontalmente" in soup.select_one(".cx-sv-scroll")["aria-label"]


def test_empates_se_ordenan_y_el_mejor_compartido_no_inventa_un_ganador():
    payload = competition_payload()
    view = payload["simple_view"]
    # El empate por puntos sigue el desempate por nombre de la competición.
    view["competition_ranking"]["rows"][0].update(total=7, por_jornada={"17": 5, "19": 2})
    view["totals"]["a"]["aciertos"] = 2
    for row in view["rows"][:2]:
        row["picks"]["a"].update(signo="1", hit=True)
    soup = BeautifulSoup(cover_render(payload)["html"], "html.parser")
    rows = soup.select("tbody .cp-st-row")
    assert [row.select_one(".cp-st-name").get_text(strip=True) for row in rows[:2]] == ["Alfa", "Beta"]
    assert [row.select_one(".cp-st-trend").get_text(strip=True) for row in rows[:2]] == ["=", "▲ 1"]
    # Hay dos mejores en otra jornada; no se elige uno solo arbitrariamente.
    tied = competition_payload()
    tied["simple_view"]["totals"]["b"]["aciertos"] = 3
    tied["simple_view"]["competition_ranking"]["rows"][1].update(total=4, por_jornada={"17": 1, "19": 3})
    for row in tied["simple_view"]["rows"][3:6]:
        row["picks"]["b"].update(signo="2", hit=False)
    soup = BeautifulSoup(cover_render(tied)["html"], "html.parser")
    leader = soup.select_one(".cp-kpi.is-hot b")
    assert leader.get_text(strip=True) == "Empate (2)"
    assert leader["title"] == "Beta, Gamma"


def test_sin_resultados_no_inventa_aciertos_ni_lideres():
    payload = competition_payload()
    for row in payload["simple_view"]["rows"]:
        row.update(has_result=False, resultado="", status="NS")
        for pick in row["picks"].values():
            pick["hit"] = None
    payload["simple_view"]["totals"] = {key: {"aciertos": 0, "jugados": 0} for key in "abcd"}
    payload["simple_view"]["competition_ranking"] = {"jornadas": [], "rows": []}
    payload["simple_view"]["pleno"] = {}
    soup = BeautifulSoup(cover_render(payload)["html"], "html.parser")
    assert not soup.select("tbody .cp-st-row")
    assert "La clasificación aparecerá" in soup.select_one(".kk-rank-list").get_text(" ")
    assert [el.get_text(strip=True) for el in soup.select(".cp-cmp-val")] == ["—"] * 4
    assert soup.select_one(".cp-kpi.is-hot b").get_text(strip=True) == "—"
    assert "AÚN SIN RESULTADOS" in soup.select_one(".cp-stats-foot").get_text(" ", strip=True)


def test_directo_muestra_minuto_y_estado_de_descanso_y_permanece_accesible():
    payload = competition_payload()
    match = {"id": 2, "local": "Osasuna", "visitante": "Athletic Club", "status": "HT",
             "minuto_live": "45", "goles_local": 1, "goles_visitante": 0}
    payload["partidos"] = [match]
    payload["live_matches"] = [match]
    rendered = cover_render(payload, live_match=match)
    item = BeautifulSoup(rendered["item"], "html.parser")
    assert item.select_one(".kk-live-teams").get_text(" ", strip=True) == "Osasuna – Athletic Club"
    assert item.select_one(".kk-live-score").get_text(strip=True) == "1-0"
    assert item.select_one(".kk-live-min").get_text(strip=True) == "45'"
    assert item.select_one(".kk-live-stage").get_text(strip=True) == "DESCANSO"
    soup = BeautifulSoup(rendered["html"], "html.parser")
    assert "has-live" in soup.select_one(".kk-page")["class"]
    assert soup.select_one(".kk-live-list")["tabindex"] == "0"
    assert soup.select_one(".kk-rank-list")["tabindex"] == "0"


def test_eventos_solo_del_partido_y_jornada_correctos_y_con_escape_html():
    payload = competition_payload()
    match = {"id": 2, "local": "Osasuna", "visitante": "Athletic Club"}
    cached = {"jornada": 19, "matches": [{
        **match,
        "events": [{"team": "Osasuna", "events": [
            {"type": "goal", "minute": "33'", "player": "<Jugador> & Co"}
        ]}],
    }]}
    html = cover_render(payload, cached, match)["events"]
    assert "Gol" in html and "33&#039;" in html
    assert "&lt;Jugador&gt; &amp; Co" in html
    # Un proveedor puede mandar grupos vacíos: no deben ocultar eventos del
    # detalle compartido que sí están disponibles para ese mismo partido.
    match_with_empty_groups = {**match, "events": [{"team": "Osasuna", "events": []}]}
    assert "&lt;Jugador&gt;" in cover_render(payload, cached, match_with_empty_groups)["events"]
    cached["matches"][0]["visitante"] = "Otro rival"
    assert cover_render(payload, cached, match)["events"] == ""
    cached["matches"][0]["visitante"] = "Athletic Club"
    cached["jornada"] = 17
    assert cover_render(payload, cached, match)["events"] == ""


def test_repintado_preserva_scroll_archivo_y_foco_de_edicion():
    script = r"""
const fs = require('fs');
const vm = require('vm');
let focused = false;
const active = { dataset: {matchIdx: '0', sign: 'X'}, matches: selector => selector === '.kk-sign[data-sign]' };
let nodes = {
    '.kk-page': {},
    '.cx-sv-scroll': {scrollLeft: 424, scrollTop: 8},
    '.kk-live-list': {scrollLeft: 0, scrollTop: 63},
    '.kk-rank-list': {scrollLeft: 0, scrollTop: 14},
    '.cp-stats-card': {scrollLeft: 0, scrollTop: 20},
    '.kk-archive-card': {open: true},
};
const container = { querySelector: selector => nodes[selector] || null, contains: node => node === active };
const sandbox = { document: {activeElement: active}, console, Date };
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync('static/js/pages/cover_page.js', 'utf8'), sandbox);
const saved = sandbox.captureCoverUi(container);
nodes = {
    '.kk-page': {},
    '.cx-sv-scroll': {scrollLeft: 0, scrollTop: 0},
    '.kk-live-list': {scrollLeft: 0, scrollTop: 0},
    '.kk-rank-list': {scrollLeft: 0, scrollTop: 0},
    '.cp-stats-card': {scrollLeft: 0, scrollTop: 0},
    '.kk-archive-card': {open: false},
    '.kk-sign[data-match-idx="0"][data-sign="X"]': {focus: options => { focused = options.preventScroll; }},
};
sandbox.restoreCoverUi(container, saved);
console.log(JSON.stringify({table: nodes['.cx-sv-scroll'], live: nodes['.kk-live-list'].scrollTop,
    ranking: nodes['.kk-rank-list'].scrollTop, stats: nodes['.cp-stats-card'].scrollTop,
    archive: nodes['.kk-archive-card'].open, focused}));
"""
    assert run_node(script) == {
        "table": {"scrollLeft": 424, "scrollTop": 8},
        "live": 63,
        "ranking": 14,
        "stats": 20,
        "archive": True,
        "focused": True,
    }


def test_cuenta_atras_sin_hora_valida_no_afirma_que_esta_cerrada():
    script = r"""
const fs = require('fs');
const vm = require('vm');
const source = fs.readFileSync('static/js/pages/cover_page.js', 'utf8');
function clock(data) {
    const element = { textContent: '', innerHTML: '', closest: () => null };
    const sandbox = {
        state: { data }, Date, console, setInterval() {},
        document: { getElementById: id => id === 'cx-cd' ? element : null },
    };
    vm.createContext(sandbox);
    vm.runInContext(source, sandbox);
    sandbox.startCoverCountdown();
    return { text: element.textContent, html: element.innerHTML };
}
console.log(JSON.stringify({
    missing: clock({is_locked: false}),
    invalid: clock({is_locked: false, edit_deadline: 'sin confirmar'}),
    locked: clock({is_locked: true}),
    future: clock({is_locked: false, edit_deadline: '2099-12-31 23:59'}),
}));
"""
    result = run_node(script)
    assert result["missing"]["text"] == "SIN HORA"
    assert result["invalid"]["text"] == "SIN HORA"
    assert "CERRADA" in result["locked"]["html"]
    assert "cx-cd-block" in result["future"]["html"]


def test_abrir_portada_por_defecto_no_guarda_preferencia_para_otras_vistas():
    script = r"""
const fs = require('fs');
const vm = require('vm');
const source = fs.readFileSync('static/js/events.js', 'utf8');
const start = source.indexOf('function bindLivePanelFold()');
const end = source.indexOf('function bindEvents()', start);
let handler, saved = [];
const sandbox = {
    document: { addEventListener: (type, callback) => { if (type === 'toggle') handler = callback; } },
    rememberLivePanelOpen: open => saved.push(open),
};
vm.createContext(sandbox);
vm.runInContext(source.slice(start, end), sandbox);
sandbox.bindLivePanelFold();
const cover = { classList: { contains: value => value === 'lm-live-fold' }, dataset: {initialOpen: '1'}, open: true };
handler({target: cover}); // toggle que produce el atributo inicial
const afterInitial = saved.slice();
cover.open = false;
handler({target: cover}); // el usuario lo pliega
cover.open = true;
handler({target: cover}); // y lo vuelve a desplegar
const afterUser = saved.slice();
// Si el usuario lo cierra antes de recibir el primer toggle, también cuenta.
const quickClose = { ...cover, dataset: {initialOpen: '1'}, open: false };
handler({target: quickClose});
const ticket = { ...cover, dataset: {}, open: true };
handler({target: ticket}); // la vista TICKET conserva su comportamiento
console.log(JSON.stringify({afterInitial, afterUser, afterQuickCloseAndTicket: saved}));
"""
    assert run_node(script) == {
        "afterInitial": [],
        "afterUser": [False, True],
        "afterQuickCloseAndTicket": [False, True, False, True],
    }


def test_poll_sin_cambios_tambien_revisa_eventos_del_directo():
    script = r"""
const fs = require('fs');
const vm = require('vm');
const source = fs.readFileSync('static/js/events.js', 'utf8');
const start = source.indexOf('async function refreshLiveSnapshot()');
const end = source.indexOf('/* La paleta de comandos', start);
let checks = 0, status = 304;
const sandbox = {
    console, document: {hidden: false},
    state: {data: {jornada: '19', partidos: [], live_matches: [], all_league_matches: []}, jornada: '19'},
    liveSnapshotEtag: null, liveSnapshotEtagJornada: '', liveIdlePolls: 0,
    logoCache: new Map(), logoAliasIndex: null,
    LIVE_VOLATILE_KEYS: [], LIVE_HEAVY_SYNC_POLLS: 5,
    resultsSignature: () => '', standingsSignature: () => '', consensoSignature: () => '', rankingSignature: () => '',
    refreshCoverLiveEvents: () => { checks++; },
    fetch: async () => status === 304 ? {status} : {
        status, ok: true, headers: {get: () => null},
        json: async () => ({jornada: '19', slim: true, partidos: [], live_matches: [], all_league_matches: []}),
    },
};
vm.createContext(sandbox);
vm.runInContext(source.slice(start, end), sandbox);
(async () => {
    const notModified = await sandbox.refreshLiveSnapshot();
    status = 200;
    const unchanged = await sandbox.refreshLiveSnapshot();
    console.log(JSON.stringify({notModified, unchanged, checks}));
})().catch(error => { console.error(error); process.exit(1); });
"""
    assert run_node(script) == {"notModified": True, "unchanged": True, "checks": 2}


def test_carga_directo_comparte_peticion_respeta_ttl_y_descarta_jornada_antigua():
    script = r"""
const fs = require('fs');
const vm = require('vm');
const source = fs.readFileSync('static/js/quantum_final.js', 'utf8');
const start = source.indexOf('const q15RequestsInFlight =');
const end = source.indexOf('// --- Porra ---', start);
if (start < 0 || end < 0) throw Error('No se encontró el cargador del directo');
let calls = 0;
const sandbox = { console, Date, Map, setTimeout,
    state: { jornada: '19', data: { jornada: 19 }, q15Directo: null,
        q15DirectoJornada: '', q15DirectoLoadedAt: 0 },
    fetch: async () => {
        calls++;
        const jornada = sandbox.state.data.jornada;
        await new Promise(resolve => setTimeout(resolve, 15));
        return { ok: true, json: async () => ({ jornada, matches: [] }) };
    },
};
vm.createContext(sandbox);
vm.runInContext(source.slice(start, end), sandbox);
(async () => {
    const simultaneous = await Promise.all([
        sandbox.ensureQ15Directo({maxAgeMs: 60000}),
        sandbox.ensureQ15Directo({maxAgeMs: 60000}),
        sandbox.ensureQ15Directo({maxAgeMs: 60000}),
    ]);
    const countAfterSimultaneous = calls;
    const cached = await sandbox.ensureQ15Directo({maxAgeMs: 60000});
    const countAfterCache = calls;
    const forced = await sandbox.ensureQ15Directo({maxAgeMs: 0});
    const countAfterExpiry = calls;
    const oldRequest = sandbox.ensureQ15Directo({maxAgeMs: 0});
    sandbox.state.jornada = '20';
    sandbox.state.data.jornada = 20;
    const outdated = await oldRequest;
    const storedBeforeNew = sandbox.state.q15Directo.jornada;
    const fresh = await sandbox.ensureQ15Directo({maxAgeMs: 60000});
    console.log(JSON.stringify({simultaneous, countAfterSimultaneous, cached, countAfterCache,
        forced, countAfterExpiry, outdated, storedBeforeNew, fresh,
        storedAfterNew: sandbox.state.q15Directo.jornada, calls}));
})().catch(error => { console.error(error); process.exit(1); });
"""
    result = run_node(script)
    assert result == {
        "simultaneous": [True, True, True],
        "countAfterSimultaneous": 1,
        "cached": False,
        "countAfterCache": 1,
        "forced": True,
        "countAfterExpiry": 2,
        "outdated": False,
        "storedBeforeNew": 19,
        "fresh": True,
        "storedAfterNew": 20,
        "calls": 4,
    }
