import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
UTILS_JS = ROOT / "static" / "js" / "utils.js"
SIGN_CHECK_JS = Path(__file__).resolve().parent / "js" / "check_sign_hits.js"


def test_frontend_hit_rendering_uses_multiple_sign_matching():
    source = UTILS_JS.read_text(encoding="utf-8")

    assert "function standardSignMatches(sign, real)" in source
    assert "prediction.includes(result)" in source
    assert 'return standardSignMatches(sign, real) ? "hit" : "miss";' in source
    assert "return standardSignMatches(sign, real);" in source


def test_cover_doubles_are_hits_not_misses():
    """La portada comparaba con igualdad estricta: un 12 con resultado 1 salia
    como fallo, que es el doble que el usuario pusio en P1 y ya le habia salido
    mal. Ejecuta los helpers reales en node: 12/1X/X2, el pleno por marcador y
    los signos vacios.
    """
    if shutil.which("node") is None:
        pytest.skip("node no disponible")

    proc = subprocess.run(
        ["node", str(SIGN_CHECK_JS)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "OK" in proc.stdout


def test_next_match_timestamp_combines_date_and_kickoff_time():
    source = UTILS_JS.read_text(encoding="utf-8")

    assert "match.fecha_raw || match.fecha" in source
    assert "ts > Date.now() - graceMinutes * 60 * 1000" in source


def test_match_timestamps_are_read_in_madrid_time():
    """El servidor manda las horas en hora de Madrid, no en la del navegador.

    Leer "2026-09-03 21:00" con ``new Date()`` lo interpretaba en la zona
    local: en Canarias, con el movil en UTC o de viaje, el saque caia mas
    tarde y el DIRECTO se vaciaba con el partido ya empezado.
    """
    source = UTILS_JS.read_text(encoding="utf-8")

    assert 'const MADRID_TIMEZONE = "Europe/Madrid";' in source
    assert "function madridWallClockToMs(" in source
    # El unico camino para convertir fecha+hora en un instante es el reloj de
    # Madrid: nada de plantar la cadena en `new Date(...)` a secas.
    assert "new Date(`${isoDate}T${timePart}`)" not in source
