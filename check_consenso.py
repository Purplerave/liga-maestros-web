import sqlite3
conn = sqlite3.connect('C:/Users/Mortadelo/Desktop/QUINIELAs/LIGA_MAESTROS/DATOS/LIGA_MAESTROS_PRO.db')

print('=== CONSENSO J74 ===')
rows = conn.execute("SELECT partido_id, ganador, p1, px, p2 FROM consenso WHERE jornada=74 ORDER BY partido_id").fetchall()
for r in rows:
    print(f'  Partido {r[0]}: {r[1]} ({r[2]}%/{r[3]}%/{r[4]}%)')

print('\n=== PREDICCIONES LA PEÑA J74 ===')
penya = ['baidu', 'geli', 'kimi', 'pepe', 'profe', 'chipi', 'fortu', 'gema', 'jimmy', 'sesudo', 'fistro']
for user in penya:
    rows = conn.execute("SELECT partido_id, signo FROM predicciones WHERE user_id=? AND jornada=74 ORDER BY partido_id", (user,)).fetchall()
    if rows:
        signs = [r[1] for r in rows]
        print(f'  {user:12s}: {"".join(signs)}')
    else:
        print(f'  {user:12s}: SIN PREDICCIONES')

conn.close()
