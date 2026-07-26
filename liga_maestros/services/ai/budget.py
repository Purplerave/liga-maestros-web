"""Control de gasto de la IA: cuota diaria y cache por firma de contenido.

Mismo patron que services/highlightly_limits.py, pero simplificado: el volumen
de la IA es de unas pocas llamadas al dia, asi que basta un JSON en disco.

Dos mecanismos:
  - Cuota diaria (AI_DAILY_CALL_LIMIT): techo duro. Aunque un bug provoque un
    bucle, se gastan N llamadas y se para hasta el dia siguiente.
  - Cache por firma: si el contenido de entrada no ha cambiado, se reutiliza la
    respuesta anterior sin llamar a nadie. Coste: 0 tokens.
"""

import hashlib
import json
import logging
import os
import threading
from datetime import date

import config

from ...utils import safe_read_json, safe_write_json

logger = logging.getLogger(__name__)

AI_DAILY_CALL_LIMIT = int(os.getenv("AI_DAILY_CALL_LIMIT", "50"))

_budget_lock = threading.RLock()


def _usage_path():
    return os.path.join(config.DATA_DIR, "AI_USAGE.json")


def _cache_path(scope):
    safe_scope = "".join(char for char in scope if char.isalnum() or char in "-_")
    return os.path.join(config.DATA_DIR, f"AI_CACHE_{safe_scope.upper()}.json")


def content_signature(parts):
    """Firma estable del contenido de entrada.

    Si dos ejecuciones producen la misma firma, la respuesta anterior sigue
    siendo valida y no hace falta gastar tokens.
    """
    joined = "|".join(sorted(str(part) for part in parts))
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def get_usage():
    """Llamadas consumidas hoy. El contador se reinicia solo al cambiar el dia."""
    today = date.today().isoformat()
    data = safe_read_json(_usage_path(), {})
    if data.get("date") != today:
        return {
            "date": today,
            "calls": 0,
            "limit": AI_DAILY_CALL_LIMIT,
            "remaining": AI_DAILY_CALL_LIMIT,
        }
    calls = int(data.get("calls") or 0)
    return {
        "date": today,
        "calls": calls,
        "limit": AI_DAILY_CALL_LIMIT,
        "remaining": max(0, AI_DAILY_CALL_LIMIT - calls),
    }


def can_spend():
    """True si queda cuota diaria."""
    return get_usage()["remaining"] > 0


def record_call():
    """Suma una llamada al contador del dia."""
    with _budget_lock:
        usage = get_usage()
        payload = {"date": usage["date"], "calls": usage["calls"] + 1}
        try:
            safe_write_json(_usage_path(), payload)
        except Exception as exc:
            logger.warning("IA: no se pudo registrar el uso (%s)", exc)


def cache_get(scope, signature):
    """Respuesta cacheada para esta firma, o None."""
    data = safe_read_json(_cache_path(scope), {})
    if data.get("signature") != signature:
        return None
    try:
        return (
            json.loads(data["payload"])
            if isinstance(data.get("payload"), str)
            else data.get("payload")
        )
    except Exception:
        return None


def cache_set(scope, signature, payload):
    """Guarda la respuesta asociada a esta firma."""
    try:
        safe_write_json(
            _cache_path(scope), {"signature": signature, "payload": payload}
        )
    except Exception as exc:
        logger.warning("IA: no se pudo cachear la respuesta (%s)", exc)
