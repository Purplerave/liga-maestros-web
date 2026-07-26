"""News routes: radar + boletin breve generado por IA."""

from flask import Blueprint, jsonify, request

from ..middleware.authz import is_admin_request
from ..services.news_radar import build_news_radar


def _build_boletin_safe(items):
    """Intenta generar el boletin. Si falla, no interrumpe el radar."""
    try:
        from ..services.ai.boletin import construir_boletin

        return construir_boletin(items)
    except Exception:
        return {"novedades": [], "bajas": []}


bp = Blueprint("news", __name__)


@bp.route("/api/noticias/radar")
def get_news_radar():
    force = request.args.get("force", "").strip().lower() in ("1", "true", "yes")
    if force and not is_admin_request():
        return jsonify({"status": "forbidden", "message": "force limitado a admin"}), 403
    payload = build_news_radar(force=force)
    if not is_admin_request():
        payload = dict(payload)
        payload.pop("errors", None)
    payload.update(_build_boletin_safe(payload.get("items") or []))
    return jsonify(payload)
