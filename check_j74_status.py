import sqlite3
conn = sqlite3.connect('C:/Users/Mortadelo/Desktop/QUINIELAs/LIGA_MAESTROS/DATOS/LIGA_MAESTROS_PRO.db')
rows = conn.execute("SELECT partido_id, local, visitante, status, fecha, hora FROM resultados WHERE jornada=74 ORDER BY partido_id").fetchall()
print('J74 matches:')
for r in rows:
    print(f'  #{r[0]}: {r[1]} vs {r[2]} - Status: {r[4]} {r[5]} ({r[3]})')
conn.close()
