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
    static_root = os.path.realpath(os.path.join(config.BASE_DIR, "static"))
    normalized = filename.replace("\\", "/").lstrip("/")
    file_path = os.path.realpath(os.path.join(static_root, normalized))

    try:
        stays_inside_static = os.path.commonpath((static_root, file_path)) == static_root
    except ValueError:
        stays_inside_static = False
    if not stays_inside_static or not os.path.isfile(file_path):
        abort(404)

    cache_control = (
        "public, max-age=31536000, immutable"
        if normalized.startswith("img/")
        else "no-store, no-cache, must-revalidate, max-age=0"
    )
    response = send_from_directory(static_root, normalized, conditional=True)
    response.headers["Cache-Control"] = cache_control
    return response

@bp.route('/juegos/<path:filename>')
def juegos_files(filename):
    return send_from_directory(os.path.join(config.BASE_DIR, "juegos"), filename, max_age=0)
