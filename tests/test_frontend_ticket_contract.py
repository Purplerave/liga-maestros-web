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
