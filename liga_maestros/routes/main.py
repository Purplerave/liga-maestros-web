"""Main routes: index page, static files."""
import os, time
from flask import Blueprint, make_response, render_template, request, jsonify, send_from_directory, session

import config
from ..services.ticket import madrid_now, today_madrid

bp = Blueprint("main", __name__)


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
    normalized = filename.replace("\\", "/")
    if normalized.startswith("img/"):
        max_age = 31536000
        cache_control = "public, max-age=31536000, immutable"
    elif normalized.startswith(("css/", "js/")):
        max_age = 0
        cache_control = "no-store, no-cache, must-revalidate, max-age=0"
    else:
        max_age = 0
        cache_control = "no-store, no-cache, must-revalidate, max-age=0"
    
    file_path = os.path.join(config.BASE_DIR, "static", filename)
    if not os.path.exists(file_path):
        from flask import abort
        abort(404)
    
    with open(file_path, "rb") as f:
        content = f.read()
    
    from flask import Response
    response = Response(content)
    response.headers["Cache-Control"] = cache_control
    response.headers["Content-Type"] = "application/javascript" if filename.endswith(".js") else "text/css" if filename.endswith(".css") else "application/octet-stream"
    return response


@bp.route('/juegos/<path:filename>')
def juegos_files(filename):
    return send_from_directory(os.path.join(config.BASE_DIR, "juegos"), filename, max_age=0)
