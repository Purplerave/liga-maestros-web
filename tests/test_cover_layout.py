from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COVER_JS = ROOT / "static" / "js" / "pages" / "cover_page.js"
COVER_CSS = ROOT / "static" / "css" / "cover_hero.css"
PORRA_JS = ROOT / "static" / "js" / "quantum_final.js"
PORRA_ROUTE = ROOT / "liga_maestros" / "routes" / "porra.py"


def test_cover_fills_lower_panel_with_useful_journey_actions():
    """Portada compacta: journey visible, sin atajos duplicados del menú."""
    cover = COVER_JS.read_text(encoding="utf-8")
    css = COVER_CSS.read_text(encoding="utf-8")

    assert 'class="cp-journey-card"' in cover
    assert 'id="cover-porra-step-status"' in cover
    assert "cp-quicklinks-footer" not in cover
    assert ".cp-journey-card" in css
    assert "align-items: start" in css
    assert "grid-template-columns: 1fr 1fr" in css


def test_porra_bonus_copy_is_short_and_consistent():
    files = (PORRA_JS, PORRA_ROUTE, COVER_JS)
    combined = "\n".join(path.read_text(encoding="utf-8") for path in files)

    assert "Marcador exacto: +2 puntos." in combined
    assert "Tú eliges el partido para tu porra" not in combined
    assert "te llevas +2 puntos extra para la general" not in combined
