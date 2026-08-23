import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COVER_JS = ROOT / "static" / "js" / "pages" / "cover_page.js"
COVER_CSS = ROOT / "static" / "css" / "cover_hero.css"
PORRA_JS = ROOT / "static" / "js" / "quantum_final.js"
PORRA_ROUTE = ROOT / "liga_maestros" / "routes" / "porra.py"


def test_cover_fills_lower_panel_with_useful_journey_actions():
    """Portada v14: comando compacto + tablero 3 cartas + ops."""
    cover = COVER_JS.read_text(encoding="utf-8")
    css = COVER_CSS.read_text(encoding="utf-8")

    assert 'class="cp-journey-card"' in cover
    assert 'id="cover-porra-step-status"' in cover
    assert "cp-duel" in cover
    assert "cp-featured" in cover
    assert "cp-main" in cover
    assert "cp-ops" in cover
    assert "cp-command-brand" in cover
    assert "cp-quicklinks-footer" not in cover
    assert ".cp-journey-card" in css
    assert ".cp-main" in css
    assert ".cp-arena" in css
    assert "grid-template-columns: repeat(3, minmax(0, 1fr))" in css


def test_cover_keeps_alerts_inside_the_panel():
    """Scorebar y urgencia viven en el panel, no como filas sueltas del app-shell."""
    cover = COVER_JS.read_text(encoding="utf-8")
    template = (ROOT / "templates" / "liga_index.html").read_text(encoding="utf-8")
    assert 'id="cp-scorebar"' in cover
    assert 'id="cp-urgency"' in cover
    assert 'id="cp-scorebar"' not in template
    assert 'id="cp-urgency"' not in template
    # La voz del duelo es una carta del tablero, no un tercer hijo que rompe el grid.
    arena_idx = cover.find('class="cp-arena"')
    voz_idx = cover.find("${coverTrashTalkHtml()}")
    ops_idx = cover.find('class="cp-ops"')
    assert arena_idx != -1 and voz_idx != -1 and ops_idx != -1
    assert arena_idx < voz_idx < ops_idx


def test_cover_pena_vote_uses_backend_percentages():
    """p1/px/p2 de consenso_pena ya vienen en tanto por ciento. No volver a * total * 100."""
    cover = COVER_JS.read_text(encoding="utf-8")
    assert "function coverAggregatePenaVote" in cover
    assert "function coverPenaPercents" in cover
    assert "PEÑISTA" in cover
    assert "(v1 / totalPct) * 100" not in cover
    assert "Number(rowCons.p1 || 0) / t" not in cover
    assert "totalVotes += t" not in cover
    css = COVER_CSS.read_text(encoding="utf-8")
    assert ".cx-cons-bar" in css


def test_cover_masters_use_column_logos_and_plain_signs():
    """Portada: una columna por Maestro con logo arriba y signo 1/X/2 normal.

    Sustituye la celda única «MAESTROS» con pastillas de color (.cx-mi) por
    columnas reales: cabecera con logo SVG + abreviatura y celdas solo con
    el signo, más una columna PEÑA con el signo de consenso.
    """
    logo_dir = ROOT / "static" / "img" / "maestros"
    for name in ("claude", "chatgpt", "gemini", "grok", "copilot", "programa"):
        assert (logo_dir / f"{name}.svg").is_file(), f"falta el logo de {name}.svg"

    cover = COVER_JS.read_text(encoding="utf-8")
    assert "_mlogoSrc" in cover
    assert "_mshort" in cover
    assert "cx-r-ia" in cover
    assert "cx-ia-sign" in cover
    assert "masterHeads" in cover
    # El Programa (PRG) es una columna oficial más del boleto: su columna no
    # debe filtrarse en la portada (los datos llegan en predicciones_actuales).
    assert '!String(col.id || "").toLowerCase().includes("programa")' not in cover
    # Las pastillas de color y la celda única desaparecen del boleto.
    assert "cx-r-masters" not in cover
    assert "cx-mi-shape" not in cover

    css = COVER_CSS.read_text(encoding="utf-8")
    assert ".cx-mi-logo" in css
    assert ".cx-ia-sign" in css


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


def test_cover_boleto_shows_finished_scores_not_only_kickoff():
    """Portada: partidos finalizados pintan el marcador, no solo la hora."""
    cover = COVER_JS.read_text(encoding="utf-8")
    css = COVER_CSS.read_text(encoding="utf-8")

    assert "function _whenLabel" in cover
    assert "function _whenCell" in cover
    assert "function _finished" in cover
    assert "HORA / RES" in cover
    assert ">HORA</th>" not in cover
    assert "is-ft-score" in cover
    assert "is-live-score" in cover
    assert "RESULTADOS" in cover
    assert "cx-ticker-item is-ft" in cover
    assert ".cx-r-when.is-ft-score" in css
    assert ".cx-up-card.is-ft" in css


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
