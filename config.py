import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Directorio base del proyecto
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Base de Datos
DEFAULT_DB_PATH = os.path.join(BASE_DIR, "DATOS", "LIGA_MAESTROS_PRO.db")
DB_PATH = os.getenv("DB_PATH", DEFAULT_DB_PATH)

# Configuración Highlightly API
HIGHLIGHTLY_HOST = "soccer.highlightly.net"
HIGHLIGHTLY_RAPIDAPI_HOST = "football-highlights-api.p.rapidapi.com"
HIGHLIGHTLY_LEAGUES = {
    "LA LIGA": 119924,
    "SEGUNDA DIVISION": 120775,
    "PREMIER LEAGUE": 33973,
    "BUNDESLIGA": 67162,
    "LIGUE 1": 52695,
    "UEFA CHAMPIONS LEAGUE": 2486,
    "FRIENDLIES": 9294,
}

# API-FOOTBALL / API-SPORTS: respaldo puntual, no motor de directo.
API_FOOTBALL_HOST = os.getenv("API_FOOTBALL_HOST", "v3.football.api-sports.io")
API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY", "")
API_FOOTBALL_DAILY_LIMIT = int(os.getenv("API_FOOTBALL_DAILY_LIMIT", "100"))
API_FOOTBALL_DAILY_RESERVE = int(os.getenv("API_FOOTBALL_DAILY_RESERVE", "10"))

# Configuración Radar de Noticias
NEWS_CACHE_PATH = os.path.join(BASE_DIR, "data", "RADAR_NOTICIAS.json")
NEWS_REFRESH_SECONDS = int(os.getenv("NEWS_REFRESH_SECONDS", "900"))
NEWS_FEEDS = [
    {"id": "laliga", "name": "LALIGA", "url": "https://www.laliga.com/noticias?format=feed&type=rss"},
    {"id": "as", "name": "AS", "url": "https://as.com/rss-de-ascom-n/"},
    {"id": "mundo_deportivo", "name": "Mundo Deportivo", "url": "https://www.mundodeportivo.com/rss"},
    {"id": "sport", "name": "Sport", "url": "https://www.sport.es/es/rss/"},
    {"id": "marca", "name": "Marca", "url": "https://e00-marca.uecdn.es/rss/futbol.xml"},
]
NEWS_TEAM_KEYWORDS = [
    "real madrid", "barcelona", "barça", "atletico", "atlético", "athletic", "betis", "celta", "espanyol",
    "getafe", "girona", "mallorca", "osasuna", "rayo", "sevilla", "valencia", "villarreal", "alaves", "alavés",
    "oviedo", "malaga", "málaga", "ceuta", "huesca", "castellon", "castellón", "cordoba", "córdoba",
    "sporting", "almeria", "almería", "racing", "santander", "eibar", "cadiz", "cádiz", "levante", "elche"
]
NEWS_GENERIC_KEYWORDS = [
    "lesion", "lesión", "baja", "convocatoria", "alineacion", "alineación", "once", "rotacion", "rotación",
    "sancion", "sanción", "entrenador", "previa", "ultima hora", "última hora", "fichaje", "mercado", "fatiga"
]

# Alias de Equipos para Logos
TEAM_LOGO_ALIASES = {
    "ATHLETIC": "ATHLETIC CLUB",
    "FC BARCELONA": "BARCELONA",
    "BARCA": "BARCELONA",
    "VILLARREAL CF": "VILLARREAL",
    "AT MADRID": "ATLETICO MADRID",
    "ATLETICO MADRID": "ATLETICO MADRID",
    "ATLETICO DE MADRID": "ATLETICO MADRID",
    "BETIS": "REAL BETIS",
    "CELTA": "CELTA DE VIGO",
    "GETAFE CF": "GETAFE",
    "RAYO": "RAYO VALLECANO",
    "VALENCIA CF": "VALENCIA",
    "R SOCIEDAD": "REAL SOCIEDAD",
    "ELCHE CF": "ELCHE",
    "LEVANTE UD": "LEVANTE",
    "CA OSASUNA": "OSASUNA",
    "RCD MALLORCA": "MALLORCA",
    "GIRONA FC": "GIRONA",
    "REAL OVIEDO": "OVIEDO",
    "CEUTA": "AD CEUTA FC",
    "AD CEUTA": "AD CEUTA FC",
    "AD CEUTA FC": "AD CEUTA FC",
    "MALAGA": "MALAGA",
    "MALAGA CF": "MALAGA",
    "DEPORTIVO": "DEPORTIVO LA CORUNA",
    "DEPOR": "DEPORTIVO LA CORUNA",
    "RC DEPORTIVO": "DEPORTIVO LA CORUNA",
    "DEPORTIVO LA CORUNA": "DEPORTIVO LA CORUNA",
    "R ZARAGOZA": "ZARAGOZA",
    "REAL ZARAGOZA": "ZARAGOZA",
    "R SANTANDER": "RACING DE SANTANDER",
    "R RACING CLUB": "RACING DE SANTANDER",
    "RACING CLUB": "RACING DE SANTANDER",
    "CADIZ": "CADIZ",
    "CADIZ CF": "CADIZ",
    "SEVILLA": "SEVILLA FC",
    "ESPANYOL": "RCD ESPANYOL",
    "RCD ESPANYOL": "RCD ESPANYOL",
    "RCD ESPANYOL DE BARCELONA": "RCD ESPANYOL",
    "CELTA VIGO": "CELTA DE VIGO",
    "ALAVES": "ALAVES",
    "DEPORTIVO ALAVES": "ALAVES",
    "LAS PALMAS": "LAS PALMAS",
    "UD LAS PALMAS": "LAS PALMAS",
    "GRANADA CF": "GRANADA",
    "UD ALMERIA": "ALMERIA",
    "CD CASTELLON": "CASTELLON",
    "BURGOS CF": "BURGOS",
    "SD EIBAR": "EIBAR",
    "CORDOBA CF": "CORDOBA",
    "ALBACETE BP": "ALBACETE",
    "REAL SPORTING": "SPORTING GIJON",
    "REAL VALLADOLID CF": "VALLADOLID",
    "REAL VALLADOLID": "VALLADOLID",
    "VALLADOLID CF": "VALLADOLID",
    "CD LEGANES": "LEGANES",
    "CD MIRANDES": "MIRANDES",
    "SD HUESCA": "HUESCA",
    "CULTURAL Y DEPORTIVA LEONESA": "CULTURAL LEONESA",
    "C LEONESA": "CULTURAL LEONESA",
    "CULTURAL LEONESA": "CULTURAL LEONESA",
    "PSG": "PARIS SAINT GERMAIN",
    "PARIS SG": "PARIS SAINT GERMAIN",
    "PARIS SAINT-GERMAIN": "PARIS SAINT GERMAIN",
    "PARIS SAINT GERMAIN": "PARIS SAINT GERMAIN",
    "JAPON": "JAPAN",
    "JAPAN": "JAPAN",
    "ISLANDIA": "ICELAND",
    "ICELAND": "ICELAND",
    "MEXICO": "MEXICO",
    "AUSTRALIA": "AUSTRALIA",
    "ALEMANIA": "GERMANY",
    "GERMANY": "GERMANY",
    "FINLANDIA": "FINLAND",
    "FINLAND": "FINLAND",
    "BELGICA": "BELGICA",
    "BELGIUM": "BELGICA",
    "TUNEZ": "TUNEZ",
    "TUNISIA": "TUNEZ",
    "LITUANIA": "LITUANIA",
    "LITHUANIA": "LITUANIA",
    "LETONIA": "LETONIA",
    "LATVIA": "LETONIA",
    "ESTONIA": "ESTONIA",
    "ISLAS FEROE": "ISLAS FEROE",
    "FAROE ISLANDS": "ISLAS FEROE",
    "FAROE": "ISLAS FEROE",
    "PORTUGAL": "PORTUGAL",
    "CHILE": "CHILE",
    "RUMANIA": "RUMANIA",
    "ROMANIA": "RUMANIA",
    "GALES": "GALES",
    "WALES": "GALES",
    "INGLATERRA": "INGLATERRA",
    "ENGLAND": "INGLATERRA",
    "NUEVA ZELANDA": "NUEVA ZELANDA",
    "NEW ZEALAND": "NUEVA ZELANDA",
    "SUIZA": "SUIZA",
    "SWITZERLAND": "SUIZA",
    "BOLIVIA": "BOLIVIA",
    "ESCOCIA": "ESCOCIA",
    "SCOTLAND": "ESCOCIA",
    "LIECHTENSTEIN": "LIECHTENSTEIN",
    "CHIPRE": "CHIPRE",
    "CYPRUS": "CHIPRE",
    "DINAMARCA": "DINAMARCA",
    "DENMARK": "DINAMARCA",
    "UCRANIA": "UCRANIA",
    "UKRAINE": "UCRANIA",
    "CROACIA": "CROACIA",
    "CROATIA": "CROACIA",
    "ESLOVENIA": "ESLOVENIA",
    "SLOVENIA": "ESLOVENIA",
    "MARRUECOS": "MARRUECOS",
    "MOROCCO": "MARRUECOS",
    "NORUEGA": "NORUEGA",
    "NORWAY": "NORUEGA",
    "GRECIA": "GRECIA",
    "GREECE": "GRECIA",
    "ITALIA": "ITALIA",
    "ITALY": "ITALIA",
    "REAL SOCIEDAD B": "REAL SOCIEDAD B",
    "R SOCIEDAD B": "REAL SOCIEDAD B",
    "R. SOCIEDAD B": "REAL SOCIEDAD B",
    "REAL SPORTING DE GIJON": "SPORTING GIJON",
    "SPORTING DE GIJON": "SPORTING GIJON",
    "FC ANDORRA": "ANDORRA",
    "RACING SANTANDER": "RACING DE SANTANDER",
    "RACING DE SANTANDER": "RACING DE SANTANDER",
    "SANTANDER": "RACING DE SANTANDER",
}

# Configuración Google OAuth
GOOGLE_SERVER_METADATA_URL = 'https://accounts.google.com/.well-known/openid-configuration'
GOOGLE_CLIENT_KWARGS = {'scope': 'openid email profile'}
