"""Liga de Maestros - Flask application factory."""
import os
from datetime import timedelta
from flask import Flask, g, jsonify, request, session
from dotenv import load_dotenv
from werkzeug.middleware.proxy_fix import ProxyFix

import config
from .db.migrations import run_startup_migrations
from .routes import register_routes
from .workers.web_collector import start_web_collector
from .db.backups import minimize_backup_personal_data, start_backup_scheduler
from .middleware.csrf import valid_csrf_request

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
        PERMANENT_SESSION_LIFETIME=timedelta(hours=int(os.getenv("SESSION_LIFETIME_HOURS", "12"))),
        PREFERRED_URL_SCHEME=os.getenv("PREFERRED_URL_SCHEME", "https"),
        MAX_CONTENT_LENGTH=int(os.getenv("MAX_CONTENT_LENGTH", str(64 * 1024))),
        MAX_FORM_MEMORY_SIZE=int(os.getenv("MAX_FORM_MEMORY_SIZE", str(32 * 1024))),
        MAX_FORM_PARTS=int(os.getenv("MAX_FORM_PARTS", "50")),
    )
    trusted_hosts = [item.strip() for item in os.getenv(
        "TRUSTED_HOSTS",
        "ligademaestros.alwaysdata.net,localhost,127.0.0.1",
    ).split(",") if item.strip()]
    app.config["TRUSTED_HOSTS"] = trusted_hosts

    register_routes(app)

    @app.before_request
    def protect_authenticated_writes():
        if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
            return None
        if not session.get("user"):
            return None
        if valid_csrf_request():
            return None
        return jsonify({"status": "error", "error": "Solicitud de seguridad caducada."}), 403

    @app.after_request
    def set_security_headers(response):
        if request.path.startswith("/juegos/"):
            response.headers["X-Frame-Options"] = "SAMEORIGIN"
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; script-src 'self' 'unsafe-inline'; "
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                "font-src 'self' https://fonts.gstatic.com; "
                "img-src 'self' data: https://highlightly.net; connect-src 'self'; "
                "object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'self'"
            )
        else:
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; script-src 'self'; "
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                "font-src 'self' https://fonts.gstatic.com; img-src 'self' data: https:; "
                "connect-src 'self'; object-src 'none'; base-uri 'self'; "
                "form-action 'self'; frame-ancestors 'none'"
            )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-XSS-Protection"] = "0"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin-allow-popups"
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        if request.is_secure:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        if request.path in {"/api/user/status", "/api/user/stats", "/cuenta"} or (
            session.get("user") and request.path.startswith("/api/")
        ):
            response.headers["Cache-Control"] = "no-store, private"
        return response

    @app.teardown_request
    def close_managed_db_connections(exc=None):
        for conn in getattr(g, "_managed_db_conns", []) or []:
            try:
                conn.close()
            except Exception:
                pass

    run_startup_migrations()
    minimize_backup_personal_data()
    start_backup_scheduler(app)
    start_web_collector(app)

    return app
