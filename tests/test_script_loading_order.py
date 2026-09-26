"""Grafo de carga de scripts y colisiones de ámbito global.

Los ficheros de `static/js` son scripts clasicos, no módulos: una declaración
`function` de nivel superior crea una propiedad en `window`. Como el shell carga
`quantum_final.js` de entrada (`liga_index.html:171`) y `navigation.js` carga
`ticket_page.js` y `pleno_modal.js` despues, bajo demanda, al entrar en TICKET,
el **último script en ejecutarse se queda con el binding**.

Eso ya_DSTUVO roto: `ticket_page.js` declaraba `ensureQ15Directo()` y
`loadPorra()`, machacando las implementaciones reales de `quantum_final.js`.
Abrir la vista TICKET dejaba muerta la porra y el Q15 directo en ARENA y
CONTEST para el resto de la sesión, sin ningun error en consola: `loadPorra()`
seguía existiendo, solo pintaba un placeholder.
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "static" / "js"
TEMPLATE = ROOT / "templates" / "liga_index.html"
NAVIGATION = JS / "navigation.js"
TICKET_PAGE = JS / "pages" / "ticket_page.js"
QUANTUM = JS / "quantum_final.js"

# Scripts que el shell carga de entrada, en el orden de liga_index.html.
SHELL_SCRIPTS = [
    "utils.js",
    "state.js",
    "logos.js",
    "navigation.js",
    "live.js",
    "arena.js",
    "events.js",
    "quantum_final.js",
]


def _declaraciones_de_nivel_superior(texto: str) -> set[str]:
    """Nombres declarados en el ámbito global del fichero.

    Solo cuenta declaraciones de nivel superior. Las que viven dentro de otra
    función, un IIFE o un bloque son locales y no tocan `window`.
    """
    nombres: set[str] = set()
    patron = re.compile(
        r"^(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(|"  # function foo(
        r"^(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?(?:\(|function\b)|"  # const foo = (
        r"^window\.([A-Za-z_$][\w$]*)\s*=",
        re.M,
    )
    for coincidencia in patron.finditer(texto):
        nombres.add(next(g for g in coincidencia.groups() if g))
    return nombres


@pytest.fixture(scope="module")
def scripts_del_shell() -> dict[str, str]:
    return {nombre: (JS / nombre).read_text(encoding="utf-8") for nombre in SHELL_SCRIPTS}


def test_los_scripts_del_shell_se_declaran_en_el_plantilla(scripts_del_shell):
    """Si el shell deja de cargar uno, este test debe notarlo."""
    plantilla = TEMPLATE.read_text(encoding="utf-8")
    for nombre in scripts_del_shell:
        assert f"filename='js/{nombre}'" in plantilla, f"{nombre} ya no se carga en liga_index.html"


def test_ticket_page_no_pisa_las_implementaciones_del_shell(scripts_del_shell):
    """El fallo concreto: stubs en un script cargado tarde."""
    del_shell = _declaraciones_de_nivel_superior(scripts_del_shell["quantum_final.js"])
    del_ticket = _declaraciones_de_nivel_superior(TICKET_PAGE.read_text(encoding="utf-8"))

    colisiones = del_shell & del_ticket
    assert not colisiones, (
        "ticket_page.js se carga DESPUES de quantum_final.js, asi que declarar aqui "
        f"estas funciones se queda con el binding global: {sorted(colisiones)}"
    )


def test_los_porra_y_q15_siguen_viviendo_en_quantum_final():
    """La implementacion real debe seguir en el shell, no en un script de vista."""
    quantum = QUANTUM.read_text(encoding="utf-8")
    assert "async function loadPorra" in quantum, "loadPorra real ha desaparecido de quantum_final.js"
    assert "async function ensureQ15Directo" in quantum, "ensureQ15Directo real ha desaparecido"

    # La real pinta los dos contenedores; el stub solo uno.
    cuerpo = re.search(r"async function loadPorra.*?\n\}", quantum, re.S)
    assert cuerpo, "no encuentro el cuerpo de loadPorra"
    assert "porra-body" in cuerpo.group(0) and "ticket-porra-body" in cuerpo.group(0), (
        "loadPorra debe pintar #porra-body y #ticket-porra-body: el stub solo pintaba "
        "el segundo, y por eso ARENA se quedaba sin porra"
    )

    # Y debe respetar el partido que le pasa el selector, cosa que el stub ignoraba.
    firma = re.search(r"async function loadPorra\s*\(([^)]*)\)", quantum)
    assert firma and firma.group(1).strip(), "loadPorra debe aceptar el partido seleccionado"


def test_los_scripts_de_vista_se_cargan_por_navegacion_y_no_estan_en_el_shell():
    """TICKET se resuelve por demanda; conviene que siga siendo así y que ambos
    archivos existan de verdad."""
    navegacion = NAVIGATION.read_text(encoding="utf-8")
    # TICKET aparece tambien en VIEW_STYLES, asi que el bloque tiene que salir de
    # VIEW_SCRIPTS: si no, el regex se come el de los CSS. Y el bloque se recorta
    # por la siguiente clave de nivel superior, no por el primer `]`, que es el
    # del primer elemento de la lista.
    scripts = navegacion.split("VIEW_SCRIPTS", 1)[1]
    inicio = re.search(r"\n\s*TICKET:\s*\[", scripts)
    assert inicio, "VIEW_SCRIPTS ya no declara la vista TICKET"
    resto = scripts[inicio.end() :]
    fin = re.search(r"\n\s*[A-Z_]+:\s*[\[{]", resto)
    bloque = resto[: fin.start()] if fin else resto
    rutas = re.findall(r"/static/js/[^\"']+", bloque)
    assert len(rutas) == 2, f"TICKET deberia cargar ticket_page y pleno_modal, carga {rutas}"
    for ruta in rutas:
        destino = ROOT / ruta.lstrip("/")
        assert destino.is_file(), f"{ruta} se carga pero no existe"
        assert f"filename='js/{ruta.split('js/', 1)[1]}'" not in TEMPLATE.read_text(encoding="utf-8"), (
            f"{ruta} sigue en el shell ademas de bajo demanda: se ejecutaria dos veces"
        )


def test_el_orden_de_carga_de_los_scripts_de_vista_esta_garantizado():
    """`async = true` en una lista ordenada deja el orden en manos de la red."""
    cuerpo = re.search(r"function loadScriptOnce.*?\n\}", NAVIGATION.read_text(encoding="utf-8"), re.S)
    assert cuerpo, "no encuentro loadScriptOnce en navigation.js"
    assert "script.async = false" in cuerpo.group(0), (
        "los scripts de vista se cargan con Promise.all; con async = true el orden "
        "de ejecucion depende de cual respuesta llegue antes"
    )
