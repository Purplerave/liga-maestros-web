import sqlite3
conn = sqlite3.connect('C:/Users/Mortadelo/Desktop/QUINIELAs/LIGA_MAESTROS/DATOS/LIGA_MAESTROS_PRO.db')
rows = conn.execute("SELECT user_id, signo FROM predicciones WHERE jornada=74 ORDER BY user_id, partido_id LIMIT 30").fetchall()
print('Local DB predictions:')
for r in rows:
    print(f'  {r[0]}: {r[1]}')
conn.close()
