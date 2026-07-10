"""Liga de Maestros - Flask application factory."""
import os
from flask import Flask, g, has_request_context
from dotenv import load_dotenv
from werkzeug.middleware.proxy_fix import ProxyFix

import config
from .db.migrations import run_startup_migrations
from .db.connection import get_db
from .routes import register_routes

load_dotenv()
config.ensure_runtime_data_dir()


def create_app():
    app = Flask(
        __name__,
        static_folder=None,
        template_folder=os.path.join(config.BASE_DIR, "templates"),
    )

    TRUST_PROXY_HEADERS = os.getenv("TRUST_PROXY_HEADERS", "0").strip().lower() in ("1", "true", "yes", "on")
    if TRUST_PROXY_HEADERS:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)

    SECRET_KEY = os.getenv("SECRET_KEY", "").strip()
    if not SECRET_KEY:
        raise RuntimeError("SECRET_KEY no configurada.")
    app.secret_key = SECRET_KEY

    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE=os.getenv("SESSION_COOKIE_SAMESITE", "Lax"),
        SESSION_COOKIE_SECURE=os.getenv("SESSION_COOKIE_SECURE", "0").strip().lower() in ("1", "true", "yes", "on"),
        PREFERRED_URL_SCHEME=os.getenv("PREFERRED_URL_SCHEME", "https"),
    )

    register_routes(app)

    @app.teardown_request
    def close_managed_db_connections(exc=None):
        for conn in getattr(g, "_managed_db_conns", []) or []:
            try:
                conn.close()
            except Exception:
                pass

    run_startup_migrations()

    return app
