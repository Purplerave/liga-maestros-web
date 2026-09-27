"""Los `catch` del front no pueden esconder fallos de render.

En `arena.js` el `catch` vacio del IntersectionObserver era un agujero visible: si
`JSON.parse` o `renderMatchCard` fallaban, el elemento se quedaba en su
placeholder de 120 px para siempre y ademas dejaba de observarse, asi que nunca
se recuperaba. Y el del banner "stale" se comia un `_panel_fetched_at` invalido
sin decir nada, porque `NaN > 15 * 60 * 1000` es `false`.

Estos tests comprueban sobre el fuente que:
- ya no queda ningun `catch` vacio en los ficheros de navegacion,
- y que los que quedan a proposito estan justificados con un comentario.
"""

import re
import subprocess
from pathlib import Path

import pytest

JS_DIR = Path("static/js")
CATCH_VACIO = re.compile(r"catch\s*\{\s*\}")


# Ficheros que se cargan en la navegacion principal. Los duplicados con hash se
# excluyen: se borran en la ola de deduplicacion de assets.
def _fuentes_navegacion():
    return [p for p in sorted(JS_DIR.rglob("*.js")) if not re.search(r"\.[0-9a-f]{8}\.js$", p.name)]


FUENTES = _fuentes_navegacion()


def test_hay_ficheros_que_analizar():
    assert len(FUENTES) > 10, "si esto falla, el glob de static/js dejo de funcionar y los tests pasan en falso"


@pytest.mark.parametrize("ruta", FUENTES, ids=lambda p: str(p))
def test_ningun_catch_vacio_sin_justificar(ruta):
    """Ningun `catch {}` puede quedar sin comentario que explique por que."""
    texto = ruta.read_text(encoding="utf-8")
    for coincidencia in CATCH_VACIO.finditer(texto):
        linea = texto[: coincidencia.start()].count("\n") + 1
        contexto = texto[max(0, coincidencia.start() - 400) : coincidencia.end() + 200]
        if "//" in contexto.split("catch")[-1]:
            continue
        pytest.fail(f"{ruta}:{linea} hay un catch vacio sin explicar")


def test_no_queda_ningun_catch_totalmente_vacio():
    """Cero `catch {}`.

    Cuando quede uno, no se anade en silencio: o se propaga, o se registra, o se
    documenta con un comentario que explique por que se ignora a proposito. Asi
    este test solo puede fallar cuando alguien introduce un silencio nuevo.
    """
    restantes = {}
    for ruta in FUENTES:
        for coincidencia in CATCH_VACIO.finditer(ruta.read_text(encoding="utf-8")):
            restantes.setdefault(str(ruta), []).append(coincidencia.start())
    assert not restantes, (
        f"catch vacios sin explicar: {restantes}. "
        "El unico motivo aceptable es localStorage en modo privado, y aun asi lleva comentario."
    )


def test_el_catch_de_localstorage_de_sonido_explica_por_que_ignora():
    """El unico error que se ignora a proposito esta documentado en el sitio."""
    texto = (JS_DIR / "sound_manager.js").read_text(encoding="utf-8")
    bloque = texto[texto.index("_save()") :]
    assert "modo privado" in bloque[:800], "el catch de localStorage debe explicar el motivo"


def test_arena_no_deja_placeholders_eternos():
    """La regresion concreta: el fallo de render debe ser visible y recovers."""
    texto = (JS_DIR / "arena.js").read_text(encoding="utf-8")
    assert "match-load-failed" in texto, "un fallo de tarjeta debe dejar marca en el DOM"
    assert 'class="match-card error-state"' in texto, "debe mostrarse un estado de error al usuario"
    assert "console.error" in texto, "el error debe quedar registrado"


def test_arena_avisa_si_el_timestamp_del_panel_es_invalido():
    """Un `_panel_fetched_at` roto no puede hacer desaparecer el aviso en silencio."""
    texto = (JS_DIR / "arena.js").read_text(encoding="utf-8")
    assert "Number.isNaN" in texto, "hay que comprobar que la fecha sea valida"
    assert "_panel_fetched_at no es una fecha valida" in texto


def test_el_banner_stale_no_rompe_la_vista_si_falla():
    texto = (JS_DIR / "arena.js").read_text(encoding="utf-8")
    bloque = texto[texto.index("stale-banner") :]
    assert "console.warn" in bloque[:2000], "el fallo del banner debe registrarse"


def test_arena_parsea():
    """Guardarraiz: si el fichero no parsea, nada de lo anterior importa."""
    resultado = subprocess.run(
        ["node", "--experimental-vm-modules", "tools/js/check_syntax.js", "."],
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr
    assert "Todos parsean correctamente" in resultado.stdout
