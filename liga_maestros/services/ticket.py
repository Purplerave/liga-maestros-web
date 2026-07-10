"""Ticket: close info, prediction validation, match info loading."""
import os, re, json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import config
from ..utils import safe_read_json

MADRID_TZ = ZoneInfo("Europe/Madrid")
PREDICTION_CLOSE_MINUTES_BEFORE_KICKOFF = int(os.getenv("PREDICTION_CLOSE_MINUTES_BEFORE_KICKOFF", "15"))


def madrid_now():
    return datetime.now(MADRID_TZ)


def today_madrid():
    return madrid_now().strftime("%Y-%m-%d")


def parse_madrid_datetime(fecha, hora):
    fecha = str(fecha or "").strip()[:10]
    hora = str(hora or "").strip()[:5]
    if not fecha or not hora or hora == "-":
        return None
    try:
        return datetime.strptime(f"{fecha} {hora}", "%Y-%m-%d %H:%M").replace(tzinfo=MADRID_TZ)
    except Exception:
        return None


def parse_madrid_date_start(fecha):
    fecha = str(fecha or "").strip()[:10]
    if not fecha:
        return None
    try:
        return datetime.strptime(fecha, "%Y-%m-%d").replace(tzinfo=MADRID_TZ)
    except Exception:
        return None


def row_value(row, *names):
    for name in names:
        try:
            value = row.get(name) if hasattr(row, "get") else row[name]
        except Exception:
            continue
        if value is not None and str(value).strip() != "":
            return value
    return None


def compute_ticket_close_info(rows, source="jornada"):
    candidates = []
    exact_count = 0
    fallback_count = 0
    for row in rows or []:
        fecha = row_value(row, "fecha_raw", "fecha")
        hora = row_value(row, "hora")
        kickoff_at = parse_madrid_datetime(fecha, hora)
        if kickoff_at:
            exact_count += 1
            candidates.append(kickoff_at)
            continue
        date_start = parse_madrid_date_start(fecha)
        if date_start:
            fallback_count += 1
            candidates.append(date_start)
    first_kickoff = min(candidates) if candidates else None
    close_at = (
        first_kickoff - timedelta(minutes=max(0, PREDICTION_CLOSE_MINUTES_BEFORE_KICKOFF))
        if first_kickoff else None
    )
    return {
        "first_kickoff": first_kickoff,
        "close_at": close_at,
        "exact_count": exact_count,
        "fallback_count": fallback_count,
    }


def validate_q15_payload(payload, jornada=None):
    Q15_EXPECTED_MATCHES = 15
    matches = payload.get("matches") if isinstance(payload, dict) else None
    if not isinstance(matches, list):
        raise ValueError("q15_payload_sin_matches")
    if jornada is not None and int(payload.get("jornada") or 0) != int(jornada):
        raise ValueError("q15_jornada_no_coincide")
    ids = []
    for match in matches:
        try:
            ids.append(int(match.get("id")))
        except Exception:
            raise ValueError("q15_id_invalido")
    expected_ids = set(range(1, Q15_EXPECTED_MATCHES + 1))
    if len(matches) != Q15_EXPECTED_MATCHES or set(ids) != expected_ids:
        raise ValueError(f"q15_matches_incompletos:{len(matches)}/{Q15_EXPECTED_MATCHES}")
    return matches


def repair_mojibake(text):
    if not isinstance(text, str):
        return text
    if "\u00c3\u0083\u0082" not in text and "\u00c3\u0082\u0083" not in text:
        return text
    try:
        return text.encode("latin1").decode("utf-8")
    except Exception:
        return text


def load_match_info_for_jornada(jornada):
    info = {}
    j_text = str(jornada)
    scrape_path = os.path.join(config.DATA_DIR, f"quiniela15_J{j_text}_scrape.json")
    if os.path.exists(scrape_path):
        try:
            with open(scrape_path, "r", encoding="utf-8") as fh:
                q15_data = json.load(fh)
            for item in q15_data.get("partidos") or []:
                pid = int(item.get("num") or item.get("id") or 0)
                if not pid:
                    continue
                info[pid] = {
                    "q15": item.get("q15"), "lae": item.get("lae"), "apu": item.get("apu"),
                    "historico": item.get("historico"),
                    "fuerza_local": item.get("fuerza_local"), "fuerza_visitante": item.get("fuerza_visitante"),
                    "detalle": repair_mojibake(item.get("detalle") or ""),
                }
        except Exception:
            pass

    parent_dir = os.path.abspath(os.path.join(config.BASE_DIR, ".."))
    prediction_candidates = [
        os.path.join(parent_dir, f"PREDICCIONES_J{j_text}_DEFINITIVO.json"),
        os.path.join(parent_dir, f"PREDICCIONES_J{j_text}_FINAL.json"),
        os.path.join(config.DATA_DIR, f"PREDICCIONES_J{j_text}_DEFINITIVO.json"),
        os.path.join(config.DATA_DIR, f"PREDICCIONES_J{j_text}_FINAL.json"),
    ]
    for path in prediction_candidates:
        if not os.path.exists(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as fh:
                pred_data = json.load(fh)
            for item in pred_data.get("maestra") or []:
                pid = int(item.get("p") or item.get("id") or 0)
                if not pid:
                    continue
                info.setdefault(pid, {})
                info[pid]["maestra"] = {
                    "signo": repair_mojibake(item.get("s") or ""),
                    "razon": repair_mojibake(item.get("r") or ""),
                }
            break
        except Exception:
            pass
    return {str(k): v for k, v in info.items()}
