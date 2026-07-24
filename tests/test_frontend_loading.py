from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "templates" / "liga_index.html"
NAVIGATION = ROOT / "static" / "js" / "navigation.js"
APP_SHELL = ROOT / "static" / "css" / "layout" / "app_shell.css"
MASTHEAD = ROOT / "static" / "css" / "layout" / "stable_masthead.css"
TYPEWRITER = ROOT / "static" / "css" / "typewriter_system.css"

LAZY_VIEW_SCRIPTS = {
    "static/js/pages/cover_page.js",
    "static/js/pages/ticket_page.js",
    "static/js/pages/games_hub.js",
    "static/js/standings.js",
    "static/js/contest.js",
    "static/js/quiz.js",
    "static/js/components/pleno_modal.js",
}


def test_page_scripts_are_loaded_only_for_the_active_view():
    template = TEMPLATE.read_text(encoding="utf-8")
    navigation = NAVIGATION.read_text(encoding="utf-8")

    for asset in LAZY_VIEW_SCRIPTS:
        assert f"filename='{asset}'" not in template
        assert f'"/{asset}"' in navigation


def test_lazy_view_script_files_exist():
    for asset in LAZY_VIEW_SCRIPTS:
        assert (ROOT / asset).is_file()


def test_shared_stylesheet_does_not_mix_page_specific_layouts():
    template = TEMPLATE.read_text(encoding="utf-8")
    surface = ROOT / "static" / "css" / "components" / "surface_shape.css"

    assert "css/components/surface_shape.css" in template
    assert "css/smooth_ui.css" not in template
    assert not (ROOT / "static" / "css" / "smooth_ui.css").exists()
    assert not (ROOT / "static" / "css" / "themes" / "cartoon.css").exists()
    assert ".games-hub-page" not in surface.read_text(encoding="utf-8")
    assert ".league-tabs" not in surface.read_text(encoding="utf-8")


def test_masthead_is_the_only_shared_page_geometry_contract():
    template = TEMPLATE.read_text(encoding="utf-8")
    masthead = MASTHEAD.read_text(encoding="utf-8")
    typewriter = TYPEWRITER.read_text(encoding="utf-8")
    app_shell = APP_SHELL.read_text(encoding="utf-8")

    assert "css/layout/stable_masthead.css" in template
    assert "css/themes/newspaper/responsive.css" not in template
    assert not (ROOT / "static" / "css" / "themes" / "newspaper" / "responsive.css").exists()
    assert ".app-shell" not in typewriter
    assert ".main-arena" not in typewriter
    assert "grid-template-columns: 188px" not in app_shell
    assert "grid-template-columns: 176px" not in app_shell
    assert "body.quiniela-focus .app-shell" not in app_shell
    assert "grid-template-rows: 66px 38px minmax(0, 1fr)" in masthead
    assert "grid-template-rows: 56px 52px 38px minmax(0, 1fr)" in masthead


def test_topbar_does_not_duplicate_the_live_page():
    template = TEMPLATE.read_text(encoding="utf-8")
    arena = (ROOT / "static" / "js" / "arena.js").read_text(encoding="utf-8")
    live = (ROOT / "static" / "js" / "live.js").read_text(encoding="utf-8")

    assert "topbar-live-slot" not in template
    assert "updateTopbarLiveTicker" not in arena
    assert "renderLiveTicker" not in live


def test_page_styles_do_not_contain_removed_cross_page_components():
    standings = (ROOT / "static" / "css" / "pages" / "standings.css").read_text(encoding="utf-8")
    match_cards = (ROOT / "static" / "css" / "components" / "match_cards.css").read_text(encoding="utf-8")

    assert ".profile-grid" not in standings
    assert ".user-side-panel" not in standings
    assert ".rank-line" not in standings
    assert ".arena-table" not in match_cards
    assert ".ia-signo" not in match_cards
    assert ".match-detail-row" not in match_cards

    app_shell = APP_SHELL.read_text(encoding="utf-8")
    assert ".side-user-stats" not in app_shell
    assert ".status-tile" not in app_shell
    assert ".secondary-btn" not in app_shell

    quiz = (ROOT / "static" / "css" / "pages" / "quiz_page.css").read_text(encoding="utf-8")
    assert ".pulse-page" not in quiz
    assert ".world-cup-quiz-card" not in quiz
    assert not (ROOT / "static" / "css" / "pages" / "porra.css").exists()
