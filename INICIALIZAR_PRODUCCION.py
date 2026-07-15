"""Create or validate the persistent production database before first start."""
import sqlite3

import config
from liga_maestros.db.migrations import run_startup_migrations


def main():
    run_startup_migrations()
    conn = sqlite3.connect(config.DB_PATH, timeout=30)
    try:
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        jornadas = conn.execute("SELECT COUNT(DISTINCT jornada) FROM resultados").fetchone()[0]
        partidos = conn.execute("SELECT COUNT(*) FROM resultados").fetchone()[0]
    finally:
        conn.close()
    if integrity != "ok":
        raise RuntimeError(f"SQLite integrity_check: {integrity}")
    print(f"Base lista: {config.DB_PATH} | jornadas={jornadas} | partidos={partidos}")


if __name__ == "__main__":
    main()
