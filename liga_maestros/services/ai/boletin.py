"""Boletin IA: novedades breves y bajas desde un unico lote de noticias RSS."""

import json
import logging
import os

from ...utils import normalize_news_text
from .bajas import _validar_bajas
from .budget import cache_get, cache_get_latest, cache_set, content_signature, reserve_call
from .client import ai_enabled, chat

logger = logging.getLogger(__name__)

CACHE_SCOPE = "boletin-v2"
MAX_NOTICIAS = 10
MIN_INTERVAL_SECONDS = int(os.getenv("AI_NEWS_MIN_INTERVAL_SECONDS", "7200"))
CATEGORIAS = {"fichaje", "baja", "alineacion", "forma", "club", "partido", "otro"}

SYSTEM_PROMPT = """Eres el redactor breve de Liga de Maestros.
Recibes noticias deportivas RSS verificadas, cada una con un id.

Devuelve SOLO JSON:
{"novedades":[{"id":1,"texto":"Resumen factual de una linea","categoria":"fichaje"}],
 "bajas":[{"id":2,"jugador":"Nombre","equipo":"Equipo","estado":"baja","nota":"motivo breve"}]}

Reglas:
- Elige entre 3 y 6 novedades realmente utiles y actuales.
- `texto` debe tener como maximo 18 palabras y no repetir el titular literalmente.
- `categoria`: fichaje, baja, alineacion, forma, club, partido u otro.
- El id debe pertenecer a una noticia recibida. No mezcles dos noticias.
- No inventes hechos, fechas, jugadores ni equipos.
- Las bajas solo admiten estado: baja, duda, sancion o vuelve.
- Cada baja debe incluir el id de la noticia que confirma jugador y equipo.
- Si una noticia no confirma disponibilidad de un jugador, no la incluyas en bajas.
- Si no hay contenido suficiente, devuelve listas vacias."""


def _preparar_entrada(noticias):
    entrada = []
    for index, noticia in enumerate(list(noticias)[:MAX_NOTICIAS], start=1):
        title = " ".join(str(noticia.get("title") or "").split())[:160]
        if not title:
            continue
        entrada.append(
            {
                "id": index,
                "fuente": str(noticia.get("source") or "")[:40],
                "titulo": title,
                "sumario": " ".join(str(noticia.get("summary") or "").split())[:320],
            }
        )
    return entrada


def _validar_novedades(crudas, noticias):
    por_id = {index: item for index, item in enumerate(list(noticias)[:MAX_NOTICIAS], start=1)}
    resultado = []
    vistos = set()
    for item in crudas if isinstance(crudas, list) else []:
        if not isinstance(item, dict):
            continue
        try:
            source_id = int(item.get("id"))
        except (TypeError, ValueError):
            continue
        fuente = por_id.get(source_id)
        texto = " ".join(str(item.get("texto") or "").split())
        categoria = str(item.get("categoria") or "otro").strip().lower()
        if not fuente or len(texto.split()) < 4 or source_id in vistos:
            continue
        vistos.add(source_id)
        if categoria not in CATEGORIAS:
            categoria = "otro"
        resultado.append(
            {
                "texto": texto[:180],
                "categoria": categoria,
                "source": fuente.get("source") or "",
                "published_at": fuente.get("published_at") or "",
                "link": fuente.get("link") or "",
                "title": fuente.get("title") or "",
            }
        )
        if len(resultado) >= 6:
            break
    return resultado


def _validar_bajas_con_fuente(crudas, noticias):
    por_id = {
        index: normalize_news_text(f"{item.get('title') or ''} {item.get('summary') or ''}")
        for index, item in enumerate(list(noticias)[:MAX_NOTICIAS], start=1)
    }
    candidatas = []
    for item in crudas if isinstance(crudas, list) else []:
        if not isinstance(item, dict):
            continue
        try:
            texto_fuente = por_id[int(item.get("id"))]
        except (KeyError, TypeError, ValueError):
            continue
        jugador = normalize_news_text(item.get("jugador") or "")
        equipo = normalize_news_text(item.get("equipo") or "")
        if not jugador or not equipo or jugador not in texto_fuente or equipo not in texto_fuente:
            logger.info("IA: baja descartada porque jugador y equipo no comparten fuente")
            continue
        candidatas.append(item)
    return _validar_bajas(candidatas)


def construir_boletin(noticias):
    """Genera novedades y bajas con una sola llamada para cada lote nuevo."""
    vacio = {"novedades": [], "bajas": []}
    if not noticias or not ai_enabled():
        return vacio

    entrada = _preparar_entrada(noticias)
    if not entrada:
        return vacio
    firma = content_signature(f"{item['id']}|{item['titulo']}|{item['sumario']}" for item in entrada)
    cacheado = cache_get(CACHE_SCOPE, firma)
    if isinstance(cacheado, dict):
        return {
            "novedades": _validar_novedades(cacheado.get("novedades"), noticias),
            "bajas": _validar_bajas_con_fuente(cacheado.get("bajas"), noticias),
        }
    reciente = cache_get_latest(CACHE_SCOPE, MIN_INTERVAL_SECONDS)
    if isinstance(reciente, dict):
        return reciente

    if not reserve_call():
        logger.warning("IA: cuota diaria agotada, se omite el boletin")
        return vacio

    respuesta = chat(
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(entrada, ensure_ascii=False)},
        ],
        json_mode=True,
        max_tokens=900,
    )
    if not respuesta:
        return vacio
    try:
        crudo = json.loads(respuesta)
        if not isinstance(crudo, dict):
            return vacio
    except (TypeError, ValueError) as exc:
        logger.warning("IA: JSON invalido en el boletin (%s)", exc)
        return vacio

    resultado = {
        "novedades": _validar_novedades(crudo.get("novedades"), noticias),
        "bajas": _validar_bajas_con_fuente(crudo.get("bajas"), noticias),
    }
    cache_set(CACHE_SCOPE, firma, resultado)
    return resultado
