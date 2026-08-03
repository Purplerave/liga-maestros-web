import sqlite3
import os

# Ruta a tu base de datos local
db_path = os.path.join(os.getcwd(), "DATOS", "LIGA_MAESTROS_PRO.db")
if not os.path.exists(db_path):
    db_path = os.path.join(os.getcwd(), "data", "LIGA_MAESTROS_PRO.db")

print(f"Abriendo: {db_path}")

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("UPDATE resultados SET local = 'VPS Vaasa' WHERE jornada = 75 AND partido_id = 1")
    cursor.execute("UPDATE resultados SET local = 'TPS Turku' WHERE jornada = 75 AND partido_id = 2")
    conn.commit()
    print("¡Nombres corregidos en la Base de Datos!")
except Exception as e:
    print(f"Error: {e}")
finally:
    if 'conn' in locals():
        conn.close()