"""Caminito critico de la portada (Frente 2 — Rendimiento/Portada, 2026-09-14).

La portada es la puerta de entrada: cada peticion bloqueante en el <head> es
un viaje de ida y vuelta mas antes del primer pintado. Estos tests fijan el
presupuesto que se acordo al cerrar el Frente 2 para que no vuelva a crecer
por descuido:

- ``tokens.css`` se descarga una sola vez (la precarga y la hoja comparten
  version; con versiones distintas el navegador la pedia dos veces).
- Las fuentes de Google no bloquean el render (terceros fuera del camino
  critico) y conservan el ``<noscript>`` de respaldo.
- Los modulos que la portada no necesita (analitica, confeti, imagen del
  boleto, sonidos, paleta, señales UX, post-jornada, onboarding, service
  worker) no van como etiquetas en el shell: los carga ``late_assets.js``.
- Lo que SI es critico sigue en el shell.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "templates" / "liga_index.html"
LATE_ASSETS = ROOT / "static" / "js" / "late_assets.js"
EVENTS = ROOT / "static" / "js" / "events.js"

# Presupuesto acordado: 25 hojas de estilo bloqueantes como maximo. Si hace
# falta una mas, que sea a cambio de sacar otra del camino critico.
MAX_BLOCKING_STYLESHEETS = 25

# El nucleo: sin estos scripts la portada no arranca.
CORE_SCRIPTS = (
    "js/utils.js",
    "js/state.js",
    "js/logos.js",
    "js/navigation.js",
    "js/live.js",
    "js/arena.js",
    "js/events.js",
    "js/quantum_final.js",
)

# Fuera del camino critico: los sirve late_assets.js cuando el hilo principal
# esta libre o en cuanto el usuario interactua.
LATE_SCRIPTS = (
    "js/analytics.js",
    "js/confetti.js",
    "js/ticket_image.js",
    "js/sound_manager.js",
    "js/command_palette.js",
    "js/ux_signals.js",
    "js/post_jornada.js",
    "js/onboarding.js",
    "js/sw_register.js",
)

LATE_STYLES = (
    "css/onboarding.css",
    "css/components/post_jornada.css",
)

FONT_HREF = "https://fonts.googleapis.com/css2"


def _template() -> str:
    return TEMPLATE.read_text(encoding="utf-8")


def _versioned_assets(text: str):
    """Devuelve {ruta_del_asset: sufijo_de_version} de tags de static_files."""
    return dict(re.findall(r"filename='([^']+)'[^\n]*?v=assets_v ~ '([^']*)'", text))


def test_tokens_preload_and_stylesheet_share_version():
    """Con dos versiones distintas el navegador descarga tokens.css dos veces."""
    template = _template()
    preloads = re.findall(r'rel="preload" as="style" href="([^"]+)"', template)
    tokens_preload = [href for href in preloads if "css/base/tokens.css" in href]
    assert tokens_preload, "tokens.css debe seguir precargandose"

    preload_version = re.search(r"v=assets_v ~ '([^']+)'", tokens_preload[0])
    sheet_match = re.search(r"filename='css/base/tokens\.css', v=assets_v ~ '([^']+)'", template)
    assert preload_version and sheet_match
    assert preload_version.group(1) == sheet_match.group(1), (
        f"precarga {preload_version.group(1)} vs hoja {sheet_match.group(1)}: descarga duplicada"
    )


def test_no_duplicate_preconnects():
    template = _template()
    hrefs = re.findall(r'<link rel="preconnect" href="([^"]+)"', template)
    assert len(hrefs) == len(set(hrefs)), f"preconnect duplicado: {hrefs}"


def test_google_fonts_do_not_block_rendering():
    template = _template()
    head = template.split("</head>", 1)[0]

    # Sin JS no hay cargador: el <noscript> SI lleva la hoja de terceros y por
    # eso se excluye del chequeo de bloqueo.
    head_without_noscript = re.sub(r"<noscript>.*?</noscript>", "", head, flags=re.DOTALL)
    blocking = [
        tag for tag in re.findall(r'<link[^>]*rel="stylesheet"[^>]*>', head_without_noscript) if FONT_HREF in tag
    ]
    assert blocking == [], f"las fuentes de Google siguen bloqueando el render: {blocking}"

    assert re.search(r'rel="preload" as="style"[^>]*id="lm-webfonts"', head), (
        "las fuentes deben viajar como preload y promocionarse desde late_assets.js"
    )
    # Sin JavaScript el navegador no ejecuta el cargador: el <noscript> mantiene
    # las fuentes en ese caso (y sin el, la tipografia caeria al fallback).
    noscript = "".join(re.findall(r"<noscript>(.*?)</noscript>", head, re.DOTALL))
    assert FONT_HREF in noscript and 'rel="stylesheet"' in noscript


def test_blocking_stylesheet_budget():
    head = _template().split("</head>", 1)[0]
    sheets = re.findall(r'<link rel="stylesheet" href=', head)
    assert len(sheets) <= MAX_BLOCKING_STYLESHEETS, (
        f"{len(sheets)} hojas bloqueantes, presupuesto {MAX_BLOCKING_STYLESHEETS}: "
        "mueve la nueva fuera del camino critico"
    )


def test_core_scripts_stay_in_the_shell():
    template = _template()
    for asset in CORE_SCRIPTS:
        assert f"filename='{asset}'" in template, f"{asset} es critico: debe seguir en el shell"


def test_late_scripts_are_not_in_the_shell():
    template = _template()
    late = LATE_ASSETS.read_text(encoding="utf-8")
    for asset in LATE_SCRIPTS:
        assert f"filename='{asset}'" not in template, f"{asset} no pinta la portada: lo carga late_assets.js"
        assert f'"/static/{asset}"' in late, f"{asset} no esta declarado en late_assets.js"


def test_late_styles_are_not_in_the_shell():
    template = _template()
    late = LATE_ASSETS.read_text(encoding="utf-8")
    for asset in LATE_STYLES:
        assert f"filename='{asset}'" not in template, f"{asset} no pinta la portada: lo carga late_assets.js"
        assert f'"/static/{asset}"' in late, f"{asset} no esta declarado en late_assets.js"


def test_late_loader_is_wired_and_knows_the_service_worker_url():
    template = _template()
    assert "filename='js/late_assets.js'" in template
    # sw_register.js lee la URL del SW de `dataset.swUrl`: sin este atributo el
    # service worker nunca se registra (la CSP no permite inline scripts).
    assert re.search(
        r"filename='js/late_assets\.js'[^>]*data-sw-url=|data-sw-url=\"[^\"]*sw\.js[^\"]*\"",
        template,
        re.DOTALL,
    )


def test_late_loader_preserves_order_and_announces_readiness():
    late = LATE_ASSETS.read_text(encoding="utf-8")
    # Descarga en paralelo, ejecucion en orden: imprescindible para los modulos
    # que dependen de globals definidos por los anteriores.
    assert "script.async = false" in late
    assert 'new CustomEvent("liga:late-ready")' in late
    # Se dispara cuando el hilo esta libre, si el usuario interactua o al load:
    # nunca compite con el primer pintado.
    assert "requestIdleCallback" in late


def test_shell_initialises_late_modules_when_they_arrive():
    events = EVENTS.read_text(encoding="utf-8")
    assert 'addEventListener("liga:late-ready"' in events
    # Init con guarda: si el modulo no ha llegado o falla, la portada sigue.
    assert "window.CommandPalette?.init()" in events
    assert "window.UXSignals?.init()" in events
