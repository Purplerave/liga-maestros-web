"""Comentarista MiMo: frases breves del directo, solo texto y con presupuesto.

Qué hace
--------
Convierte la foto actual del directo (partidos en juego con minuto y marcador)
en 1-3 frases cortas estilo comentarista ("gol de X", "le toca remontar a Y")
para la banda del ticker de la portada.

Por qué es barato (y por qué no te deja sin créditos)
-----------------------------------------------------
- **Una sola llamada para TODOS los partidos en juego.** Nunca una llamada por
  partido ni por minuto.
- **Disparo por cambio:** la firma del contenido (equipos + minuto + marcador)
  actúa de caché. Si el marcador no cambió, no se gastan tokens.
- **Cadencia mínima:** aunque cambie el marcador, no se llama más de una vez por
  ``MIMO_COMENTARISTA_MIN_INTERVAL_SECONDS`` (por defecto 10 minutos).
- **Presupuesto duro:** comparte el tope diario de ``services/ai/budget.py``
  (``AI_DAILY_CALL_LIMIT``). Agotado el cupo, se sirve lo último cacheado o nada.
- **Salida pequeña:** ``max_tokens`` reducido y validación estricta contra la
  foto, para que MiMo no invente goles, jugadores ni resultados.
- **Sin repeticiones:** un registro de frases ya emitidas evita repetir la misma
  idea en cada refresco.

Nunca lanza: si no hay key, cuota o red, devuelve ``{"comentarios": []}`` y la
web sigue funcionando exactamente igual.
"""

import json
import logging
import os

import config

from ...utils import normalize_news_text, safe_read_json, safe_write_json
from ..live_state import is_live_status
from .budget import cache_get, cache_get_latest, cache_set, content_signature, reserve_call
from .client import ai_enabled, chat

logger = logging.getLogger(__name__)

CACHE_SCOPE = "comentarista-v1"
EMITIDOS_PATH = os.path.join(config.DATA_DIR, "MIMO_COMENTARISTA_EMITIDOS.json")

MIN_INTERVAL_SECONDS = int(os.getenv("MIMO_COMENTARISTA_MIN_INTERVAL_SECONDS", "600"))
MAX_PARTIDOS = 6
MAX_COMENTARIOS = 3
MAX_PALABRAS = 16
MAX_EMITIDOS = 40

SYSTEM_PROMPT = (
    "Eres el comentarista breve de Liga de Maestros. "
    "Recibes una foto del directo: partidos en juego con minuto y marcador. "
    'Devuelve SOLO JSON: {"comentarios":[{"partido":1,"texto":"frase breve"}]}. '
    "Reglas:\n"
    "- Entre 1 y 3 comentarios. Si no hay nada relevante, lista vacia.\n"
    '- "partido" debe ser exactamente el id numerico de un partido recibido.\n'
    '- "texto": maximo 16 palabras, en espanol, estilo "gol de Fulanito" o '
    '"le toca remontar a Menganito".\n'
    "- Solo comenta hechos de la foto (marcador, minuto, estado). No inventes "
    "jugadores, goles ni resultados.\n"
    "- No repitas la misma idea dos veces.\n"
)


def _live_matches(matches):
    """Solo los partidos realmente en juego. El resto no interesa al comentarista."""
    return [m for m in (matches or []) if is_live_status(m.get("status"))]


def _preparar_entrada(live):
    """Foto compacta de hasta MAX_PARTIDOS partidos para mandar en una llamada."""
    entrada = []
    for index, match in enumerate(live[:MAX_PARTIDOS], start=1):
        local = " ".join(str(match.get("local") or "").split())[:40]
        visitante = " ".join(str(match.get("visitante") or "").split())[:40]
        if not local or not visitante:
            continue
        entrada.append(
            {
                "id": index,
                "local": local,
                "visitante": visitante,
                "minuto": str(match.get("minuto") or match.get("time") or "").strip()[:8],
                "marcador": str(match.get("marcador") or match.get("score") or "").strip()[:12],
                "estado": str(match.get("status") or "").strip().upper()[:12],
            }
        )
    return entrada


def _firma(entrada):
    """Firma estable de la foto: si no cambia, la respuesta anterior sigue valiendo."""
    return content_signature(
        f"{m['id']}|{m['local']}|{m['visitante']}|{m['minuto']}|{m['marcador']}|{m['estado']}" for m in entrada
    )


def _parsear_json(texto):
    """Tolera JSON puro o texto con un bloque JSON embebido (por si MiMo no honra response_format)."""
    try:
        return json.loads(texto)
    except (TypeError, ValueError):
        pass
    inicio = texto.find("{")
    fin = texto.rfind("}")
    if inicio != -1 and fin > inicio:
        try:
            return json.loads(texto[inicio : fin + 1])
        except (TypeError, ValueError):
            return None
    return None


def _validar_comentarios(crudas, entrada):
    """Descarta frases sin partido real, vacías, largas o repetidas en el lote."""
    por_id = {m["id"]: m for m in entrada}
    resultado = []
    vistos = set()
    for item in crudas if isinstance(crudas, list) else []:
        if not isinstance(item, dict):
            continue
        try:
            partido_id = int(item.get("partido"))
        except (TypeError, ValueError):
            continue
        match = por_id.get(partido_id)
        texto = " ".join(str(item.get("texto") or "").split())
        palabras = len(texto.split())
        if not match or palabras < 3 or palabras > MAX_PALABRAS:
            continue
        clave = normalize_news_text(texto)
        if clave in vistos:
            continue
        vistos.add(clave)
        resultado.append(
            {
                "texto": texto[:140],
                "local": match["local"],
                "visitante": match["visitante"],
                "minuto": match["minuto"],
                "marcador": match["marcador"],
            }
        )
        if len(resultado) >= MAX_COMENTARIOS:
            break
    return resultado


def _cargar_emitidos():
    data = safe_read_json(EMITIDOS_PATH, [])
    return [str(x) for x in (data if isinstance(data, list) else [])][-MAX_EMITIDOS:]


def _guardar_emitidos(emitidos):
    safe_write_json(EMITIDOS_PATH, list(emitidos)[-MAX_EMITIDOS:])


def _filtrar_repetidos(comentarios):
    """Quita las frases ya emitidas en refrescos anteriores y registra las nuevas."""
    emitidos = _cargar_emitidos()
    nuevos = []
    for c in comentarios:
        clave = normalize_news_text(c.get("texto") or "")
        if not clave or clave in emitidos:
            continue
        emitidos.append(clave)
        nuevos.append(c)
    if nuevos:
        _guardar_emitidos(emitidos)
    return nuevos


def _normalizar_cache(payload):
    if not isinstance(payload, dict):
        return None
    comentarios = [c for c in payload.get("comentarios") or [] if isinstance(c, dict)]
    return comentarios if comentarios else None


def construir_comentarios(matches):
    """Genera 1-3 frases de comentarista para la foto actual del directo.

    Devuelve ``{"comentarios": [...], "generated": bool}``. ``generated`` es True
    solo cuando se ha hecho una llamada nueva a la IA en esta invocación.
    """
    vacio = {"comentarios": [], "generated": False}
    if not ai_enabled():
        return vacio

    entrada = _preparar_entrada(_live_matches(matches))
    if not entrada:
        return vacio

    firma = _firma(entrada)
    cacheado = _normalizar_cache(cache_get(CACHE_SCOPE, firma))
    if cacheado is not None:
        return {"comentarios": cacheado, "generated": False}

    reciente = _normalizar_cache(cache_get_latest(CACHE_SCOPE, MIN_INTERVAL_SECONDS))
    if reciente is not None:
        return {"comentarios": reciente, "generated": False}

    if not reserve_call():
        # Cuota diaria agotada: degradar a lo último que tengamos (hasta 24h) o nada.
        ultimo = _normalizar_cache(cache_get_latest(CACHE_SCOPE, 86400))
        return {"comentarios": ultimo or [], "generated": False}

    respuesta = chat(
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(entrada, ensure_ascii=False)},
        ],
        json_mode=True,
        max_tokens=160,
        temperature=0.4,
        prefer="mimo",
    )
    if not respuesta:
        return {"comentarios": reciente or [], "generated": False}

    crudo = _parsear_json(respuesta)
    if not isinstance(crudo, dict):
        return {"comentarios": reciente or [], "generated": False}

    comentarios = _filtrar_repetidos(_validar_comentarios(crudo.get("comentarios"), entrada))
    cache_set(CACHE_SCOPE, firma, {"comentarios": comentarios})
    return {"comentarios": comentarios, "generated": bool(comentarios)}
