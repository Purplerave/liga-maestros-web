"""Main routes: index page, static files."""
import os, time
from flask import Blueprint, render_template, request, jsonify, send_from_directory, session

import config
from ..services.ticket import madrid_now, today_madrid

bp = Blueprint("main", __name__)

_assets_version = None


def _get_assets_version():
    global _assets_version
    if _assets_version:
        return _assets_version
    paths = [
        os.path.join(config.BASE_DIR, "static", "css", "quantum_pro.css"),
        os.path.join(config.BASE_DIR, "static", "css", "newspaper_theme.css"),
        os.path.join(config.BASE_DIR, "static", "css", "newspaper_cover.css"),
        os.path.join(config.BASE_DIR, "static", "js", "quantum_final.js"),
        os.path.join(config.BASE_DIR, "static", "img", "ligademaestroslogo_trans.png"),
    ]
    mtimes = []
    for path in paths:
        try:
            mtimes.append(int(os.path.getmtime(path)))
        except OSError:
            continue
    _assets_version = str(max(mtimes or [int(time.time())]))
    return _assets_version


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
        return render_template('liga_index.html', jornada=j, user=user, assets_v=_get_assets_version())
    except Exception:
        return f"La plantilla no se encontro. Jornada actual: {j}", 200


@bp.route('/static/<path:filename>')
def static_files(filename):
    normalized = filename.replace("\\", "/")
    if normalized.startswith("img/"):
        max_age = 31536000
        cache_control = "public, max-age=31536000, immutable"
    elif normalized.startswith(("css/", "js/")):
        max_age = 0
        cache_control = "no-cache, max-age=0"
    else:
        max_age = 0
        cache_control = "no-cache, max-age=0"
    response = send_from_directory(os.path.join(config.BASE_DIR, "static"), filename, max_age=max_age)
    response.headers["Cache-Control"] = cache_control
    return response
