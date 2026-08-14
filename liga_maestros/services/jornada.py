"""Resolución única de la jornada activa de la aplicación.

La jornada que se muestra en la web y la jornada sobre la que se aceptan
predicciones deben salir de la misma regla. Mantenerla aquí evita que una BD
con datos históricos o de preparación haga que cada endpoint elija una
jornada distinta.
"""

from .season import filter_season_jornadas, season_start


def resolve_active_jornada(conn):
    """Return the jornada currently editable and displayed as active.

    La temporada publicada empieza en J1. Mientras se conserva en la BD el
    archivo histórico (liga de pruebas J51-J73 y los ensayos J75/J76), no debe
    ganar ese histórico por el simple hecho de ser el número mayor: la frontera
    la define ``services.season``.
    """
    start = season_start()
    try:
        has_start = conn.execute("SELECT 1 FROM resultados WHERE jornada = ? LIMIT 1", (start,)).fetchone()
        if has_start:
            return start
    except Exception:
        pass

    rows = conn.execute("SELECT jornada FROM resultados GROUP BY jornada HAVING COUNT(*) > 0").fetchall()
    jornadas = [int(row[0]) for row in rows if row[0] is not None]
    if not jornadas:
        return start

    published = filter_season_jornadas(jornadas)
    return max(published) if published else start
