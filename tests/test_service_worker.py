"""Contrato del service worker.

El SW se sirve en `/static/sw.js` pero se registra con `scope: "/"`
(`static/js/sw_register.js`) y `main.py:112-113` manda `Service-Worker-Allowed: /`,
 asi que controla TODO el origen. Eso includes `/api/*`, `/cuenta` y las paginas
legales, y antes de estos tests nadie lo tenia en cuenta.

Lo que se fija aqui, porque cada uno fue un fallo real:

- los POST no se interceptan: caian en el `networkFirst` por defecto, y
  `cache.put()` con un request no-GET lanza TypeError -> `throw new Error('Offline')`,
  lo que rompia POST /cuenta/eliminar y todos los formularios;
- el texto legal no se cachea: `/privacidad` y `/cookies` se servian desde Cache
  Storage indefinidamente, asi que offline salia la politica de privacidad de
  hace semanas;
- `/cuenta` no se cachea: llega con `no-store, private` y contiene nombre y email;
- se respeta el `Cache-Control` del servidor;
- la cache de navegacion tiene caducidad (24 h);
- `install` no es todo-o-nada: un 404 cancelaba los 25 precacheos;
- `activate` solo borra caches propias y todas las versiones anteriores.
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SW = ROOT / "static" / "sw.js"
REGISTER = ROOT / "static" / "js" / "sw_register.js"
MAIN = ROOT / "liga_maestros" / "routes" / "main.py"


@pytest.fixture(scope="module")
def sw() -> str:
    return SW.read_text(encoding="utf-8")


def _bloque_fetch(sw: str) -> str:
    """Codigo del listener 'fetch', que es donde se decide cada ruta."""
    match = re.search(r"addEventListener\('fetch'.*?\n\}\);", sw, re.S)
    assert match, "no encuentro el listener fetch en sw.js"
    return match.group(0)


def test_el_sw_parsea_y_el_registro_es_coherente():
    """`static/sw.js` tiene que ser JS valido o el navegador lo descarta entero."""
    proc = subprocess.run(
        ["node", "--check", str(SW)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if proc.returncode != 0 and "Unexpected token" in (proc.stderr or ""):
        # En Windows `node --check` devuelve 0 siempre; solo nos fiamos si fallo
        # de verdad. El validador de V8 es el que da la verdad.
        validador = subprocess.run(
            ["node", "--experimental-vm-modules", str(ROOT / "tools" / "js" / "check_syntax.js"), str(ROOT)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert validador.returncode == 0, "sw.js no parsea:\n" + (validador.stdout + validador.stderr)


def test_los_metodos_distintos_de_get_no_se_interceptan(sw):
    fetch = _bloque_fetch(sw)
    assert re.search(r"if\s*\(request\.method\s*!==\s*['\"]GET['\"]\)\s*return", fetch), (
        "sin el return temprano para metodos distintos de GET, un POST cae en el "
        "networkFirst por defecto y cache.put() con request no-GET lanza TypeError"
    )


def test_el_ambito_real_del_sw_es_todo_el_origen():
    """El comentario de sw.js afirmaba que el ambito era /static/. No lo es."""
    registro = REGISTER.read_text(encoding="utf-8")
    assert re.search(r"scope:\s*['\"]\/['\"]", registro), "el SW ya no se registra con scope '/'"
    assert 'Service-Worker-Allowed"] = "/"' in MAIN.read_text(encoding="utf-8"), (
        "main.py deberia seguir mandando Service-Worker-Allowed: /"
    )


@pytest.mark.parametrize("ruta", ["/cuenta", "/privacidad", "/cookies", "/aviso-legal", "/ayuda"])
def test_las_rutas_que_no_se_deben_cachear_estan_listadas(sw, ruta):
    match = re.search(r"NEVER_CACHE_PATHS\s*=\s*\[(.*?)\]", sw, re.S)
    assert match, "no encuentro NEVER_CACHE_PATHS en sw.js"
    assert f"'{ruta}'" in match.group(1), f"{ruta} no esta en NEVER_CACHE_PATHS"


def test_se_respeta_el_cache_control_del_servidor(sw):
    assert "function isCacheable" in sw, "falta isCacheable"
    bloque = re.search(r"function isCacheable.*?\n\}", sw, re.S)
    assert bloque, "no encuentro isCacheable"
    cuerpo = bloque.group(0)
    for token in ("no-store", "private", "no-cache"):
        assert token in cuerpo, f"isCacheable no mira {token}"


def test_la_cache_de_navegacion_tiene_caducidad(sw):
    assert "NAV_TTL_MS" in sw, "falta la caducidad de la cache de navegacion"
    match = re.search(r"NAV_TTL_MS\s*=\s*([0-9*_ ]+?)\s*;?\s*//", sw)
    assert match, "no encuentro el valor de NAV_TTL_MS"
    expresion = match.group(1).replace(" ", "").replace("_", "")
    assert re.fullmatch(r"[0-9*]+", expresion), f"expresion de caducidad inesperada: {expresion!r}"
    # Se evalua como aritmetica de enteros, sin Builtins ni nada.
    milisegundos = eval(expresion, {"__builtins__": {}}, {})  # noqa: S307
    assert 0 < milisegundos <= 7 * 24 * 60 * 60 * 1000, (
        f"NAV_TTL_MS = {milisegundos} ms ({milisegundos / 3600000:.1f} h) es mas de una semana"
    )
    assert milisegundos >= 60 * 60 * 1000, "una caducidad de menos de una hora no evita servir contenido rancio"


def test_activate_no_borra_caches_de_otras_apps(sw):
    activate = re.search(r"addEventListener\('activate'.*?\n\}\);", sw, re.S)
    assert activate, "no encuentro el listener activate"
    cuerpo = activate.group(0)
    assert "CACHE_PREFIX" in cuerpo, "activate deberia filtrar por prefijo propio"
    assert not re.search(r"keys\.filter\(key => key !== CACHE && key !== STATIC_CACHE\)", cuerpo), (
        "activate sigue borrando todas las caches del origen que no sean las suyas"
    )


def test_install_no_es_todo_o_nada(sw):
    install = re.search(r"addEventListener\('install'.*?\n\}\);", sw, re.S)
    assert install, "no encuentro el listener install"
    cuerpo = install.group(0)
    assert "addAll" not in cuerpo, "cache.addAll es todo-o-nada: un 404 cancela el precacheo entero"
    assert "allSettled" in cuerpo, "el precacheo deberia tolerar un recurso fallido"


def test_la_navegacion_se_bloquea_por_ttl_al_servir_desde_cache(sw):
    assert "function matchFresh" in sw, "falta matchFresh para la caducidad"
    bloque = re.search(r"async function matchFresh.*?\n\}", sw, re.S)
    assert bloque and "X-SW-Cached-At" in bloque.group(0), "matchFresh no comprueba la antiguedad de la entrada"
    network = re.search(r"async function networkFirst.*?\n\}", sw, re.S)
    assert network and "matchFresh" in network.group(0), "networkFirst no usa matchFresh"


def test_el_api_nunca_se_cachea(sw):
    assert re.search(r"if\s*\(path\.startsWith\('/api/'\)\)", _bloque_fetch(sw)), "la API debe seguir en su rama propia"
    assert "networkWithTimeout(request, API_TIMEOUT_MS)" in sw, "la API debe ir con tope de espera"


def test_el_tope_de_espera_de_la_api_no_es_un_filtro_de_rendimiento(sw):
    match = re.search(r"API_TIMEOUT_MS\s*=\s*(\d+)", sw)
    assert match, "no encuentro API_TIMEOUT_MS"
    assert int(match.group(1)) >= 15000, (
        "un tope bajo convierte respuestas lentas pero sanas en 503 inventados "
        "(en produccion /api/noticias/radar media 4,28 s)"
    )


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash is required to exercise the deploy sed")
def test_el_deploy_bupea_el_nombre_de_cache_del_sw():
    deploy = (ROOT / ".github" / "workflows" / "deploy-alwaysdata.yml").read_text(encoding="utf-8")
    assert "liga-maestros-(static-)?v" in deploy, (
        "el deploy debe reescribir el nombre de cache del SW; si no, el navegador "
        "reutiliza el sw.js viejo y su activate nunca borra la cache anterior"
    )
