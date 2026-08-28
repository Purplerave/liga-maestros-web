"""Liga de Maestros - Flask application factory."""

import logging
import os
import secrets
import time
from datetime import timedelta

from dotenv import load_dotenv
from flask import Flask, g, jsonify, render_template, request, session
from werkzeug.middleware.proxy_fix import ProxyFix

import config

logger = logging.getLogger(__name__)

from .db.backups import minimize_backup_personal_data, start_backup_scheduler
from .db.migrations import run_startup_migrations
from .middleware.authz import is_admin_or_service_request
from .middleware.csrf import valid_csrf_request
from .middleware.security import init_rate_limiter
from .routes import register_routes
from .workers.web_collector import start_web_collector

load_dotenv()
config.ensure_runtime_data_dir()

# Sentry error tracking (optional, only if SENTRY_DSN is set)
_sentry_dsn = os.getenv("SENTRY_DSN", "").strip()
if _sentry_dsn:
    import sentry_sdk
    from sentry_sdk.integrations.flask import FlaskIntegration

    sentry_sdk.init(
        dsn=_sentry_dsn,
        integrations=[FlaskIntegration()],
        traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
        environment=os.getenv("FLASK_ENV", "production"),
        release=os.getenv("BUILD_SHA", "dev"),
    )


def _configure_logging(app):
    """Set up consistent logging for production."""
    level = logging.DEBUG if os.getenv("FLASK_DEBUG", "0").strip().lower() in ("1", "true") else logging.INFO
    fmt = "%(asctime)s %(levelname)s [%(name)s] %(message)s"
    logging.basicConfig(level=level, format=fmt, force=True)
    # Suppress noisy libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    app.logger.setLevel(level)


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

    _is_dev = os.getenv("FLASK_DEBUG", "0").strip().lower() in ("1", "true", "yes", "on") or os.getenv(
        "FLASK_ENV", ""
    ).strip().lower() in ("development", "dev")

    # En desarrollo: permitir cualquier host (necesario para proxies de preview)
    # En produccion: restringir a hosts conocidos
    if _is_dev:
        preferred_scheme = os.getenv("PREFERRED_URL_SCHEME", "http")
        app.config["TRUSTED_HOSTS"] = None  # None = aceptar cualquier host
    else:
        preferred_scheme = os.getenv("PREFERRED_URL_SCHEME", "https")
        trusted_hosts = [
            item.strip()
            for item in os.getenv(
                "TRUSTED_HOSTS",
                "ligademaestros.alwaysdata.net,localhost,127.0.0.1",
            ).split(",")
            if item.strip()
        ]
        app.config["TRUSTED_HOSTS"] = trusted_hosts if trusted_hosts else None

    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE=os.getenv("SESSION_COOKIE_SAMESITE", "Lax"),
        SESSION_COOKIE_SECURE=os.getenv("SESSION_COOKIE_SECURE", "0").strip().lower() in ("1", "true", "yes", "on"),
        PERMANENT_SESSION_LIFETIME=timedelta(hours=int(os.getenv("SESSION_LIFETIME_HOURS", "12"))),
        PREFERRED_URL_SCHEME=preferred_scheme,
        MAX_CONTENT_LENGTH=int(os.getenv("MAX_CONTENT_LENGTH", str(64 * 1024))),
        MAX_FORM_MEMORY_SIZE=int(os.getenv("MAX_FORM_MEMORY_SIZE", str(32 * 1024))),
        MAX_FORM_PARTS=int(os.getenv("MAX_FORM_PARTS", "50")),
    )

    _configure_logging(app)
    register_routes(app)
    slow_request_ms = max(1.0, float(os.getenv("SLOW_REQUEST_MS", "750")))

    @app.before_request
    def begin_request_observability():
        g.request_started_at = time.perf_counter()
        g.request_id = secrets.token_hex(8)

    @app.before_request
    def protect_admin_api():
        if not request.path.startswith("/api/admin/"):
            return None
        if is_admin_or_service_request():
            return None
        return jsonify({"status": "forbidden", "message": "Solo admin"}), 403

    @app.before_request
    def protect_authenticated_writes():
        if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
            return None
        if not session.get("user"):
            return None
        if valid_csrf_request():
            return None
        return jsonify({"status": "error", "error": "Solicitud de seguridad caducada."}), 403

    @app.before_request
    def enforce_json_content_type():
        """Rechazar mutaciones API con Content-Type incorrecto cuando hay body."""
        if request.method not in {"POST", "PUT", "PATCH"}:
            return None
        if not request.path.startswith("/api/"):
            return None
        if request.content_length is not None and request.content_length > 0:
            ct = request.content_type or ""
            if "application/json" not in ct:
                return jsonify({"status": "error", "error": "Content-Type debe ser application/json."}), 415
        return None

    @app.before_request
    def reject_request_smuggling():
        """Bloquear combinaciones sospechosas de Transfer-Encoding / Content-Length."""
        te = (request.headers.get("Transfer-Encoding") or "").lower()
        cl = request.headers.get("Content-Length")
        if te and cl:
            return jsonify({"status": "error", "error": "Solicitud rechazada."}), 400
        if "chunked" in te:
            return jsonify({"status": "error", "error": "Solicitud rechazada."}), 400

    @app.after_request
    def set_security_headers(response):
        _is_dev = os.getenv("FLASK_DEBUG", "0").strip().lower() in ("1", "true", "yes", "on")
        _allow_frame_embed = _is_dev or os.getenv("ALLOW_IFRAME_EMBED", "0").strip().lower() in (
            "1",
            "true",
            "yes",
            "on",
        )

        if request.path.startswith("/juegos/"):
            response.headers["X-Frame-Options"] = "SAMEORIGIN"
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; script-src 'self'; "
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                "font-src 'self' https://fonts.gstatic.com; "
                "img-src 'self' data: https://highlightly.net; connect-src 'self'; "
                "object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'self'"
            )
        elif _allow_frame_embed:
            # En desarrollo / previews: permitir embedding para que funcione el proxy de preview
            response.headers["X-Frame-Options"] = "ALLOWALL"
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; script-src 'self'; "
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                "font-src 'self' https://fonts.gstatic.com; img-src 'self' data: https:; "
                "connect-src 'self' https:; object-src 'none'; base-uri 'self'; "
                "form-action 'self'; frame-ancestors *"
            )
            response.headers["Cross-Origin-Opener-Policy"] = "unsafe-none"
            response.headers["Cross-Origin-Resource-Policy"] = "cross-origin"
        else:
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; script-src 'self'; "
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                "font-src 'self' https://fonts.gstatic.com; img-src 'self' data: https:; "
                "connect-src 'self'; object-src 'none'; base-uri 'self'; "
                "form-action 'self'; frame-ancestors 'none'"
            )
        if not _allow_frame_embed:
            response.headers["Cross-Origin-Opener-Policy"] = "same-origin-allow-popups"
            response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-XSS-Protection"] = "0"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
        if request.is_secure:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        if (
            request.path in {"/api/user/status", "/api/user/stats", "/cuenta"}
            or request.path.startswith("/api/admin/")
            or (session.get("user") and request.path.startswith("/api/"))
        ):
            response.headers["Cache-Control"] = "no-store, private"

        request_id = getattr(g, "request_id", "")
        started_at = getattr(g, "request_started_at", None)
        if request_id:
            response.headers["X-Request-ID"] = request_id
        if started_at is not None:
            duration_ms = (time.perf_counter() - started_at) * 1000
            response.headers["Server-Timing"] = f"app;dur={duration_ms:.1f}"
            if duration_ms >= slow_request_ms:
                logger.warning(
                    "Slow request request_id=%s method=%s path=%s status=%s duration_ms=%.1f",
                    request_id,
                    request.method,
                    request.path,
                    response.status_code,
                    duration_ms,
                )
        return response

    @app.teardown_request
    def close_managed_db_connections(exc=None):
        for conn in getattr(g, "_managed_db_conns", []) or []:
            try:
                conn.close()
            except Exception:
                pass

    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(e):
        return render_template("errors/500.html"), 500

    run_startup_migrations()
    minimize_backup_personal_data()
    start_backup_scheduler(app)
    start_web_collector(app)
    init_rate_limiter(app)

    return app
