"""La versión móvil no puede romperse en silencio.

Cada test de aquí cubre un defecto que estaba presente en producción y que es
difícil de ver sin un iPhone en la mano:

- `100vh` en lugar de `100dvh` dejaba un scroll fantasma con la barra del
  navegador visible, en practicamente todas las paginas.
- No existia `safe-area-inset-left/right`, asi que en landscape el contenido se
  metia debajo del notch.
- Los overlays (pleno, onboarding, resumen de jornada) no tenian `max-height` ni
  scroll: en pantallas bajas el boton de confirmar quedaba inalcanzable.
- No habia scroll-lock en ningun sitio: arrastrar sobre un modal desplazaba la
  quiniela de fondo.
- La píldora de "sin conexion" tapaba el boton central de la bottom nav.

Los tests trabajan sobre el fuente porque no hay navegador en la CI. Es lo unico
que se puede comprobar de forma fiable, y evita que un `catch {}` o un
refactor silencioso deshaga el arreglo.
"""

import re
import subprocess
from pathlib import Path

import pytest

CSS = Path("static/css")
JS = Path("static/js")


def _css(*partes):
    return (CSS.joinpath(*partes)).read_text(encoding="utf-8")


def _sin_comentarios(fuente):
    """Quita `/* ... */`.

    Sin esto, un comentario que menciona varios selectores se parsea como si
    fueran selectores de la regla siguiente y los tests dan un falso positivo
    sobre reglas que en realidad no existen.
    """
    return re.sub(r"/\*.*?\*/", "", fuente, flags=re.S)


# ── Tokens de safe-area ──────────────────────────────────────────────────────


def test_los_tokens_de_safe_area_existen():
    """`viewport-fit=cover` obliga a Honorarlos: sin esto, el recorte fisico tapa
    el contenido. Los tokens centralizan el uso en un solo sitio."""
    tokens = _css("base", "tokens.css")
    for lado in ("top", "right", "bottom", "left"):
        assert f"--safe-{lado}: env(safe-area-inset-{lado}" in tokens, (
            f"falta el token --safe-{lado}. Con viewport-fit=cover, un inset sin "
            "honrar significa contenido bajo el notch o el indicador de inicio."
        )


def test_viewport_declara_viewport_fit_cover():
    """Es la premisa de todo lo anterior: sin `viewport-fit=cover` los insets
    valen 0 y estas reglas no hacen nada."""
    plantilla = Path("templates/liga_index.html").read_text(encoding="utf-8")
    match = re.search(r'<meta name="viewport" content="([^"]+)"', plantilla)
    assert match, "falta el meta viewport"
    assert "viewport-fit=cover" in match.group(1), "los safe-area-inset* solo tienen efecto con viewport-fit=cover"
    assert "width=device-width" in match.group(1)


def test_el_shell_se_aparta_de_los_insets_laterales():
    """Landscape en iPhone: el notch va a un lado, no arriba. Con `padding-inline`
    a cero, los botones de las esquinas quedan bajo el recorte."""
    shell = _css("layout", "app_shell.css")
    assert "--safe-inline" in shell, (
        "el app-shell debe respetar los insets laterales: en landscape el notch "
        "ocupa un lateral y las esquinas son justo donde caen los botones."
    )


# ── Altura de viewport: dvh y no vh ──────────────────────────────────────────

# Ficheros donde una altura de viewport mal medida rompe la pagina de verdad.
# Rutas relativas a static/css, como cadenas: `Path.join` con ".." resolveria
# fuera del arbol y es mas fragil que escribir la ruta entera.
ALTURA_CRITICA = [
    "layout/app_shell.css",
    "pages/legal.css",
    "pages/quiz_page.css",
    "snake_gol_arcade.css",
]


# `vh` que NO es `dvh`: en "100dvh" la letra anterior a "vh" es "d", asi que el
# lookbehind basta para separar las dos familias. Un `\b` no serviria: en "100dvh"
# no hay limite de palabra entre "0" y "d".
_ALTURA_VH = re.compile(r"(?:min-|max-)?height\s*:\s*[^;{}]*?(?<!d)vh\b")
# La variante dvh se busca a partir del FINAL de la coincidencia, admitiendo el
# resto del valor (`calc(100vh - 202px)`) antes del `;` de cierre.
_VARIANTE_DVH = re.compile(r"[^;{}]*?;?\s*(?:min-|max-)?height\s*:\s*[^;{}]*dvh\b")


@pytest.mark.parametrize("ruta", ALTURA_CRITICA)
def test_las_alturas_de_viewport_usan_dvh(ruta):
    """`100vh` mide el viewport con la barra del navegador oculta, asi que mide de
    mas. Con `overflow: hidden` (app-shell, snake) eso recorta contenido.

    Se comprueba DECLARACION A DECLARACION, y no con un "dvh" suelto por el
    fichero: con cinco alturas y una sola corregida, un chequeo global daria el
    visto bueno por el camino equivocado.
    """
    fuente = (CSS / ruta).read_text(encoding="utf-8")
    encontradas = list(_ALTURA_VH.finditer(fuente))
    if not encontradas:
        pytest.skip("este fichero no fija altura de viewport en vh")
    for coincidencia in encontradas:
        # Tras la declaracion debe venir la misma propiedad en dvh: el navegador
        # que no conoce `dvh` descarta la segunda y se queda con `vh`.
        assert _VARIANTE_DVH.match(fuente[coincidencia.end() :]), (
            f"en {ruta}, `{coincidencia.group(0).strip()}` no tiene su variante dvh "
            "justo despues: sin ella, en movil sobra scroll o se recorta contenido."
        )


def test_el_fallback_de_dvh_va_declarado_antes():
    """El patron correcto es `100vh` y despues `100dvh`, para que los navegadores
    que no conocen `dvh` usen `vh`. Si `dvh` va primero, en un navegador sin
    soporte la segunda declaracion se descarta y no hay fallback."""
    shell = _css("layout", "app_shell.css")
    assert re.search(r"height:\s*100vh;\s*height:\s*100dvh;", shell), (
        "el fallback va antes: `height: 100vh;` seguido de `height: 100dvh;`"
    )


def test_mobile_v2_no_reintroduce_vh_sin_dvh():
    """Este fichero ya aplicaba el patron correcto; no debe perderlo."""
    fuente = _css("mobile_v2.css")
    for linea in fuente.splitlines():
        if re.search(r"(?:min-)?height:\s*100vh", linea):
            siguiente = fuente.splitlines()[fuente.splitlines().index(linea) + 1]
            assert "dvh" in siguiente, f"`{linea.strip()}` necesita su variante dvh justo debajo"


# ── Overlays: no pueden recortar contenido ───────────────────────────────────

OVERLAYS = [
    "components/pleno_modal.css",
    "onboarding.css",
    "components/post_jornada.css",
]


@pytest.mark.parametrize("ruta", OVERLAYS)
def test_los_paneles_de_overlay_no_recortan_contenido(ruta):
    """El defecto original: `overflow: hidden` sin `max-height` recorta la cabecera
    y el boton de accion, y sin scroll no hay forma de llegar a ellos. En landscape
    de iPhone SE (375px de alto) el boton Confirmar quedaba inalcanzable."""
    fuente = (CSS / ruta).read_text(encoding="utf-8")
    assert re.search(r"max-height:\s*[^;]*dvh", fuente), (
        "el panel necesita `max-height` en `dvh`: sin el, en pantallas bajas se "
        "sale por arriba y por abajo sin ninguna forma de hacer scroll."
    )
    assert re.search(r"overflow-y:\s*auto", fuente), "el contenido que no cabe necesita scroll propio."


def test_el_modal_de_pleno_mantiene_las_acciones_visibles():
    """Cabecera y footer no deben encogerse como flex items: si se comprimen,
    Confirmar queda ilegible justo cuando el contenido no cabe."""
    fuente = _css("components", "pleno_modal.css")
    assert "flex-direction: column" in fuente, "el panel debe ser una columna flex"
    assert fuente.count("flex: 0 0 auto") >= 2, "header y footer deben llevar `flex: 0 0 auto` para no encogerse"
    cuerpo = fuente[fuente.index(".pleno-modal-body") :]
    assert "min-height: 0" in cuerpo, (
        "el cuerpo scrolleable necesita `min-height: 0`; sin el, un flex item no "
        "baja de su altura de contenido y el panel sigue desbordando."
    )


@pytest.mark.parametrize("ruta", OVERLAYS)
def test_los_overlays_respetan_los_insets(ruta):
    """Con `viewport-fit=cover`, un overlay a pantalla completa sin los insets
    pone sus botones bajo el notch o el indicador de inicio."""
    assert "--safe" in (CSS / ruta).read_text(encoding="utf-8"), f"{ruta} no respeta los safe-area"


def test_los_botones_del_modal_alcanzan_el_minimo_tactil():
    """40px queda por debajo del minimo comodo (44px) y es facil fallar el
    Confirmar con el dedo."""
    fuente = _css("components", "pleno_modal.css")
    assert "@media (pointer: coarse)" in fuente, "los botones del modal necesitan una regla para puntero grueso"
    grueso = fuente[fuente.index("@media (pointer: coarse)") :]
    assert re.search(r"min-height:\s*(4[4-9]|[5-9]\d)px", grueso), "el minimo tactil es 44px"


# ── Scroll lock ──────────────────────────────────────────────────────────────


def test_existe_el_servicio_de_scroll_lock():
    servicio = JS / "core" / "scroll_lock.js"
    assert servicio.exists(), "falta el servicio de scroll lock"
    assert "window.lmBloquearScroll" in servicio.read_text(encoding="utf-8"), (
        "los scripts del proyecto son globales planos, sin modulos ES: el servicio "
        "tiene que exponerse en window para que el resto lo alcance."
    )


def test_el_scroll_lock_usa_un_contador():
    """Un toggle simple se rompe con dos overlays a la vez: si uno cierra y
    desbloquea, la pagina queda bloqueada para siempre con el otro abierto."""
    fuente = (JS / "core" / "scroll_lock.js").read_text(encoding="utf-8")
    assert "_lmOverlaysAbiertos" in fuente
    assert re.search(r"if \(_lmOverlaysAbiertos > 0\) return", fuente), (
        "solo el ultimo overlay en cerrar debe restaurar el scroll"
    )


def test_el_scroll_lock_guarda_la_posicion():
    """Al cerrar, el usuario vuelve al mismo punto: si no, aparece arriba del
    todo y pierde el sitio en medio de la quiniela."""
    fuente = (JS / "core" / "scroll_lock.js").read_text(encoding="utf-8")
    assert "lmScrollY" in fuente, "hay que guardar el scrollY antes de fijar el body"
    assert "window.scrollTo" in fuente, "hay que restaurarlo al liberar"


def test_el_scroll_lock_ignora_dobles_llamadas():
    fuente = (JS / "core" / "scroll_lock.js").read_text(encoding="utf-8")
    assert "if (liberado) return" in fuente, (
        "una doble llamada al liberador decrementaria dos veces y desbloquearia la "
        "pagina con otro overlay todavia abierto"
    )


@pytest.mark.parametrize(
    "fichero",
    [
        "components/pleno_modal.js",
        "command_palette.js",
        "onboarding.js",
        "post_jornada.js",
    ],
)
def test_los_overlays_llaman_al_scroll_lock(fichero):
    """Que exista el servicio no basta: cada overlay tiene que tomarlo y soltarlo.
    Un overlay que solo lo toma deja la pagina bloqueada para siempre."""
    fuente = (JS / fichero).read_text(encoding="utf-8")
    assert "lmBloquearScroll" in fuente, f"{fichero} no bloquea el scroll"
    assert fuente.count("liberarScroll") >= 2 or fuente.count("_liberarScroll") >= 2, (
        f"{fichero} debe soltar el scroll en su punto de salida, no solo tomarlo"
    )


# ── La píldora de estado no puede tapar la navegación ────────────────────────


def test_la_pildora_de_estado_no_tapa_la_bottom_nav():
    """Estaba a `bottom: 20px` con `z-index: 9000` frente a `z-index: 50` de la
    nav: flotaba ENCIMA y tapaba el boton central, y ademas quedaba bajo el
    indicador de inicio. Justo el aviso que mas falta hace cuando no hay red."""
    fuente = _css("components", "ux_signals.css")
    movil = fuente[fuente.index("@media (max-width: 899px)") :] if "@media (max-width: 899px)" in fuente else ""
    assert movil, "la píldora necesita una regla movil"
    assert "58px" in movil, "debe levantarse por encima de la bottom nav (min-height: 58px)"
    assert "--safe-bottom" in movil, "y por encima del indicador de inicio"


def test_el_skip_link_no_aparece_bajo_el_notch():
    """Al enfocarse con el teclado, `top: var(--space-2)` lo ponia literalmente
    bajo el recorte superior de un iPhone."""
    fuente = _css("components", "ux_signals.css")
    skip = fuente[fuente.index(".skip-link") : fuente.index(".skip-link:focus-visible")]
    assert "--safe-top" in skip
    assert "--safe-left" in skip


# ── Objetivos táctiles ───────────────────────────────────────────────────────


def test_los_botones_de_signo_alcanzan_el_minimo_tactil():
    """Es la interaccion principal de la app: 15 botones por jornada."""
    fuente = _css("mobile_v2.css")
    bloque = fuente[fuente.index(".ticket-user-sign-group button.ia-signo") :]
    alto = re.search(r"(?:min-)?height:\s*(\d+)px", bloque)
    assert alto, "no se encuentra la altura de los botones de signo"
    assert int(alto.group(1)) >= 44, (
        f"los botones de signo miden {alto.group(1)}px, por debajo del minimo tactil de 44px"
    )


def test_las_celdas_de_la_portada_alcanzan_el_minimo_tactil():
    """En pantallas de 480px o menos las celdas de signo medían 32px y 30px de
    alto: por debajo del mínimo cómodo de 44px. El ancho NO se toca, porque en
    360px caben siete columnas por fila y ampliarlas desborda la tabla; la fila
    entera ya es clicable por delegación, lo que faltaba era alto."""
    fuente = _css("cover_hero.css")
    inicio = fuente.index("@media (max-width: 480px)")
    bloque = fuente[inicio : fuente.index("@media", inicio + 10)]

    for selector in (".cx-r-pick-val {", ".cx-r-ia .cx-ia-sign {"):
        decl = bloque[bloque.index(selector) :]
        decl = decl[: decl.index("}")]
        alto = re.search(r"height:\s*(\d+)px", decl)
        assert alto, f"{selector} no fija altura en el bloque <=480px"
        assert int(alto.group(1)) >= 44, f"{selector} mide {alto.group(1)}px, por debajo del mínimo de 44px"


def test_los_signos_de_la_quiniela_alcanzan_el_minimo_tactil():
    """Los botones 1X2 del boleto (.ia-signo, .saved-ticket-sign, .pena-pick)
    median 30px de alto. Son el elemento que mas se toca al rellenar la
    quiniela, y a 30px se fallaba el toque y se marcaba el partido
    equivocado."""
    fuente = _css("mobile_v2.css")
    regla = fuente[fuente.index(".tension-chip .ia-signo") :]
    regla = regla[: regla.index("}")]
    alto = re.search(r"min-height:\s*(\d+)px", regla)
    assert alto, "los signos de la quiniela no fijan min-height"
    assert int(alto.group(1)) >= 44, f"los signos miden {alto.group(1)}px, por debajo del minimo de 44px"


def test_la_reserva_inferior_cubre_la_nav_y_el_safe_area():
    """La nav fija mide min-height 58px MAS el inset inferior del dispositivo
    (~34px en iPhone con home indicator): unos 92px. Se reservaban 70px fijos,
    asi que los ultimos ~22px de contenido quedaban tapados por la barra."""
    fuente = _css("mobile_v2.css")
    nav = fuente[fuente.index(".newspaper-page-nav {") :]
    nav = nav[: nav.index("}")]
    alto_nav = int(re.search(r"min-height:\s*(\d+)px", nav).group(1))

    # `padding-bottom` y `min-height` pueden venir en cualquier orden dentro de
    # la regla, asi que se toma el bloque entero y no una ventana fija.
    bloque = fuente[fuente.index("quiniela-focus .main-arena {") :]
    bloque = bloque[: bloque.index("}")]
    reserva = re.search(r"padding-bottom:\s*([^;]+);", bloque)
    assert reserva, ".main-arena no reserva hueco para la nav fija"
    digitos = re.findall(r"(\d+)px", reserva.group(1))
    assert digitos, "la reserva inferior debe medirse en px"
    fijo = int(digitos[0])
    assert fijo >= alto_nav, f"la reserva ({fijo}px) es menor que la nav ({alto_nav}px): el contenido queda tapado"
    assert "safe-area-inset-bottom" in reserva.group(1), "la reserva debe sumar el inset inferior del dispositivo"


def test_la_tabla_no_esta_mas_ancha_que_la_pantalla():
    """A 480px de breakpoint se imponia `min-width: 500px` a .arena-table: en un
    iPhone SE (375px) o un Android de 360px la tabla era mas ancha que la
    pantalla y habia que arrastrar en horizontal para leer el boleto."""
    fuente = _css("mobile_responsive.css")
    bloque = fuente[fuente.index("@media (max-width: 480px)") :]
    bloque = bloque[: bloque.index("\n}")]
    regla = bloque[bloque.index(".arena-table {") :]
    regla = regla[: regla.index("}")]
    assert "min-width: 0" in regla or "min-width: 0px" in regla, (
        ".arena-table no puede llevar min-width > 0 en el breakpoint de 480px"
    )


def test_los_inputs_evitan_el_zoom_automatico_de_ios():
    """Safari hace zoom al enfocar un input con menos de 16px y no lo devuelve,
    dejando la pagina medio ilegible. Mobile_v2 ya lo resuelve con 16px."""
    fuente = _css("mobile_v2.css")
    assert re.search(r"input[^{]*\{[^}]*font-size:\s*16px", fuente, re.S), (
        "los inputs y selects del movil deben ir a 16px para evitar el zoom de iOS"
    )


# Selectores de formulario que el movil deja por debajo de 16px. Se midieron en
# la auditoria: el estilo de escritorio los baja con selectores mas especificos
# y, al ganar por especificidad, anulaban el `select, input, textarea` de 16px.
CAMPO_SENSIBLE_IOS = [
    "body .field-group select",
    "body .field-group input",
    "body .field-group textarea",
    "body .award-picker select",
]


@pytest.mark.parametrize("selector", CAMPO_SENSIBLE_IOS)
def test_los_campos_de_formulario_no_caen_de_16px_en_movil(selector):
    """El fallo era silencioso: el movil declara `input { font-size: 16px }` y aun
    asi `.field-group select` acababa a 10.2px, porque gana por especificidad.
    Basta con anadir un selector mas especifico y el zoom vuelve a aparecer."""
    fuente = _sin_comentarios(_css("mobile_v2.css"))
    # Los overrides van agrupados con comas, asi que hay que partir la lista de
    # selectores de cada regla en vez de buscar `selector {`.
    reglas = re.findall(r"([^{}]+)\{([^{}]*)\}", fuente)
    candidatos = [decl for sel, decl in reglas if selector in [s.strip() for s in sel.split(",")]]
    assert candidatos, f"falta el override movil para `{selector}`"
    for decl in candidatos:
        px = re.search(r"font-size:\s*([0-9.]+)rem", decl)
        if px:
            assert float(px.group(1)) * 16 >= 16, f"`{selector}` queda en {float(px.group(1)) * 16:.1f}px"
        else:
            assert "font-size: 16px" in decl, f"`{selector}` no fija 16px"


# ── Red de seguridad ─────────────────────────────────────────────────────────


def test_el_javascript_sigue_parseando():
    resultado = subprocess.run(
        ["node", "--experimental-vm-modules", "tools/js/check_syntax.js", "."],
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr


def test_el_scroll_lock_se_carga_antes_que_los_overlays():
    """Va como `<script defer>` sin `type="module"`, asi que el orden importa:
    si se cargara despues, `lmBloquearScroll` seria `undefined` en el primer
    overlay que se abra, y el que protege con `typeof` lo dejaria sin bloquear."""
    plantilla = Path("templates/liga_index.html").read_text(encoding="utf-8")
    lineas = [linea for linea in plantilla.splitlines() if "<script" in linea]
    posicion = next((i for i, l in enumerate(lineas) if "scroll_lock.js" in l), None)
    assert posicion is not None, "scroll_lock.js no se carga en la pagina principal"
    assert 'type="module"' not in lineas[posicion], (
        "los scripts son globales planos: con type=module no habria `window`"
    )
    for pendiente in ("pleno_modal", "command_palette", "onboarding"):
        assert not any(pendiente in l for l in lineas[:posicion]), f"{pendiente} se carga antes que scroll_lock.js"
