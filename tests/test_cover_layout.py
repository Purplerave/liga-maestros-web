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


def test_porra_bonus_copy_is_short_and_consistent():
    files = (PORRA_JS, PORRA_ROUTE, COVER_JS)
    combined = "\n".join(path.read_text(encoding="utf-8") for path in files)

    assert "Marcador exacto: +2 puntos." in combined
    assert "Tú eliges el partido para tu porra" not in combined
    assert "te llevas +2 puntos extra para la general" not in combined
