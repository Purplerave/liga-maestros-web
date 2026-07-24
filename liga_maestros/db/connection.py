import os
import sqlite3
import config

_sqlite_pragma_lock = None
_sqlite_wal_ready = False


def _get_pragma_lock():
    global _sqlite_pragma_lock
    if _sqlite_pragma_lock is None:
        import threading
        _sqlite_pragma_lock = threading.Lock()
    return _sqlite_pragma_lock


class ClosingConnection(sqlite3.Connection):
    def __exit__(self, exc_type, exc, tb):
        result = super().__exit__(exc_type, exc, tb)
        self.close()
        return result


def ensure_db_file():
    db_dir = os.path.dirname(config.DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    if os.path.exists(config.DB_PATH):
        if os.name != "nt":
            os.chmod(config.DB_PATH, 0o600)
        return
    default_path = getattr(config, "BOOTSTRAP_DB_PATH", getattr(config, "DEFAULT_DB_PATH", ""))
    if default_path and os.path.exists(default_path) and os.path.abspath(default_path) != os.path.abspath(config.DB_PATH):
        import shutil
        shutil.copy2(default_path, config.DB_PATH)
    if os.path.exists(config.DB_PATH) and os.name != "nt":
        os.chmod(config.DB_PATH, 0o600)


def get_db():
    global _sqlite_wal_ready
    from flask import has_request_context, g
    if has_request_context():
        if not hasattr(g, "_managed_db_conns"):
            g._managed_db_conns = []
        if g._managed_db_conns:
            try:
                g._managed_db_conns[0].execute("SELECT 1")
                return g._managed_db_conns[0]
            except Exception:
                g._managed_db_conns.clear()

    ensure_db_file()
    conn = sqlite3.connect(config.DB_PATH, timeout=10, factory=ClosingConnection)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 10000")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA synchronous = NORMAL")
    if not _sqlite_wal_ready:
        lock = _get_pragma_lock()
        with lock:
            if not _sqlite_wal_ready:
                try:
                    conn.execute("PRAGMA journal_mode = WAL")
                    _sqlite_wal_ready = True
                except sqlite3.Error:
                    pass

    if has_request_context():
        g._managed_db_conns.append(conn)
    return conn
