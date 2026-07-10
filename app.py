"""Liga de Maestros - Entry point."""
from liga_maestros import create_app

app = create_app()

if __name__ == '__main__':
    import os
    debug = os.getenv("FLASK_DEBUG", "0").strip().lower() in ("1", "true", "yes", "on")
    app.run(debug=debug, port=5000, use_reloader=debug)
