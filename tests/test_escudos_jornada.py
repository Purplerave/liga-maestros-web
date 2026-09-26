"""Cobertura de escudos por jornada, de extremo a extremo.

La cadena tiene tres eslabones y los tres se rompiaron a la vez:

1. `matches.py:213` emitía `logo_local`/`logo_visitante` calculados.
2. `MatchPayload` no los declaraba y `_StrictBase` va con `extra="ignore"`, así
   que se descartaban al serializar. J9 llegaba a producción con 0 de 15.
3. `load_team_logos()` no aplicaba `TEAM_LOGO_ALIASES`, de modo que las variantes
   femeninas no llegaban al escudo del club aunque el fichero estuviera en disco.

Aquí se comprueba el resultado sobre una jornada real, que es donde se ven los
agujeros: no basta con que el mapa tenga la clave.
"""

import pytest

from liga_maestros.schemas import MatchPayload
from liga_maestros.services.payloads.matches import build_jornada_matches
from liga_maestros.utils import FEMALE_LOGO_FALLBACK, TEAM_LOGO_ALIASES, load_team_logos, team_keys_compatible

# Los cuatro equipos femeninos que entran en la J9 con la forma que trae la fuente.
FEMENINOS_J9 = ["Ath. Club (F)", "At. Madrid (F)", "Deportivo (F)", "Espanyol (F)"]


@pytest.fixture(scope="module")
def partidos_j9():
    from liga_maestros.db import get_db

    conn = get_db()
    return [MatchPayload(**p) for p in build_jornada_matches(conn, 9, load_team_logos())]


def test_la_jornada_9_tiene_quince_partidos(partidos_j9):
    assert len(partidos_j9) == 15


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
    """La tabla de alias no debe gainedear ninguna entrada femenina al masculino."""
    para_femeninos = {alias for alias, canonico in TEAM_LOGO_ALIASES.items() if canonico.endswith("FEMENINO")}
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
