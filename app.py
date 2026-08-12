"""Liga de Maestros - Entry point."""

from liga_maestros import create_app

app = create_app()

if __name__ == "__main__":
    import os

    debug = os.getenv("FLASK_DEBUG", "0").strip().lower() in ("1", "true", "yes", "on")
    host = os.getenv("HOST", "0.0.0.0")  # noqa: S104 — bind explícito para deploys/proxy
    port = int(os.getenv("PORT", "5000"))
    app.run(debug=debug, host=host, port=port, use_reloader=debug)
