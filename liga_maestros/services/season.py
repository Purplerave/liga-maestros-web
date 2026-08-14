"""Frontera de la temporada activa: qué jornadas son "esta temporada".

Regla única del proyecto: **la temporada 2026-27 empieza en la Jornada 1**.

Todo lo anterior (las jornadas 51-73 de la liga de pruebas y las J75/J76 que
se usaron para ensayar el verano de 2026) se conserva en la base de datos como
archivo histórico, pero **no debe aparecer en ninguna pantalla**: ni en el
ranking acumulado, ni en el selector de jornadas, ni en galardones, momentos o
rachas.

Antes, cada módulo aplicaba su propio criterio —`CONTEST_DYNAMIC_START_JORNADA
= 58` en el concurso, listas negras `(75, 76)` en dos sitios, `MAX(jornada)` a
pelo en otros— y por eso el ranking general seguía sumando la pretemporada
mientras la pestaña Quiniela ya mostraba la J1. Este módulo centraliza la
decisión para que exista una sola respuesta.
"""

from __future__ import annotations

import os

# Primera jornada de la temporada publicada.
SEASON_START_JORNADA = 1

# La liga de pruebas usaba numeración continua (llegó hasta la J76), así que sus
# jornadas son NUMÉRICAMENTE MAYORES que las de la temporada nueva aunque sean
# ANTERIORES en el tiempo. Por eso no basta con un `jornada >= 1`: hay que
# excluir explícitamente esa ventana. La temporada 2026-27 tiene 38 jornadas,
# así que nunca colisiona con este rango.
LEGACY_JORNADA_MIN = 40
LEGACY_JORNADA_MAX = 76

# Conjunto explícito del archivo histórico (liga de pruebas + ensayos J75/J76).
LEGACY_JORNADAS = frozenset(range(LEGACY_JORNADA_MIN, LEGACY_JORNADA_MAX + 1))


def season_start() -> int:
    """Primera jornada válida de la temporada activa (configurable)."""
    raw = str(os.getenv("SEASON_START_JORNADA", "")).strip()
    if raw.lstrip("-").isdigit():
        return int(raw)
    return SEASON_START_JORNADA


def is_season_jornada(jornada) -> bool:
    """¿Esta jornada pertenece a la temporada publicada?"""
    try:
        value = int(jornada)
    except (TypeError, ValueError):
        return False
    return value >= season_start() and not (LEGACY_JORNADA_MIN <= value <= LEGACY_JORNADA_MAX)


def filter_season_jornadas(jornadas) -> list[int]:
    """Filtra un iterable de jornadas dejando solo las de la temporada activa."""
    out = []
    for jornada in jornadas or []:
        try:
            value = int(jornada)
        except (TypeError, ValueError):
            continue
        if is_season_jornada(value):
            out.append(value)
    return out


def season_sql_filter(column: str = "jornada") -> tuple[str, list]:
    """Fragmento SQL reutilizable + parámetros para acotar a la temporada.

    Devuelve ``("jornada >= ? AND jornada NOT BETWEEN ? AND ?", [1, 40, 76])``
    para inyectar tras un WHERE.
    """
    return (
        f"{column} >= ? AND {column} NOT BETWEEN ? AND ?",
        [season_start(), LEGACY_JORNADA_MIN, LEGACY_JORNADA_MAX],
    )
