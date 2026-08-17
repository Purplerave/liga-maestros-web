"""Trash talk: frases de los Maestros IA y réplica del mejor humano.

Regla de oro: las frases son reacciones al estado del duelo (ganando/perdiendo/
empate/primera). NUNCA inventan marcadores ni resultados.

Elección determinista por seed (jornada + maestro) para que rote sin duplicar
visitas consecutivas y sea estable bajo SSR/caché.
"""

from __future__ import annotations

import json
import logging
import os

import config

logger = logging.getLogger(__name__)

# Estados del duelo que el frontend ya sabe calcular
_VALID_STATES = ("va_ganando", "va_perdiendo", "empate", "primera")

# Maestros oficiales (en el mismo orden que en ECOSISTEMA_PARTICIPANTES.json)
_MASTER_IDS = ("programa", "claude", "grok", "chatgpt", "copilot", "gemini")


def _load_bank():
    """Carga el banco de frases desde seed o runtime. Robusto ante fichero ausente."""
    path = os.path.join(config.SEED_DATA_DIR, "MAESTROS_TRASH_TALK.json")
    if not os.path.exists(path):
        path = os.path.join(config.DATA_DIR, "MAESTROS_TRASH_TALK.json")
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError) as exc:
        logger.warning("MAESTROS_TRASH_TALK.json no disponible: %s", exc)
        return {"frases": {}, "replicas_pena": {}}


def _pick(lines, seed: int):
    """Elige una frase del banco de forma estable por seed. Robusto ante listas vacías."""
    if not lines:
        return ""
    return lines[seed % len(lines)]


def _seed_for(jornada: str, maestro: str) -> int:
    """Hash determinista 32-bit a partir de jornada + maestro."""
    raw = f"{jornada or '0'}|{maestro or ''}"
    h = 2166136261
    for ch in raw:
        h ^= ord(ch)
        h = (h * 16777619) & 0xFFFFFFFF
    return h


def maestro_phrase(maestro_id: str, bando_state: str, jornada: str) -> str:
    """Devuelve la frase del maestro para esta jornada y estado del duelo.

    ``bando_state`` ∈ {va_ganando, va_perdiendo, empate, primera}.
    Si el estado no se reconoce o el maestro no tiene banco, devuelve "" (calles neutras).
    """
    bank = _load_bank().get("frases", {})
    maestro = (maestro_id or "").lower()
    if maestro not in bank:
        return ""
    state = bando_state if bando_state in _VALID_STATES else "primera"
    lines = bank[maestro].get(state) or bank[maestro].get("primera") or []
    if not lines:
        return ""
    return _pick(lines, _seed_for(jornada, maestro))


def pena_replica(bando_state: str, jornada: str) -> str:
    """Réplica del mejor humano de La Peña. Sale de frases plantilla, nunca de un nombre real."""
    bank = _load_bank().get("replicas_pena", {})
    state = bando_state if bando_state in _VALID_STATES else "primera"
    lines = bank.get(state) or bank.get("primera") or []
    if not lines:
        return ""
    return _pick(lines, _seed_for(jornada, "pena-replica"))


def build_trash_talk(jornada, bando_state):
    """Devuelve el payload completo para el frontend.

    Devuelve un dict con la frase de cada maestro (mismo orden que ``_MASTER_IDS``)
    y la frase de réplica de La Peña. Vacío si no hay banco.
    """
    state = bando_state if bando_state in _VALID_STATES else "primera"
    jornada_key = str(jornada or "")
    return {
        "jornada": jornada_key,
        "bando_state": state,
        "masters": {mid: maestro_phrase(mid, state, jornada_key) for mid in _MASTER_IDS},
        "pena_replica": pena_replica(state, jornada_key),
    }
