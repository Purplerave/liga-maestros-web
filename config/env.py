"""Lectura defensiva de variables de entorno.

`int(os.getenv("X", "1"))` es una bomba de relojería: si alguien deja `X=""` o
`X="abc"` en el `.env`, la app no arranca, porque el error salta en tiempo de
import. Y aquí eso no es hipotético: `HIGHLIGHTLY_LIGA_F_ID` viene de un panel
externo que se rellena a mano.

Un identificador mal puesto, un limite de llamadas equivocado o un tamaño de
formulario raro no justifican que el sitio se caiga. Estos helpers devuelven el
valor por defecto y avisan por log, para que el fallo se vea en el log en vez de
impedir el arranque.
"""

import logging
import os

logger = logging.getLogger(__name__)


def env_str(name: str, default: str = "") -> str:
    raw = os.getenv(name)
    if raw is None:
        return default
    cleaned = str(raw).strip()
    # Una variable presente pero vacia se trata como ausente: en un `.env` escrito
    # a mano, "CLAVE=" significa "sin valor", no "la cadena vacia".
    return cleaned or default


def env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return default
    try:
        return int(str(raw).strip())
    except (TypeError, ValueError):
        logger.warning("%s=%r no es un entero; se usa el valor por defecto %s", name, raw, default)
        return default


def env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return default
    try:
        return float(str(raw).strip())
    except (TypeError, ValueError):
        logger.warning("%s=%r no es un numero; se usa el valor por defecto %s", name, raw, default)
        return default


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return default
    cleaned = str(raw).strip().lower()
    if cleaned in {"1", "true", "yes", "on", "si", "sí"}:
        return True
    if cleaned in {"0", "false", "no", "off"}:
        return False
    logger.warning("%s=%r no es un booleano; se usa el valor por defecto %s", name, raw, default)
    return default


def env_min_int(name: str, default: int, minimum: int) -> int:
    """Entero de entorno con suelo, para limites que nunca deben bajar de cero."""
    return max(minimum, env_int(name, default))
