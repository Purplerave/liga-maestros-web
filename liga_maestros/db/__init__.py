from .connection import ClosingConnection, ensure_db_file, get_db
from .migrations import run_startup_migrations
from . import migrations as _migrations
from .jornada_fallbacks import J75_FALLBACK_MATCHES, J76_FALLBACK_MATCHES

# Expose real fallbacks (CI tests) without rewriting the large migrations.py.
_migrations.J75_FALLBACK_MATCHES = J75_FALLBACK_MATCHES
_migrations.J76_FALLBACK_MATCHES = J76_FALLBACK_MATCHES


def _ensure_jornada_75(conn):
    _migrations.ensure_jornada_completa(
        conn, 75, fallback_matches=J75_FALLBACK_MATCHES, force=True
    )
    conn.commit()


def _ensure_jornada_76(conn):
    _migrations.ensure_jornada_completa(
        conn, 76, fallback_matches=J76_FALLBACK_MATCHES
    )
    conn.commit()


_migrations.ensure_jornada_75 = _ensure_jornada_75
_migrations.ensure_jornada_76 = _ensure_jornada_76

__all__ = ["get_db", "ensure_db_file", "ClosingConnection", "run_startup_migrations"]
