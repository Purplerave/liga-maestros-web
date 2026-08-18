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

    Temporada 2026/27: J1..42. Devuelve la **primera jornada abierta** (con
    al menos un partido en NS). Así J1 sigue activa mientras se pueda firmar,
    y la web promociona a J2, J3... automáticamente cuando J1 ya está
    terminada (sin NS). Ignora 75/76.
    """
    try:
        rows = conn.execute("SELECT jornada FROM resultados GROUP BY jornada HAVING COUNT(*) > 0").fetchall()
        jornadas = sorted({int(row[0]) for row in rows if row[0] is not None and is_current_season_jornada(row[0])})
        if jornadas:
            for j in jornadas:
                try:
                    ns = conn.execute(
                        "SELECT 1 FROM resultados WHERE jornada = ? AND UPPER(COALESCE(status,'')) IN ('NS','SCHEDULED','') LIMIT 1",
                        (j,),
                    ).fetchone()
                    if ns:
                        return j
                except Exception:
                    return j
            # Todas cerradas (sin NS): devolver la última
            return max(jornadas)
    except Exception:
        pass

    try:
        rows = conn.execute("SELECT jornada FROM resultados GROUP BY jornada HAVING COUNT(*) > 0").fetchall()
        jornadas = sorted({int(row[0]) for row in rows if row[0] is not None and is_current_season_jornada(row[0])})
        if jornadas:
            return jornadas[0]
    except Exception:
        pass

    try:
        rows = conn.execute("SELECT jornada FROM resultados GROUP BY jornada HAVING COUNT(*) > 0").fetchall()
        jornadas = [int(row[0]) for row in rows if row[0] is not None]
        if not jornadas:
            return 1
        published = [j for j in jornadas if j not in (75, 76)]
        return min(published or jornadas)
    except Exception:
        return 1
