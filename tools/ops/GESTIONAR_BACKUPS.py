"""Create, list, verify and ship off-site production-compatible SQLite backups.

Off-site uploads use the BACKUP_S3_* environment variables (works with any
S3-compatible storage: Backblaze B2, Cloudflare R2, DigitalOcean Spaces...).
The scheduler already uploads automatically when DB_BACKUP_ENABLED=1; the
`upload` subcommand covers manual/cron-driven off-site pushes.
"""

import argparse
import os

from liga_maestros.db.backups import (
    create_backup,
    list_backups,
    prune_s3_backups,
    upload_backup_to_s3,
    verify_backup,
)


def _upload(path):
    if not os.getenv("BACKUP_S3_BUCKET"):
        print("BACKUP_S3_BUCKET no configurado: define las variables BACKUP_S3_* en el entorno.")
        raise SystemExit(2)
    if not verify_backup(path):
        print(f"INVALID: {path} no supera integrity_check, no se sube.")
        raise SystemExit(1)
    ok = upload_backup_to_s3(path)
    print(f"{'UPLOADED' if ok else 'FAILED'}\t{path}")
    if ok:
        prune_s3_backups()
    raise SystemExit(0 if ok else 1)


def main():
    parser = argparse.ArgumentParser(description="Gestiona backups de Liga de Maestros.")
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create", help="Crea un backup verificado en DB_BACKUP_DIR.")
    create.add_argument("--reason", default="manual")
    create.add_argument(
        "--upload",
        action="store_true",
        help="Sube el backup recién creado al almacenamiento S3 configurado (BACKUP_S3_*).",
    )
    sub.add_parser("list", help="Lista los backups locales retenidos.")
    verify = sub.add_parser("verify", help="Comprueba integrity_check de un backup.")
    verify.add_argument("path")
    upload = sub.add_parser("upload", help="Sube un backup existente (o el más reciente) al S3 configurado.")
    upload.add_argument("path", nargs="?", help="Ruta del backup. Si se omite, usa el más reciente.")
    args = parser.parse_args()

    if args.command == "create":
        path = create_backup(args.reason)
        print(path)
        if args.upload:
            _upload(path)
    elif args.command == "list":
        for path in list_backups():
            print(f"{os.path.getsize(path)}\t{path}")
    elif args.command == "verify":
        ok = verify_backup(args.path)
        print("OK" if ok else "INVALID")
        raise SystemExit(0 if ok else 1)
    elif args.command == "upload":
        path = args.path or next(iter(list_backups()), None)
        if not path:
            print("No hay backups locales que subir.")
            raise SystemExit(1)
        _upload(path)


if __name__ == "__main__":
    main()
