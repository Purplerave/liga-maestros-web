"""Resolución única de la jornada activa de la aplicación.

La jornada que se muestra en la web y la jornada sobre la que se aceptan
predicciones deben salir de la misma regla. Mantenerla aquí evita que una BD
con datos históricos o de preparación haga que cada endpoint elija una
jornada distinta.
"""


def resolve_active_jornada(conn):
    """Return the jornada currently editable and displayed as active.

    La temporada publicada empieza en J1. Mientras se conserva en la BD
    información de jornadas antiguas/de prueba (J75/J76), no debe ganar ese
    histórico por el simple hecho de ser el número mayor.
    """
    try:
        has_j1 = conn.execute("SELECT 1 FROM resultados WHERE jornada = 1 LIMIT 1").fetchone()
        if has_j1:
            return 1
    except Exception:
        pass

    rows = conn.execute("SELECT jornada FROM resultados GROUP BY jornada HAVING COUNT(*) > 0").fetchall()
    jornadas = [int(row[0]) for row in rows if row[0] is not None]
    if not jornadas:
        return 1

    published = [jornada for jornada in jornadas if jornada not in (75, 76)]
    return max(published or jornadas)
