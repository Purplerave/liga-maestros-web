"""Main routes: index page, static files."""

import os
import time
from functools import lru_cache

from flask import Blueprint, abort, make_response, render_template, request, send_from_directory, session

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
    max_j_row = conn.execute("SELECT MAX(jornada) FROM resultados").fetchone()
    max_j = max_j_row[0] if max_j_row else "62"
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

    # Las URLs versionadas (?v=<cambian con el contenido>) pueden cachearse de
    # forma inmutable: si el archivo cambia, la plantilla emite una URL nueva.
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
    """Probe ligero para monitores de uptime (sin datos sensibles)."""
    return {"status": "ok", "service": "liga-maestros-web"}


@bp.route("/robots.txt")
def robots_txt():
    body = (
        "User-agent: *\n"
        "Allow: /$\n"
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
