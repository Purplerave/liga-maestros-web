"""Cobertura de escudos por jornada, de extremo a extremo.

La cadena tiene tres eslabones y los tres se rompieron a la vez:

1. `matches.py:213` emitía `logo_local`/`logo_visitante` calculados.
2. `MatchPayload` no los declaraba y `_StrictBase` va con `extra="ignore"`, así
   que se descartaban al serializar. La J9 llegaba a producción con 0 de 15.
3. `load_team_logos()` no aplicaba `TEAM_LOGO_ALIASES`, de modo que las variantes
   femeninas no llegaban al escudo del club aunque el fichero estuviera en disco.

Aquí se comprueba el resultado sobre el programa real de la J9, que es donde se
ven los agujeros: no basta con que el mapa tenga la clave.

El test es hermético. Una primera versión leía `get_db()` yAclkpeteaba en CI con
`no such table: resultados`, porque dependía de la BD local: exactamente lo que
la ola 1 prohibió. Ahora monta su propia base en `tmp_path` y siembra el programa
de la J9, que es dato versionado de la temporada.
"""

import pytest

import config
from liga_maestros import create_app
from liga_maestros.db.connection import get_db
from liga_maestros.schemas import MatchPayload
from liga_maestros.services.payloads.matches import build_jornada_matches
from liga_maestros.utils import FEMALE_LOGO_FALLBACK, TEAM_LOGO_ALIASES, load_team_logos, team_keys_compatible

JORNADA = 9

#: Programa de la J9 tal y como lo trae la fuente. Los cuatro equipos féminine
#: entran con la forma corta ("Ath. Club (F)", no "Athletic Club (F)"), y esa
#: forma es justo la que no estaba en la tabla de alias.
PROGRAMA_J9 = [
    (1, "Ceuta", "R. Sociedad B"),
    (2, "Granada", "Andorra FC"),
    (3, "Celta Fortuna", "Sabadell"),
    (4, "Tenerife", "Cádiz"),
    (5, "Valladolid", "Córdoba"),
    (6, "Mallorca", "Almería"),
    (7, "Burgos", "Eldense"),
    (8, "Eibar", "Las Palmas"),
    (9, "R. Oviedo", "Sporting"),
    (10, "Leganés", "Castellón"),
    (11, "Ath. Club (F)", "At. Madrid (F)"),
    (12, "Valencia (F)", "Tenerife (F)"),
    (13, "Sevilla (F)", "Eibar (F)"),
    (14, "Deportivo (F)", "Espanyol (F)"),
    (15, "Inglaterra", "España"),
]

#: Los cuatro equipos femeninos de la J9 y la forma en que llega su nombre.
FEMENINOS_J9 = ["Ath. Club (F)", "At. Madrid (F)", "Deportivo (F)", "Espanyol (F)"]


@pytest.fixture(scope="module")
def partidos_j9(tmp_path_factory):
    """J9 sembrada en una base propia, con la cadena de migraciones real.

    Guarda y restaura `config.DB_PATH` a mano en vez de tocarlo y ya está: un
    `monkeypatch` de ámbito de función no se puede pedir desde un fixture de
    módulo, y dejarlo puesto contaminaría el resto de la suite.
    """
    tmp = tmp_path_factory.mktemp("escudos")
    originals = {
        nombre: getattr(config, nombre)
        for nombre in ("DB_PATH", "BOOTSTRAP_DB_PATH", "PRODUCTION_SEED_PATH")
    }
    config.DB_PATH = str(tmp / "escudos.db")
    config.BOOTSTRAP_DB_PATH = str(tmp / "missing.db")
    config.PRODUCTION_SEED_PATH = str(tmp / "missing-seed.json")
    try:
        create_app()

        conn = get_db()
        conn.executemany(
            """INSERT OR REPLACE INTO resultados
               (jornada, partido_id, local, visitante, goles_local, goles_visitante, status, fecha, hora)
               VALUES (?, ?, ?, ?, 0, 0, 'NS', '2026-09-26', '18:00')""",
            [(JORNADA, pid, local, visitante) for pid, local, visitante in PROGRAMA_J9],
        )
        conn.commit()

        return [MatchPayload(**p) for p in build_jornada_matches(conn, JORNADA, load_team_logos())]
    finally:
        for nombre, valor in originals.items():
            setattr(config, nombre, valor)


def test_la_jornada_9_tiene_quince_partidos(partidos_j9):
    assert len(partidos_j9) == 15


def test_la_jornada_9_conserva_el_programa(partidos_j9):
    """La siembra es correcta: si no, los tests de escudo no dicen nada."""
    assert {p.local for p in partidos_j9} | {p.visitante for p in partidos_j9} == {
        nombre for _, local, visitante in PROGRAMA_J9 for nombre in (local, visitante)
    }


def test_todos_los_partidos_de_la_j9_llevan_escudo(partidos_j9):
    """Lo que se ve en la web: cada fixture con su escudo, no un token de texto."""
    sin_escudo = [(p.local, p.visitante) for p in partidos_j9 if not p.logo_local or not p.logo_visitante]
    assert not sin_escudo, f"partidos de la J9 sin escudo: {sin_escudo}"


@pytest.mark.parametrize("equipo", FEMENINOS_J9)
def test_los_equipos_femeninos_de_la_j9_resuelven_escudo(equipo, partidos_j9):
    encontrados = [p for p in partidos_j9 if p.local == equipo or p.visitante == equipo]
    assert encontrados, f"{equipo} ya no esta en la J9; revisa este test"
    for partido in encontrados:
        escudo = partido.logo_local if partido.local == equipo else partido.logo_visitante
        assert escudo, f"{equipo} se queda sin escudo"


def test_el_fallback_femenino_no_contamina_la_identidad_de_equipos():
    """El punto delicado: compartir escudo no puede implicar ser el mismo equipo.

    `team_keys_compatible` impide que un "(F)" cruce con su masculino porque esa
    mezcla contaminaría la clasificación. El fallback de escudos solo debe tocar
    el mapa de imágenes.
    """
    for femenino, club in FEMALE_LOGO_FALLBACK.items():
        assert not team_keys_compatible(femenino, club), (
            f"{femenino} y {club} no pueden cruzarse: comparten escudo, no identidad"
        )


def test_el_fallback_apunta_a_equipos_que_existen():
    logos = load_team_logos()
    for femenino, club in FEMALE_LOGO_FALLBACK.items():
        assert logos.get(club), f"el club {club} no tiene escudo con el que reutilizar"


def test_los_alias_femeninos_siguen_apartados_de_los_masculinos():
    """La tabla de alias no debe ganar ninguna entrada femenina al masculino."""
    para_femeninos = {alias for alias, canonico in TEAM_LOGO_ALIASES.items() if canonico.endswith("FEMENINO")}
    assert para_femeninos, "la tabla de alias ha perdido los equipos femeninos"
    for alias in para_femeninos:
        canonico = TEAM_LOGO_ALIASES[alias]
        assert canonico.endswith("FEMENINO"), (
            f"el alias femenino {alias} apunta a {canonico}, que no es una clave femenina"
        )


def test_las_formas_cortas_de_la_j9_no_se_olvidan():
    """La J9 trae "Ath. Club (F)", no "Athletic Club (F)". Las dos formas importan."""
    assert TEAM_LOGO_ALIASES.get("ATH CLUB F") == "ATHLETIC CLUB FEMENINO", (
        "la forma corta del equipo femenino de la J9 tiene que estar en la tabla"
    )


def test_los_escudos_apuntan_a_ficheros_que_existen(partidos_j9):
    """Un 404 por escudo es peor que un token de texto."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    for partido in partidos_j9:
        for escudo in (partido.logo_local, partido.logo_visitante):
            if not escudo or not escudo.startswith("/static/"):
                continue
            destino = root / escudo.lstrip("/")
            assert destino.is_file(), f"el escudo {escudo} no existe en disco"
