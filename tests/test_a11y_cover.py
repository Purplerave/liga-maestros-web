"""Tests de accesibilidad y performance (P2 4.x)."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COVER_JS = ROOT / "static" / "js" / "pages" / "cover_page.js"
COVER_CSS = ROOT / "static" / "css" / "cover_hero.css"
TEMPLATE = ROOT / "templates" / "liga_index.html"


def test_skip_link_present_and_targets_main():
    text = TEMPLATE.read_text(encoding="utf-8")
    assert "skip-link" in text
    assert 'href="#matches-body"' in text
    assert 'id="matches-body"' in text


def test_skip_link_css_hidden_until_focused():
    css = (ROOT / "static" / "css" / "components" / "ux_signals.css").read_text(encoding="utf-8")
    assert ".skip-link" in css
    assert "focus-visible" in css
    # No debe ser visible por defecto (translateY -160% u off-screen)
    assert "translateY(-160" in css or "translateY(-100" in css or "left: -9999" in css


def test_cover_hero_crest_has_explicit_dimensions():
    """LCP: la imagen del crest debe tener width/height/decoding/fetchpriority."""
    cover = COVER_JS.read_text(encoding="utf-8")
    assert "cp-hero-crest" in cover
    assert 'width="72"' in cover and 'height="72"' in cover
    assert 'fetchpriority="high"' in cover
    assert 'decoding="async"' in cover


def test_focus_visible_on_cover_ctas():
    css = COVER_CSS.read_text(encoding="utf-8")
    # CTAs principales con focus-visible
    assert ".cp-primary:focus-visible" in css
    assert ".cp-secondary:focus-visible" in css
    assert ".cp-featured-cta:focus-visible" in css
    assert ".cp-journey-step:focus-visible" in css
    # Carrusel trash-talk también
    assert ".cp-voz-avatar:focus-visible" in css
    assert ".cp-voz-dot:focus-visible" in css


def test_reduced_motion_disables_new_animations():
    css = COVER_CSS.read_text(encoding="utf-8")
    # Patrones clave de la nueva sección trash-talk
    assert "@keyframes cpVozFade" in css
    assert "@media (prefers-reduced-motion: reduce)" in css
    # La regla RM desactiva las animaciones que introducimos
    section = css[css.rfind("@media (prefers-reduced-motion: reduce)") :]
    assert ".cp-voz-quote" in section and "animation: none" in section
    # Y también los hovers nuevos
    assert ".cp-primary" in section or ".cp-primary:hover" in section


def test_cover_trash_talk_keyboard_accessible():
    cover = COVER_JS.read_text(encoding="utf-8")
    # dots y avatares son <button> o tienen role
    assert "data-voz-idx" in cover
    assert 'type="button"' in cover
    # aria-labels para los dots
    assert "aria-label=" in cover


def test_cover_uses_real_data_not_invented():
    """Regla de oro: nunca inventar marcadores."""
    cover = COVER_JS.read_text(encoding="utf-8")
    forbidden_scores = ["3-1", "2-0", "1-0", "0-0", "0-1", "1-1", "2-1"]
    # Buscamos en strings hardcodeados de HTML templates (no en nombres de variables)
    for forbidden in forbidden_scores:
        assert forbidden not in cover, f"marcador hardcodeado {forbidden!r} en cover_page.js"


def test_cover_version_bumped_after_change():
    """El cache-bust de la portada debe haber sido bumpeado para invalidar la caché."""
    nav = (ROOT / "static" / "js" / "navigation.js").read_text(encoding="utf-8")
    template = TEMPLATE.read_text(encoding="utf-8")
    # Tras los cambios, ambos deben apuntar al menos a 66
    assert "cover-page-66" in nav
    assert "cover-hero-66" in template
