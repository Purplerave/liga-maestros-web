import os
import json
import re
import unicodedata
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import xml.etree.ElementTree as ET
try:
    from .config import BASE_DIR, TEAM_LOGO_ALIASES, NEWS_TEAM_KEYWORDS, NEWS_GENERIC_KEYWORDS
except ImportError:
    from config import BASE_DIR, TEAM_LOGO_ALIASES, NEWS_TEAM_KEYWORDS, NEWS_GENERIC_KEYWORDS

def clean_team_key(value):
    text = unicodedata.normalize("NFD", str(value or "").upper())
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = re.sub(r"[^A-Z0-9]+", " ", text).strip()
    text = re.sub(r"\b(F C|FC|C F|CF|S A D|SAD|R C D|RCD|C D|CD|U D|UD|S D|SD)\b", "", text).strip()
    text = re.sub(r"\s+", " ", text)
    return text

def normalize_team_key(value):
    text = clean_team_key(value)
    return TEAM_LOGO_ALIASES.get(text, text)

def load_team_logos():
    logos_path = os.path.join(BASE_DIR, "data", "TEAM_LOGOS.json")
    manifest_path = os.path.join(BASE_DIR, "static", "img", "team_logos", "manifest.json")
    logos = {}
    try:
        if os.path.exists(logos_path):
            with open(logos_path, "r", encoding="utf-8") as fh:
                raw = json.load(fh)
            logos.update({normalize_team_key(name): logo for name, logo in raw.items()})
        if os.path.exists(manifest_path):
            with open(manifest_path, "r", encoding="utf-8") as fh:
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
    return {
        "version": datetime.now().strftime("%Y-%m-%d"),
        "logos": logos,
        "aliases": {clean_team_key(k): normalize_team_key(v) for k, v in TEAM_LOGO_ALIASES.items()},
        "teams": [
            {"key": key, "logo": logo}
            for key, logo in sorted(logos.items())
        ],
    }

def load_standings_override():
    path = os.path.join(BASE_DIR, "data", "standings_oficial.json")
    laliga_path = os.path.join(BASE_DIR, "data", "STANDINGS_LALIGA_BASE.json")
    segunda_path = os.path.join(BASE_DIR, "data", "STANDINGS_SEGUNDA_BASE.json")
    if not os.path.exists(path):
        data = {"primera": [], "segunda": []}
    else:
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except Exception:
            data = {"primera": [], "segunda": []}
    try:
        if os.path.exists(laliga_path):
            with open(laliga_path, "r", encoding="utf-8") as fh:
                data["primera"] = json.load(fh)
        if os.path.exists(segunda_path):
            with open(segunda_path, "r", encoding="utf-8") as fh:
                data["segunda"] = json.load(fh)
    except Exception:
        pass
    return data

def safe_read_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return default

def safe_write_json(path, payload):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
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
    return raw[:16]

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
    if int(partido_id) == 15:
        return f"{home_goals}-{away_goals}"
    if home_goals > away_goals:
        return "1"
    if home_goals < away_goals:
        return "2"
    return "X"

def highlightly_status(state):
    desc = str((state or {}).get("description") or "").upper()
    if desc in ("FINISHED", "ENDED", "FT", "MATCH FINISHED", "FINISHED AFTER PENALTIES", "FINISHED AFTER EXTRA TIME") or desc.startswith("FINISHED"):
        return "FT", "Finalizado"
    if desc in ("FIRST HALF", "SECOND HALF", "LIVE", "IN PLAY"):
        clock = str((state or {}).get("clock") or "").strip()
        return "LIVE", f"{clock}'" if clock.isdigit() else clock
    if desc in ("HALF TIME", "HALF TIME BREAK"):
        return "LIVE", "HT"
    return "NS", "NS"

def highlightly_match_to_panel(match):
    state = match.get("state") or {}
    status, minute = highlightly_status(state)
    score_text = ((state.get("score") or {}).get("current") or "")
    date_str = match.get("date", "")
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S.%fZ")
        dt = dt.replace(tzinfo=ZoneInfo("UTC")).astimezone(ZoneInfo("Europe/Madrid"))
        added_date = dt.strftime("%Y-%m-%d %H:%M:%S")
        scheduled_time = dt.strftime("%H:%M")
    except Exception:
        added_date = date_str
        scheduled_time = ""
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
        "competition": {"name": match.get("_competition_name") or "Liga"},
        "competition_name": match.get("_competition_name") or "Liga",
        "added": added_date,
        "scheduled": scheduled_time,
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

def parse_any_match_datetime(match):
    raw_date = str(match.get("fecha_raw") or "").strip()[:10]
    raw_time = str(match.get("hora") or match.get("scheduled") or "").strip()[:5]
    if not raw_date:
        added = str(match.get("added") or "").strip()
        if added:
            raw_date = added[:10]
            if not raw_time and len(added) >= 16:
                raw_time = added[11:16]
    if not raw_date:
        raw_iso = str(match.get("date") or "").strip()
        if raw_iso:
            try:
                dt = datetime.strptime(raw_iso, "%Y-%m-%dT%H:%M:%S.%fZ")
                return dt.replace(tzinfo=ZoneInfo("UTC")).astimezone(ZoneInfo("Europe/Madrid")).replace(tzinfo=None)
            except Exception:
                pass
    if not raw_date:
        return None
    if not raw_time:
        raw_time = "00:00"
    try:
        return datetime.strptime(f"{raw_date} {raw_time}", "%Y-%m-%d %H:%M")
    except Exception:
        return None
