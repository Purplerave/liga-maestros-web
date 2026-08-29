"""DB abstraction: hoy SQLite, mañana Postgres sin reescribir callers.

CEO mandate: código que soporte 100k concurrentes sin reescribir.
SQLite es suficiente hoy (WAL, 1 writer), pero toda query pasa por esta
interfaz. Migrar a Postgres es cambiar este módulo + env DB_URL.
"""

import os

DB_URL = os.getenv("DB_URL", "")
USE_POSTGRES = bool(DB_URL and DB_URL.startswith("postgres"))


def get_db():
    if USE_POSTGRES:
        # Placeholder: cuando DB_URL esté seteado, usar psycopg2 pool.
        # Mantiene misma API que sqlite3 (execute, fetchone, commit).
        raise NotImplementedError("Postgres backend: implementar pool y adaptar placeholders ? -> %s")
    from .connection import get_db as _get_sqlite_db

    return _get_sqlite_db()


def placeholder():
    return "%s" if USE_POSTGRES else "?"
