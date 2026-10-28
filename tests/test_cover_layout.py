import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COVER_JS = ROOT / "static" / "js" / "pages" / "cover_page.js"
COVER_CSS = ROOT / "static" / "css" / "cover_hero.css"
PORRA_JS = ROOT / "static" / "js" / "quantum_final.js"
PORRA_ROUTE = ROOT / "liga_maestros" / "routes" / "porra.py"


def test_cover_pick_cell_shows_the_sign_without_glyphs():
    """La columna TU se leia regular: con un doble el signo se cortaba y las
    columnas de los Maestros llevaban una raya diagonal que parecia una "x".

    El acierto y el fallo se avisan con color y fondo, nunca con un glifo o una
    tachadura pegados encima del signo.
    """
    css = COVER_CSS.read_text(encoding="utf-8")

    # Ni un glifo pegado al signo de la quiniela del usuario...
    assert "is-hit .cx-r-pick-val::after" not in css
    assert "is-miss .cx-r-pick-val::after" not in css
    # ...ni una raya atravesando el signo de los Maestros o La Pena.
    assert "is-miss::before" not in css
    # La casilla del signo tiene que hospedar un doble ("12") sin recorte.
    # Resultado a la izquierda del TÚ, los dos grandes y legibles.
    assert ".cx-r-pick { text-align: center; width: 88px; }" in css
    assert "min-width: 46px;" in css
    assert "white-space: nowrap;" in css
    assert ".cx-r-when-val" in css


def test_cover_pick_cell_contrast_is_readable():
    css = COVER_CSS.read_text(encoding="utf-8")

    assert "rgba(239, 68, 68, 0.26)" in css  # fondo del fallo con alpha suficiente
    assert "color: #fff1f2;" in css  # texto del fallo sobre fondo rojo
    assert "color: #052e16;" in css  # texto del acierto sobre verde


def test_cover_boleto_includes_programa_column():
    """La quiniela de la portada muestra la columna del Programa (PRG).

    El contrato de participantes lista 6 columnas oficiales y `_visibleMasters`
    debe devolverlas todas: si el Programa se filtra, sus 15 signos quedan
    visibles solo en la vista TICKET y la portada los oculta.
    """
    import shutil
    import subprocess

    if shutil.which("node") is None:
        import pytest

        pytest.skip("Node is required to exercise cover helpers")

    script = """
        const fs = require("fs");
        const vm = require("vm");
        const ctx = { console, Map, Set, String, Number, Date, JSON, Math,
            document: { body: { dataset: { assetsV: "test" } } } };
        vm.createContext(ctx);
        vm.runInContext(fs.readFileSync("static/js/pages/cover_page.js", "utf8"), ctx);
        ctx.state = { data: { participant_contract: { visible_ai_columns: [
            { id: "programa", label: "PROG", name: "Programa" },
            { id: "claude", label: "CLAU", name: "Claude" },
            { id: "grok", label: "GROK", name: "Grok" },
            { id: "chatgpt", label: "GPT", name: "ChatGPT" },
            { id: "copilot", label: "COP", name: "Copilot" },
            { id: "gemini", label: "GEM", name: "Gemini" }
        ] } } };
        const visible = ctx._visibleMasters(ctx.coverMasterColumns());
        console.log(JSON.stringify({
            ids: visible.map(c => c.id),
            short: ctx._mshort({ id: "programa", label: "Programa" }),
            tone: ctx._mtone({ id: "programa", label: "Programa" })
        }));
    """
    result = subprocess.run(["node", "-e", script], cwd=ROOT, check=True, text=True, capture_output=True)
    payload = json.loads(result.stdout)
    assert payload["ids"] == ["programa", "claude", "grok", "chatgpt", "copilot", "gemini"]
    assert payload["short"] == "PRG"
    assert payload["tone"] == "is-programa"


def test_cover_when_label_switches_from_schedule_to_score():
    """Un partido FT muestra 2-1; uno NS sigue mostrando el horario."""
    import shutil
    import subprocess

    if shutil.which("node") is None:
        import pytest

        pytest.skip("Node is required to exercise cover helpers")

    script = r"""
        const fs = require("fs");
        const vm = require("vm");
        const ctx = {
            console, Map, Set, String, Number, Date, JSON, Math,
            document: { body: { dataset: { assetsV: "test" } } },
            escapeHtml(value) { return String(value ?? ""); },
            state: { data: { partidos: [] } },
            isFinishedStatus(status) {
                return ["FT", "FINISHED", "TERMINADO"].includes(String(status || "").toUpperCase());
            },
            isImplicitlyFinished() { return false; },
            isExpiredLiveMatch() { return false; },
            isMatchLiveNow(m) { return String(m.status || "").toUpperCase() === "LIVE"; },
            isLiveStatus(status) { return String(status || "").toUpperCase() === "LIVE"; },
            needsFixtureSchedule(m) { return String(m.status || "").toUpperCase() === "NS"; },
            scoreOnly(value) {
                const m = String(value || "").match(/^(\d+\s*[-–]\s*\d+)/);
                return m ? m[1].replace(/\s/g, "") : null;
            },
            liveScoreDisplay(m) { return m.marcador_base || `${m.goles_local}-${m.goles_visitante}`; },
            liveScoreWithMinute(m, fallback) {
                return m.minuto_live ? `${fallback} · ${m.minuto_live}'` : fallback;
            },
            fixtureScheduleDisplay(m) { return m.hora ? `${m.hora}h` : "Horario por confirmar"; },
        };
        vm.createContext(ctx);
        vm.runInContext(fs.readFileSync("static/js/pages/cover_page.js", "utf8"), ctx);
        const ft = {
            id: 1, local: "Barça", visitante: "Getafe",
            status: "FT", hora: "16:00", kickoff: "16:00",
            goles_local: 2, goles_visitante: 1,
            marcador: "2-1", marcador_base: "2-1", signo_actual: "1",
        };
        const live = {
            id: 2, local: "Madrid", visitante: "Sevilla",
            status: "LIVE", hora: "18:30",
            goles_local: 0, goles_visitante: 0,
            marcador: "0-0 (67')", marcador_base: "0-0",
            minuto_live: "67", signo_actual: "X",
        };
        const ns = {
            id: 3, local: "Betis", visitante: "Valencia",
            status: "NS", hora: "21:00", kickoff: "21:00",
            marcador: "domingo 21:00h", marcador_base: "",
        };
        console.log(JSON.stringify({
            ftKind: ctx._whenKind(ft),
            ftLabel: ctx._whenLabel(ft),
            ftCell: ctx._whenCell(ft),
            liveKind: ctx._whenKind(live),
            liveLabel: ctx._whenLabel(live),
            nsKind: ctx._whenKind(ns),
            nsLabel: ctx._whenLabel(ns),
        }));
    """
    result = subprocess.run(["node", "-e", script], cwd=ROOT, check=True, text=True, capture_output=True)
    payload = json.loads(result.stdout)
    assert payload["ftKind"] == "finished"
    assert payload["ftLabel"] == "2-1"
    assert "is-ft-score" in payload["ftCell"]
    assert "2-1" in payload["ftCell"]
    assert "16:00" not in payload["ftCell"]
    assert payload["liveKind"] == "live"
    assert "0-0" in payload["liveLabel"]
    assert "67" in payload["liveLabel"]
    assert payload["nsKind"] == "scheduled"
    assert "21:00" in payload["nsLabel"]


def test_porra_bonus_copy_is_short_and_consistent():
    files = (PORRA_JS, PORRA_ROUTE, COVER_JS)
    combined = "\n".join(path.read_text(encoding="utf-8") for path in files)

    assert "Marcador exacto: +2 puntos." in combined
    assert "Tú eliges el partido para tu porra" not in combined
    assert "te llevas +2 puntos extra para la general" not in combined
