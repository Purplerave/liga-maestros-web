"""Main routes: index page, static files."""

import os
import time
from functools import lru_cache

from flask import Blueprint, abort, jsonify, make_response, render_template, request, send_from_directory, session

import config

bp = Blueprint("main", __name__)


@lru_cache(maxsize=1)
def _get_assets_version():
    static_dir = os.path.join(config.BASE_DIR, "static")
    mtimes = []
    try:
        for root, _, files in os.walk(static_dir):
            for file in files:
                if file.endswith((".css", ".js", ".png", ".jpg", ".svg")):
                    try:
                        mtimes.append(int(os.path.getmtime(os.path.join(root, file))))
                    except OSError:
                        continue
    except OSError:
        pass
    return str(max(mtimes) if mtimes else int(time.time()))


@bp.route("/")
def index():
    from ..db.connection import get_db

    user = session.get("user")
    conn = get_db()
    from ..services.jornada import resolve_active_jornada

    max_j = resolve_active_jornada(conn)
    j = request.args.get("j", str(max_j))
    try:
        response = make_response(
            render_template("liga_index.html", jornada=j, user=user, assets_v=_get_assets_version())
        )
        response.headers["Cache-Control"] = "no-store, max-age=0"
        return response
    except Exception:
        from markupsafe import escape

        return f"La plantilla no se encontro. Jornada actual: {escape(j)}", 500


@bp.route("/landing")
def landing():
    """Landing SEO de conversión (kit viral). Indexable, CTAs hacia /app."""
    response = make_response(render_template("landing.html"))
    response.headers["Cache-Control"] = "public, max-age=300"
    return response


@bp.route("/app")
def app_index():
    """Alias explícito de la app (para CTAs de la landing)."""
    return index()


@bp.route("/static/<path:filename>")
def static_files(filename):
    static_root = os.path.realpath(os.path.join(config.BASE_DIR, "static"))
    normalized = filename.replace("\\", "/").lstrip("/")
    file_path = os.path.realpath(os.path.join(static_root, normalized))

    try:
        stays_inside_static = os.path.commonpath((static_root, file_path)) == static_root
    except ValueError:
        stays_inside_static = False
    if not stays_inside_static or not os.path.isfile(file_path):
        abort(404)

    has_fingerprint = bool(request.args.get("v"))
    if normalized.startswith("img/") or has_fingerprint:
        cache_control = "public, max-age=31536000, immutable"
    else:
        cache_control = "no-store, no-cache, must-revalidate, max-age=0"
    response = send_from_directory(static_root, normalized, conditional=True)
    response.headers["Cache-Control"] = cache_control
    return response


@bp.route("/juegos/<path:filename>")
def juegos_files(filename):
    return send_from_directory(os.path.join(config.BASE_DIR, "juegos"), filename, max_age=0)


@bp.route("/api/season-summary")
def season_summary():
    import json as _json

    summary_path = os.path.join(config.DATA_DIR, "season_2025_2026_summary.json")
    if not os.path.isfile(summary_path):
        return jsonify({"status": "not_found"}), 404
    try:
        with open(summary_path, encoding="utf-8") as f:
            data = _json.load(f)
        return jsonify(data)
    except Exception:
        return jsonify({"status": "error"}), 500


@bp.route("/ayuda")
def help_page():
    return render_template("legal/help.html", user=session.get("user"))


@bp.route("/health")
def health():
    """Probe ligero + enriquecido para Alwaysdata/Render (sin secretos)."""
    import sqlite3
    from ..db.connection import get_db
    build_sha = "local"
    try:
        with open(os.path.join(config.BASE_DIR, ".release-sha"), encoding="utf-8") as f:
            build_sha = f.read().strip() or "local"
    except OSError:
        pass
    # DB check
    db_ok = False
    db_integrity = "unknown"
    db_size_mb = 0.0
    try:
        conn = get_db()
        try:
            row = conn.execute("PRAGMA integrity_check").fetchone()
            db_integrity = row[0] if row else "unknown"
            db_ok = db_integrity == "ok"
            conn.execute("SELECT 1")
            if os.path.exists(config.DB_PATH):
                db_size_mb = round(os.path.getsize(config.DB_PATH)/(1024*1024), 2)
        finally:
            conn.close()
    except Exception:
        db_ok = False
    # backup
    backup_ok = False
    backup_age_h = None
    try:
        candidates = [os.path.join(config.DATA_DIR, n) for n in os.listdir(config.DATA_DIR) if "backup" in n.lower()]
        if candidates:
            latest = max(candidates, key=lambda p: os.path.getmtime(p) if os.path.exists(p) else 0)
            if os.path.exists(latest):
                backup_ok = True
                backup_age_h = round((time.time() - os.path.getmtime(latest))/3600, 1)
    except Exception:
        pass
    # collector health
    collector_status = "unknown"
    collector_age_s = None
    try:
        hp = os.path.join(config.DATA_DIR, "LIVE_COLLECTOR_HEALTH.json")
        if os.path.exists(hp):
            collector_age_s = int(time.time() - os.path.getmtime(hp))
            import json as _j
            with open(hp, encoding="utf-8") as fh:
                collector_status = _j.load(fh).get("status", "unknown")
        else:
            collector_status = "missing"
    except Exception:
        collector_status = "error"
    # quota sin secretos
    quota = {}
    try:
        from ..services.highlightly import get_highlightly_usage
        u = get_highlightly_usage()
        quota = {"remaining_pct": u.get("remaining_pct"), "used": u.get("used"), "limit": u.get("limit")}
    except Exception:
        quota = {"remaining_pct": None}
    payload = {
        "status": "ok" if db_ok else "degraded",
        "service": "liga-maestros-web",
        "build_sha": build_sha,
        "db": {"ok": db_ok, "integrity": db_integrity, "size_mb": db_size_mb},
        "backup": {"ok": backup_ok, "age_hours": backup_age_h},
        "collector": {"status": collector_status, "age_seconds": collector_age_s},
        "quota": quota,
        "version": build_sha,
    }
    return payload


@bp.route("/robots.txt")
def robots_txt():
    body = (
        "User-agent: *\n"
        "Allow: /$\n"
        "Allow: /landing\n"
        "Allow: /app\n"
        "Allow: /static/\n"
        "Disallow: /api/\n"
        "Disallow: /cuenta\n"
        "Disallow: /login\n"
        "Disallow: /auth/\n\n"
        f"Sitemap: {request.url_root.rstrip('/')}/sitemap.xml\n"
    )
    response = make_response(body)
    response.headers["Content-Type"] = "text/plain; charset=utf-8"
    response.headers["Cache-Control"] = "public, max-age=86400"
    return response


@bp.route("/sitemap.xml")
def sitemap_xml():
    root = request.url_root.rstrip("/")
    urls = "".join(
        f"  <url><loc>{root}{path}</loc><changefreq>{freq}</changefreq></url>\n"
        for path, freq in (
            ("/", "daily"),
            ("/landing", "weekly"),
            ("/app", "daily"),
            ("/privacidad", "yearly"),
            ("/cookies", "yearly"),
            ("/aviso-legal", "yearly"),
            ("/ayuda", "monthly"),
        )
    )
    response = make_response(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{urls}</urlset>\n"
    )
    response.headers["Content-Type"] = "application/xml; charset=utf-8"
    response.headers["Cache-Control"] = "public, max-age=86400"
    return response
