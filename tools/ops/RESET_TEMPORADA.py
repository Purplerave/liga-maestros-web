"""Reset the database for a new season.

Saves the final test-season rankings, clears old data, and loads Jornada 1.

Usage:
    python tools/ops/RESET_TEMPORADA.py
"""

import json
import os
import sqlite3
from datetime import UTC, datetime

import config
from liga_maestros.db.migrations import ensure_jornada_completa, run_startup_migrations


def backup_database():
    """Copia la BD antes de borrar nada. Este script es destructivo."""
    import shutil

    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    dest = f"{config.DB_PATH}.pre-reset-{stamp}.bak"
    shutil.copy2(config.DB_PATH, dest)
    return dest


def save_season_summary(conn):
    """Save top 3 participants and season stats before reset."""
    rows = conn.execute("""
        SELECT u.id, u.nombre, u.puntos_acumulados
        FROM usuarios u
        WHERE u.puntos_acumulados > 0
        ORDER BY u.puntos_acumulados DESC
        LIMIT 10
    """).fetchall()

    total_participants = conn.execute("SELECT COUNT(*) FROM usuarios WHERE puntos_acumulados > 0").fetchone()[0]

    total_jornadas = conn.execute("SELECT COUNT(DISTINCT jornada) FROM resultados").fetchone()[0]

    total_partidos = conn.execute("SELECT COUNT(*) FROM resultados WHERE status IN ('FT', 'FINISHED')").fetchone()[0]

    summary = {
        "season": "2025-2026 (Pruebas)",
        "saved_at": datetime.now(UTC).isoformat(),
        "total_participants": total_participants,
        "total_jornadas": total_jornadas,
        "total_partidos_jugados": total_partidos,
        "top_3": [
            {"position": i + 1, "name": row["nombre"] or "Participante", "points": row["puntos_acumulados"]}
            for i, row in enumerate(rows[:3])
        ],
        "top_10": [
            {"position": i + 1, "name": row["nombre"] or "Participante", "points": row["puntos_acumulados"]}
            for i, row in enumerate(rows)
        ],
    }

    out_path = os.path.join(config.DATA_DIR, "season_2025_2026_summary.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"Season summary saved to {out_path}")
    return summary


def reset_tables(conn):
    """Clear old season data for a fresh start.

    OJO: esto BORRA el histórico. La política por defecto del proyecto es
    conservarlo y limitarse a ocultarlo (ver `liga_maestros/services/season.py`),
    cosa que ocurre sola en cada arranque. Este script es la opción destructiva,
    solo para cuando se quiera vaciar la base de verdad.
    """
    tables_to_clear = [
        ("predicciones", None),
        ("resultados", None),
        ("consenso", None),
        ("historico", None),
    ]

    for table, _ in tables_to_clear:
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        conn.execute(f"DELETE FROM {table}")
        print(f"  Cleared {table}: {count} rows")

    # Reset accumulated points but keep user accounts
    conn.execute("UPDATE usuarios SET puntos_acumulados = 0")
    users = conn.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0]
    print(f"  Reset puntos_acumulados for {users} users")

    # Clear clasificacion
    count = conn.execute("SELECT COUNT(*) FROM clasificacion").fetchone()[0]
    conn.execute("DELETE FROM clasificacion")
    print(f"  Cleared clasificacion: {count} rows")

    conn.commit()


def load_jornada_1(conn):
    """Load Jornada 1 fixture from scrape file."""
    updated = ensure_jornada_completa(conn, 1)
    print(f"  Jornada 1: {updated} rows inserted/updated")
    conn.commit()


def reload_clasificacion_zero(conn):
    """Repone la clasificación a cero con los equipos correctos tras el reset."""
    from liga_maestros.db.migrations import ensure_clasificacion_zero

    ensure_clasificacion_zero(conn)
    cnt = conn.execute("SELECT COUNT(*) FROM clasificacion").fetchone()[0]
    print(f"  Clasificación repoblada a cero: {cnt} equipos (20 Primera + 22 Segunda)")


def main():
    print("=== RESET TEMPORADA 2026-2027 ===")
    print()

    run_startup_migrations()
    conn = sqlite3.connect(config.DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row

    try:
        print("0. Backing up the database...")
        backup_path = backup_database()
        print(f"   Backup: {backup_path}")
        print()

        print("1. Saving season summary...")
        summary = save_season_summary(conn)
        print(f"   Top 3: {[p['name'] + ' (' + str(p['points']) + 'pts)' for p in summary['top_3']]}")
        print()

        print("2. Resetting tables...")
        reset_tables(conn)
        print()

        print("3. Loading Jornada 1...")
        load_jornada_1(conn)
        print()
        print("4. Repoblando clasificación a cero...")
        reload_clasificacion_zero(conn)
        print()

        print("=== RESET COMPLETE ===")
        print(f"Database: {config.DB_PATH}")
        print(f"Summary: {os.path.join(config.DATA_DIR, 'season_2025_2026_summary.json')}")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
