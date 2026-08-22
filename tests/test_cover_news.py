"""La portada debe mostrar el radar RSS aunque el boletin IA venga vacio."""

import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUANTUM = ROOT / "static" / "js" / "quantum_final.js"
COVER = ROOT / "static" / "js" / "pages" / "cover_page.js"
ARENA = ROOT / "static" / "js" / "arena.js"
NAV = ROOT / "static" / "js" / "navigation.js"
STATE = ROOT / "static" / "js" / "state.js"


def test_cover_news_uses_radar_items_not_only_ai_boletin():
    quantum = QUANTUM.read_text(encoding="utf-8")
    cover = COVER.read_text(encoding="utf-8")

    assert "function normalizeNewsRows" in quantum
    assert "data.items" in quantum or "items.forEach" in quantum
    assert "novedades.length" in quantum
    assert "cx-news-item" in quantum
    assert "cp-news-row" not in quantum
    assert "cover-news-content" in quantum
    assert "normalizeNewsRows(state.newsRadar" in cover
    assert "news_briefing" not in cover


def test_news_page_is_wired_from_cover_link():
    cover = COVER.read_text(encoding="utf-8")
    arena = ARENA.read_text(encoding="utf-8")
    nav = NAV.read_text(encoding="utf-8")
    state = STATE.read_text(encoding="utf-8")

    assert 'data-page-action="NEWS"' in cover
    assert 'state.currentFilter === "NEWS_PAGE"' in arena
    assert 'target === "NEWS"' in nav
    assert "function isNewsPage" in state
    assert '"NEWS_PAGE"' in state
    assert "function renderNewsPage" in QUANTUM.read_text(encoding="utf-8")


def test_normalize_news_rows_falls_back_to_radar_items():
    if shutil.which("node") is None:
        import pytest

        pytest.skip("Node is required to exercise news helpers")

    script = """
        const fs = require("fs");
        const vm = require("vm");
        const ctx = {
            console, Map, Set, String, Number, Date, JSON, Math,
            window: {}, document: { getElementById() { return null; } },
            fetch: async () => ({ ok: true, json: async () => ({}) }),
            state: { newsRadar: null, newsRadarFetchedAt: 0 },
            qs() { return null; },
            escapeHtml(value) { return String(value ?? ""); },
        };
        vm.createContext(ctx);
        vm.runInContext(fs.readFileSync("static/js/quantum_final.js", "utf8"), ctx);
        const rows = ctx.normalizeNewsRows({
            novedades: [],
            bajas: [],
            items: [
                {
                    source: "Marca",
                    title: "Yuri no entrena con el grupo",
                    link: "https://www.marca.com/yuri",
                    published_at: "2026-08-22 12:05",
                },
                { source: "AS", title: "   ", link: "https://as.com/vacio" },
            ],
        });
        const html = ctx.renderNewsRows(rows, { limit: 4 });
        console.log(JSON.stringify({
            count: rows.length,
            source: rows[0].category,
            title: rows[0].title,
            url: rows[0].url,
            hasItemClass: html.includes("cx-news-item"),
            hasOldClass: html.includes("cp-news-row"),
            hasLink: html.includes("https://www.marca.com/yuri"),
        }));
    """
    result = subprocess.run(
        ["node", "-e", script],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    payload = json.loads(result.stdout)
    assert payload["count"] == 1
    assert payload["source"] == "MARCA"
    assert payload["title"] == "Yuri no entrena con el grupo"
    assert payload["url"] == "https://www.marca.com/yuri"
    assert payload["hasItemClass"] is True
    assert payload["hasOldClass"] is False
    assert payload["hasLink"] is True
