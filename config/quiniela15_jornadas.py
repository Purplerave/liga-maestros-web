"""Equivalencia entre la jornada del boleto y la jornada de quiniela15.com.

Las dos numeraciones no siempre coinciden. La Quiniela oficial de SELAE mete
boletos extraordinarios (Copa del Rey, jornadas de media semana) que
quiniela15.com publica como una jornada mas, mientras que el boleto de esta
liga sigue el calendario de LaLiga/Liga F. Cuando pasa, el colector pide
``/resultados-quiniela/17`` y recibe OTRA quiniela: todos los cruces por
``partido_id`` fallan, la jornada entera se queda en ``NS`` y en la portada se
sigue viendo el horario aunque los partidos ya se hayan jugado.

Caso real (31/10/2026): el boleto J17 de la liga (Levante-Atletico,
Rayo-Celta, Betis-Malaga, ...) es la **J18** de quiniela15; la J17 de
quiniela15 es la Copa del Rey del miercoles 28/10, que no entra en el boleto.

La tabla es solo un override: por defecto la jornada se pide con su mismo
numero, asi que si la quiniela15 vuelve a alinearse no hay que tocar nada.
"""

# jornada del boleto -> jornada a pedir a quiniela15.com
QUINIELA15_JORNADA_OVERRIDES = {
    17: 18,
}

# Margen de fechas. En la J17 esta jornada se juega del sabado 31/10 al lunes
# 2/11, asi que un partido puede caer a 2 dias del saque del boleto. Con 3 se
# colaba un partido de Copa del miercoles en una casilla del sabado; con 2 no.
Q15_BOLETO_DATE_TOLERANCE_DAYS = 2


def q15_jornada(jornada):
    """Jornada a pedir a quiniela15.com para el boleto ``jornada``."""
    try:
        numero = int(jornada)
    except (TypeError, ValueError):
        return jornada
    return QUINIELA15_JORNADA_OVERRIDES.get(numero, numero)
