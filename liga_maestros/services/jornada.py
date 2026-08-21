"""Resolución única de la jornada activa de la aplicación.

La jornada que se muestra en la web y la jornada sobre la que se aceptan
predicciones deben salir de la misma regla. Mantenerla aquí evita que una BD
con datos históricos o de preparación haga que cada endpoint elija una
jornada distinta.
"""

from datetime import date, datetime
from zoneinfo import ZoneInfo

MADRID_TZ = ZoneInfo("Europe/Madrid")


def _madrid_today():
    return datetime.now(MADRID_TZ).date()


def _ns_match_still_open(fecha):
    """True si un partido sin empezar mantiene su jornada abierta.

    Un NS con fecha en el pasado (aplazado sin nueva fecha o resultado que el
    scraper aún no ha recogido) no debe mantener activa una jornada que ya no
    se puede firmar: bloquearía la promoción automática a la siguiente. NS sin
    fecha o con fecha de hoy/futura sigue contando como jornada abierta.
    """
    text = str(fecha or "").strip()
    if not text or text == "-":
        return True
    try:
        return date.fromisoformat(text[:10]) >= _madrid_today()
    except ValueError:
        return True

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
    al menos un partido en NS cuya fecha no haya quedado atrás). Así J1 sigue
    activa mientras se pueda firmar, y la web promociona a J2, J3...
    automáticamente cuando J1 ya está terminada (sin NS o solo con NS
    caducados, p. ej. aplazados sin nueva fecha). Ignora 75/76.
    """
    try:
        rows = conn.execute("SELECT jornada FROM resultados GROUP BY jornada HAVING COUNT(*) > 0").fetchall()
        jornadas = sorted({int(row[0]) for row in rows if row[0] is not None and is_current_season_jornada(row[0])})
        if jornadas:
            for j in jornadas:
                try:
                    ns_rows = conn.execute(
                        "SELECT fecha FROM resultados WHERE jornada = ? AND UPPER(COALESCE(status,'')) IN ('NS','SCHEDULED','')",
                        (j,),
                    ).fetchall()
                    if any(_ns_match_still_open(row["fecha"]) for row in ns_rows):
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
