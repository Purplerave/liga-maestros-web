"""Liga data route: the main data endpoint."""

import hashlib
import logging
import time
from functools import lru_cache

from flask import Blueprint, jsonify, request, session

import config

from ..db.connection import get_db
from ..middleware.authz import is_admin_request
from ..schemas import validate_liga_data
from ..services.multi_standings import build_multi_league_standings
from ..services.payloads.league_matches import build_all_league_matches, build_live_matches
from ..services.payloads.matches import build_jornada_matches
from ..services.payloads.predictions import build_predictions_payload
from ..services.payloads.standings import build_standings_payload, matchday_played, persist_standings
from ..services.teams import build_participant_contract
from ..services.ticket import compute_ticket_close_info, load_match_info_for_jornada, madrid_now, today_madrid
from ..services.trash_talk import build_trash_talk
from ..utils import load_team_logos

bp = Blueprint("liga_data", __name__)
logger = logging.getLogger(__name__)

# Simple in-memory cache for standings (TTL 5 min)
_STANDINGS_CACHE = {"data": None, "expires": 0, "key": None}
_STANDINGS_TTL = 300  # seconds


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
    return hashlib.md5(payload.encode()).hexdigest()


@bp.route("/api/liga/data")
def get_liga_data():
    requested_jornada = request.args.get("j", "")
    conn = get_db()
    try:
        max_jornada = _resolve_max_jornada(conn)
        if max_jornada is None:
            return jsonify({"status": "error", "message": "No hay jornadas cargadas en resultados"}), 404

        jornadas_disponibles = _resolve_available_jornadas(conn)
        jornada = requested_jornada or max_jornada
        # Nueva temporada: si piden 75/76 u otra jornada de pruebas, redirigir a J1
        if jornadas_disponibles and str(jornada) not in {str(j) for j in jornadas_disponibles}:
            jornada = str(jornadas_disponibles[0])
        team_logos = load_team_logos()
        partidos = build_jornada_matches(conn, jornada, team_logos)
        standings, standings_db = _get_standings_cached(conn, partidos, team_logos)
        all_league_matches = build_all_league_matches(jornada, partidos, standings_db, team_logos)
        live_matches = build_live_matches(partidos, team_logos, standings_db)
        multi_league_leagues = build_multi_league_standings(standings, team_logos)
        multi_league_standings = {"leagues": multi_league_leagues}
        jornada_liga = str(matchday_played(standings) or "")
        match_info = _load_and_repair_match_info(jornada, partidos)
        close_info = compute_ticket_close_info(partidos, source=f"api_liga_data_j{jornada}")
        is_locked = _is_ticket_locked(partidos, close_info)
        user = session.get("user") or {}
        predictions_payload = build_predictions_payload(
            conn,
            jornada,
            current_user_id=user.get("id"),
            reveal_all=is_locked,
        )
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

        participant_contract = predictions_payload.get("participant_contract") or build_participant_contract()
        trash_talk = _build_trash_talk_payload(
            jornada=jornada,
            ranking=predictions_payload.get("ranking_maestros", {}),
            participant_contract=participant_contract,
        )
        comentarista = _build_comentarista_payload(partidos)
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
        validated, schema_error = validate_liga_data(response_payload)
        if schema_error:
            logger.info("api_liga_data served with schema drift: %s", schema_error)

        # ETag support
        response_json = jsonify(validated).get_data(as_text=True)
        etag = _etag_for(response_json)
        if_none_match = request.headers.get("If-None-Match")
        if if_none_match and if_none_match == etag:
            resp = jsonify({"status": "not_modified"})
            resp.status_code = 304
            resp.headers["ETag"] = etag
            resp.headers["Cache-Control"] = "public, max-age=60, must-revalidate"
            return resp

        resp = jsonify(validated)
        resp.headers["ETag"] = etag
        resp.headers["Cache-Control"] = "public, max-age=60, must-revalidate"
        return resp
    except Exception as exc:
        logger.exception("api_liga_data failed")
        return jsonify({"status": "error", "message": str(exc)}), 500


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


def _is_ticket_locked(partidos, close_info):
    close_at = close_info.get("close_at")
    close_started = bool(close_at and madrid_now() >= close_at)
    match_started = any((match.get("status") or "") in ("LIVE", "FT", "FINISHED") for match in partidos)
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
    """Comentarios breves del directo (MiMo). Best-effort: nunca rompe la portada."""
    try:
        from ..services.ai.comentarista import construir_comentarios

        return construir_comentarios(matches)
    except Exception:
        return {"comentarios": [], "generated": False}


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

    summary = refresh_all_standings(season=2026)
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
        standings = refresh_all_standings(season=2026)
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
    except Exception as exc:
        logger.exception("api/liga/standings failed")
        return jsonify({"status": "error", "message": str(exc)}), 500


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
    except Exception as exc:
        logger.exception("api/liga/live failed")
        return jsonify({"status": "error", "message": str(exc)}), 500


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
            {"jornada": jornada, "partidos": partidos, "all_league_matches": all_league_matches, "today_madrid": today_madrid()}
        )
        resp.headers["Cache-Control"] = "public, max-age=30, must-revalidate"
        return resp
    except Exception as exc:
        logger.exception("api/liga/matches failed")
        return jsonify({"status": "error", "message": str(exc)}), 500
