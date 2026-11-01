"""Numero de boleto real de SELAE para cada jornada interna.

La app numera sus jornadas **por concurso**: J1, J2, J3... desde el arranque de
la temporada 2026/27. SELAE numera sus boletos de forma distinta (en 2026/27 el
boleto de la jornada 17 del concurso es el SELAE **18**, porque hay boletos
extra entre medias).

El colector pedia los resultados a
``https://www.quiniela15.com/resultados-quiniela/<jornada_interna>``, es decir,
a un boleto que **no era el de la app**: para la J17 devolvia el boleto 17
(RSD Alcala - Las Palmas, Alcoyano - Mallorca...), un boleto ya jugado y sin
relacion con los quince partidos del boleto de la app. El cruce de equipos
descartaba esas quince filas (``q15_team_mismatch_skipped``) y los resultados
nunca entraban. Con el boleto correcto (18) la quiniela publica justo los
mismos quince partidos y el cruce funciona.

Este modulo resuelve el numero de boleto desde los datos versionados (la clave
``boleto.selae`` del fichero de scrape de la jornada), de modo que:
- el scraper pide el boleto correcto;
- una jornada sin dato explicito se queda con su propio numero (comportamiento
  historico, que era correcto mientras concurso y boleto coincidian);
- el dato vive en ``data/`` y no se inventa en el codigo.
"""

import json
import os
import re

import config

# Un boleto SELAE por numero de concurso. El rango cubre una temporada entera
# sin permitir que un valor absurdo de un fichero de datos dispare una URL
# arbitraria.
MIN_BOLETO = 1
MAX_BOLETO = 999

_CACHE = {}


def _candidate_dirs():
    for base in (
        getattr(config, "SEED_DATA_DIR", "") or "",
        getattr(config, "DATA_DIR", "") or "",
        os.path.join(getattr(config, "BASE_DIR", "") or "", "data"),
    ):
        if base:
            yield base


def _read_json(path):
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError, TypeError):
        return None


def _scrape_metadata(jornada):
    """Payload versionado de la jornada (``quiniela15_JN_scrape.json``)."""
    name = f"quiniela15_J{int(jornada)}_scrape.json"
    seen = set()
    for base in _candidate_dirs():
        path = os.path.join(base, name)
        if path in seen or not os.path.exists(path):
            continue
        seen.add(path)
        data = _read_json(path)
        if not isinstance(data, dict):
            continue
        try:
            if int(data.get("jornada") or 0) != int(jornada):
                continue
        except (TypeError, ValueError):
            continue
        return data
    return None


def _validate(value):
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return number if MIN_BOLETO <= number <= MAX_BOLETO else None


def _from_boleto_metadata(data):
    """``boleto.selae`` o, en su defecto, el numero dentro de ``boleto.nombre``.

    ``nombre`` es "SELAE 18"; se acepta como respaldo porque es el mismo dato
    escrito de forma legible. Cualquier otro texto se ignora en vez de
    adivinarse.
    """
    boleto = (data or {}).get("boleto")
    if not isinstance(boleto, dict):
        return None
    explicit = _validate(boleto.get("selae") or boleto.get("numero"))
    if explicit:
        return explicit
    match = re.search(r"\bSELAE\s+(\d{1,3})\b", str(boleto.get("nombre") or ""), flags=re.I)
    return _validate(match.group(1)) if match else None


def resolve_boleto_number(jornada):
    """Numero de boleto SELAE cuya tabla de resultados corresponde a la jornada.

    Devuelve la jornada interna cuando no hay dato explicito: es el mapeo que
    usaban las jornadas anteriores y el unico defendible sin informacion
    verificada. Nunca lanza: el colector debe seguir funcionando aunque el
    fichero de datos este corrupto.
    """
    try:
        key = int(jornada)
    except (TypeError, ValueError):
        return None
    if key in _CACHE:
        return _CACHE[key]
    resolved = _from_boleto_metadata(_scrape_metadata(key)) or key
    _CACHE[key] = resolved
    return resolved


def clear_cache():
    """Olvida lo resuelto (tests y recargas de datos en caliente)."""
    _CACHE.clear()
