"""Verified SQLite backups stored outside the deployed source tree."""
from datetime import datetime, timezone
import os
import sqlite3
import threading
import time

import config

_backup_thread = None
_backup_lock = threading.Lock()


def _truthy(value):
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def verify_backup(path):
    if not os.path.isfile(path):
        return False
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=20)
    try:
        result = conn.execute("PRAGMA integrity_check").fetchone()
        return bool(result and result[0] == "ok")
    finally:
        conn.close()


def create_backup(reason="manual"):
    if not os.path.isfile(config.DB_PATH):
        raise FileNotFoundError(config.DB_PATH)
    os.makedirs(config.DB_BACKUP_DIR, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_reason = "".join(ch for ch in reason.lower() if ch.isalnum() or ch in "-_") or "manual"
    final_path = os.path.join(config.DB_BACKUP_DIR, f"liga_maestros_{stamp}_{safe_reason}.db")
    temp_path = f"{final_path}.tmp"

    with _backup_lock:
        source = sqlite3.connect(config.DB_PATH, timeout=30)
        destination = sqlite3.connect(temp_path, timeout=30)
        try:
            source.backup(destination)
        finally:
            destination.close()
            source.close()
        if not verify_backup(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass
            raise RuntimeError("La copia SQLite no supera integrity_check")
        os.replace(temp_path, final_path)
        prune_backups()
    return final_path


def list_backups():
    if not os.path.isdir(config.DB_BACKUP_DIR):
        return []
    paths = [
        os.path.join(config.DB_BACKUP_DIR, name)
        for name in os.listdir(config.DB_BACKUP_DIR)
        if name.startswith("liga_maestros_") and name.endswith(".db")
    ]
    return sorted(paths, key=os.path.getmtime, reverse=True)


def prune_backups(retention=None):
    retention = retention or int(os.getenv("DB_BACKUP_RETENTION", "14"))
    for path in list_backups()[max(1, retention):]:
        try:
            os.remove(path)
        except OSError:
            pass


def start_backup_scheduler(app=None):
    global _backup_thread
    if not _truthy(os.getenv("DB_BACKUP_ENABLED", "0")):
        return None
    if _backup_thread and _backup_thread.is_alive():
        return _backup_thread

    interval = max(900, int(os.getenv("DB_BACKUP_INTERVAL_SECONDS", "21600")))

    def worker():
        time.sleep(5)
        while True:
            try:
                create_backup("scheduled")
            except Exception:
                if app:
                    app.logger.exception("Automatic database backup failed")
            time.sleep(interval)

    _backup_thread = threading.Thread(target=worker, name="db-backup", daemon=True)
    _backup_thread.start()
    return _backup_thread
