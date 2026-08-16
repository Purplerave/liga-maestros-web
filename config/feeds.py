"""News radar configuration."""

import os

from . import DATA_DIR

NEWS_CACHE_PATH = os.path.join(DATA_DIR, "RADAR_NOTICIAS.json")
NEWS_REFRESH_SECONDS = int(os.getenv("NEWS_REFRESH_SECONDS", "900"))

NEWS_FEEDS = [
    {"id": "laliga", "name": "LALIGA", "url": "https://www.laliga.com/noticias?format=feed&type=rss"},
    {"id": "as", "name": "AS", "url": "https://as.com/rss-de-ascom-n/"},
    {"id": "mundo_deportivo", "name": "Mundo Deportivo", "url": "https://www.mundodeportivo.com/rss"},
    {"id": "sport", "name": "Sport", "url": "https://www.sport.es/es/rss/"},
    {"id": "marca", "name": "Marca", "url": "https://e00-marca.uecdn.es/rss/futbol.xml"},
]

NEWS_TEAM_KEYWORDS = [
    "real madrid",
    "barcelona",
    "barça",
    "atletico",
    "atlético",
    "athletic",
    "betis",
    "celta",
    "espanyol",
    "getafe",
    "girona",
    "mallorca",
    "osasuna",
    "rayo",
    "sevilla",
    "valencia",
    "villarreal",
    "alaves",
    "alavés",
    "oviedo",
    "malaga",
    "málaga",
    "ceuta",
    "huesca",
    "castellon",
    "castellón",
    "cordoba",
    "córdoba",
    "sporting",
    "almeria",
    "almería",
    "racing",
    "santander",
    "eibar",
    "cadiz",
    "cádiz",
    "levante",
    "elche",
    "tenerife",
    "eldense",
    "sabadell",
    "fortuna",
    "deportivo",
]

NEWS_GENERIC_KEYWORDS = [
    "lesion",
    "lesión",
    "baja",
    "convocatoria",
    "alineacion",
    "alineación",
    "once",
    "rotacion",
    "rotación",
    "sancion",
    "sanción",
    "entrenador",
    "previa",
    "ultima hora",
    "última hora",
    "fichaje",
    "mercado",
    "fatiga",
]
