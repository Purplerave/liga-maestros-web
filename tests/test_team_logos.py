"""Los escudos de la jornada activa deben salir de nuestro dominio.

Hotlinkear a quiniela15.com / highlightly.net deja huecos en la quiniela si el
tercero cambia la ruta o bloquea el referer, y filtra tráfico de los usuarios
a otro dominio. Además, varias claves normalizadas ni siquiera existían en
TEAM_LOGOS.json, así que la web pintaba el hueco directamente.
"""

import json
import os

import config
from liga_maestros.utils import normalize_team_key

LOGOS_PATH = os.path.join(config.SEED_DATA_DIR, "TEAM_LOGOS.json")
LOGO_DIR = os.path.join(config.BASE_DIR, "static", "img", "team_logos")

#: Equipos de la jornada publicada (J1 2026/27).
JORNADA_TEAMS = [
    "Alavés",
    "Getafe",
    "Sevilla",
    "Rayo Vallecano",
    "R. Santander",
    "Villarreal",
    "Espanyol",
    "Levante",
    "Celta",
    "Osasuna",
    "Andorra",
    "Ceuta",
    "Cádiz",
    "Real Oviedo",
    "Granada",
    "Mallorca",
    "Valladolid",
    "Eibar",
    "Burgos",
    "Córdoba",
    "Girona",
    "Leganés",
    "Las Palmas",
    "Albacete",
    "Sporting Gijón",
    "Deportivo",
    "Elche",
]

#: Escudos que siguen pendientes de descargar (necesitan red).
#: Deben ir bajando; no debe crecer.
KNOWN_REMOTE = {"CELTA FORTUNA", "SABADELL", "TENERIFE"}


def _logos():
    with open(LOGOS_PATH, encoding="utf-8") as handle:
        return json.load(handle)


def test_ningun_equipo_de_la_jornada_se_queda_sin_escudo():
    logos = _logos()
    missing = [team for team in JORNADA_TEAMS if not logos.get(normalize_team_key(team))]
    assert missing == [], f"Equipos sin escudo (se pintará un hueco): {missing}"


def test_los_escudos_de_la_jornada_no_son_hotlinks_externos():
    logos = _logos()
    external = [
        team
        for team in JORNADA_TEAMS
        if str(logos.get(normalize_team_key(team), "")).startswith("http")
        and normalize_team_key(team) not in KNOWN_REMOTE
    ]
    assert external == [], f"Escudos servidos desde un dominio ajeno: {external}"


def test_las_rutas_locales_de_la_jornada_existen_en_disco():
    logos = _logos()
    broken = []
    for team in JORNADA_TEAMS:
        url = str(logos.get(normalize_team_key(team), ""))
        if not url.startswith("/static/"):
            continue
        if not os.path.isfile(os.path.join(config.BASE_DIR, url.lstrip("/"))):
            broken.append((team, url))
    assert broken == [], f"Escudos que apuntan a ficheros inexistentes: {broken}"


def test_la_lista_de_pendientes_no_crece():
    """Si descargas los que faltan, reduce KNOWN_REMOTE. Nunca la amplíes."""
    assert len(KNOWN_REMOTE) <= 3
