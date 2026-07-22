import sqlite3
conn = sqlite3.connect('C:/Users/Mortadelo/Desktop/QUINIELAs/LIGA_MAESTROS/DATOS/LIGA_MAESTROS_PRO.db')
rows = conn.execute("SELECT jornada, partido_id, local, visitante, status, fecha, hora FROM resultados WHERE status IN ('LIVE', 'IN_PLAY', 'HT') ORDER BY jornada DESC, partido_id").fetchall()
print('Partidos en directo:')
for r in rows:
    print(f'  J{r[0]} #{r[1]}: {r[2]} vs {r[3]} - Status: {r[4]} ({r[5]} {r[6]})')
if not rows:
    print('  Ninguno')
conn.close()
