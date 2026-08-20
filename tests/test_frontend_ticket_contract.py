"""Browser-side contracts for ticket signs, fixture labels and Directo groups."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
UTILS = ROOT / "static" / "js" / "utils.js"
ARENA = ROOT / "static" / "js" / "arena.js"
TICKET = ROOT / "static" / "js" / "pages" / "ticket_page.js"


@pytest.mark.skipif(shutil.which("node") is None, reason="Node is required to exercise browser utility functions")
def test_frontend_keeps_doubles_and_pleno_scores_and_reads_league_names():
    """The browser must not turn 1X or 2-1 into an empty dash."""
    script = f"""
        const fs = require("fs");
        const vm = require("vm");
        const context = {{ console, Map, String, Number, Date, JSON, Set }};
        vm.createContext(context);
        vm.runInContext(fs.readFileSync({json.dumps(str(UTILS))}, "utf8"), context);
        vm.runInContext(fs.readFileSync({json.dumps(str(ARENA))}, "utf8"), context);
        context.renderMatchCard = match => `<article>${{match.local}}</article>`;
        context.isLiveMatch = () => false;
        context.state = {{ data: {{ today_madrid: "2026-08-16" }} }};
        const grouped = context.renderGroupedMatchCards([
            {{ local: "A", competition: {{ name: "La Liga" }} }},
            {{ local: "B", competition_name: "Segunda Division" }},
            {{ local: "C", competition: {{ name: "La Liga" }} }}
        ]);
        console.log(JSON.stringify({{
            double: context.normalizeSign("x1"),
            triple: context.normalizeSign("21x"),
            pleno: context.normalizeSign("2 - 1"),
            plenoBucket: context.plenoScoreKey("3-1"),
            namedCompetition: context.competitionLabel({{ competition_name: "La Liga" }}),
            objectCompetition: context.competitionLabel({{ competition: {{ name: "Segunda Division" }} }}),
            sameDayFixture: context.fixtureScheduleDisplay({{ fecha_raw: "2026-08-16", hora: "21:30" }}),
            olderFixture: context.fixtureScheduleDisplay({{ fecha_raw: "2026-08-15", hora: "21:30" }}),
            groupCount: (grouped.match(/league-match-group/g) || []).length,
            hasLaLigaGroup: grouped.includes('data-competition="LA LIGA"'),
            hasSegundaGroup: grouped.includes('data-competition="SEGUNDA DIVISION"')
        }}));
    """
    result = subprocess.run(["node", "-e", script], cwd=ROOT, check=True, text=True, capture_output=True)
    payload = json.loads(result.stdout)

    assert payload == {
        "double": "1X",
        "triple": "1X2",
        "pleno": "2-1",
        "plenoBucket": "M-1",
        "namedCompetition": "LA LIGA",
        "objectCompetition": "SEGUNDA DIVISION",
        "sameDayFixture": "21:30h",
        "olderFixture": "sab 15/08 21:30h",
        "groupCount": 2,
        "hasLaLigaGroup": True,
        "hasSegundaGroup": True,
    }


@pytest.mark.skipif(shutil.which("node") is None, reason="Node is required to exercise browser utility functions")
def test_ticket_pena_percentages_render_as_visible_breakdown():
    """La columna Peña muestra 1/X/2 en % sin recortar ni reescalar p1/px/p2."""
    ticket = TICKET.read_text(encoding="utf-8")
    compact = (ROOT / "static" / "css" / "pages" / "ticket_compact.css").read_text(encoding="utf-8")
    newspaper = (ROOT / "static" / "css" / "themes" / "newspaper" / "ticket_compact.css").read_text(encoding="utf-8")

    assert "function penaPercents" in ticket
    assert "pena-pick-breakdown" in ticket
    assert "pena-breakdown-item" in ticket
    assert "p1/total*100" not in ticket.replace(" ", "")
    assert "Math.round(p1/total*100)" not in ticket

    assert "grid-template-columns: repeat(3, minmax(0, 1fr))" in compact
    assert ".ticket-pena-cell .pena-pick" in compact
    assert "height: auto" in compact
    assert "overflow: visible" in compact
    assert "min-width: 118px" in compact

    mobile = newspaper.split("@media (max-width: 700px)", 1)[1]
    assert "grid-column: span 2" in mobile
    assert ".ticket-pena-cell .pena-pick-breakdown" in mobile
    assert newspaper.count(".tension-chip .pena-pick small {\n    display: none;") == 0

    script = f"""
        const fs = require("fs");
        const vm = require("vm");
        const context = {{ console, Map, String, Number, Date, JSON, Set, Math }};
        vm.createContext(context);
        vm.runInContext(fs.readFileSync({json.dumps(str(UTILS))}, "utf8"), context);
        vm.runInContext(fs.readFileSync({json.dumps(str(TICKET))}, "utf8"), context);
        const html = context.renderConsensus({{ ganador: "1", p1: 70, px: 20, p2: 10, total: 10 }}, "-", "NS");
        console.log(JSON.stringify({{
            html,
            has70: html.includes("70%"),
            has20: html.includes("20%"),
            has10: html.includes("10%"),
            scaledWrong: html.includes("700%") || html.includes("7%"),
            breakdown: html.includes("pena-pick-breakdown"),
        }}));
    """
    result = subprocess.run(["node", "-e", script], cwd=ROOT, check=True, text=True, capture_output=True)
    payload = json.loads(result.stdout)
    assert payload["has70"] and payload["has20"] and payload["has10"]
    assert payload["breakdown"]
    assert not payload["scaledWrong"]


def test_ticket_and_directo_render_a_schedule_instead_of_pending_result_text():
    arena = ARENA.read_text(encoding="utf-8")
    ticket = TICKET.read_text(encoding="utf-8")

    assert "fixtureScheduleDisplay(match)" in arena
    assert "fixtureScheduleDisplay(m)" in ticket
    assert "Pendiente de resultado" not in arena
    assert "Pendiente de resultado" not in ticket


def test_live_cards_keep_a_distinct_group_for_each_competition():
    arena = ARENA.read_text(encoding="utf-8")

    assert 'data-competition="${escapeHtml(group.key)}"' in arena
    assert "const expectedCompetitions = new Set(matches.map(competitionLabel));" in arena
    assert 'renderGroupedMatchCards(matches, state.currentFilter !== "LIVE")' in arena
