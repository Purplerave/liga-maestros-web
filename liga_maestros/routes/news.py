"""News routes: radar."""
from flask import Blueprint, request, jsonify
from ..middleware.authz import is_admin_request
from ..services.news_radar import build_news_radar

bp = Blueprint("news", __name__)


@bp.route('/api/noticias/radar')
def get_news_radar():
    force = request.args.get("force", "").strip().lower() in ("1", "true", "yes")
    if force and not is_admin_request():
        return jsonify({"status": "forbidden", "message": "force limitado a admin"}), 403
    payload = build_news_radar(force=force)
    if not is_admin_request():
        payload = dict(payload)
        payload.pop("errors", None)
    return jsonify(payload)
