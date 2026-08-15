"""Directo (frontend): el mismo partido no puede pintarse dos veces.

Bug real: `matchPairKey()` solo leía la forma plana (`local`/`visitante`), pero
los partidos que llegan del proveedor externo traen únicamente la forma anidada
(`home.name`/`away.name`). Para esos, la clave salía vacía ("-"), así que el
agrupado no reconocía que el partido del proveedor y el de la quiniela eran el
mismo y Directo pintaba dos tarjetas del mismo encuentro.

Este test ejecuta el `utils.js` real con Node en vez de reimplementarlo, para
que no pueda quedarse obsoleto respecto al código de producción.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
UTILS = ROOT / "static" / "js" / "utils.js"
STATE = ROOT / "static" / "js" / "state.js"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node no disponible")

# Mismo encuentro por las dos vías: el proveedor solo manda la forma anidada
# y con otra grafía; la quiniela lo manda plano.
EXTERNAL_MATCH = {
    "fixture_id": 987654,
    "status": "LIVE",
    "score": "1-0",
    "home": {"name": "Deportivo Alaves"},
    "away": {"name": "Getafe CF"},
}
QUINIELA_MATCH = {
    "fixture_id": "quiniela-1-1",
    "status": "LIVE",
    "local": "Alavés",
    "visitante": "Getafe",
    "home": {"name": "Alavés"},
    "away": {"name": "Getafe"},
}
OTHER_MATCH = {
    "fixture_id": 111222,
    "status": "LIVE",
    "home": {"name": "Sevilla"},
    "away": {"name": "Rayo Vallecano"},
}


def _pair_key(match):
    script = f"""
{UTILS.read_text(encoding="utf-8")}
process.stdout.write(JSON.stringify(matchPairKey({json.dumps(match)})));
"""
    result = subprocess.run(  # noqa: S603
        ["node", "-e", script],  # noqa: S607
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    return json.loads(result.stdout)


def test_el_partido_externo_produce_una_clave_util():
    """Si la clave sale vacía, el dedupe no puede funcionar."""
    key = _pair_key(EXTERNAL_MATCH)
    assert key not in ("", "-"), "matchPairKey no lee home.name/away.name del proveedor externo"


def test_el_mismo_encuentro_colapsa_aunque_cambie_la_forma_y_la_grafia():
    assert _pair_key(EXTERNAL_MATCH) == _pair_key(QUINIELA_MATCH)


def test_encuentros_distintos_no_colapsan():
    assert _pair_key(OTHER_MATCH) != _pair_key(EXTERNAL_MATCH)


def test_el_agrupado_de_directo_reutiliza_matchpairkey():
    """state.js no debe reimplementar la clave por su cuenta.

    Tener dos lógicas de clave distintas fue justo lo que dejó pasar el bug.
    """
    state = STATE.read_text(encoding="utf-8")
    assert "matchPairKey(match)" in state, "getLiveLeagueMatches debe usar matchPairKey"
