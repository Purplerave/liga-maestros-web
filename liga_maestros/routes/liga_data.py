"""Liga data route: the main data endpoint."""

import logging

from flask import Blueprint, jsonify, request, session

import config

from ..db.connection import get_db
from ..middleware.authz import is_admin_request
from ..services.multi_standings import build_multi_league_standings
from ..services.payloads.league_matches import build_all_league_matches, build_live_matches
from ..services.payloads.matches import build_jornada_matches
from ..services.payloads.predictions import build_predictions_payload
from ..services.payloads.standings import build_standings_payload
from ..services.teams import build_participant_contract
from ..services.ticket import compute_ticket_close_info, load_match_info_for_jornada, madrid_now, today_madrid
from ..utils import load_team_logos

bp = Blueprint("liga_data", __name__)
logger = logging.getLogger(__name__)


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
        standings, standings_db = build_standings_payload(conn, partidos)
        all_league_matches = build_all_league_matches(jornada, partidos, standings_db, team_logos)
        live_matches = build_live_matches(partidos, team_logos)
        multi_league_leagues = build_multi_league_standings(standings, team_logos)
        multi_league_standings = {"leagues": multi_league_leagues}
        jornada_liga = _detect_jornada_liga(conn)
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

        participant_contract = predictions_payload.get("participant_contract") or build_participant_contract()
        return jsonify(
            {
                "jornada": jornada,
                "jornada_liga": jornada_liga,
                "max_jornada": max_jornada,
                "jornadas_disponibles": jornadas_disponibles,
                "today_madrid": today_madrid(),
                "is_locked": is_locked,
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
                "auth_enabled": config.GOOGLE_AUTH_ENABLED,
                "live_stream_enabled": config.LIVE_SSE_ENABLED,
                "is_admin": is_admin_request(),
                "ticket_policy": {
                    "max_dobles": config.MAX_DOBLES_PER_TICKET,
                    "max_triples": config.MAX_TRIPLES_PER_TICKET,
                },
            }
        )
    except Exception as exc:
        logger.exception("api_liga_data failed")
        return jsonify({"status": "error", "message": str(exc)}), 500
    finally:
        conn.close()


def _resolve_max_jornada(conn):
    # La web y el guardado comparten exactamente esta jornada activa.
    from ..services.jornada import resolve_active_jornada

    return resolve_active_jornada(conn)


def _resolve_available_jornadas(conn):
    # Lista oficial para la nueva temporada: únicamente Jornada 1 cuando está disponible.
    # En producción tras la migración, solo [1] será visible. En tests con BDs temporales
    # mantenemos las jornadas reales insertadas para no romper las pruebas.
    try:
        has_j1 = conn.execute("SELECT 1 FROM resultados WHERE jornada = 1 LIMIT 1").fetchone()
        if has_j1:
            return [1]
    except Exception:
        pass
    rows = conn.execute("""
        SELECT jornada, COUNT(*) AS partidos
        FROM resultados
        GROUP BY jornada
        HAVING partidos > 0
        ORDER BY jornada DESC
    """).fetchall()
    jornadas = [int(row["jornada"]) for row in rows if row["jornada"] is not None]
    if not jornadas:
        import os as _os

        import config as _cfg

        for base in (_cfg.SEED_DATA_DIR, _cfg.DATA_DIR, _os.path.join(_cfg.BASE_DIR, "data")):
            if base and _os.path.exists(_os.path.join(base, "quiniela15_J1_scrape.json")):
                return [1]
        return [1]
    if 1 in jornadas:
        return [1]
    # Sin J1 en la BD: mostrar las jornadas existentes pero ocultar 75/76 que fueron pruebas de verano
    filtered = [j for j in jornadas if j not in (75, 76)]
    # Si tras filtrar queda vacío (solo había 75/76), mostrar 1
    return filtered if filtered else [1]


def _detect_jornada_liga(conn):
    try:
        row = conn.execute("SELECT AVG(pj) as avg_pj FROM clasificacion WHERE division = 1").fetchone()
        if row and row["avg_pj"] is not None:
            return str(int(round(row["avg_pj"])))
    except Exception:
        logger.exception("No se pudo detectar la jornada de liga")
        return ""
    return ""


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
