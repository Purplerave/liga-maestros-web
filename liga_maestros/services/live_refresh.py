"""Refresco del directo bajo demanda: la web no depende de que el colector viva.

Foto del 22/11/2026 (J22, boleto SELAE 23): tras el despliegue de las 16:04 el
hilo del colector hizo una sola pasada y se quedo colgado. Nadie lo volvio a
arrancar, asi que a partir de ahi solo entro un scrape de quiniela15 (17:03),
y fue por casualidad: el de primera pintura, que solo saltaba con un partido
en ventana todavia en NS. A los 30 minutos sin noticias la lectura segura de
la portada cerro como STALE «Sin datos» los tres partidos que se estaban
jugando (Racing - Real Sociedad, Sporting - Las Palmas y Tenerife -
Madrid CFF): sin marcador en la quiniela y fuera del DIRECTO.

Aqui vive la decision —pura, sin IO— de cuando una lectura de la portada debe
pedir datos frescos, y el disparador de un unico refresco en segundo plano:

* Basta con que UN partido de la jornada este en su ventana de juego (de 10
  minutos antes del saque a 3 horas despues), no tenga un final confirmado y
  su ultimo dato de proveedor tenga mas de ``ROW_STALE_AFTER`` segundos. Da
  igual que este en NS, LIVE, HT o STALE: lo que manda es la frescura.
* El scrape compartido (colector o web) se respeta: si la cache de
  quiniela15 de la jornada se escribio hace menos de ``CACHE_FRESH_FOR``
  segundos no se vuelve a pedir. Con el colector sano la web no duplica nada.
* Un solo refresco a la vez en todo el proceso y como mucho uno cada
  ``MIN_GAP_SECONDS``. Si uno se queda colgado mas de ``STUCK_AFTER_SECONDS``
  se abandona (es un hilo daemon) y se permite otro, con un tope de
  abandonados para que una red rota no acumule hilos sin fin.
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

MADRID_TZ = ZoneInfo("Europe/Madrid")

# Ventana de juego de una casilla: igual que el poll rapido del frontend.
WINDOW_BEFORE = timedelta(minutes=10)
WINDOW_AFTER = timedelta(hours=3)
# Un dato de proveedor mas viejo que esto ya no es "directo". En directo el
# colector sano hace una pasada cada 60 s (mas lo que dure la pasada) y sella
# las filas en vivo en cada una.
ROW_STALE_AFTER = 100
# La cache de quiniela15 de la jornada se considera reciente durante este
# tiempo (la escribe tanto el colector, al principio de cada pasada, como este
# refresco). Es la guarda que evita duplicar el trabajo de un colector sano;
# con el colector caido marca el ritmo del refresco: ~100-130 s.
CACHE_FRESH_FOR = 100
MIN_GAP_SECONDS = 60
STUCK_AFTER_SECONDS = 180
MAX_ABANDONED = 5

# Estados que confirman un final: esas filas ya no necesitan directo. STALE no
# esta aqui a proposito: es justo el directo degradado que hay que recuperar.
FINAL_STATUSES = frozenset(
    {
        "FT",
        "FINISHED",
        "TERMINADO",
        "AET",
        "PEN",
        "AWARDED",
        "FINISHED AFTER EXTRA TIME",
        "FINISHED AFTER PENALTIES",
    }
)

_lock = threading.Lock()
_state = {
    "token": None,
    "running_since": 0.0,
    "last_started": 0.0,
    "last_finished": 0.0,
    "last_reason": "",
    "last_error": "",
    "runs": 0,
    "abandoned": 0,
}


def _as_naive_madrid(value):
    if value is None:
        return None
    if value.tzinfo is not None:
        return value.astimezone(MADRID_TZ).replace(tzinfo=None)
    return value


def parse_stamp(raw):
    """``updated_at`` de la BD (ISO, con o sin zona) a hora de Madrid naive."""
    if not raw:
        return None
    try:
        return _as_naive_madrid(datetime.fromisoformat(str(raw).strip()))
    except ValueError:
        return None


def parse_kickoff(fecha, hora):
    fecha = str(fecha or "").strip()[:10]
    hora = str(hora or "").strip()[:5]
    if len(fecha) != 10 or len(hora) != 5:
        return None
    try:
        return datetime.strptime(f"{fecha} {hora}", "%Y-%m-%d %H:%M")
    except ValueError:
        return None


def stale_live_rows(rows, now, row_stale_after=ROW_STALE_AFTER):
    """Casillas en ventana de juego sin final confirmado y con el dato viejo.

    ``rows`` son dicts (o ``sqlite3.Row``) con ``partido_id``/``id``, ``fecha``,
    ``hora``, ``status`` y ``updated_at``. ``now`` es hora de Madrid (naive o
    con zona). Devuelve la lista de ids, vacia si todo esta al dia.
    """
    now = _as_naive_madrid(now)
    stale = []
    for row in rows or []:
        getter = row.get if isinstance(row, dict) else (lambda key, _row=row: _row[key])
        try:
            kickoff = parse_kickoff(getter("fecha"), getter("hora"))
        except (KeyError, IndexError):
            continue
        if kickoff is None or not (kickoff - WINDOW_BEFORE <= now <= kickoff + WINDOW_AFTER):
            continue
        status = str(getter("status") or "").strip().upper()
        if status in FINAL_STATUSES:
            continue
        try:
            updated_at = parse_stamp(getter("updated_at"))
        except (KeyError, IndexError):
            updated_at = None
        if updated_at is not None and (now - updated_at).total_seconds() < row_stale_after:
            continue
        partido_id = None
        for key in ("partido_id", "id"):
            try:
                partido_id = getter(key)
            except (KeyError, IndexError):
                partido_id = None
            if partido_id is not None:
                break
        stale.append(partido_id)
    return stale


def needs_live_refresh(rows, now, cache_age_seconds=None):
    """True cuando una lectura de la portada debe pedir un scrape fresco.

    ``cache_age_seconds`` es la edad de la cache de quiniela15 de la jornada
    (``None`` si no existe): si alguien la acaba de escribir no se repite.
    """
    if cache_age_seconds is not None and cache_age_seconds < CACHE_FRESH_FOR:
        return False
    return bool(stale_live_rows(rows, now))


def refresh_state():
    """Foto del ultimo refresco bajo demanda (para /health y los tests)."""
    with _lock:
        snapshot = dict(_state)
    snapshot.pop("token", None)
    now = time.time()
    snapshot["running"] = bool(snapshot["running_since"])
    snapshot["running_for_seconds"] = int(now - snapshot["running_since"]) if snapshot["running_since"] else 0
    return snapshot


def trigger_refresh(jornada, runner, reason="", now_ts=None, thread_factory=None):
    """Lanza ``runner(jornada)`` en un hilo daemon si nadie lo esta haciendo ya.

    Devuelve True si se ha lanzado. Nunca bloquea al llamador: es seguro
    llamarlo desde el ciclo de una peticion.
    """
    now_ts = time.time() if now_ts is None else now_ts
    with _lock:
        running_since = _state["running_since"]
        if running_since:
            if now_ts - running_since < STUCK_AFTER_SECONDS:
                return False
            if _state["abandoned"] >= MAX_ABANDONED:
                return False
            # El anterior lleva demasiado: se abandona y se permite otro.
            _state["abandoned"] += 1
            logger.warning(
                "live_refresh colgado %ss; se lanza otro (abandonados=%s)",
                int(now_ts - running_since),
                _state["abandoned"],
            )
        if now_ts - _state["last_started"] < MIN_GAP_SECONDS:
            return False
        token = object()
        _state.update(
            {
                "token": token,
                "running_since": now_ts,
                "last_started": now_ts,
                "last_reason": str(reason or ""),
                "runs": _state["runs"] + 1,
            }
        )

    def _run():
        error = ""
        try:
            runner(jornada)
        except Exception as exc:  # pragma: no cover - el runner ya es best-effort
            error = str(exc)[:200]
            logger.exception("live_refresh fallo para J%s", jornada)
        finally:
            with _lock:
                if _state["token"] is token:
                    _state["running_since"] = 0.0
                    _state["last_finished"] = time.time()
                    _state["last_error"] = error
                    # Un refresco que acaba demuestra que la red responde: los
                    # abandonados anteriores ya no cuentan contra el tope.
                    _state["abandoned"] = 0

    factory = thread_factory or threading.Thread
    factory(target=_run, name="liga-live-refresh", daemon=True).start()
    return True


def _reset_for_tests():
    with _lock:
        _state.update(
            {
                "token": None,
                "running_since": 0.0,
                "last_started": 0.0,
                "last_finished": 0.0,
                "last_reason": "",
                "last_error": "",
                "runs": 0,
                "abandoned": 0,
            }
        )
