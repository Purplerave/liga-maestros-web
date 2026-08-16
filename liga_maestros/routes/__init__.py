"""Register all route blueprints."""

from .ai_predictions import bp as ai_predictions_bp
from .api_v1 import register_api_v1_aliases
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


def register_routes(app):
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(liga_data_bp)
    app.register_blueprint(predictions_bp)
    app.register_blueprint(contest_bp)
    app.register_blueprint(porra_bp)
    app.register_blueprint(snake_bp)
    app.register_blueprint(live_bp)
    app.register_blueprint(news_bp)
    app.register_blueprint(teams_bp)
    app.register_blueprint(user_bp)
    app.register_blueprint(quiz_bp)
    app.register_blueprint(legal_bp)
    app.register_blueprint(arcade_bp)
    app.register_blueprint(comments_bp)
    app.register_blueprint(ai_predictions_bp)
    register_api_v1_aliases(app)
