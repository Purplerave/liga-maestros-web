"""API versioning: expose all /api/* routes under /api/v1/* without duplicates."""

from flask import Blueprint

from .ai_predictions import bp as ai_predictions_bp
from .arcade import bp as arcade_bp
from .auth import bp as auth_bp
from .comments import bp as comments_bp
from .contest_routes import bp as contest_bp
from .legal import bp as legal_bp
from .liga_data import bp as liga_data_bp
from .live import bp as live_bp
from .main import bp as main_bp
from .news import bp as news_bp
from .porra import bp as porra_bp
from .predictions import bp as predictions_bp
from .quiz import bp as quiz_bp
from .snake import bp as snake_bp
from .teams_routes import bp as teams_bp
from .user import bp as user_bp

_BLUEPRINTS = {
    "main": main_bp,
    "live": live_bp,
    "liga_data": liga_data_bp,
    "predictions": predictions_bp,
    "contest": contest_bp,
    "porra": porra_bp,
    "snake": snake_bp,
    "news": news_bp,
    "teams": teams_bp,
    "user": user_bp,
    "quiz": quiz_bp,
    "legal": legal_bp,
    "arcade": arcade_bp,
    "comments": comments_bp,
    "ai_predictions": ai_predictions_bp,
    "auth": auth_bp,
}


def register_api_v1_aliases(app):
    """Register /api/v1 aliases for every existing /api/* route."""
    api_v1_bp = Blueprint("api_v1", __name__, url_prefix="/api/v1")
    for rule in app.url_map.iter_rules():
        if not rule.rule.startswith("/api/"):
            continue
        if rule.endpoint.startswith("api_v1."):
            continue
        bp_name, _, func_name = rule.endpoint.partition(".")
        original_bp = _BLUEPRINTS.get(bp_name)
        if original_bp is None:
            continue
        view_func = app.view_functions.get(rule.endpoint)
        if view_func is None:
            continue
        # Strip the /api prefix; the blueprint url_prefix supplies /api/v1.
        relative_rule = rule.rule[4:]
        if not relative_rule.startswith("/"):
            relative_rule = "/" + relative_rule
        api_v1_bp.add_url_rule(
            relative_rule,
            view_func=view_func,
            endpoint=func_name,
            methods=rule.methods,
            defaults=dict(rule.defaults or {}),
        )
    app.register_blueprint(api_v1_bp)
