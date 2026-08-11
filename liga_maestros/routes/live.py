"""Live routes: ticker, Q15 directo, sync status, health, refresh, probe, SSE."""

import json
import os
import time
from datetime import datetime

from flask import Blueprint, Response, jsonify, request

import config

from ..db.connection import get_db
from ..middleware.authz import is_admin_request
from ..middleware.json_lock import write_json_locked
from ..services.highlightly import (
    HIGHLIGHTLY_REFRESH_ENABLED,
    Q15_EXPECTED_MATCHES,
    compute_refresh_window,
    get_highlightly_circuit,
    get_highlightly_usage,
    madrid_now,
    resolve_jornada,
    trigger_highlightly_refresh_async,
)
from ..services.ticket import validate_q15_payload
from ..utils import safe_read_json

bp = Blueprint("live", __name__)


def _build_q15_cache_status(jornada):
    status = {
        "available": False,
        "ok": False,
        "last_sync": "--:--",
        "matches": 0,
        "matches_expected": Q15_EXPECTED_MATCHES,
        "matches_received": 0,
        "message": "sin_jornada",
    }
    if not jornada:
        return status
    q15_path = os.path.join(config.DATA_DIR, f"quiniela15_directo_J{jornada}.json")
    if not os.path.exists(q15_path):
        status["message"] = "sin_cache"
        return status
    try:
        payload = safe_read_json(q15_path, {})
        received = len(payload.get("matches") or [])
        status.update(
            {
                "available": True,
                "ok": received == Q15_EXPECTED_MATCHES,
                "last_sync": datetime.fromtimestamp(os.path.getmtime(q15_path)).strftime("%H:%M"),
                "matches": received,
                "matches_received": received,
                "message": "ok" if received == Q15_EXPECTED_MATCHES else "matches_incompletos",
            }
        )
    except Exception:
        status["message"] = "error_cache"
    return status


@bp.route("/api/live/ticker")
def get_live_ticker():
    ticker_path = os.path.join(config.DATA_DIR, "LIVE_TICKER.json")
    if not os.path.exists(ticker_path):
        ticker_path = os.path.join(config.BASE_DIR, "LIVE_TICKER.json")
    if os.path.exists(ticker_path):
        try:
            with open(ticker_path, encoding="utf-8") as f:
                return jsonify(json.load(f))
        except Exception:
            pass
    return jsonify({"matches": []})


@bp.route("/api/q15/directo")
def q15_directo():
    jornada = (request.args.get("j") or request.args.get("jornada") or "").strip()
    if not jornada.isdigit():
        return jsonify({"matches": []})
    path = os.path.join(config.DATA_DIR, f"quiniela15_directo_J{jornada}.json")
    if not os.path.exists(path):
        return jsonify({"jornada": int(jornada), "matches": [], "cached": False})
    try:
        with open(path, encoding="utf-8") as fh:
            payload = json.load(fh)
        payload["cached"] = True
        return jsonify(payload)
    except Exception:
        return jsonify({"jornada": int(jornada), "matches": [], "cached": False})


@bp.route("/api/sync/status")
def sync_status():
    conn = get_db()
    try:
        target_jornada = resolve_jornada(conn, request.args.get("j"))
        refresh_window = compute_refresh_window(conn, target_jornada)
        today = madrid_now().strftime("%Y-%m-%d")
        live = (
            conn.execute(
                "SELECT COUNT(*) FROM resultados WHERE jornada = ? AND fecha = ? AND status IN ('LIVE', 'IN PLAY', 'HT', 'EN JUEGO')",
                (target_jornada, today),
            ).fetchone()[0]
            if target_jornada
            else 0
        )
        pending = (
            conn.execute(
                "SELECT COUNT(*) FROM resultados WHERE jornada = ? AND status IN ('NS', 'SCHEDULED', 'NOT STARTED')",
                (target_jornada,),
            ).fetchone()[0]
            if target_jornada
            else 0
        )
        panel_path = os.path.join(config.DATA_DIR, "LIVE_ALL_MATCHES_V3.json")
        last_sync = "--:--"
        last_sync_source = "none"
        try:
            if os.path.exists(panel_path):
                last_sync = datetime.fromtimestamp(os.path.getmtime(panel_path)).strftime("%H:%M")
                last_sync_source = "highlightly"
        except Exception:
            pass
        api_usage = get_highlightly_usage()
        q15_cache = _build_q15_cache_status(target_jornada)
        if q15_cache.get("available") and q15_cache.get("last_sync") not in ("", "--:--"):
            last_sync = q15_cache["last_sync"]
            last_sync_source = "quiniela15"
    finally:
        conn.close()
    payload = {
        "jornada": target_jornada,
        "live_matches": live,
        "pending_matches": pending,
        "last_sync": last_sync,
        "last_sync_source": last_sync_source,
        "auto_refresh": False,
        "refresh_available": bool(HIGHLIGHTLY_REFRESH_ENABLED and refresh_window.get("enabled")),
        "refresh_reason": refresh_window.get("reason", "cache-only"),
        "q15_cache": q15_cache,
    }
    if is_admin_request():
        payload["api_usage"] = api_usage
    return jsonify(payload)


@bp.route("/api/live/health")
def live_health():
    import sys

    start = time.time()
    conn = get_db()
    try:
        target_jornada = resolve_jornada(conn, request.args.get("j"))
    finally:
        conn.close()
    health_path = os.path.join(config.DATA_DIR, "LIVE_COLLECTOR_HEALTH.json")
    exists = os.path.exists(health_path)
    health = safe_read_json(health_path, {}) if exists else {}
    age_seconds = None
    if exists:
        try:
            age_seconds = int(time.time() - os.path.getmtime(health_path))
        except Exception:
            age_seconds = None
    release_path = os.path.join(config.BASE_DIR, ".release-sha")
    build_sha = "local"
    try:
        with open(release_path, encoding="utf-8") as release_file:
            build_sha = release_file.read().strip() or "unknown"
    except OSError:
        pass
    db_ok = False
    db_size_mb = 0.0
    try:
        conn2 = get_db()
        try:
            conn2.execute("SELECT 1")
            db_ok = True
            db_path = config.DB_PATH
            if os.path.exists(db_path):
                db_size_mb = round(os.path.getsize(db_path) / (1024 * 1024), 2)
        finally:
            conn2.close()
    except Exception:
        pass
    uptime_s = int(time.time() - start) if start else None
    try:
        from importlib.metadata import version as get_version

        flask_ver = get_version("flask")
    except Exception:
        flask_ver = "unknown"
    payload = {
        "status": "ok",
        "build_sha": build_sha,
        "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "flask": flask_ver,
        "db": {"ok": db_ok, "size_mb": db_size_mb},
        "jornada_activa": target_jornada,
    }
    if is_admin_request():
        payload.update(
            {
                "collector": {
                    "running": (health or {}).get("status") == "ok",
                    "last_tick_s": age_seconds,
                },
                "collector_detail": health or {"status": "missing"},
                "health_file": exists,
                "age_seconds": age_seconds,
                "q15_cache": _build_q15_cache_status(target_jornada),
                "api_usage": get_highlightly_usage(),
                "highlightly_circuit": {k: v for k, v in get_highlightly_circuit().items() if k != "path"},
            }
        )
    return jsonify(payload)


@bp.route("/api/live/refresh", methods=["POST"])
def manual_live_refresh():
    if not is_admin_request():
        return jsonify({"status": "forbidden", "message": "Refresco externo limitado a entorno local/admin"}), 403
    if not HIGHLIGHTLY_REFRESH_ENABLED:
        return jsonify({"status": "disabled", "message": "Refresco externo desactivado"}), 409
    if not os.getenv("HIGHLIGHTLY_API_KEY", ""):
        return jsonify({"status": "disabled", "message": "Highlightly no tiene API key configurada"}), 409
    circuit = get_highlightly_circuit()
    if circuit.get("open"):
        return jsonify(
            {
                "status": "degraded",
                "started": False,
                "message": "Circuito Highlightly abierto",
                "next_retry_at": datetime.fromtimestamp(circuit["open_until"]).isoformat(),
            }
        ), 200
    payload = request.get_json(silent=True) or {}
    jornada = request.args.get("j") or payload.get("j")
    started = trigger_highlightly_refresh_async(force=True, jornada=jornada)
    return jsonify({"status": "ok" if started else "busy", "started": bool(started)})


@bp.route("/api/live/probe", methods=["POST"])
def live_probe():
    if not is_admin_request():
        return jsonify({"status": "forbidden", "message": "Sondeo manual limitado a entorno local/admin"}), 403
    payload_json = request.get_json(silent=True) or {}
    requested_jornada = request.args.get("j") or payload_json.get("j")
    with get_db() as conn:
        target_jornada = resolve_jornada(conn, requested_jornada)
        refresh_window = compute_refresh_window(conn, target_jornada)

    q15_status = {
        "ok": False,
        "matches": 0,
        "matches_expected": Q15_EXPECTED_MATCHES,
        "matches_received": 0,
        "message": "sin_jornada",
    }
    if target_jornada:
        try:
            from SCRAPE_QUINIELA15_DIRECTO import scrape as scrape_q15_directo

            payload = scrape_q15_directo(int(target_jornada))
            matches = validate_q15_payload(payload, target_jornada)
            q15_path = os.path.join(config.DATA_DIR, f"quiniela15_directo_J{target_jornada}.json")
            write_json_locked(q15_path, payload)
            received = len(matches)
            q15_status = {
                "ok": received == Q15_EXPECTED_MATCHES,
                "matches": received,
                "matches_expected": Q15_EXPECTED_MATCHES,
                "matches_received": received,
                "last_sync": datetime.fromtimestamp(os.path.getmtime(q15_path)).strftime("%H:%M"),
                "message": "ok" if received == Q15_EXPECTED_MATCHES else "matches_incompletos",
            }
        except Exception:
            q15_status = {
                "ok": False,
                "matches": 0,
                "matches_expected": Q15_EXPECTED_MATCHES,
                "matches_received": 0,
                "message": "q15_probe_error",
            }

    highlightly_started = False
    highlightly_skipped = "fuera_de_ventana"
    if HIGHLIGHTLY_REFRESH_ENABLED and refresh_window.get("enabled"):
        circuit = get_highlightly_circuit()
        if circuit.get("open"):
            highlightly_skipped = "circuit_open"
        else:
            highlightly_started = trigger_highlightly_refresh_async(force=True, jornada=target_jornada)
            highlightly_skipped = ""

    return jsonify(
        {
            "status": "ok",
            "jornada": target_jornada,
            "q15": q15_status,
            "highlightly": {
                "started": bool(highlightly_started),
                "skipped": highlightly_skipped,
                "window_enabled": bool(refresh_window.get("enabled")),
                "reason": refresh_window.get("reason"),
                "next_retry_at": datetime.fromtimestamp(get_highlightly_circuit()["open_until"]).isoformat()
                if get_highlightly_circuit().get("open")
                else "",
            },
            "api_usage": get_highlightly_usage(),
        }
    )


@bp.route("/api/live/stream")
def live_stream():
    """SSE endpoint for live match updates."""
    jornada = request.args.get("j", "")

    def generate():
        last_signature = None
        while True:
            try:
                conn = get_db()
                rows = conn.execute(
                    """
                    SELECT jornada, partido_id, local, visitante, signo_actual,
                           goles_local, goles_visitante, status, minuto
                    FROM resultados
                    WHERE jornada = ?
                    ORDER BY partido_id
                    """,
                    (jornada,),
                ).fetchall()
                conn.close()

                matches = []
                for row in rows:
                    matches.append(
                        {
                            "partido_id": int(row["partido_id"]),
                            "local": row["local"] or "",
                            "visitante": row["visitante"] or "",
                            "signo_actual": row["signo_actual"] or "-",
                            "goles_local": row["goles_local"],
                            "goles_visitante": row["goles_visitante"],
                            "status": row["status"] or "",
                            "minuto": row["minuto"],
                        }
                    )

                signature = json.dumps(matches, sort_keys=True)
                if signature == last_signature:
                    time.sleep(5)
                    continue

                last_signature = signature
                payload = json.dumps(
                    {"type": "live_update", "jornada": jornada, "matches": matches},
                    ensure_ascii=False,
                )
                yield f"data: {payload}\n\n"
                time.sleep(5)
            except Exception:
                yield f"data: {json.dumps({'type': 'error', 'message': 'connection lost'})}\n\n"
                time.sleep(10)

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@bp.route("/api/admin/reset-standings", methods=["POST"])
def reset_standings():
    """Reset all league standings and accumulated points to zero."""
    if not is_admin_request():
        secret = request.headers.get("X-Admin-Secret") or request.args.get("secret")
        admin_secret = os.getenv("ADMIN_SECRET", "liga-maestros-2026")
        if not secret or secret != admin_secret:
            return jsonify({"status": "forbidden", "message": "Solo admin"}), 403

    conn = get_db()
    try:
        # Reset accumulated points
        conn.execute("UPDATE usuarios SET puntos_acumulados = 0")
        users = conn.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0]

        # Reset clasificacion
        conn.execute("UPDATE clasificacion SET pj=0, pts=0, pg=0, pe=0, pp=0, gf=0, gc=0, racha=NULL")
        teams = conn.execute("SELECT COUNT(*) FROM clasificacion").fetchone()[0]

        # Clear predicciones, resultados, consenso
        conn.execute("DELETE FROM predicciones")
        conn.execute("DELETE FROM resultados")
        conn.execute("DELETE FROM consenso")

        conn.commit()
        return jsonify({
            "status": "ok",
            "message": "Ligas reseteadas a 0",
            "users_reset": users,
            "teams_reset": teams,
        })
    except Exception as e:
        conn.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500
