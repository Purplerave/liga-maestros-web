import sqlite3
from liga_maestros.db.connection import get_db

def debug_jornadas_status():
    conn = get_db()
    try:
        # 1. Summary of all jornadas
        print("--- Jornadas Summary ---")
        rows = conn.execute(
            "SELECT jornada, COUNT(*) as total, SUM(CASE WHEN status IN ('FT', 'FINISHED', 'TERMINADO') THEN 1 ELSE 0 END) as finished FROM resultados GROUP BY jornada ORDER BY jornada DESC"
        ).fetchall()
        
        for row in rows:
            print(f"Jornada {row['jornada']}: {row['finished']}/{row['total']} finished")
        
        # 2. Detailed view of the one with most finished matches
        best_jornada = None
        max_fin = -1
        for row in rows:
            if row['finished'] > max_fin:
                max_fin = row['finished']
                best_jornada = row['jornada']
        
        if best_jornada:
            print(f"\n--- Detailed View: Jornada {best_jornada} (Max finished: {max_fin}) ---")
            rows_det = conn.execute(
                "SELECT partido_id, local, visitante, goles_local, goles_visitante, status FROM resultados WHERE jornada = ?",
                (best_jornada,)
            ).fetchall()
            
            print(f"{'ID':<5} | {'Local':<20} | {'Visitante':<20} | {'GL':<5} | {'GV':<5} | {'Status':<15}")
            print("-" * 75)
            for row in rows_det:
                print(f"{row['partido_id']:<5} | {row['local']:<20} | {row['visitante']:<20} | {str(row['goles_local']):<5} | {str(row['goles_visitante']):<5} | {row['status']:<15}")
            
    finally:
        conn.close()

if __name__ == "__main__":
    debug_jornadas_status()
