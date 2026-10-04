"""Liga data route: the main data endpoint."""

import hashlib
import logging
import threading
import time
from datetime import datetime, timedelta

from flask import Blueprint, g, jsonify, request, session

import config

from ..db.connection import get_db
from ..middleware.authz import is_admin_request
from ..schemas import validate_liga_data, validate_liga_data_first, validate_liga_data_slim
from ..services.multi_standings import build_multi_league_standings
from ..services.payloads.league_matches import build_all_league_matches, build_live_matches
from ..services.payloads.matches import build_jornada_matches
from ..services.payloads.predictions import build_predictions_payload
from ..services.payloads.standings import build_standings_payload, matchday_played, persist_standings
from ..services.teams import build_participant_contract, is_live_scored_status, is_scored_status
from ..services.ticket import compute_ticket_close_info, load_match_info_for_jornada, madrid_now, today_madrid
from ..services.trash_talk import build_trash_talk
from ..utils import load_team_logos, normalize_team_key

bp = Blueprint("liga_data", __name__)
logger = logging.getLogger(__name__)

# Simple in-memory cache for standings (TTL 5 min)
_STANDINGS_CACHE = {"data": None, "expires": 0, "key": None}
_STANDINGS_TTL = 300  # seconds
_COLD_START_RETRY_AFTER = 2
# Antipisarrapeos del refresco de primera pintura (ver
# _maybe_refresh_stale_window): un scrape Q15 como mucho cada 90 s en todo el
# proceso, y nunca dos a la vez.
_WINDOW_REFRESH_LOCK = threading.Lock()
_WINDOW_REFRESH_LAST = {"at": 0.0}
_WINDOW_REFRESH_MIN_GAP = 90  # seconds
_WINDOW_REFRESH_BUDGET = 6  # seconds max bloqueando la respuesta
# Ventana en la que un NS con el saque ya pasado exige dato fresco antes de
# pintar: desde 10 min antes del saque hasta 3 h despues (igual que el poll
# rapido del frontend). Fuera de ahi manda el catchup del colector.
_WINDOW_PRE_MINUTES = 10
_WINDOW_POST_HOURS = 3
# ``?slim=1`` lo pide el poll del directo (static/js/events.js). Cualquiera de
# estos valores activa la variante ligera; cualquier otro la desactiva.
_SLIM_FLAGS = frozenset({"1", "true", "yes", "on"})


def _cold_start_response(message="Los datos de la jornada aún se están preparando."):
    """Return a retryable response while the first live snapshot is warming."""
    response = jsonify(
        {
            "status": "cold_start",
            "code": "COLD_START",
            "message": message,
        }
    )
    response.status_code = 503
    response.headers["Retry-After"] = str(_COLD_START_RETRY_AFTER)
    response.headers["Cache-Control"] = "no-store"
    return response


def _wants_slim():
    """True cuando el cliente pide la variante ligera (``?slim=1``).

    La usa el poll del directo: cada 15 s por cliente, solo necesita lo que
    puede cambiar en esa ventana.
    """
    return (request.args.get("slim") or "").strip().lower() in _SLIM_FLAGS


def _wants_first():
    """True cuando el cliente pide la primera pintura (``?first=1``).

    Solo lo mínimo para firmar la quiniela; el resto llega después con
    la carga completa. Pensado para el móvil.
    """
    return (request.args.get("first") or "").strip().lower() in _SLIM_FLAGS


def _maybe_refresh_stale_window(conn, jornada, partidos):
    """Scrape Q15 sincrono (con tope) cuando la primera pintura saldria rancia.

    Si algun partido esta en ventana de juego (saque entre hace 3 h y dentro
    de 10 min) pero la BD aun lo marca NS, la pagina pintaria "no empezado"
    aunque el partido vaya por el minuto 5: es justo lo que se ve al abrir
    tras un cold start, con el colector aun despertando. En ese caso se lanza
    un scrape directo con presupuesto maximo de 6 s y se reconstruye la lista
    de partidos con lo que traiga. Best-effort total: cualquier fallo (o el
    tope) deja la respuesta como estaba y el poll del directo la cura en 30 s.
    """
    try:
        now = madrid_now().replace(tzinfo=None)
    except Exception:
        return partidos
    try:
        in_window_ns = False
        for match in partidos or []:
            if str(match.get("status") or "").upper() not in ("NS", "SCHEDULED", "NOT STARTED", ""):
                continue
            kickoff = _parse_payload_kickoff(match)
            if kickoff is None:
                continue
            if kickoff - timedelta(minutes=_WINDOW_PRE_MINUTES) <= now <= kickoff + timedelta(
                hours=_WINDOW_POST_HOURS
            ):
                in_window_ns = True
                break
        if not in_window_ns:
            return partidos
    except Exception:
        return partidos
    if not _WINDOW_REFRESH_LOCK.acquire(blocking=False):
        return partidos
    try:
        if time.time() - _WINDOW_REFRESH_LAST["at"] < _WINDOW_REFRESH_MIN_GAP:
            return partidos
        _WINDOW_REFRESH_LAST["at"] = time.time()
    finally:
        _WINDOW_REFRESH_LOCK.release()
    try:
        import sys as _sys
        from pathlib import Path as _Path

        tools_ops = str(_Path(config.BASE_DIR) / "tools" / "ops")
        if tools_ops not in _sys.path:
            _sys.path.insert(0, tools_ops)

        holder = {}
        worker = threading.Thread(
            target=lambda: holder.update(_run_q15_cache(jornada)),
            name="liga-first-paint-refresh",
            daemon=True,
        )
        worker.start()
        worker.join(timeout=_WINDOW_REFRESH_BUDGET)
        if not holder.get("done"):
            logger.info("first-paint refresh supera %ss para J%s; pinta BD y el poll curara", _WINDOW_REFRESH_BUDGET, jornada)
            return partidos
        from ..services.payloads.matches import build_jornada_matches
        from ..utils import load_team_logos

        return build_jornada_matches(conn, jornada, load_team_logos())
    except Exception:
        logger.exception("first-paint refresh fallo para J%s", jornada)
        return partidos


def _run_q15_cache(jornada):
    try:
        from LIVE_COLLECTOR import write_q15_directo_cache

        write_q15_directo_cache(int(jornada))
        return {"done": True}
    except Exception:
        return {"done": False}


def _parse_payload_kickoff(match):
    """Kickoff naive (Madrid) desde los campos del payload de partidos."""
    try:
        date = str(match.get("fecha_raw") or match.get("fecha") or "")[:10]
        hour = str(match.get("hora") or "")[:5]
        if len(date) != 10 or len(hour) != 5:
            return None
        return datetime.strptime(f"{date} {hour}", "%Y-%m-%d %H:%M")
    except Exception:
        return None


def _get_standings_cached(conn, partidos, team_logos):
    """Return (standings, standings_db) with 5-min TTL cache keyed by jornada+partidos hash."""
    # Cache key: jornada + hash of partidos IDs + count
    partido_ids = tuple(sorted(str(p.get("id")) for p in partidos if p.get("id")))
    cache_key = f"{len(partido_ids)}:{hash(partido_ids)}"
    now = time.time()
    if _STANDINGS_CACHE["data"] and now < _STANDINGS_CACHE["expires"] and _STANDINGS_CACHE["key"] == cache_key:
        return _STANDINGS_CACHE["data"]
    standings, standings_db = build_standings_payload(conn, partidos)
    persist_standings(conn, standings)
    _STANDINGS_CACHE["data"] = (standings, standings_db)
    _STANDINGS_CACHE["expires"] = now + _STANDINGS_TTL
    _STANDINGS_CACHE["key"] = cache_key
    return standings, standings_db


def _etag_for(payload):
    """Generate ETag from payload content hash."""
    return hashlib.md5(payload.encode(), usedforsecurity=False).hexdigest()  # noqa: S324


@bp.route("/api/liga/data")
def get_liga_data():
    requested_jornada = request.args.get("j", "")
    conn = get_db()
    try:
        max_jornada = _resolve_max_jornada(conn)
        if max_jornada is None:
            return _cold_start_response()

        jornadas_disponibles = _resolve_available_jornadas(conn)
        jornada = requested_jornada or max_jornada
        # Nueva temporada: si piden 75/76 u otra jornada de pruebas, redirigir a J1
        if jornadas_disponibles and str(jornada) not in {str(j) for j in jornadas_disponibles}:
            jornada = str(jornadas_disponibles[0])
        team_logos = load_team_logos()
        partidos = build_jornada_matches(conn, jornada, team_logos)
        if len(partidos) < 15:
            return _cold_start_response("La jornada todavía no tiene sus 15 partidos disponibles.")
        # Primera pintura fresca: si hay saques en ventana aun marcados NS
        # (cold start con BD dormida), intenta traer el directo ahora mismo
        # con tope de 6 s en vez de pintar "no empezado" hasta el refresh.
        partidos = _maybe_refresh_stale_window(conn, jornada, partidos)
        standings, standings_db = _get_standings_cached(conn, partidos, team_logos)
        all_league_matches = build_all_league_matches(jornada, partidos, standings_db, team_logos)
        live_matches = build_live_matches(partidos, team_logos, standings_db)
        multi_league_leagues = build_multi_league_standings(standings, team_logos)
        multi_league_standings = {"leagues": multi_league_leagues}
        jornada_liga = str(matchday_played(standings) or "")
        close_info = compute_ticket_close_info(partidos, source=f"api_liga_data_j{jornada}")
        is_locked = _is_ticket_locked(partidos, close_info, _raw_match_statuses(conn, jornada))
        user = session.get("user") or {}
        # Señal explícita de "ya guardó la quiniela de esta jornada". El frontend
        # la usa para mostrar el boleto en solo lectura (sin selector 1X2) aunque
        # la hidratación de predicciones no encuentre la clave del usuario.
        ticket_guardado = False
        if user.get("id"):
            row = conn.execute(
                "SELECT COUNT(*) AS c FROM predicciones WHERE user_id = ? AND jornada = ?",
                (str(user.get("id")), str(jornada)),
            ).fetchone()
            ticket_guardado = bool(row and row["c"] > 0)

        comentarista = _build_comentarista_payload(_live_matches_for_commentator(partidos, live_matches))

        if _wants_first():
            # Primera pintura: solo lo necesario para firmar. Sin predicciones,
            # ranking, trash talk, standings ni comentarista.
            response_payload = {
                "first": True,
                "jornada": jornada,
                "max_jornada": max_jornada,
                "today_madrid": today_madrid(),
                "is_locked": is_locked,
                "ticket_guardado": ticket_guardado,
                "edit_deadline": _format_dt(close_info.get("close_at")),
                "kickoff_at": _format_dt(close_info.get("first_kickoff")),
                "partidos": partidos,
                "ticket_policy": {
                    "max_dobles": config.MAX_DOBLES_PER_TICKET,
                    "max_triples": config.MAX_TRIPLES_PER_TICKET,
                },
            }
        elif _wants_slim():
            # El poll del directo solo necesita lo que puede cambiar en 30 s.
            # Todo lo que sale de las predicciones (participantes, consenso,
            # ranking, trash talk) se calcula una sola vez en la carga completa
            # y el frontend lo conserva entre polls. Medido sobre la DB de
            # producción: ~65 % menos CPU por poll.
            response_payload = {
                "slim": True,
                "jornada": jornada,
                "jornada_liga": jornada_liga,
                "max_jornada": max_jornada,
                "today_madrid": today_madrid(),
                "is_locked": is_locked,
                "ticket_guardado": ticket_guardado,
                "edit_deadline": _format_dt(close_info.get("close_at")),
                "kickoff_at": _format_dt(close_info.get("first_kickoff")),
                "partidos": partidos,
                "all_league_matches": all_league_matches,
                "live_matches": live_matches,
                "standings": standings,
                "multi_league_standings": multi_league_standings,
                "comentarista": comentarista,
            }
        else:
            match_info = _load_and_repair_match_info(jornada, partidos)
            predictions_payload = build_predictions_payload(
                conn,
                jornada,
                current_user_id=user.get("id"),
                reveal_all=is_locked,
            )
            participant_contract = predictions_payload.get("participant_contract") or build_participant_contract()
            trash_talk = _build_trash_talk_payload(
                jornada=jornada,
                ranking=predictions_payload.get("ranking_maestros", {}),
                participant_contract=participant_contract,
            )
            response_payload = {
                "jornada": jornada,
                "jornada_liga": jornada_liga,
                "max_jornada": max_jornada,
                "jornadas_disponibles": jornadas_disponibles,
                "today_madrid": today_madrid(),
                "is_locked": is_locked,
                "ticket_guardado": ticket_guardado,
                "edit_deadline": _format_dt(close_info.get("close_at")),
                "kickoff_at": _format_dt(close_info.get("first_kickoff")),
                "partidos": partidos,
                "all_league_matches": all_league_matches,
                "live_matches": live_matches,
                "standings": standings,
                "multi_league_standings": multi_league_standings,
                "participant_contract": participant_contract,
                "match_info": match_info,
                "predicciones_actuales": predictions_payload["predicciones_actuales"],
                "consenso_pena": predictions_payload["consenso_pena"],
                "consenso_pleno_pena": predictions_payload["consenso_pleno_pena"],
                "ranking_maestros": predictions_payload["ranking_maestros"],
                "trash_talk": trash_talk,
                "comentarista": comentarista,
                "auth_enabled": config.GOOGLE_AUTH_ENABLED,
                "live_stream_enabled": config.LIVE_SSE_ENABLED,
                "is_admin": is_admin_request(),
                "ticket_policy": {
                    "max_dobles": config.MAX_DOBLES_PER_TICKET,
                    "max_triples": config.MAX_TRIPLES_PER_TICKET,
                },
            }
        # Validación de contrato (no rompe la respuesta si hay drift, solo loguea)
        if response_payload.get("first"):
            validated, schema_error = validate_liga_data_first(response_payload)
        elif response_payload.get("slim"):
            validated, schema_error = validate_liga_data_slim(response_payload)
        else:
            validated, schema_error = validate_liga_data(response_payload)
        if schema_error:
            logger.info("api_liga_data served with schema drift: %s", schema_error)

        # ETag support
        response_json = jsonify(validated).get_data(as_text=True)
        etag = _etag_for(response_json)
        # Esta respuesta es POR USUARIO: `ticket_guardado`, `is_locked`,
        # `predicciones_actuales` e `is_admin` dependen de la sesion. Servirla con
        # `public` hacia que un CDN o un proxy compartido guardara el body y se lo
        # devolviera a otro usuario: el boleto de A servido a B. `private`+vary
        # Cookie lo prohibe y `no-cache` conserva el 304 por ETag, que es justo lo
        # que hace falta con un boleto que cambia a mitad de jornada.
        if_none_match = request.headers.get("If-None-Match")
        if if_none_match and if_none_match == etag:
            resp = jsonify({"status": "not_modified"})
            resp.status_code = 304
            resp.headers["ETag"] = etag
            resp.headers["Cache-Control"] = "private, no-cache, must-revalidate"
            resp.headers["Vary"] = "Cookie"
            return resp

        resp = jsonify(validated)
        resp.headers["ETag"] = etag
        resp.headers["Cache-Control"] = "private, no-cache, must-revalidate"
        resp.headers["Vary"] = "Cookie"
        return resp
    except Exception:
        logger.exception("api_liga_data failed")
        return jsonify(
            {
                "status": "error",
                "message": "No se pudo procesar la solicitud",
                "request_id": getattr(g, "request_id", ""),
            }
        ), 500


def _resolve_max_jornada(conn):
    # La web y el guardado comparten exactamente esta jornada activa.
    from ..services.jornada import resolve_active_jornada

    return resolve_active_jornada(conn)


def _resolve_available_jornadas(conn):
    # Jornadas visibles de la temporada 2026/27 (1..42), ordenadas de más
    # reciente a más antigua. Así la web promociona a J2 cuando ya está
    # cargada, sin dejar J1 fija para siempre.
    from ..services.jornada import is_current_season_jornada

    def _row_jornada(row):
        try:
            return row["jornada"]
        except Exception:
            try:
                return row[0]
            except Exception:
                return None

    try:
        rows = conn.execute("""
            SELECT jornada, COUNT(*) AS partidos
            FROM resultados
            GROUP BY jornada
            HAVING partidos > 0
            ORDER BY jornada DESC
        """).fetchall()
        jornadas = [
            int(_row_jornada(row))
            for row in rows
            if _row_jornada(row) is not None and is_current_season_jornada(_row_jornada(row))
        ]
        if jornadas:
            return sorted(set(jornadas), reverse=True)
    except Exception:
        pass

    # Fallback: sin jornadas de la temporada actual
    try:
        rows = conn.execute("""
            SELECT jornada, COUNT(*) AS partidos
            FROM resultados
            GROUP BY jornada
            HAVING partidos > 0
            ORDER BY jornada DESC
        """).fetchall()
        jornadas = [int(_row_jornada(row)) for row in rows if _row_jornada(row) is not None]
        filtered = [j for j in jornadas if j not in (75, 76)]
        if filtered:
            cur = [j for j in filtered if is_current_season_jornada(j)]
            return sorted(set(cur or filtered), reverse=True)
    except Exception:
        pass

    # Último recurso: si hay scrape de alguna jornada 1..42 en disco, ofrecerla
    import os as _os

    import config as _cfg

    found = []
    for j in range(1, 43):
        for base in (_cfg.SEED_DATA_DIR, _cfg.DATA_DIR, _os.path.join(_cfg.BASE_DIR, "data")):
            if base and _os.path.exists(_os.path.join(base, f"quiniela15_J{j}_scrape.json")):
                found.append(j)
                break
    if found:
        return sorted(set(found), reverse=True)
    return [1]


def _raw_match_statuses(conn, jornada):
    """Estados tal y como estan en la tabla, sin el autoreparado de
    `build_jornada_matches`.

    Ese autoreparado existe para no pintar un partido fantasma en vivo cuando el
    collector se quedó colgado, asi que es correcto para la pantalla. El problema
    es que `POST /api/predicciones/save` lee la tabla cruda: si un LIVE con el
    saque en el futuro se rebaja a NS para mostrarlo, el front invita a firmar y
    el guardado responde 403. El usuario pierde los 15 signos sin aviso, y sin
    este dato el bloqueo no puede saberlo.
    """
    try:
        filas = conn.execute("SELECT status FROM resultados WHERE jornada = ?", (str(jornada),)).fetchall()
    except Exception:  # pragma: no cover - defensivo: sin dato crudo, no se bloquea de mas
        logger.warning("No se pudieron leer los estados crudos de la jornada %s", jornada, exc_info=True)
        return []
    return [fila["status"] for fila in filas if fila["status"]]


def _is_ticket_locked(partidos, close_info, estados_crudos=()):
    """El boleto se bloquea con los MISMOS estados que acepta el guardado.

    Tres fallos se acumulaban aqui:

    1. Se comparaba contra una lista a mano, `("LIVE", "FT", "FINISHED")`, que se
       quedaba corta: el guardado cierra con `is_scored_status` o
       `is_live_scored_status`, que ademas reconocen IN PLAY, HT, HALF TIME BREAK,
       EN JUEGO y TERMINADO. Con cualquiera de esos el front habria pintado el
       selector 1X2 editable y el guardado devolveria 403.
    2. Solo se miraba el status ya autoreparado del payload (ver
       `_raw_match_statuses`): un LIVE con el saque en el futuro se pinta como NS,
       el front ofrece firmar y el guardado lo rechaza.
    3. La comprobacion por estado era mas laxa que la del guardado. Cuando el
       horario no se puede interpretar `close_at` es None y el tiempo no bloquea
       nada, asi que el estado es la unica red.

    Ante la duda, cerrar. Perder una quiniela cuesta mucho mas que dejar un
    partido sin firmar.
    """
    close_at = close_info.get("close_at")
    close_started = bool(close_at and madrid_now() >= close_at)
    estados = [match.get("status") for match in partidos]
    estados.extend(estados_crudos or ())
    match_started = any(is_scored_status(estado) or is_live_scored_status(estado) for estado in estados)
    return close_started or match_started


def _format_dt(value):
    return value.strftime("%Y-%m-%d %H:%M") if value else ""


def _load_and_repair_match_info(jornada, partidos):
    match_info = load_match_info_for_jornada(jornada)
    partidos_by_id = {str(match.get("id")): match for match in partidos}
    for match_id, info in match_info.items():
        detail = info.get("detalle") or ""
        if "Hypermotion" not in detail:
            continue
        match = partidos_by_id.get(str(match_id)) or {}
        detail = (
            detail.replace("6Âº Hypermotion", match.get("local") or "Local")
            .replace("3Âº Hypermotion", match.get("visitante") or "Visitante")
            .replace("5Âº Hypermotion", match.get("local") or "Local")
            .replace("4Âº Hypermotion", match.get("visitante") or "Visitante")
        )
        info["detalle"] = detail
    return match_info


def _bando_state_for(ranking, participant_contract):
    """Calcula el estado del duelo (Peña vs IA) replicando la lógica del frontend.

    Devuelve: va_ganando (Peña), va_perdiendo (Peña), empate, primera.
    Usa las medias de puntos por jornada (``jornada_live`` o ``jornada``) sobre
    el conjunto de ids oficiales y de La Peña. Robusto ante ranking vacío.
    """
    if not ranking or not participant_contract:
        return "primera"
    ai_ids = {str(col.get("id", "")).lower() for col in participant_contract.get("visible_ai_columns", [])}
    pena_ids = {str(uid).lower() for uid in participant_contract.get("pena_ids", [])}
    human_total, human_count, ai_total, ai_count = 0, 0, 0, 0
    for raw_uid, values in ranking.items():
        uid = str(raw_uid or "").lower()
        jornada_pts = values.get("jornada_live") if values.get("jornada_live") is not None else values.get("jornada", 0)
        try:
            pts = int(jornada_pts or 0)
        except (TypeError, ValueError):
            pts = 0
        if uid in ai_ids:
            ai_total += pts
            ai_count += 1
        elif uid in pena_ids:
            human_total += pts
            human_count += 1
    if human_count == 0 and ai_count == 0:
        return "primera"
    if human_count == 0 or ai_count == 0:
        return "primera"
    human_avg = human_total / human_count
    ai_avg = ai_total / ai_count
    diff = ai_avg - human_avg
    if diff > 0.05:
        return "va_perdiendo"  # Peña perdiendo (IA ganando)
    if diff < -0.05:
        return "va_ganando"  # Peña ganando
    return "empate"


def _build_trash_talk_payload(*, jornada, ranking, participant_contract):
    """Construye el payload de trash-talk para el frontend."""
    state = _bando_state_for(ranking, participant_contract)
    return build_trash_talk(jornada, state)


def _build_comentarista_payload(matches):
    """Comentarios breves del directo (MiMo). Best-effort: nunca rompe la portada.

    Usa la variante no bloqueante: la llamada a la IA se hace en un hilo y esta
    petición sirve lo que ya hay en caché. Generar dentro del ciclo de petición
    retenía /api/liga/data hasta un minuto (timeout por proveedor x reintentos)
    justo cuando había partidos en juego, que es cuando el comentarista dispara.
    """
    try:
        from ..services.ai.comentarista import comentarios_para_web

        return comentarios_para_web(matches)
    except Exception:
        return {"comentarios": [], "generated": False}


def _live_matches_for_commentator(partidos, live_matches):
    """Foto unica de lo que esta en juego: quiniela + las 5 ligas seguidas.

    El directo no depende de la quiniela: un jueves con la Real Sociedad -
    Celta y el Toulouse - Lille en juego tiene tanto futbol que comentar como
    un sabado de jornada, aunque ninguno de esos partidos entre en el boleto.
    Por eso se mezclan las dos fuentes (la quiniela y el panel externo de las
    ligas) y se normalizan a una unica forma antes de pasarselas a la IA.

    Cuando el mismo partido llega por los dos caminos gana la copia de la
    quiniela, que es la que usa el resto de la web para nombrar a los equipos.
    """
    merged = {}

    def add(match, home, away):
        home = str(home or "").strip()
        away = str(away or "").strip()
        if not home or not away:
            return
        key = (normalize_team_key(home), normalize_team_key(away))
        if key in merged:
            return
        merged[key] = {
            "local": home,
            "visitante": away,
            "minuto": str(match.get("minuto") or match.get("time") or "").strip(),
            "marcador": str(match.get("marcador") or match.get("score") or "").strip(),
            "status": str(match.get("status") or "").strip(),
        }

    for match in partidos or []:
        add(match, match.get("local"), match.get("visitante"))
    for match in live_matches or []:
        home = match.get("local") or match.get("home_name") or (match.get("home") or {}).get("name")
        away = match.get("visitante") or match.get("away_name") or (match.get("away") or {}).get("name")
        add(match, home, away)
    return list(merged.values())


def _refresh_issue_message(status, skipped, failures):
    if status == "ok":
        return "Actualización completada sin incidencias."

    def describe(item):
        label = item.get("league") or item.get("component") or "operación"
        reason = item.get("reason")
        return f"{label} ({reason})" if reason else label

    details = []
    if skipped:
        details.append(f"Omitidos: {', '.join(describe(item) for item in skipped)}")
    if failures:
        details.append(f"Fallos: {', '.join(describe(item) for item in failures)}")
    suffix = f" {'; '.join(details)}." if details else ""
    return f"Actualización parcial.{suffix}"


def _tag_refresh_issues(issues, component):
    return [{"component": component, **issue} for issue in issues if isinstance(issue, dict)]


@bp.post("/api/admin/refresh-standings")
def refresh_standings():
    if not is_admin_request():
        return jsonify({"status": "forbidden"}), 403
    from ..services.multi_standings import refresh_all_standings

    summary = refresh_all_standings(season=config.CURRENT_SEASON_START_YEAR)
    status = summary.get("status", "ok")
    skipped = _tag_refresh_issues(summary.get("skipped", []), "standings")
    failures = _tag_refresh_issues(summary.get("failures", []), "standings")
    return jsonify(
        {
            "status": status,
            "updated": summary,
            "skipped": skipped,
            "failures": failures,
            "message": _refresh_issue_message(status, skipped, failures),
        }
    )


@bp.post("/api/admin/refresh-all")
def refresh_everything():
    """Admin-only 'update everything NOW' switch.

    Refreshes, in order: all league standings (Spanish BASE + foreign cache),
    today's agenda for every followed league, today's live scores/panel (which
    also archives newly finished matches with their statistics), and kicks the
    quiniela live refresh asynchronously.
    """
    if not is_admin_request():
        return jsonify({"status": "forbidden"}), 403

    from ..services.daily_matches import refresh_daily_agenda, refresh_live_scores
    from ..services.highlightly import trigger_highlightly_refresh_async
    from ..services.multi_standings import refresh_all_standings

    summary = {}
    skipped = []
    failures = []
    try:
        standings = refresh_all_standings(season=config.CURRENT_SEASON_START_YEAR)
        summary["standings"] = standings
        skipped.extend(_tag_refresh_issues(standings.get("skipped", []), "standings"))
        failures.extend(_tag_refresh_issues(standings.get("failures", []), "standings"))
        if standings.get("status") in ("partial", "error") and not (skipped or failures):
            failures.append({"component": "standings", "reason": "la actualización no se completó"})
    except Exception:
        logger.exception("refresh-all: standings failed")
        summary["standings"] = "error"
        failures.append({"component": "standings", "reason": "falló la actualización de clasificaciones"})
    try:
        agenda = refresh_daily_agenda(force=True)
        summary["agenda_matches"] = len(agenda.get("matches", []))
    except Exception:
        logger.exception("refresh-all: agenda failed")
        summary["agenda_matches"] = "error"
        failures.append({"component": "agenda", "reason": "falló la actualización de la agenda"})
    try:
        summary["panel_matches"] = refresh_live_scores()
    except Exception:
        logger.exception("refresh-all: live scores failed")
        summary["panel_matches"] = "error"
        failures.append({"component": "directo", "reason": "falló la actualización del panel en directo"})
    try:
        summary["quiniela_refresh_started"] = bool(trigger_highlightly_refresh_async(force=True))
        if not summary["quiniela_refresh_started"]:
            skipped.append({"component": "quiniela", "reason": "la actualización asíncrona no se inició"})
    except Exception:
        logger.exception("refresh-all: quiniela live refresh failed")
        summary["quiniela_refresh_started"] = False
        failures.append({"component": "quiniela", "reason": "falló el inicio de la actualización"})

    status = "partial" if skipped or failures else "ok"
    return jsonify(
        {
            "status": status,
            "summary": summary,
            "skipped": skipped,
            "failures": failures,
            "message": _refresh_issue_message(status, skipped, failures),
        }
    )


# Granular endpoints (FASE 4) — wrappers ligeros sobre /api/liga/data
@bp.route("/api/liga/standings")
def get_standings():
    conn = get_db()
    try:
        from ..services.jornada import resolve_active_jornada

        jornada = str(resolve_active_jornada(conn) or "1")
        team_logos = load_team_logos()
        partidos = build_jornada_matches(conn, jornada, team_logos)
        standings, _ = _get_standings_cached(conn, partidos, team_logos)
        resp = jsonify({"jornada": jornada, "standings": standings, "today_madrid": today_madrid()})
        resp.headers["Cache-Control"] = "public, max-age=60, must-revalidate"
        return resp
    except Exception:
        logger.exception("api/liga/standings failed")
        return jsonify(
            {
                "status": "error",
                "message": "No se pudo procesar la solicitud",
                "request_id": getattr(g, "request_id", ""),
            }
        ), 500


@bp.route("/api/liga/live")
def get_live():
    conn = get_db()
    try:
        from ..services.jornada import resolve_active_jornada

        jornada = str(resolve_active_jornada(conn) or "1")
        team_logos = load_team_logos()
        partidos = build_jornada_matches(conn, jornada, team_logos)
        _, standings_db = _get_standings_cached(conn, partidos, team_logos)
        live_matches = build_live_matches(partidos, team_logos, standings_db)
        resp = jsonify({"jornada": jornada, "live_matches": live_matches, "today_madrid": today_madrid()})
        resp.headers["Cache-Control"] = "public, max-age=10, must-revalidate"
        return resp
    except Exception:
        logger.exception("api/liga/live failed")
        return jsonify(
            {
                "status": "error",
                "message": "No se pudo procesar la solicitud",
                "request_id": getattr(g, "request_id", ""),
            }
        ), 500


@bp.route("/api/liga/matches")
def get_matches():
    conn = get_db()
    try:
        from ..services.jornada import resolve_active_jornada

        jornada = str(resolve_active_jornada(conn) or "1")
        team_logos = load_team_logos()
        partidos = build_jornada_matches(conn, jornada, team_logos)
        _, standings_db = _get_standings_cached(conn, partidos, team_logos)
        all_league_matches = build_all_league_matches(jornada, partidos, standings_db, team_logos)
        resp = jsonify(
            {
                "jornada": jornada,
                "partidos": partidos,
                "all_league_matches": all_league_matches,
                "today_madrid": today_madrid(),
            }
        )
        resp.headers["Cache-Control"] = "public, max-age=30, must-revalidate"
        return resp
    except Exception:
        logger.exception("api/liga/matches failed")
        return jsonify(
            {
                "status": "error",
                "message": "No se pudo procesar la solicitud",
                "request_id": getattr(g, "request_id", ""),
            }
        ), 500
