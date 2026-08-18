"""Resolución única de la jornada activa de la aplicación.

La jornada que se muestra en la web y la jornada sobre la que se aceptan
predicciones deben salir de la misma regla. Mantenerla aquí evita que una BD
con datos históricos o de preparación haga que cada endpoint elija una
jornada distinta.
"""

# Temporada publicada 2026/27. La quiniela publicada reinicia su numeración
# en J1 (LaLiga: 38 jornadas; se deja margen hasta 42 por boletos extra).
# Las jornadas 51-76 conservadas en la BD pertenecen al periodo de pruebas
# 2025/26: se mantienen como archivo, pero no deben alimentar rankings,
# rachas, galardones ni estadísticas de jugadores. La competición y las
# estadísticas de todos los participantes arrancan de cero con la J1.
CURRENT_SEASON_MAX_JORNADA = 42


def is_current_season_jornada(jornada):
    """True si la jornada pertenece a la temporada publicada (2026/27)."""
    try:
        num = int(jornada)
    except (TypeError, ValueError):
        return False
    return 1 <= num <= CURRENT_SEASON_MAX_JORNADA


def current_season_sql(column="jornada"):
    """Fragmento SQL que limita una consulta a la temporada actual.

    El límite es una constante interna (int literal), nunca entrada externa.
    """
    return f"{column} BETWEEN 1 AND {int(CURRENT_SEASON_MAX_JORNADA)}"


def resolve_active_jornada(conn):
    """Return the jornada currently editable and displayed as active.

    Temporada 2026/27: J1..42. Devuelve la última jornada con al menos un
    partido cargado (normalmente 15), ignorando 75/76 de pruebas.
    Así J1 deja de ser fija y la web promociona automáticamente a J2, J3...
    """
    try:
        rows = conn.execute("SELECT jornada FROM resultados GROUP BY jornada HAVING COUNT(*) > 0").fetchall()
        jornadas = [int(row[0]) for row in rows if row[0] is not None and is_current_season_jornada(row[0])]
        if jornadas:
            return max(jornadas)
    except Exception:
        pass

    # Fallback: si no hay nada en la temporada actual, mantener J1 (seed) y no
    # dejar que 75/76 de pruebas se convierta en activa por ser mayor.
    try:
        rows = conn.execute("SELECT jornada FROM resultados GROUP BY jornada HAVING COUNT(*) > 0").fetchall()
        jornadas = [int(row[0]) for row in rows if row[0] is not None]
        if not jornadas:
            return 1
        published = [j for j in jornadas if j not in (75, 76)]
        return max(published or jornadas)
    except Exception:
        return 1
