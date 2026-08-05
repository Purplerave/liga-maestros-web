from liga_maestros.db.connection import get_db


def debug_latest_jornada():
    conn = get_db()
    try:
        # Get max jornada
        row = conn.execute("SELECT MAX(jornada) FROM resultados").fetchone()
        if not row or row[0] is None:
            print("No jornadas found in resultados table.")
            return

        max_jornada = row[0]
        print(f"Analyzing Jornada: {max_jornada}")

        # Fetch all matches for this jornada
        rows = conn.execute(
            "SELECT partido_id, local, visitante, goles_local, goles_visitante, status FROM resultados WHERE jornada = ?",
            (max_jornada,),
        ).fetchall()

        print(f"{'ID':<5} | {'Local':<20} | {'Visitante':<20} | {'GL':<5} | {'GV':<5} | {'Status':<15}")
        print("-" * 75)

        for row in rows:
            print(
                f"{row['partido_id']:<5} | {row['local']:<20} | {row['visitante']:<20} | {str(row['goles_local']):<5} | {str(row['goles_visitante']):<5} | {row['status']:<15}"
            )

    finally:
        conn.close()


if __name__ == "__main__":
    debug_latest_jornada()
