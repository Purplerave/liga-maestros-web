"""Parte de bajas: convierte noticias RSS en titulares cortos y accionables.

Entrada:  noticias del radar (titulo + sumario, texto real de la prensa).
Salida:   [{"jugador": "Isco", "equipo": "Betis", "estado": "baja",
            "nota": "lesion muscular"}]

Importante: la IA NUNCA recibe enlaces, solo el texto que el RSS ya nos ha dado.
Los modelos de las APIs gratuitas no navegan; si les pasas una URL se inventan
el contenido. Trabajar sobre el texto del feed evita esa alucinacion.

Coste tipico: 1 llamada (~1.400 tokens) por refresco con contenido nuevo.
"""

import json
import logging

from ...utils import normalize_team_key
from .budget import cache_get, cache_set, can_spend, content_signature, record_call
from .client import ai_enabled, chat

logger = logging.getLogger(__name__)

CACHE_SCOPE = "bajas"
MAX_NOTICIAS = 8
MIN_SCORE = 4  # solo noticias que mencionan algun equipo

ESTADOS_VALIDOS = {"baja", "duda", "sancion", "vuelve"}

ICONOS = {
    "baja": "\u274c",
    "duda": "\u26a0\ufe0f",
    "sancion": "\U0001f7e5",
    "vuelve": "\u2705",
}

SYSTEM_PROMPT = """Eres el redactor del parte de bajas de una quiniela española.
Recibes noticias de prensa deportiva en JSON.

Devuelves SOLO este JSON, sin texto alrededor:
{"bajas":[{"jugador":"Isco","equipo":"Betis","estado":"baja","nota":"lesion muscular"}]}

Reglas estrictas:
- `estado` solo puede ser: "baja" (seguro que no juega), "duda" (puede que no juegue),
  "sancion" (expulsado o sancionado), "vuelve" (regresa tras lesion).
- `nota`: MAXIMO 5 palabras.
- Si una noticia no habla de la disponibilidad de un jugador concreto, IGNORALA.
- NO inventes jugadores ni equipos que no aparezcan literalmente en el texto.
- Si ninguna noticia sirve, devuelve {"bajas":[]}."""


def _preparar_entrada(noticias):
    """Filtra y recorta las noticias que merece la pena enviar."""
    candidatas = [n for n in noticias if int(n.get("score") or 0) >= MIN_SCORE][
        :MAX_NOTICIAS
    ]
    if not candidatas:
        # Sin score (uso manual o pruebas): se aceptan tal cual.
        candidatas = list(noticias)[:MAX_NOTICIAS]
    return [
        {"t": str(n.get("title") or "")[:120], "s": str(n.get("summary") or "")[:220]}
        for n in candidatas
        if n.get("title")
    ]


def _validar_bajas(crudas, equipos_validos=None):
    """Descarta todo lo que no cumpla el contrato o invente equipos."""
    limpias = []
    vistos = set()
    for item in crudas:
        if not isinstance(item, dict):
            continue
        jugador = " ".join(str(item.get("jugador") or "").split())[:40]
        equipo = " ".join(str(item.get("equipo") or "").split())[:40]
        estado = str(item.get("estado") or "").strip().lower()
        nota = " ".join(str(item.get("nota") or "").split())[:60]

        if not jugador or not equipo or estado not in ESTADOS_VALIDOS:
            continue

        # Antialucinacion: el equipo debe existir de verdad en la jornada.
        if equipos_validos is not None:
            if normalize_team_key(equipo) not in equipos_validos:
                logger.info("IA: descartada baja de equipo desconocido (%s)", equipo)
                continue

        clave = (normalize_team_key(equipo), jugador.lower())
        if clave in vistos:
            continue
        vistos.add(clave)

        limpias.append(
            {
                "jugador": jugador,
                "equipo": equipo,
                "estado": estado,
                "nota": nota,
                "icono": ICONOS.get(estado, ""),
            }
        )
    return limpias


def construir_parte_bajas(noticias, equipos_validos=None):
    """Devuelve el parte de bajas. Lista vacia si la IA no esta disponible.

    Nunca lanza. Cualquier fallo (sin key, cuota agotada, proveedor caido,
    JSON invalido) se traduce en [] y la web sigue igual que hoy.
    """
    if not noticias or not ai_enabled():
        return []

    entrada = _preparar_entrada(noticias)
    if not entrada:
        return []

    firma = content_signature(item["t"] for item in entrada)

    cacheado = cache_get(CACHE_SCOPE, firma)
    if cacheado is not None:
        logger.info("IA: parte de bajas servido desde cache (0 tokens)")
        return _validar_bajas(cacheado, equipos_validos)

    if not can_spend():
        logger.warning("IA: cuota diaria agotada, se omite el parte de bajas")
        return []

    respuesta = chat(
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(entrada, ensure_ascii=False)},
        ],
        json_mode=True,
        max_tokens=600,
    )
    if not respuesta:
        return []

    record_call()

    try:
        crudas = json.loads(respuesta).get("bajas") or []
        if not isinstance(crudas, list):
            return []
    except Exception as exc:
        logger.warning("IA: JSON invalido en el parte de bajas (%s)", exc)
        return []

    cache_set(CACHE_SCOPE, firma, crudas)
    return _validar_bajas(crudas, equipos_validos)


def bajas_por_partido(bajas, partidos):
    """Cruza el parte con los partidos de la jornada. No consume IA.

    Devuelve {partido_id: [baja, ...]} para pintar el aviso junto a cada partido.
    """
    if not bajas or not partidos:
        return {}

    indice = {}
    for baja in bajas:
        indice.setdefault(normalize_team_key(baja["equipo"]), []).append(baja)

    resultado = {}
    for partido in partidos:
        partido_id = partido.get("id")
        if partido_id is None:
            continue
        for lado in ("local", "visitante"):
            clave = normalize_team_key(partido.get(lado) or "")
            if clave and clave in indice:
                resultado.setdefault(partido_id, []).extend(indice[clave])
    return resultado


def equipos_de_jornada(partidos):
    """Conjunto de claves normalizadas para validar lo que devuelve la IA."""
    claves = set()
    for partido in partidos or []:
        for lado in ("local", "visitante"):
            clave = normalize_team_key(partido.get(lado) or "")
            if clave:
                claves.add(clave)
    return claves
