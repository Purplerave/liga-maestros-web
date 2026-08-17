"""Contratos de navegador para nombres de equipo y directos en la clasificacion.

Reproduce dos averias reportadas el 16/08/2026:

* El partido 13 mostraba "LAS.." en vez de "LAS PALMAS": el nombre corto se
  generaba recortando caracteres, asi que cualquier club cuyo nombre empieza
  por un articulo ("Las Palmas") o por siglas ("CE Sabadell", "CD Eldense")
  perdia justo la palabra que lo identifica.
* Un partido del Sevilla ya terminado seguia mostrando su marcador como si
  estuviera en juego en la clasificacion.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
UTILS = ROOT / "static" / "js" / "utils.js"
STANDINGS = ROOT / "static" / "js" / "standings.js"

requires_node = pytest.mark.skipif(
    shutil.which("node") is None, reason="Node is required to exercise browser utility functions"
)


def _run_node(script):
    result = subprocess.run(["node", "-e", script], cwd=ROOT, check=True, text=True, capture_output=True)
    return json.loads(result.stdout)


@requires_node
def test_short_names_never_cut_a_club_name_in_half():
    script = f"""
        const fs = require("fs");
        const vm = require("vm");
        const context = {{ console, Map, String, Number, Date, JSON, Set, RegExp }};
        vm.createContext(context);
        vm.runInContext(fs.readFileSync({json.dumps(str(UTILS))}, "utf8"), context);
        const names = [
            "UD Las Palmas", "Las Palmas", "CE Sabadell", "CD Eldense", "Real Sporting",
            "Celta", "Celta Fortuna", "Real Zaragoza", "Albacete BP", "AD Ceuta FC",
            "Real Oviedo", "R. Sociedad B", "FC Barcelona"
        ];
        const out = {{}};
        for (const name of names) out[name] = context.getShortName(name);
        console.log(JSON.stringify(out));
    """
    short = _run_node(script)

    assert short["UD Las Palmas"] == "LAS PALMAS"
    assert short["Las Palmas"] == "LAS PALMAS"
    assert short["CE Sabadell"] == "SABADELL"
    assert short["CD Eldense"] == "ELDENSE"
    assert short["Real Zaragoza"] == "ZARAGOZA"
    assert short["AD Ceuta FC"] == "CEUTA"
    assert short["Real Sporting"] == "SPORTING"
    assert short["FC Barcelona"] == "BARCA"
    # Un filial y su primer equipo no pueden compartir etiqueta.
    assert short["Celta"] != short["Celta Fortuna"]
    assert short["Real Oviedo"] != short["R. Sociedad B"]


@requires_node
def test_short_names_are_never_truncated_mid_word():
    script = f"""
        const fs = require("fs");
        const vm = require("vm");
        const context = {{ console, Map, String, Number, Date, JSON, Set, RegExp }};
        vm.createContext(context);
        vm.runInContext(fs.readFileSync({json.dumps(str(UTILS))}, "utf8"), context);
        const roster = [
            "RCD Mallorca", "Girona FC", "Real Oviedo", "UD Almeria", "UD Las Palmas",
            "CD Castellon", "Burgos CF", "SD Eibar", "Cordoba CF", "Albacete BP",
            "AD Ceuta FC", "FC Andorra", "Real Sporting", "Granada CF", "Real Valladolid CF",
            "Cadiz CF", "CD Leganes", "CD Tenerife", "CD Eldense", "CE Sabadell",
            "Sevilla FC", "Rayo Vallecano", "Deportivo Alaves", "Getafe CF", "Levante UD"
        ];
        const out = roster.map(name => [name, context.getShortName(name)]);
        console.log(JSON.stringify(out));
    """
    pairs = _run_node(script)

    for original, short in pairs:
        assert short, f"{original} se quedo sin nombre corto"
        assert len(short) >= 4, f"{original} se abrevio hasta ser ilegible: {short!r}"
        # Cada palabra mostrada existe entera en el nombre original (o es una
        # inicial abreviada tipo "R."), nunca un trozo suelto como "ZARAGOZ".
        source = original.upper().replace(".", "")
        for word in short.split(" "):
            token = word.rstrip(".")
            assert len(token) <= 2 or token in source.replace("Á", "A"), (
                f"{original} => {short}: '{word}' no aparece completo en el nombre original"
            )


def test_live_standings_use_the_strict_live_guard():
    """La clasificacion no puede fiarse de la etiqueta de estado a secas."""
    source = STANDINGS.read_text(encoding="utf-8")

    assert "isMatchLiveNow" in source, "hay que descartar directos caducados o ya finalizados"
    assert "isLiveMatch(" not in source, "isLiveMatch no descarta un partido terminado"
    assert "function getFinishedStandingsTeams()" in source
    assert "function teamLiveState(team, liveResults, finishedTeams)" in source
    assert 'if (finishedTeams.has(key)) return { live: false, score: "" };' in source


def _standings_script(partidos, all_league_matches, teams):
    """Render the standings page in a bare VM with a controlled clock.

    ``ago(minutes)`` yields the ``fecha_raw``/``hora`` of a kickoff that many
    minutes ago, so the fixtures are always relative to the moment the test
    runs and never drift out of the live window.
    """
    template = r"""
        const fs = require("fs");
        const vm = require("vm");
        const context = { console, Map, String, Number, Date, JSON, Set, RegExp, Array, Boolean, Object };
        vm.createContext(context);
        vm.runInContext(fs.readFileSync(__UTILS__, "utf8"), context);
        vm.runInContext(fs.readFileSync(__LOGOS__, "utf8"), context);
        context.findTeamLogo = () => "";
        const now = new Date();
        const iso = d => d.toISOString().slice(0, 10);
        const hm = d => String(d.getHours()).padStart(2, "0") + ":" + String(d.getMinutes()).padStart(2, "0");
        const ago = minutes => {
            const d = new Date(now.getTime() - minutes * 60000);
            return { fecha_raw: iso(d), hora: hm(d) };
        };
        context.state = { data: {
            today_madrid: iso(now),
            jornada_liga: 1,
            partidos: (__PARTIDOS__)(ago),
            all_league_matches: (__LEAGUE_MATCHES__)(ago),
            multi_league_standings: { leagues: [{ name: "LA LIGA", teams: __TEAMS__ }] }
        } };
        vm.runInContext(fs.readFileSync(__STANDINGS__, "utf8"), context);
        const rows = {};
        for (const row of context.renderFullStandingsPage().split("<tr").slice(1)) {
            const name = (row.match(/<span>([^<]+)<\/span>/) || [])[1];
            if (!name) continue;
            const live = (row.match(/standings-live[^>]*>([^<]*)</) || [])[1] || "";
            rows[name] = { live: live.replace("\u25cf", "").trim(), playing: row.includes("is-playing") };
        }
        console.log(JSON.stringify(rows));
    """
    replacements = {
        "__UTILS__": json.dumps(str(UTILS)),
        "__LOGOS__": json.dumps(str(ROOT / "static" / "js" / "logos.js")),
        "__STANDINGS__": json.dumps(str(STANDINGS)),
        "__PARTIDOS__": partidos,
        "__LEAGUE_MATCHES__": all_league_matches,
        "__TEAMS__": teams,
    }
    for placeholder, value in replacements.items():
        template = template.replace(placeholder, value)
    return template


@requires_node
def test_finished_match_stops_showing_a_live_score_in_the_classification():
    """El partido del Sevilla ya habia acabado y seguia con marcador en vivo.

    El servidor puede mandar la fila con ``en_juego`` (respuesta cacheada o
    colector caido). Si el navegador ve que el partido termino, el distintivo
    de directo desaparece y solo quedan puntos y goles.
    """
    rows = _run_node(
        _standings_script(
            partidos="""ago => [
                { id: 2, local: "Sevilla", visitante: "Rayo Vallecano", status: "LIVE",
                  marcador: "2-1", marcador_base: "2-1", minuto_live: "90", ...ago(300) },
                { id: 5, local: "Celta", visitante: "Osasuna", status: "LIVE",
                  marcador: "1-0", marcador_base: "1-0", minuto_live: "30", ...ago(30) }
            ]""",
            all_league_matches="ago => []",
            teams="""[
                { n: "Sevilla FC", pj: 1, pg: 1, pe: 0, pp: 0, gf: 2, gc: 1, dg: 1, pts: 3,
                  form: ["W"], streak: "1W", en_juego: true, marcador_live: "2-1" },
                { n: "Celta", pj: 0, pg: 0, pe: 0, pp: 0, gf: 0, gc: 0, dg: 0, pts: 0,
                  form: [], streak: "", en_juego: true, marcador_live: "1-0" },
                { n: "Real Madrid", pj: 0, pg: 0, pe: 0, pp: 0, gf: 0, gc: 0, dg: 0, pts: 0,
                  form: [], streak: "", en_juego: false, marcador_live: "" }
            ]""",
        )
    )

    assert rows["Sevilla FC"] == {"live": "", "playing": False}, "un partido acabado no puede seguir en directo"
    assert rows["Celta"] == {"live": "1-0", "playing": True}, "el directo real si tiene que verse"
    assert rows["Real Madrid"] == {"live": "", "playing": False}


@requires_node
def test_live_match_outside_the_quiniela_is_shown_in_the_classification():
    """Un directo que no pertenece a la quiniela tambien tiene que verse."""
    rows = _run_node(
        _standings_script(
            partidos="ago => []",
            all_league_matches="""ago => [
                { local: "Real Madrid", visitante: "Villarreal", status: "LIVE", score: "1-0",
                  competition_name: "LA LIGA", minute: "20", ...ago(20) }
            ]""",
            teams="""[
                { n: "Real Madrid", pj: 0, pg: 0, pe: 0, pp: 0, gf: 0, gc: 0, dg: 0, pts: 0,
                  form: [], streak: "", en_juego: false, marcador_live: "" },
                { n: "Villarreal CF", pj: 0, pg: 0, pe: 0, pp: 0, gf: 0, gc: 0, dg: 0, pts: 0,
                  form: [], streak: "", en_juego: false, marcador_live: "" }
            ]""",
        )
    )

    assert rows["Real Madrid"] == {"live": "1-0", "playing": True}
    assert rows["Villarreal CF"] == {"live": "0-1", "playing": True}


@requires_node
def test_accented_panel_competition_still_shows_the_live_score():
    """'Segunda División' llega con tilde desde el panel: el directo se ve igual."""
    rows = _run_node(
        _standings_script(
            partidos="ago => []",
            all_league_matches="""ago => [
                { local: "Castellón", visitante: "R. Sociedad B", status: "LIVE", score: "1-0",
                  competition_name: "Segunda División", minute: "20", ...ago(20) }
            ]""",
            teams="""[
                { n: "CD Castellón", pj: 0, pg: 0, pe: 0, pp: 0, gf: 0, gc: 0, dg: 0, pts: 0,
                  form: [], streak: "", en_juego: false, marcador_live: "" },
                { n: "R. Sociedad B", pj: 0, pg: 0, pe: 0, pp: 0, gf: 0, gc: 0, dg: 0, pts: 0,
                  form: [], streak: "", en_juego: false, marcador_live: "" }
            ]""",
        )
    )

    assert rows["CD Castellón"] == {"live": "1-0", "playing": True}
    assert rows["R. Sociedad B"] == {"live": "0-1", "playing": True}
