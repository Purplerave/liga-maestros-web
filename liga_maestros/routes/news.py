"""News routes: radar."""
from flask import Blueprint, request, jsonify, session
from ..services.news_radar import build_news_radar

bp = Blueprint("news", __name__)


def _is_admin_request():
    import os
    from flask import request as req
    user = session.get("user") or {}
    email = str(user.get("email") or "").strip().lower()
    allow_local = os.getenv("ALLOW_LOCAL_ADMIN", "0").strip().lower() in ("1", "true", "yes", "on")
    is_local = req.remote_addr in ("127.0.0.1", "::1", "localhost")
    admin_emails = {e.strip().lower() for e in os.getenv("ADMIN_EMAILS", "").split(",") if e.strip()}
    return (allow_local and is_local) or (email and email in admin_emails)


@bp.route('/api/noticias/radar')
def get_news_radar():
    force = request.args.get("force", "").strip().lower() in ("1", "true", "yes")
    if force and not _is_admin_request():
        return jsonify({"status": "forbidden", "message": "force limitado a admin"}), 403
    return jsonify(build_news_radar(force=force))
