import sqlite3
conn = sqlite3.connect('C:/Users/Mortadelo/Desktop/QUINIELAs/LIGA_MAESTROS/DATOS/LIGA_MAESTROS_PRO.db')
rows = conn.execute("SELECT partido_id, signo FROM predicciones WHERE user_id='oraculo' AND jornada=74 ORDER BY partido_id").fetchall()
signs = [r[1] for r in rows]
print(f'Oráculo signs: {len(signs)}')
print(f'Oráculo prediction: {" ".join(signs)}')
print(f'Full string: {"".join(signs)}')
conn.close()
