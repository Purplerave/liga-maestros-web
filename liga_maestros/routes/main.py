"""Main routes: index page, static files."""
import hashlib
import os
import time
from pathlib import Path

from flask import Blueprint, make_response, render_template, request, jsonify, send_from_directory, session, abort

import config
from ..services.ticket import madrid_now, today_madrid

bp = Blueprint("main", __name__)

_STATIC_HASH_CACHE = None
_STATIC_HASH_DIRTY = False


def _get_static_fingerprint():
    global _STATIC_HASH_CACHE, _STATIC_HASH_DIRTY
    if _STATIC_HASH_CACHE and not _STATIC_HASH_DIRTY:
        return _STATIC_HASH_CACHE
    h = hashlib.sha256()
    static_dir = Path(config.BASE_DIR) / "static"
    for path in sorted(static_dir.rglob("*")):
        if path.is_file() and path.suffix in {".css", ".js"}:
            try:
                h.update(path.relative_to(static_dir).as_posix().encode())
                h.update(b"\0")
                h.update(str(path.stat().st_mtime_ns).encode())
                h.update(b"\0")
            except OSError:
                continue
    _STATIC_HASH_CACHE = h.hexdigest()[:10]
    _STATIC_HASH_DIRTY = False
    return _STATIC_HASH_CACHE


def _get_assets_version():
    return _get_static_fingerprint()


def invalidate_assets_version():
    global _STATIC_HASH_DIRTY
    _STATIC_HASH_DIRTY = True


@bp.route('/')
def index():
    from ..db.connection import get_db
    user = session.get('user')
    conn = get_db()
    try:
        max_j_row = conn.execute("SELECT MAX(jornada) FROM resultados").fetchone()
        max_j = max_j_row[0] if max_j_row else '62'
    finally:
        conn.close()
    j = request.args.get('j', str(max_j))
    try:
        response = make_response(render_template('liga_index.html', jornada=j, user=user, assets_v=_get_assets_version()))
        response.headers["Cache-Control"] = "no-store, max-age=0"
        return response
    except Exception:
        from markupsafe import escape
        return f"La plantilla no se encontro. Jornada actual: {escape(j)}", 500


@bp.route('/static/<path:filename>')
def static_files(filename):
    if "\0" in filename or filename.startswith(("/", "\\")):
        abort(404)
    is_long_term = filename.startswith("img/")
    static_dir = os.path.join(config.BASE_DIR, "static")
    if not os.path.isfile(os.path.join(static_dir, filename)):
        abort(404)
    response = send_from_directory(
        static_dir,
        filename,
        max_age=31536000 if is_long_term else 0,
        conditional=True,
        as_attachment=False,
    )
    if is_long_term:
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    else:
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    if filename.endswith((".js", ".mjs")):
        response.headers["Content-Type"] = "application/javascript; charset=utf-8"
    elif filename.endswith(".css"):
        response.headers["Content-Type"] = "text/css; charset=utf-8"
    elif filename.endswith(".svg"):
        response.headers["Content-Type"] = "image/svg+xml"
    return response


@bp.route('/juegos/<path:filename>')
def juegos_files(filename):
    return send_from_directory(os.path.join(config.BASE_DIR, "juegos"), filename, max_age=0)


@bp.route('/robots.txt')
def robots_txt():
    from flask import Response
    return Response(
        "User-agent: *\nAllow: /\nDisallow: /api/\nDisallow: /static/\nSitemap: https://ligademaestros.alwaysdata.net/sitemap.xml\n",
        mimetype="text/plain",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@bp.route('/sitemap.xml')
def sitemap_xml():
    from flask import Response
    from ..db.connection import get_db
    base = "https://ligademaestros.alwaysdata.net"
    pages = [
        f"  <url><loc>{base}/</loc><changefreq>daily</changefreq><priority>1.0</priority></url>",
        f"  <url><loc>{base}/privacidad</loc><changefreq>monthly</changefreq><priority>0.3</priority></url>",
        f"  <url><loc>{base}/aviso-legal</loc><changefreq>monthly</changefreq><priority>0.3</priority></url>",
        f"  <url><loc>{base}/cookies</loc><changefreq>monthly</changefreq><priority>0.3</priority></url>",
    ]
    conn = get_db()
    try:
        row = conn.execute("SELECT MAX(jornada) FROM resultados").fetchone()
        max_j = row[0] if row and row[0] else None
        if max_j:
            for j in range(max(1, max_j - 5), max_j + 1):
                pages.append(f"  <url><loc>{base}/?j={j}</loc><changefreq>weekly</changefreq><priority>0.8</priority></url>")
    finally:
        conn.close()
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "\n".join(pages) + "\n</urlset>"
    return Response(xml, mimetype="application/xml", headers={"Cache-Control": "public, max-age=3600"})
