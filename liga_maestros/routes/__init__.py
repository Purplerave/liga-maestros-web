"""Register all route blueprints."""
from .auth import bp as auth_bp
from .main import bp as main_bp
from .liga_data import bp as liga_data_bp
from .predictions import bp as predictions_bp
from .contest_routes import bp as contest_bp
from .porra import bp as porra_bp
from .snake import bp as snake_bp
from .live import bp as live_bp
from .news import bp as news_bp
from .teams_routes import bp as teams_bp
from .user import bp as user_bp
from .quiz import bp as quiz_bp
from .legal import bp as legal_bp
from .arcade import bp as arcade_bp


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
