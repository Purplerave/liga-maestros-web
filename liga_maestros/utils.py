"""Liga de Maestros - utilities.

This module owns the canonical implementations. The root ``utils.py`` shim
re-exports these symbols so existing scripts and tests do not break during
the cleanup of the repository root.
"""

import json
import os
import re
import unicodedata
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from config import BASE_DIR, DATA_DIR, NEWS_GENERIC_KEYWORDS, NEWS_TEAM_KEYWORDS, TEAM_LOGO_ALIASES

# Unico huso que se muestra al usuario. El servidor (Alwaysdata/Render) corre en
# UTC, asi que toda hora que se pinta o se compara pasa por aqui; fiarse de
# ``datetime.now()`` o de un ``strptime`` que no sepa de donde viene el texto es
# lo que hacia aparecer los partidos con el saque 1-2 horas adelantado.
MADRID_TZ = ZoneInfo("Europe/Madrid")
UTC_TZ = ZoneInfo("UTC")

_DATE_ONLY_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y")
_DATETIME_ONLY_FORMATS = ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S")


def madrid_now():
    """Reloj de Madrid con zona: la unica referencia temporal valida en la app."""
    return datetime.now(MADRID_TZ)


def madrid_today():
    return madrid_now().strftime("%Y-%m-%d")


def to_madrid_naive(value):
    """Devuelve ``value`` como reloj de pared de Madrid sin zona (naive).

    Acepta texto ISO con o sin sufijo ``Z``, texto con offset, texto sin zona (que
    por contrato del proyecto ya es hora de Madrid) y epoch en segundos o
    milisegundos.
    """
    if isinstance(value, datetime):
        dt = value
    else:
        dt = parse_provider_datetime(value)
        if dt is None:
            return None
        return dt
    if dt.tzinfo is not None:
        dt = dt.astimezone(MADRID_TZ).replace(tzinfo=None)
    return dt


def parse_provider_datetime(value):
    """Interpreta la marca de tiempo de un proveedor y la pasa a hora de Madrid.

    Highlightly devuelve SIEMPRE UTC (``2026-09-05T19:00:00.000Z``) y solo el
    parametro ``timezone`` de la query cambia a que dia pertenecen los partidos.
    Las variantes sin milisegundos (``...T19:00:00Z``) o con offset hacian fallar
    al ``strptime`` con ``.%fZ`` y el ``except`` devolvia el texto crudo en UTC:
    el partido de las 21:00 se pintaba a las 19:00 y, en los saques tardios del
    finde, hasta cambiaba de dia. Aqui se normaliza y se reconvierte siempre.
    """
    if isinstance(value, datetime):
        dt = value
    else:
        raw = str(value or "").strip()
        if not raw:
            return None
        if re.fullmatch(r"\d{9,13}", raw):
            # Epoch en segundos o milisegundos.
            seconds = int(raw) / 1000.0 if len(raw) >= 13 else float(raw)
            try:
                return datetime.fromtimestamp(seconds, MADRID_TZ).astimezone(MADRID_TZ).replace(tzinfo=None)
            except (OverflowError, OSError, ValueError):
                return None
        normalized = raw.replace("Z", "+00:00") if raw.endswith("Z") else raw
        dt = None
        try:
            dt = datetime.fromisoformat(normalized)
        except ValueError:
            for fmt in _DATETIME_ONLY_FORMATS + _DATE_ONLY_FORMATS:
                try:
                    dt = datetime.strptime(raw[:19], fmt)
                    break
                except ValueError:
                    continue
        if dt is None:
            return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(MADRID_TZ)
    return dt.replace(tzinfo=None)


def kickoff_datetime(match):
    """Inicio real (reloj de Madrid, naive) de un partido de cualquier payload.

    Vale tanto para filas de la quiniela (``fecha_raw`` + ``hora``) como para
    entradas del panel externo (``added``/``scheduled``/``date``). Devuelve None
    solo cuando de verdad no hay horario conocido: un horario desconocido nunca
    debe inventarse (inventarlo es lo que daba por muerto un directo en juego).
    """
    return parse_any_match_datetime(match)


def kickoff_date_text(match):
    """Dia (YYYY-MM-DD, hora de Madrid) del saque de un partido, o cadena vacia."""
    if not match:
        return ""
    dt = kickoff_datetime(match)
    if dt is not None:
        return dt.strftime("%Y-%m-%d")
    for key in ("fecha_raw", "added"):
        text = str(match.get(key) or "").strip()
        if len(text) >= 10 and text[4] in "-/":
            return text[:10]
    return ""


def day_span_centered_on(today_text, days_before=1, days_after=1):
    """Ventana de fechas [hoy - dias_before, hoy + dias_after] como textos ISO.

    Los findes de semana el partido del sabado sigue vivo a las 00:30 del domingo
    y sus resultados se consultan el lunes: comparar el texto de la fecha contra
    el dia exacto es lo que hacia desaparecer esos partidos del directo.
    """
    try:
        base = datetime.strptime(str(today_text or "")[:10], "%Y-%m-%d")
    except (TypeError, ValueError):
        base = datetime.now(MADRID_TZ)
    start = (base - timedelta(days=max(0, int(days_before)))).strftime("%Y-%m-%d")
    end = (base + timedelta(days=max(0, int(days_after)))).strftime("%Y-%m-%d")
    return start, end


def runtime_data_path(*parts):
    path = os.path.join(DATA_DIR, *parts)
    if os.path.exists(path):
        return path
    return os.path.join(BASE_DIR, "data", *parts)


LATIN_TRANSLIT = {
    "Ø": "O",
    "ø": "o",
    "Æ": "AE",
    "æ": "ae",
    "ß": "SS",
    "Ð": "D",
    "ð": "d",
    "Þ": "TH",
    "þ": "th",
    "Ł": "L",
    "ł": "l",
    "Đ": "D",
    "đ": "d",
    "Ŋ": "N",
    "ŋ": "n",
    "Œ": "OE",
    "œ": "oe",
}


def clean_team_key(value):
    text = str(value or "").upper()
    text = "".join(LATIN_TRANSLIT.get(ch, ch) for ch in text)
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    # Preserve women's marker (F) before stripping punctuation
    text = re.sub(r"\(F\)", " F ", text)
    text = re.sub(r"[^A-Z0-9]+", " ", text).strip()
    text = re.sub(r"\b(F C|FC|C F|CF|S A D|SAD|R C D|RCD|C D|CD|U D|UD|S D|SD)\b", "", text).strip()
    text = re.sub(r"\s+", " ", text)
    return text


def _is_feminine_raw(value):
    raw = str(value or "").upper()
    if "(F)" in raw:
        return True
    if "FEMENINO" in raw or "FEMENINA" in raw or " WOMEN" in raw:
        return True
    return False


def normalize_team_key(value):
    text = clean_team_key(value)
    # Direct alias
    if text in TEAM_LOGO_ALIASES:
        return TEAM_LOGO_ALIASES[text]

    raw_upper = str(value or "").upper()
    if _is_feminine_raw(raw_upper):
        # Try F variant
        candidate_f = f"{text} F".strip() if not text.endswith(" F") else text
        if candidate_f in TEAM_LOGO_ALIASES:
            return TEAM_LOGO_ALIASES[candidate_f]
        candidate_fem = f"{text} FEMENINO".strip()
        if " FEMENINO" not in text and candidate_fem in TEAM_LOGO_ALIASES:
            return TEAM_LOGO_ALIASES[candidate_fem]
        # Base without F
        base = text[:-2].strip() if text.endswith(" F") else text
        if base.endswith(" FEMENINO"):
            base = base[: -len(" FEMENINO")].strip()
        # Special handling for Las Planas / Badalona
        if base in ("LAS PLANAS", "LEVANTE LAS PLANAS", "LEVANTE BADALONA", "BADALONA", "FC BADALONA"):
            return TEAM_LOGO_ALIASES.get("LEVANTE LAS PLANAS", "LEVANTE LAS PLANAS")
        fem_candidate = f"{base} FEMENINO"
        if fem_candidate in TEAM_LOGO_ALIASES.values() or fem_candidate in TEAM_LOGO_ALIASES:
            return TEAM_LOGO_ALIASES.get(fem_candidate, fem_candidate)
        if base == "ALAVES":
            if "(F)" in raw_upper or "FEMENINO" in raw_upper:
                return TEAM_LOGO_ALIASES.get("ALAVES FEMENINO", "ALAVES FEMENINO")

    return TEAM_LOGO_ALIASES.get(text, text)


def short_team_name(value):
    key = normalize_team_key(value)
    names = {
        "ATLETICO MADRID": "AT. MADRID",
        "REAL MADRID": "R. MADRID",
        "BARCELONA": "BARCA",
        "REAL SOCIEDAD": "R. SOC.",
        "REAL BETIS": "BETIS",
        "DEPORTIVO LA CORUNA": "DEPOR",
        "RACING DE SANTANDER": "RACING",
        "RACING SANTANDER": "RACING",
        "CULTURAL LEONESA": "C. LEONESA",
        "SPORTING GIJON": "SPORTING",
        "COSTA DE MARFIL": "C. MARFIL",
        "COREA DEL SUR": "C. SUR",
        "REPUBLICA CHECA": "R. CHECA",
    }
    if key in names:
        return names[key]
    cleaned = re.sub(
        r"\b(REAL|CLUB|FC|CF|RC|RCD|CD|UD|SD|SAD|BALOMPIE|DEPORTIVO)\b",
        "",
        key,
    ).strip()
    return re.sub(r"\s+", " ", cleaned or key)[:18]


def team_token(value):
    short = short_team_name(value)
    token = re.sub(r"[^A-Z0-9]", "", clean_team_key(short))
    return token[:2] or "--"


def load_team_logos():
    logos_path = runtime_data_path("TEAM_LOGOS.json")
    manifest_path = os.path.join(BASE_DIR, "static", "img", "team_logos", "manifest.json")
    logos = {}
    try:
        if os.path.exists(logos_path):
            with open(logos_path, encoding="utf-8") as fh:
                raw = json.load(fh)
            logos.update({normalize_team_key(name): logo for name, logo in raw.items()})
        if os.path.exists(manifest_path):
            with open(manifest_path, encoding="utf-8") as fh:
                manifest = json.load(fh)
            for name, rel_path in manifest.items():
                url = str(rel_path or "").replace("\\", "/").lstrip("/")
                if not url.startswith("static/"):
                    url = f"static/{url}"
                logos[normalize_team_key(name)] = f"/{url}"
        return logos
    except Exception:
        return logos


def build_team_contract():
    logos = load_team_logos()
    aliases = {clean_team_key(k): normalize_team_key(v) for k, v in TEAM_LOGO_ALIASES.items()}
    keys = set(logos.keys()) | set(aliases.values())
    short_names = {key: short_team_name(key) for key in keys}
    tokens = {key: team_token(key) for key in keys}
    return {
        "version": madrid_today(),
        "aliases_resolved": True,
        "logos": logos,
        "aliases": aliases,
        "short_names": short_names,
        "tokens": tokens,
        "teams": [
            {
                "canonical_key": key,
                "key": key,
                "logo": logo,
                "logo_url": logo,
                "short_name": short_names.get(key, key),
                "token": tokens.get(key, "--"),
            }
            for key, logo in sorted(logos.items())
        ],
    }


def load_standings_override():
    path = runtime_data_path("standings_oficial.json")
    laliga_path = runtime_data_path("STANDINGS_LALIGA_BASE.json")
    segunda_path = runtime_data_path("STANDINGS_SEGUNDA_BASE.json")
    if not os.path.exists(path):
        data = {"primera": [], "segunda": []}
    else:
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
        except Exception:
            data = {"primera": [], "segunda": []}
    try:
        if os.path.exists(laliga_path):
            with open(laliga_path, encoding="utf-8") as fh:
                data["primera"] = json.load(fh)
        if os.path.exists(segunda_path):
            with open(segunda_path, encoding="utf-8") as fh:
                data["segunda"] = json.load(fh)
    except Exception:
        pass
    return data


def safe_read_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return default


def _lock_file(lock_fh):
    if os.name == "nt":
        import msvcrt

        msvcrt.locking(lock_fh.fileno(), msvcrt.LK_LOCK, 1)
    else:
        import fcntl

        fcntl.flock(lock_fh.fileno(), fcntl.LOCK_EX)


def _unlock_file(lock_fh):
    if os.name == "nt":
        import msvcrt

        lock_fh.seek(0)
        msvcrt.locking(lock_fh.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl

        fcntl.flock(lock_fh.fileno(), fcntl.LOCK_UN)


def safe_write_json(path, payload):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        lock_path = f"{path}.lock"
        with open(lock_path, "a+b") as lock_fh:
            _lock_file(lock_fh)
            try:
                tmp_path = f"{path}.tmp"
                with open(tmp_path, "w", encoding="utf-8") as fh:
                    json.dump(payload, fh, ensure_ascii=False, indent=2)
                os.replace(tmp_path, path)
            finally:
                _unlock_file(lock_fh)
        return True
    except Exception:
        return False


def strip_html(value):
    text = re.sub(r"<[^>]+>", " ", str(value or ""))
    return re.sub(r"\s+", " ", text).strip()


def normalize_news_text(value):
    text = unicodedata.normalize("NFD", str(value or "").lower())
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return re.sub(r"\s+", " ", text).strip()


def news_relevance_score(text):
    text_norm = normalize_news_text(text)
    score = 0
    for key in NEWS_TEAM_KEYWORDS:
        if normalize_news_text(key) in text_norm:
            score += 4
    for key in NEWS_GENERIC_KEYWORDS:
        if normalize_news_text(key) in text_norm:
            score += 2
    return score


def parse_rfc822_to_iso(value):
    raw = str(value or "").strip()
    if not raw:
        return ""
    for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S%Z"):
        try:
            dt = datetime.strptime(raw, fmt)
            if dt.tzinfo:
                dt = dt.astimezone(ZoneInfo("Europe/Madrid"))
            return dt.strftime("%Y-%m-%d %H:%M")
        except Exception:
            continue
    return ""


def sanitize_xml_payload(payload):
    text = payload.decode("utf-8", errors="replace")
    text = re.sub(r"&(?!#?\w+;)", "&amp;", text)
    text = text.replace("\x0b", " ").replace("\x0c", " ")
    return text.encode("utf-8")


def parse_score_text(score_text):
    match = re.search(r"(\d+)\s*-\s*(\d+)", str(score_text or ""))
    if not match:
        return None, None
    return int(match.group(1)), int(match.group(2))


def signo_for_match(partido_id, home_goals, away_goals):
    if home_goals is None or away_goals is None:
        return "-"
    try:
        match_id = int(partido_id)
    except (TypeError, ValueError):
        return "-"
    if match_id == 15:
        return f"{home_goals}-{away_goals}"
    if home_goals > away_goals:
        return "1"
    if home_goals < away_goals:
        return "2"
    return "X"


def highlightly_status(state):
    # Highlightly documents state.description values such as "Not started",
    # "First half", "Second half", "Half time", "Extra time", "Break time",
    # "Penalties", "In progress", "Finished", "Finished after extra time"...
    # (see highlightly.net/documentation/football). Normalising every live
    # variant here is what keeps a live Liga F match from being written as NS.
    desc = str((state or {}).get("description") or "").upper()
    clock = str((state or {}).get("clock") or "").strip()
    if desc in (
        "FINISHED",
        "ENDED",
        "FT",
        "FULL TIME",
        "MATCH FINISHED",
        "FINISHED AFTER PENALTIES",
        "FINISHED AFTER EXTRA TIME",
        "AET",
        "AP",
        "AWARDED",
    ) or desc.startswith("FINISHED"):
        return "FT", "Finalizado"
    if desc in (
        "FIRST HALF",
        "1ST HALF",
        "SECOND HALF",
        "2ND HALF",
        "LIVE",
        "IN PLAY",
        "IN PROGRESS",
        "EXTRA TIME",
        "EXTRA TIME HALF TIME",
        "BREAK TIME",
        "PENALTIES",
        "PENALTY SHOOTOUT",
    ):
        return "LIVE", f"{clock}'" if clock.isdigit() else clock
    if desc in ("HALF TIME", "HALF TIME BREAK", "HALF-TIME", "HT"):
        return "LIVE", "HT"
    return "NS", "NS"


def highlightly_match_to_panel(match, updated_at=None):
    """Foto de un partido del proveedor lista para el panel de directo.

    Todas las horas que salen de aqui son RELOJ DE MADRID sin zona (contrato del
    proyecto: ``added``/``scheduled``/``fecha_raw``/``hora`` se pintan tal cual).
    El proveedor habla en UTC, asi que la conversion es obligatoria: sin ella el
    saque de las 21:00 aparecia a las 19:00 y, en los partidos del finde que
    empiezan tarde, hasta se iba al dia anterior.
    """
    state = match.get("state") or {}
    league = match.get("league") or {}
    country = match.get("country") or {}
    competition_name = match.get("_competition_name") or league.get("name") or "Liga"
    status, minute = highlightly_status(state)
    score_text = (state.get("score") or {}).get("current") or ""
    kickoff = parse_provider_datetime(match.get("date"))
    if kickoff is None:
        # Sin saque fiable no se inventa una hora: se deja vacia y el dia se
        # deduce del propio ``date`` para no perder el partido del panel.
        raw_date = str(match.get("date") or "").strip()[:10]
        kickoff = parse_provider_datetime(raw_date) if len(raw_date) == 10 else None
    added_date = kickoff.strftime("%Y-%m-%d %H:%M:%S") if kickoff else ""
    scheduled_time = kickoff.strftime("%H:%M") if kickoff else ""
    fecha_raw = kickoff.strftime("%Y-%m-%d") if kickoff else ""
    return {
        "id": match.get("id"),
        "fixture_id": match.get("id"),
        "status": "FINISHED" if status == "FT" else ("IN PLAY" if status == "LIVE" else "SCHEDULED"),
        "time": minute.replace("'", "") if minute and minute != "Finalizado" else minute,
        "score": score_text,
        "home": {
            "name": (match.get("homeTeam") or {}).get("name"),
            "logo": (match.get("homeTeam") or {}).get("logo"),
        },
        "away": {
            "name": (match.get("awayTeam") or {}).get("name"),
            "logo": (match.get("awayTeam") or {}).get("logo"),
        },
        "home_logo": (match.get("homeTeam") or {}).get("logo"),
        "away_logo": (match.get("awayTeam") or {}).get("logo"),
        "competition": {"name": competition_name},
        "competition_name": competition_name,
        "country": country.get("name") or "",
        "country_code": country.get("code") or "",
        "added": added_date,
        "scheduled": scheduled_time,
        "fecha_raw": fecha_raw,
        "hora": scheduled_time,
        # Sellado de frescura: permite aplicar la regla de "el proveedor dejo de
        # emitir" tambien a las filas del panel, no solo a las de la quiniela.
        "updated_at": str(updated_at or ""),
    }


def parse_db_match_datetime(fecha_value, hora_value):
    fecha = str(fecha_value or "").strip()[:10]
    hora = str(hora_value or "").strip()[:5]
    if not fecha or not hora or hora == "-":
        return None
    try:
        return datetime.strptime(f"{fecha} {hora}", "%Y-%m-%d %H:%M")
    except Exception:
        return None


_TIME_PATTERN = re.compile(r"^(\d{1,2}):(\d{2})")


def _match_time_text(value):
    """Primer ``HH:MM`` util de un campo de hora (rechaza '-', '' y minutos)."""
    text = str(value or "").strip().rstrip("hH").strip()
    if not text or text == "-":
        return ""
    match = _TIME_PATTERN.match(text)
    if not match:
        return ""
    hour = int(match.group(1))
    if hour > 23:
        return ""
    return f"{hour:02d}:{match.group(2)}"


def _looks_like_iso_date(value):
    text = str(value or "").strip()
    return len(text) >= 10 and text[:4].isdigit() and text[4] in "-/"


def parse_any_match_datetime(match):
    """Inicio del partido en hora de Madrid (naive) desde cualquier payload.

    Se usan las fechas explicitas de la quiniela si las hay; si no, se interpreta
    ``added`` (texto de Madrid o ISO UTC del proveedor) y, en ultimo termino, el
    ``date`` crudo del proveedor. Antes se devolvia ``None`` (o el texto UTC sin
    convertir) y el partido quedaba fuera de cualquier filtro por dia.
    """
    if not match:
        return None
    raw_date = str(match.get("fecha_raw") or match.get("fecha") or "").strip()[:10]
    raw_time = _match_time_text(match.get("hora") or match.get("scheduled") or "")
    if _looks_like_iso_date(raw_date):
        normalized = parse_provider_datetime(raw_date)
        if normalized is not None:
            if not raw_time:
                return normalized.replace(hour=0, minute=0, second=0, microsecond=0)
            hour, minute = (int(part) for part in raw_time.split(":"))
            return normalized.replace(hour=hour, minute=minute, second=0, microsecond=0)
    for key in ("added", "kickoff", "date", "start_time", "startTime"):
        value = str(match.get(key) or "").strip()
        if not value:
            continue
        dt = parse_provider_datetime(value)
        if dt is not None:
            return dt
    return None


def match_kickoff_datetime(match):
    """Alias legible de :func:`parse_any_match_datetime` para los filtros."""
    return parse_any_match_datetime(match)
