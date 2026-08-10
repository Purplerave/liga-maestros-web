"""Verified SQLite backups stored outside the deployed source tree."""

import logging
import os
import sqlite3
import threading
import time
from datetime import UTC, datetime

import config

logger = logging.getLogger(__name__)

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
    os.makedirs(config.DB_BACKUP_DIR, mode=0o700, exist_ok=True)
    if os.name != "nt":
        os.chmod(config.DB_BACKUP_DIR, 0o700)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
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
        if os.name != "nt":
            os.chmod(final_path, 0o600)
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
    for path in list_backups()[max(1, retention) :]:
        try:
            os.remove(path)
        except OSError:
            pass


def _s3_configured():
    return bool(os.getenv("BACKUP_S3_BUCKET"))


def upload_backup_to_s3(local_path):
    """Upload a backup file to S3-compatible storage. Returns True on success."""
    if not _s3_configured():
        return False
    try:
        import boto3
    except ImportError:
        logger.warning("boto3 not installed, skipping S3 upload")
        return False

    bucket = os.getenv("BACKUP_S3_BUCKET")
    prefix = os.getenv("BACKUP_S3_PREFIX", "liga-maestros-backups/")
    endpoint = os.getenv("BACKUP_S3_ENDPOINT")  # For B2/Spaces/MinIO

    s3 = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=os.getenv("BACKUP_S3_KEY_ID"),
        aws_secret_access_key=os.getenv("BACKUP_S3_SECRET"),
        region_name=os.getenv("BACKUP_S3_REGION", "us-east-1"),
    )

    filename = os.path.basename(local_path)
    key = f"{prefix.rstrip('/')}/{filename}"
    try:
        s3.upload_file(local_path, bucket, key)
        logger.info("Backup uploaded to s3://%s/%s", bucket, key)
        return True
    except Exception:
        logger.exception("Failed to upload backup to S3")
        return False


def prune_s3_backups():
    """Remove old backups from S3 beyond retention limit."""
    if not _s3_configured():
        return
    try:
        import boto3
    except ImportError:
        return

    bucket = os.getenv("BACKUP_S3_BUCKET")
    prefix = os.getenv("BACKUP_S3_PREFIX", "liga-maestros-backups/")
    endpoint = os.getenv("BACKUP_S3_ENDPOINT")
    retention = int(os.getenv("DB_BACKUP_RETENTION", "14"))

    s3 = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=os.getenv("BACKUP_S3_KEY_ID"),
        aws_secret_access_key=os.getenv("BACKUP_S3_SECRET"),
        region_name=os.getenv("BACKUP_S3_REGION", "us-east-1"),
    )

    try:
        resp = s3.list_objects_v2(Bucket=bucket, Prefix=prefix.rstrip("/") + "/")
        objects = sorted(resp.get("Contents", []), key=lambda o: o["LastModified"], reverse=True)
        for obj in objects[max(1, retention):]:
            s3.delete_object(Bucket=bucket, Key=obj["Key"])
            logger.info("Pruned S3 backup: %s", obj["Key"])
    except Exception:
        logger.exception("Failed to prune S3 backups")


def minimize_backup_personal_data():
    """Remove legacy stored emails from retained SQLite backups."""
    cleaned = 0
    for path in list_backups():
        conn = sqlite3.connect(path, timeout=20)
        try:
            columns = {row[1] for row in conn.execute("PRAGMA table_info(usuarios)")}
            if "email" not in columns:
                continue
            cursor = conn.execute("UPDATE usuarios SET email = NULL WHERE email IS NOT NULL")
            conn.commit()
            cleaned += max(0, int(cursor.rowcount or 0))
        finally:
            conn.close()
        if os.name != "nt":
            os.chmod(path, 0o600)
        if not verify_backup(path):
            raise RuntimeError(f"La copia no supera integrity_check tras minimizar datos: {path}")
    return cleaned


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
                path = create_backup("scheduled")
                upload_backup_to_s3(path)
                prune_s3_backups()
            except Exception:
                logger.exception("Automatic database backup failed")
            time.sleep(interval)

    _backup_thread = threading.Thread(target=worker, name="db-backup", daemon=True)
    _backup_thread.start()
    return _backup_thread
