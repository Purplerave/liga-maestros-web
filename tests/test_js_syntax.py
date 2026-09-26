"""Todo el JavaScript de `static/js/` tiene que parsear.

Existia un `.js` roto en produccion (`static/js/features/shared/utils.js`, con un
`.replace` cuyo segundo argumento era una cadena sin cerrar) que nadie detectaba
porque el paso de sintaxis de la CI usaba `static/js/**/*.js` sin
`shopt -s globstar`, y sin globstar eso es un solo nivel: los ficheros de
`static/js/features/` nunca se comprotaban.

Ademas `node --check <fichero>` devuelve 0 siempre en maquinas Windows de este
entorno (pasa incluso un `prueba( )`), asi que este test delega en
`tools/js/check_syntax.js`, que compila el fuente con el parser de V8 de verdad.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "tools" / "js" / "check_syntax.js"


@pytest.mark.skipif(shutil.which("node") is None, reason="Node is required to parse the frontend")
def test_todo_el_javascript_parsea():
    proc = subprocess.run(
        ["node", "--experimental-vm-modules", str(CHECKER), str(ROOT)],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=str(ROOT),
    )
    salida = (proc.stdout or "") + (proc.stderr or "")
    assert proc.returncode == 0, "hay JavaScript que no parsea:\n" + salida


def test_no_vuelve_a_aparecer_el_globstar_roto():
    """`static/js/**/*.js` sin `shopt -s globstar` solo mira un nivel."""
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "shopt -s globstar" in ci, "la CI vuelve a comprobar JS de un solo nivel"
