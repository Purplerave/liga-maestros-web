"""Team aliases and standings leagues."""

# Canonical logos keyed by cleaned team name (see utils.clean_team_key).
# This mapping is intentionally deduplicated: every key maps to exactly one
# canonical value and there are no redundant entries.
TEAM_LOGO_ALIASES = {
    # LaLiga / Spain
    "ATHLETIC BILBAO": "ATHLETIC CLUB",
    "ATHLETIC": "ATHLETIC CLUB",
    "ATH CLUB": "ATHLETIC CLUB",
    "REAL BETIS BALOMPIE": "REAL BETIS",
    "BETIS": "REAL BETIS",
    "CELTA FORTUNA": "CELTA FORTUNA",
    "CELTA VIGO": "CELTA DE VIGO",
    "CELTA": "CELTA DE VIGO",
    "RC CELTA FORTUNA": "CELTA FORTUNA",
    "CELTA B": "CELTA FORTUNA",
    "CELTA II": "CELTA FORTUNA",
    "CELTA VIGO B": "CELTA FORTUNA",
    "CELTA VIGO II": "CELTA FORTUNA",
    "CELTA DE VIGO B": "CELTA FORTUNA",
    "CELTA DE VIGO II": "CELTA FORTUNA",
    "DEPORTIVO": "DEPORTIVO LA CORUNA",
    "DEPOR": "DEPORTIVO LA CORUNA",
    "RC DEPORTIVO": "DEPORTIVO LA CORUNA",
    "DEPORTIVO LA CORUNA": "DEPORTIVO LA CORUNA",
    "FC BARCELONA": "BARCELONA",
    "BARCA": "BARCELONA",
    "GETAFE CF": "GETAFE",
    "GIRONA FC": "GIRONA",
    "AD CEUTA": "AD CEUTA FC",
    "CEUTA": "AD CEUTA FC",
    "AGRUPACION DEPORTIVA CEUTA": "AD CEUTA FC",
    "MALAGA": "MALAGA",
    "MALAGA CF": "MALAGA",
    "R ZARAGOZA": "ZARAGOZA",
    "REAL ZARAGOZA": "ZARAGOZA",
    "R SANTANDER": "RACING DE SANTANDER",
    "R RACING CLUB": "RACING DE SANTANDER",
    "RACING CLUB": "RACING DE SANTANDER",
    "RACING SANTANDER": "RACING DE SANTANDER",
    "SANTANDER": "RACING DE SANTANDER",
    "REAL RACING CLUB": "RACING DE SANTANDER",
    # "Racing" a secas es como lo escribe la quiniela15 en la J17; la forma
    # larga ("Racing Santander") en la J4. Sin el alias corto la fila del
    # boleto no cruzaba con el directo (R. Racing Club vs Real Madrid).
    "RACING": "RACING DE SANTANDER",
    "CADIZ": "CADIZ",
    "CADIZ CF": "CADIZ",
    "SEVILLA": "SEVILLA FC",
    "ESPANYOL": "RCD ESPANYOL",
    "ESPANYOL DE BARCELONA": "RCD ESPANYOL",
    "RCD ESPANYOL": "RCD ESPANYOL",
    "RCD ESPANYOL DE BARCELONA": "RCD ESPANYOL",
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
    "ALBACETE BALOMPIE": "ALBACETE",
    "REAL SPORTING": "SPORTING GIJON",
    "REAL SPORTING DE GIJON": "SPORTING GIJON",
    "REAL SPORTING GIJON": "SPORTING GIJON",
    "SPORTING DE GIJON": "SPORTING GIJON",
    # La quiniela publica "Sporting"/"Sporting Gijon" para el filial asturiano;
    # sin estas dos claves el cruce con el proveedor fallaba y el partido
    # quedaba para siempre sin resultado (J4 2026/27, Sporting - Girona).
    "SPORTING": "SPORTING GIJON",
    "SPORTING GIJON": "SPORTING GIJON",
    "REAL VALLADOLID CF": "VALLADOLID",
    "REAL VALLADOLID": "VALLADOLID",
    "VALLADOLID CF": "VALLADOLID",
    # La quiniela publica "Valladolid" y el boleto importa "R. Valladolid":
    # sin esta clave el cruce del resultado se descartaba (J6 2026/27,
    # R. Valladolid - R. Oviedo).
    "R VALLADOLID": "VALLADOLID",
    "CD LEGANES": "LEGANES",
    "CD MIRANDES": "MIRANDES",
    "SD HUESCA": "HUESCA",
    "CULTURAL Y DEPORTIVA LEONESA": "CULTURAL LEONESA",
    "C LEONESA": "CULTURAL LEONESA",
    "CULTURAL LEONESA": "CULTURAL LEONESA",
    "R OVIEDO": "OVIEDO",
    "REAL OVIEDO": "OVIEDO",
    "AT MADRID": "ATLETICO MADRID",
    "ATLETICO MADRID": "ATLETICO MADRID",
    "ATLETICO DE MADRID": "ATLETICO MADRID",
    # La quiniela15 alterna las dos grafias segun la jornada ("At. Madrid" en
    # la J2/J3/J4, "Atletico" a secas en la J17). Sin esta clave la fila que el
    # boleto guarda como "Atletico" nunca cruzaba con "At. Madrid" del directo
    # y el partido se quedaba sin resultado toda la jornada.
    "ATLETICO": "ATLETICO MADRID",
    "R MADRID": "REAL MADRID",
    "REAL MADRID": "REAL MADRID",
    "R SOCIEDAD": "REAL SOCIEDAD",
    "ELCHE CF": "ELCHE",
    "LEVANTE UD": "LEVANTE",
    "CA OSASUNA": "OSASUNA",
    "RCD MALLORCA": "MALLORCA",
    "VILLARREAL CF": "VILLARREAL",
    "RAYO": "RAYO VALLECANO",
    "VALENCIA CF": "VALENCIA",
    "FC ANDORRA": "ANDORRA",
    "CD TENERIFE": "TENERIFE",
    "TENERIFE": "TENERIFE",
    "CD ELDENSE": "ELDENSE",
    "ELDENSE": "ELDENSE",
    "CE SABADELL": "SABADELL",
    "CD SABADELL": "SABADELL",
    "SABADELL": "SABADELL",
    # England
    "COVENTRY": "COVENTRY CITY",
    "COVENTRY CITY": "COVENTRY CITY",
    "IPSWICH": "IPSWICH TOWN",
    "IPSWICH TOWN": "IPSWICH TOWN",
    "HULL": "HULL CITY",
    "HULL CITY": "HULL CITY",
    # Germany
    "SCHALKE": "SCHALKE 04",
    "SCHALKE 04": "SCHALKE 04",
    "ELVERSBERG": "SV ELVERSBERG",
    "SV ELVERSBERG": "SV ELVERSBERG",
    "PADERBORN": "SC PADERBORN",
    "SC PADERBORN": "SC PADERBORN",
    "SC PADERBORN 07": "SC PADERBORN",
    "HALMSTAD": "HALMSTADS",
    "IFK GOTEBORG": "GOTEBORG",
    "GOTEBORG": "GOTEBORG",
    "KALMAR FF": "KALMAR",
    "ORGRYTE IS": "ORGRYTE",
    "ORGRYTE": "ORGRYTE",
    "VASTERAS SK FK": "VASTERAS",
    "VASTERAS SK": "VASTERAS",
    "MALMOE": "MALMO",
    "MALMO FF": "MALMO",
    "DEGERFORS IF": "DEGERFORS",
    # France / misc clubs
    "TROYES": "TROYES",
    "LE MANS": "LE MANS",
    "PSG": "PARIS SAINT GERMAIN",
    "PARIS SG": "PARIS SAINT GERMAIN",
    "PARIS SAINT-GERMAIN": "PARIS SAINT GERMAIN",
    "PARIS SAINT GERMAIN": "PARIS SAINT GERMAIN",
    # Countries / international
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
    # La quiniela publica "Ferencvarosi" (nombre completo hungaro) y el boleto
    # trae "Ferencvaros": sin este alias el cruce Q15<->BD fallaba y el partido
    # J7#12 no se actualizaba solo (false negative del matcher).
    "FERENCVAROSI": "FERENCVAROS",
    # El directo Q15 escribe "R. Checa" y el boleto "Republica Checa": el pleno
    # al 15 no cruzaba nunca y solo entraba por JSON manual.
    "R CHECA": "REPUBLICA CHECA",
    "REP CHECA": "REPUBLICA CHECA",
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
    "TURKU PS": "TPS",
    "TPS TURKUTP": "TPS",
    "TPS TURKU": "TPS",
    "VAASA PS": "VPS",
    "VPS VAASA": "VPS",
    "VAASAN PALLOSEURA": "VPS",
    "ILVES TAMPERE": "ILVES",
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
    "REAL SOCIEDAD II": "REAL SOCIEDAD B",
    "R SOCIEDAD II": "REAL SOCIEDAD B",
    # Liga F / Femenina - canonical forms
    "ATHLETIC CLUB F": "ATHLETIC CLUB FEMENINO",
    # "Ath. Club (F)" es como lo llama la J9. Su forma corta no estaba, y la
    # masculina si ("ATH CLUB" -> "ATHLETIC CLUB"), asi que se quedaba sin escudo.
    "ATH CLUB F": "ATHLETIC CLUB FEMENINO",
    "ATHLETIC CLUB FEMENINO": "ATHLETIC CLUB FEMENINO",
    "ATHLETIC CLUB WOMEN": "ATHLETIC CLUB FEMENINO",
    "ATHLETIC FEMENINO": "ATHLETIC CLUB FEMENINO",
    # El proveedor publica el nombre completo ("Athletic Bilbao Femenino") y el
    # boleto lo abrevia ("Athletic (F)"): sin alias quedaba sin resultado y sin
    # escudo en la J17.
    "ATHLETIC BILBAO FEMENINO": "ATHLETIC CLUB FEMENINO",
    "ATHLETIC CLUB BILBAO FEMENINO": "ATHLETIC CLUB FEMENINO",
    "EIBAR F": "EIBAR FEMENINO",
    "SD EIBAR F": "EIBAR FEMENINO",
    "EIBAR FEMENINO": "EIBAR FEMENINO",
    "EIBAR WOMEN": "EIBAR FEMENINO",
    "ESPANYOL F": "ESPANYOL FEMENINO",
    "RCD ESPANYOL F": "ESPANYOL FEMENINO",
    "ESPANYOL FEMENINO": "ESPANYOL FEMENINO",
    "RCD ESPANYOL FEMENINO": "ESPANYOL FEMENINO",
    "ESPANYOL WOMEN": "ESPANYOL FEMENINO",
    "VALENCIA F": "VALENCIA FEMENINO",
    "VALENCIA CF F": "VALENCIA FEMENINO",
    "VALENCIA FEMENINO": "VALENCIA FEMENINO",
    "VCF FEMENINO": "VALENCIA FEMENINO",
    "VALENCIA WOMEN": "VALENCIA FEMENINO",
    "REAL MADRID F": "REAL MADRID FEMENINO",
    # La quiniela15 abrevia "Real Madrid (F)" como "R. Madrid (F)" en la J17 y
    # "R. Sociedad (F)" en la J11/J17. "R MADRID" ya existia (masculino) pero
    # la forma femenina se quedaba en "R MADRID F", una clave que no publicaba
    # nadie: los dos partidos de Liga F no cruzaban con el directo ni tenian
    # escudo.
    "R MADRID F": "REAL MADRID FEMENINO",
    "R SOCIEDAD F": "REAL SOCIEDAD FEMENINO",
    "REAL MADRID CF F": "REAL MADRID FEMENINO",
    "REAL MADRID FEMENINO": "REAL MADRID FEMENINO",
    "REAL MADRID WOMEN": "REAL MADRID FEMENINO",
    "AT MADRID F": "ATLETICO MADRID FEMENINO",
    "ATLETICO MADRID F": "ATLETICO MADRID FEMENINO",
    "AT MADRID FEMENINO": "ATLETICO MADRID FEMENINO",
    "ATLETICO MADRID FEMENINO": "ATLETICO MADRID FEMENINO",
    "ATLETICO DE MADRID FEMENINO": "ATLETICO MADRID FEMENINO",
    "ATLETICO DE MADRID F": "ATLETICO MADRID FEMENINO",
    "ATLETICO MADRID WOMEN": "ATLETICO MADRID FEMENINO",
    "ALAVES F": "ALAVES FEMENINO",
    "DEPORTIVO ALAVES F": "ALAVES FEMENINO",
    "ALAVES FEMENINO": "ALAVES FEMENINO",
    "DEPORTIVO ALAVES FEMENINO": "ALAVES FEMENINO",
    "ALAVES WOMEN": "ALAVES FEMENINO",
    "LAS PLANAS": "LEVANTE LAS PLANAS",
    "LAS PLANAS F": "LEVANTE LAS PLANAS",
    "LEVANTE LAS PLANAS": "LEVANTE LAS PLANAS",
    "LEVANTE LAS PLANAS F": "LEVANTE LAS PLANAS",
    "LEVANTE LAS PLANAS FEMENINO": "LEVANTE LAS PLANAS",
    "LEVANTE LAS PLANAS WOMEN": "LEVANTE LAS PLANAS",
    "LEVANTE BADALONA": "LEVANTE LAS PLANAS",
    "LEVANTE BADALONA F": "LEVANTE LAS PLANAS",
    "FC BADALONA WOMEN": "LEVANTE LAS PLANAS",
    "BADALONA WOMEN": "LEVANTE LAS PLANAS",
    # El proveedor ingles nombra al club "Badalona W." y el boleto lo importa
    # tal cual; la quiniela publica "Las Planas (F)". Sin estas claves el
    # resultado del partido nunca cruzaba (J6 2026/27, Eibar (F) - Badalona W.).
    "BADALONA W": "LEVANTE LAS PLANAS",
    "BADALONA W F": "LEVANTE LAS PLANAS",
    "BADALONA W FEMENINO": "LEVANTE LAS PLANAS",
    "SEVILLA F": "SEVILLA FEMENINO",
    "SEVILLA FC F": "SEVILLA FEMENINO",
    "SEVILLA FEMENINO": "SEVILLA FEMENINO",
    "GRANADA F": "GRANADA FEMENINO",
    "GRANADA CF F": "GRANADA FEMENINO",
    "GRANADA FEMENINO": "GRANADA FEMENINO",
    "MADRID CFF": "MADRID CFF",
    "MADRID CFF F": "MADRID CFF",
    "REAL SOCIEDAD F": "REAL SOCIEDAD FEMENINO",
    "REAL SOCIEDAD FEMENINO": "REAL SOCIEDAD FEMENINO",
    "REAL SOCIEDAD WOMEN": "REAL SOCIEDAD FEMENINO",
    "COSTA ADEJE TENERIFE": "COSTA ADEJE TENERIFE",
    # El proveedor y el calendario llaman "UD Tenerife" (y "Tenerife (F)" al
    # equipo de Liga F) al mismo club; el masculino canoniza como "TENERIFE".
    # Solo se cruzan entre si (ambos llevan marcador femenino), nunca con el
    # Tenerife masculino.
    "UD TENERIFE": "COSTA ADEJE TENERIFE",
    "UD TENERIFE F": "COSTA ADEJE TENERIFE",
    "UD TENERIFE FEMENINO": "COSTA ADEJE TENERIFE",
    "TENERIFE FEMENINO": "COSTA ADEJE TENERIFE",
    "COSTA ADEJE TENERIFE FEMENINO": "COSTA ADEJE TENERIFE",
    "DEPORTIVO ABANCA": "DEPORTIVO ABANCA",
    "DEPORTIVO FEMENINO": "DEPORTIVO ABANCA",
    "DEPORTIVO DE LA CORUNA WOMEN": "DEPORTIVO ABANCA",
    # El calendario/el proveedor a veces publica el nombre largo con el
    # marcador femenino pegado ("Deportivo de La Coruna Femenino"). Antes
    # canonizaba distinto que "Deportivo (F)" del boleto.
    "DEPORTIVO DE LA CORUNA FEMENINO": "DEPORTIVO ABANCA",
    "DEPORTIVO DE LA CORUNA F": "DEPORTIVO ABANCA",
    "DEPORTIVO CORUNA FEMENINO": "DEPORTIVO ABANCA",
    "LOGROÑO UNITED": "LOGRONO UNITED F",
    "LOGRONO UNITED": "LOGRONO UNITED F",
    "LOGRONO UNITED F": "LOGRONO UNITED F",
    "LOGRONO UNITED FEMENINO": "LOGRONO UNITED F",
    "DUX LOGRONO": "LOGRONO UNITED F",
    "DUX LOGRONO F": "LOGRONO UNITED F",
    # La quiniela llama "Edf Logrono" al club que el boleto trae como
    # "Logrono United (F)": el canonico lleva la F para que ambas orillas
    # queden en "LOGRONO UNITED F" (la igualdad gana antes de mirar el
    # genero, y Q15 no marca este equipo como femenino).
    "EDF LOGRONO": "LOGRONO UNITED F",
    "EDF LOGRONO F": "LOGRONO UNITED F",
    "EDF LOGRONO FEMENINO": "LOGRONO UNITED F",
    "LOGRONO": "LOGRONO UNITED F",
    "LOGRONO F": "LOGRONO UNITED F",
    "LOGRONO FEMENINO": "LOGRONO UNITED F",
    # Barca femenino: "Barcelona (F)" quedaba en "BARCELONA F" sin canonico y
    # no cruzaba con "Barcelona Femenino" del proveedor.
    "BARCELONA F": "BARCELONA FEMENINO",
    "BARCELONA FEMENINO": "BARCELONA FEMENINO",
    "FC BARCELONA F": "BARCELONA FEMENINO",
    "FC BARCELONA FEMENINO": "BARCELONA FEMENINO",
    "BARCELONA WOMEN": "BARCELONA FEMENINO",
}

# Nombres que solo existen en femenino aunque quien los escribe no ponga el
# marcador de genero: el proveedor llama "UD Tenerife" al Costa Adeje Tenerife
# de Liga F y "Athletic Bilbao Femenino" al Athletic Club. Hasta ahora "UD
# Tenerife" canonizaba como el TENERIFE masculino, asi que un nombre de Liga F
# podia casar (o descartar) con el equipo masculino por accidente. Estas claves
# se tratan como femeninas en ``_is_feminine_raw`` y su canonico es siempre el
# del equipo femenino: el cruce masculino <-> femenino sigue cerrado.
FEMININE_TEAM_KEYS = frozenset(
    {
        "UD TENERIFE",
        "UD TENERIFE F",
        "UD TENERIFE FEMENINO",
        # Ojo: "ATHLETIC BILBAO" a secas NO entra aqui, que ya canoniza al
        # Athletic masculino en TEAM_LOGO_ALIASES.
        "ATHLETIC BILBAO F",
        "ATHLETIC BILBAO FEMENINO",
        "ATHLETIC CLUB BILBAO",
        "ATHLETIC CLUB BILBAO FEMENINO",
    }
)

# Leagues shown in standings tabs.
STANDINGS_LEAGUES = {
    "PREMIER LEAGUE": 33973,
    "BUNDESLIGA": 67162,
    "LIGUE 1": 52695,
}
