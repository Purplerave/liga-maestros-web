import sqlite3
conn = sqlite3.connect('C:/Users/Mortadelo/Desktop/QUINIELAs/LIGA_MAESTROS/DATOS/LIGA_MAESTROS_PRO.db')

# Check predictions for La Peña members
penya_users = ['baidu', 'geli', 'kimi', 'pepe', 'profe', 'chipi', 'fortu', 'gema', 'jimmy', 'sesudo', 'fistro']

print('=== PREDICCIONES LA PEÑA J74 ===')
for user in penya_users:
    rows = conn.execute(
        "SELECT partido_id, signo FROM predicciones WHERE user_id=? AND jornada=74 ORDER BY partido_id",
        (user,)
    ).fetchall()
    if rows:
        signs = [r[1] for r in rows]
        print(f'{user:12s}: {"".join(signs)}')
    else:
        print(f'{user:12s}: SIN PREDICCIONES')

print('\n=== PREDICCIONES MAESTROS J74 ===')
maestros = ['programa', 'chatgpt', 'gemini', 'grok', 'copilot', 'claude', 'oraculo']
for user in maestros:
    rows = conn.execute(
        "SELECT partido_id, signo FROM predicciones WHERE user_id=? AND jornada=74 ORDER BY partido_id",
        (user,)
    ).fetchall()
    if rows:
        signs = [r[1] for r in rows]
        print(f'{user:12s}: {"".join(signs)}')
    else:
        print(f'{user:12s}: SIN PREDICCIONES')

conn.close()
