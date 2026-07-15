"""Create, list and verify production-compatible SQLite backups."""
import argparse
import os

from liga_maestros.db.backups import create_backup, list_backups, verify_backup


def main():
    parser = argparse.ArgumentParser(description="Gestiona backups de Liga de Maestros.")
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create")
    create.add_argument("--reason", default="manual")
    sub.add_parser("list")
    verify = sub.add_parser("verify")
    verify.add_argument("path")
    args = parser.parse_args()

    if args.command == "create":
        print(create_backup(args.reason))
    elif args.command == "list":
        for path in list_backups():
            print(f"{os.path.getsize(path)}\t{path}")
    elif args.command == "verify":
        ok = verify_backup(args.path)
        print("OK" if ok else "INVALID")
        raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
