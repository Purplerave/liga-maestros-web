"""Contract tests for the 2026-07 frontend UX upgrade.

Locks in three things that are easy to regress:

1. No inline ``<script>`` blocks in templates. The site ships
   ``script-src 'self'`` without ``'unsafe-inline'``, so any inline script is
   silently dropped by the browser (this is how the service worker
   registration was broken before this change).
2. The command palette and the UX signal layer are wired into the shell.
3. The lazily-shipped assets actually exist and are precached by the SW.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "templates"
TEMPLATE = TEMPLATES / "liga_index.html"
SW = ROOT / "static" / "sw.js"
COMMAND_PALETTE_CSS = ROOT / "static" / "css" / "components" / "command_palette.css"
MATCH_CARDS_CSS = ROOT / "static" / "css" / "components" / "match_cards.css"
QUANTUM_JS = ROOT / "static" / "js" / "quantum_final.js"

INLINE_SCRIPT = re.compile(r"<script(?![^>]*\ssrc=)(?![^>]*type\s*=\s*\"application/ld\+json\")[^>]*>", re.IGNORECASE)

NEW_ASSETS = (
    "static/css/components/command_palette.css",
    "static/css/components/ux_signals.css",
    "static/js/command_palette.js",
    "static/js/ux_signals.js",
    "static/js/sw_register.js",
)


def test_no_inline_scripts_in_templates():
    """CSP is `script-src 'self'`: inline scripts never execute."""
    offenders = []
    for path in TEMPLATES.rglob("*.html"):
        text = path.read_text(encoding="utf-8")
        if INLINE_SCRIPT.search(text):
            offenders.append(str(path.relative_to(ROOT)))
    assert offenders == [], f"inline <script> blocks are dead code under the CSP: {offenders}"


def test_new_frontend_assets_exist():
    for asset in NEW_ASSETS:
        assert (ROOT / asset).is_file(), f"missing asset {asset}"


def test_shell_wires_command_palette_and_ux_signals():
    template = TEMPLATE.read_text(encoding="utf-8")
    for asset in NEW_ASSETS:
        assert f"filename='{asset.removeprefix('static/')}'" in template, f"{asset} not referenced in shell"
    assert 'id="cmdk-trigger"' in template, "the palette needs a visible, discoverable trigger"


def test_service_worker_precaches_the_new_shell():
    sw = SW.read_text(encoding="utf-8")
    for asset in ("command_palette.css", "ux_signals.css", "command_palette.js", "ux_signals.js"):
        assert asset in sw, f"{asset} is not precached by the service worker"


def test_service_worker_cache_names_are_bumped_together():
    sw = SW.read_text(encoding="utf-8")
    versions = set(re.findall(r"const \w+_?CACHE = 'liga-maestros-[a-z-]*(v\d+)';", sw))
    assert len(versions) == 1, f"service worker cache versions drifted apart: {versions}"


def test_service_worker_never_caches_api_or_post_requests():
    """Dynamic/private API data and writes must bypass Cache Storage."""
    sw = SW.read_text(encoding="utf-8")
    api_block = sw.split("if (path.startsWith('/api/'))", 1)[1].split("// Archivos estaticos", 1)[0]
    assert "request.method !== 'GET'" in api_block
    assert "fetch(request)" in api_block
    assert "networkWithTimeout(request" in api_block
    assert "API_CACHE" not in sw
    assert "caches.open" not in sw.split("async function networkWithTimeout", 1)[1]


def test_palette_is_progressive_enhancement():
    """Init failures must never take the app down."""
    events = (ROOT / "static" / "js" / "events.js").read_text(encoding="utf-8")
    assert "window.CommandPalette?.init()" in events
    assert "window.UXSignals?.init()" in events
    # both guarded by try//catch so a broken module cannot block refreshData()
    init_block = events.split("DOMContentLoaded")[-1]
    assert init_block.count("try {") >= 2


def test_closed_palette_cannot_block_the_page():
    """The full-screen backdrop must disappear while the palette is closed."""
    css = COMMAND_PALETTE_CSS.read_text(encoding="utf-8")
    assert re.search(
        r"\.cmdk-backdrop\[hidden\]\s*\{[^}]*display:\s*none",
        css,
        re.DOTALL,
    )


def test_live_matches_keep_the_league_card_grid():
    css = MATCH_CARDS_CSS.read_text(encoding="utf-8")
    assert re.search(
        r"\.live-grouped-grid\s*\{[^}]*display:\s*grid[^}]*grid-template-columns:",
        css,
        re.DOTALL,
    )


def test_live_refresh_does_not_spawn_goal_popups():
    js = QUANTUM_JS.read_text(encoding="utf-8")
    assert "showInAppNotification" not in js
    assert "checkLiveNotifications" not in js
