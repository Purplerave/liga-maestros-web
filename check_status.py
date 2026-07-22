import sqlite3
conn = sqlite3.connect('C:/Users/Mortadelo/Desktop/QUINIELAs/LIGA_MAESTROS/DATOS/LIGA_MAESTROS_PRO.db')
# Check all statuses
rows = conn.execute("SELECT status, COUNT(*) FROM resultados GROUP BY status").fetchall()
print('Status distribution:')
for r in rows:
    print(f'  {r[0]}: {r[1]}')
conn.close()
