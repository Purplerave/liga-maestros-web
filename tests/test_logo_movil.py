"""El logo de cabecera no debe costar 231KB en movil.

`header-brand-panel` esta oculto en <=899px (`mobile_v2.css`, sin condiciones),
pero un `<img>` a pelo se descarga igual: cada visita movil pagaba el PNG de la
marca para un elemento que no se ve. Estos tests fijan las tres garantias:

- En <=899px se sirve el escudo SVG (1,5KB, y ya en cache porque lo usa el
  crest de la portada).
- En >=900px el PNG se mantiene intacto, con su `fetchpriority="high"` y sus
  width/height: es el LCP de las paginas interiores y esa decision es
  deliberada.
- El `<picture>` no rompe el layout del panel (`display: contents`), porque si no
  pasaria a ser el hijo flex y el `height: 100%` de la imagen dejaria de
  resolver contra el alto del panel.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "templates" / "liga_index.html"
MASTHEAD = ROOT / "static" / "css" / "layout" / "stable_masthead.css"
MOBILE_V2 = ROOT / "static" / "css" / "mobile_v2.css"

PNG_PESADO = "img/ligademaestroslogo_trans.png"
SVG_LIGERO = "img/liga_maestros_mark.svg"

# El corte tiene que ser el mismo que usa mobile_v2.css para ocultar el panel.
CORTE_MOVIL = re.search(r"@media \(max-width: (\d+)px\)", MOBILE_V2.read_text(encoding="utf-8"))


def _bloque_movil(fuente: str) -> str:
    """Porcion de la hoja dentro del primer `@media (max-width: Npx)`."""
    corte = re.search(r"@media \(max-width: \d+px\)", fuente)
    assert corte, "la hoja debe declarar su bloque movil"
    siguiente = re.search(r"@media ", fuente[corte.end() :])
    fin = corte.end() + siguiente.start() if siguiente else len(fuente)
    return fuente[corte.start() : fin]


def test_el_panel_de_marca_esta_oculto_en_movil():
    """Premisa del ahorro: si el panel se ve, el SVG dejaria de ser correcto."""
    bloque = _bloque_movil(MOBILE_V2.read_text(encoding="utf-8"))
    panel = re.search(r"\.header-brand-panel\s*\{[^}]*display:\s*none", bloque)
    assert panel, "en <=899px el panel de marca tiene que estar oculto"


def test_en_movil_se_sirve_el_escudo_svg():
    plantilla = TEMPLATE.read_text(encoding="utf-8")
    source = re.search(r"<source media=\"\(max-width: (\d+)px\)\"[^>]*srcset=\"([^\"]+)\"", plantilla)
    assert source, "el logo debe tener un <source> para movil"
    assert SVG_LIGERO in source.group(2), "en movil se sirve el SVG, no el PNG"
    assert int(source.group(1)) == int(CORTE_MOVIL.group(1)), (
        f"el corte del <source> debe coincidir con el que oculta el panel en mobile_v2.css ({CORTE_MOVIL.group(1)}px)"
    )


def test_en_escritorio_el_png_sigue_intacto():
    """El PNG es el LCP de las paginas interiores: no se toca."""
    plantilla = TEMPLATE.read_text(encoding="utf-8")
    img = re.search(r"<img class=\"sidebar-brand-image\"[^>]*>", plantilla)
    assert img, "el logo debe seguir siendo un <img class='sidebar-brand-image'>"
    etiqueta = img.group(0)
    assert PNG_PESADO in etiqueta
    assert 'fetchpriority="high"' in etiqueta, "el LCP se carga con prioridad alta"
    assert re.search(r'width="\d+"', etiqueta) and re.search(r'height="\d+"', etiqueta), (
        "width/height explicitos reservan el hueco y evitan CLS"
    )
    assert 'loading="lazy"' not in etiqueta, "el LCP no puede ir diferido"


def test_el_picture_no_rompe_el_layout_del_panel():
    """Sin `display: contents` el <picture> absorbe el alto del panel."""
    masthead = MASTHEAD.read_text(encoding="utf-8")
    regla = re.search(r"\.header-brand-panel picture\s*\{[^}]*display:\s*contents", masthead)
    assert regla, "el <picture> debe ser transparente al layout del panel"
