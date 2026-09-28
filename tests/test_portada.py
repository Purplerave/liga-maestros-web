"""Portada y boleto: la columna PENA no puede inventar consenso y la tabla no puede marcar lo que no es navegacion.

Los casos se ejecutan en el arnes Node de `tools/js/cover_harness.js`, que carga
el `utils.js` y `cover_page.js` reales en una maquina virtual. Asi no se
comprueban cadenas sueltas, sino el comportamiento de las funciones.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]

CASOS_PORTADA = [
    "la-cuenta-atras-reintenta-sin-nodo",
    "la-porra-de-la-portada-no-se-queda-cargando",
    "la-porra-guardada-muestra-el-marcador",
    "la-porra-cerrada-no-ofrece-formulario",
    "el-fallo-de-la-porra-no-rompe-el-panel",
    "filas-alineadas-permiten-el-parche",
    "filas-desordenadas-exigen-render-completo",
    "filas-de-mas-exigen-render-completo",
    "el-parche-usa-la-regla-de-alineacion",
    "sin-votos-no-inventa-consenso",
    "porcentajes-sin-votos-son-cero",
    "empate-a-tres-no-es-lectura",
    "mayoria-clara-si-se-lee",
    "mayoria-simple-sobre-la-mitad",
    "la-fila-del-boleto-es-operable-y-segura",
    "la-navegacion-no-marca-las-filas",
    "el-separador-de-pena-va-encima-de-su-celda",
    "el-parche-incremental-esta-muerto",
]


@pytest.mark.parametrize("caso", CASOS_PORTADA)
def test_la_portada_se_comporta_como_debe(caso):
    """Cada caso del arnes falla si se revierte su arreglo correspondiente.

    Si Node no esta disponible, el test se salta en vez de dar un verde falso.
    """
    harness = RAIZ / "tools" / "js" / "cover_harness.js"
    node = shutil.which("node")
    if not node:
        pytest.skip("node no esta disponible para ejecutar el arnes de la portada")

    resultado = subprocess.run(
        [node, str(harness), caso],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=RAIZ,
    )
    salida = (resultado.stdout or "") + (resultado.stderr or "")
    assert resultado.returncode == 0, (
        f"el arnes de la portada fallo en el caso {caso!r} (codigo {resultado.returncode}):\n{salida.strip()}"
    )
