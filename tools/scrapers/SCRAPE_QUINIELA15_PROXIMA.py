import argparse
import json
import re
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent
PROGRAM_DIR = PROJECT_ROOT / "PROGRAMA_QUINIELA"
URL = "https://www.quiniela15.com/pronostico-quiniela"

MONTHS = {
    "ene": 1,
    "enero": 1,
    "feb": 2,
    "febrero": 2,
    "mar": 3,
    "marzo": 3,
    "abr": 4,
    "abril": 4,
    "may": 5,
    "mayo": 5,
    "jun": 6,
    "junio": 6,
    "jul": 7,
    "julio": 7,
    "ago": 8,
    "agosto": 8,
    "sep": 9,
    "sept": 9,
    "septiembre": 9,
    "oct": 10,
    "octubre": 10,
    "nov": 11,
    "noviembre": 11,
    "dic": 12,
    "diciembre": 12,
}


def clean(text):
    return re.sub(r"\s+", " ", str(text or "")).strip()


def split_team_force(text):
    text = clean(text)
    match = re.match(r"^(.*?)\s*\(([-+]?\d+(?:\.\d+)?)\)$", text)
    if not match:
        return text, None
    return clean(match.group(1)), float(match.group(2))


def extract_percent_block(label, text):
    match = re.search(rf"{label}:\s*(\d+)%\s*\|\s*(\d+)%\s*\|\s*(\d+)%", text, flags=re.I)
    if not match:
        return None
    return {"1": int(match.group(1)), "X": int(match.group(2)), "2": int(match.group(3))}


def extract_score_probs(text):
    if "Marcador Q15" not in text:
        return []
    tail = text.split("Marcador Q15", 1)[1]
    return [{"score": score, "pct": int(pct)} for score, pct in re.findall(r"\b([0-2M]-[0-2M])\s+(\d+)%", tail)][:6]


def sign_from_probs(probs):
    if not probs:
        return "-"
    return max(("1", "X", "2"), key=lambda key: int(probs.get(key, 0)))


def load_segunda_position_map():
    candidates = [
        ROOT / "data" / "STANDINGS_SEGUNDA_BASE.json",
        ROOT / "data" / "standings_oficial.json",
    ]
    for path in candidates:
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            rows = data.get("segunda", data) if isinstance(data, dict) else data
            mapping = {int(row["pos"]): row["n"] for row in rows if str(row.get("pos", "")).isdigit() and row.get("n")}
            if mapping:
                return mapping
        except Exception:
            continue
    return {}


def resolve_hypermotion_placeholder(name, position_map):
    match = re.match(r"^(\d+)[ºª]?\s+Hypermotion$", clean(name), flags=re.I)
    if not match:
        return name
    return position_map.get(int(match.group(1)), name)


MADRID_TZ = ZoneInfo("Europe/Madrid")

_WEEKDAY_WORDS = (
    "lunes",
    "martes",
    "miercoles",
    "jueves",
    "viernes",
    "sabado",
    "domingo",
    "lun",
    "mar",
    "mie",
    "jue",
    "vie",
    "sab",
    "dom",
)
_MONTH_WORDS = "|".join(sorted({re.escape(word) for word in MONTHS}, key=len, reverse=True))
_HOUR_PATTERN = r"([01]?[0-9]|2[0-4]):([0-5][0-9])"

_DATE_PATTERNS = (
    # "sábado 22 ago 17:00h" / "sab 22 ago17:00h" / "domingo 6 de septiembre"
    re.compile(rf"(?:{'|'.join(_WEEKDAY_WORDS)})\s+(\d{{1,2}})\s*(?:º|°)?\s*(?:de\s+)?({_MONTH_WORDS})", re.I),
    # "22 ago 17:00" sin dia de la semana
    re.compile(rf"(\d{{1,2}})\s*(?:º|°)?\s*(?:de\s+)?({_MONTH_WORDS})(?=\D|$)", re.I),
    # "22/08" o "22-08-2026"
    re.compile(r"(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?", re.I),
)


def _strip_accents(value):
    return unicodedata.normalize("NFD", str(value or "").lower()).encode("ascii", "ignore").decode()


def _resolve_month(token):
    if not token:
        return None
    key = _strip_accents(token).strip().rstrip(".")
    if key in MONTHS:
        return MONTHS[key]
    for name, number in MONTHS.items():
        if len(key) >= 3 and _strip_accents(name).startswith(key):
            return number
    return None


def _find_hour(text):
    """Primera hora HH:MM del detalle, normalizada ('24:00' -> 00:00 del dia despues)."""
    match = re.search(_HOUR_PATTERN, str(text or ""))
    if not match:
        return "", False
    hour, minute = int(match.group(1)), int(match.group(2))
    if hour == 24:
        return "00:00", True
    return f"{hour:02d}:{minute:02d}", False


def parse_detail_datetime(text, now=None):
    """Fecha y hora de saque del detalle de Quiniela15, como reloj de Madrid.

    El horario de la quiniela define el cierre del boleto, la ventana de directo y
    el dia al que se asocia cada partido, y aqui se perdía casi siempre: el regex
    exigia «sabado 22 agosto 17:00h» con espacio delante de la hora y sufijo 'h',
    mientras la pagina escribe «sábado 22 ago17:00h» (abreviatura pegada a la hora).
    Sin coincidencia devolvia («», «») y la jornada se importaba sin fecha: los
    partidos del finde quedaban fuera de todo filtro por dia y no se refrescaban.

    Ahora se aceptan las variantes reales del HTML —«21 ago 17:00», «21/08»,
    «hoy 21:30h», «mañana a las 19:00», «24:00»— y el anio se deduce del reloj de
    Madrid (no del UTC del servidor, que cambia de anio horas antes).
    """
    raw = clean(text)
    if not raw:
        return "", ""
    # 'h' final pegada ("17:00h") y "a las" molesto
    body = re.sub(r"(\d{1,2}:\d{2})\s*h\b", r"\1 ", _strip_accents(raw))
    body = re.sub(r"\ba las\b", " ", body)
    if now is None:
        now = datetime.now(MADRID_TZ)
    hour, rolls_to_next_day = _find_hour(body)
    if not hour:
        return "", ""

    day = month = year_hint = None
    lowered = body
    # "2026-08-23 19:00": fecha ISO ya resuelta (la usan los importadores y los
    # boletos corregidos a mano). Se respeta tal cual, anio incluido.
    iso = re.search(r"\b(20\d{2})-(\d{1,2})-(\d{1,2})\b", lowered)
    if iso:
        try:
            fixed = datetime(int(iso.group(1)), int(iso.group(2)), int(iso.group(3)))
        except ValueError:
            fixed = None
        if fixed is not None:
            if rolls_to_next_day:
                fixed += timedelta(days=1)
            return fixed.strftime("%Y-%m-%d"), hour
    if re.search(r"\bhoy\b", lowered):
        base = now.date()
        return base.strftime("%Y-%m-%d"), hour
    relative = None
    if re.search(r"\bmanana\b", lowered):
        relative = now.date() + timedelta(days=1)
    if relative is not None:
        return relative.strftime("%Y-%m-%d"), hour

    for pattern in _DATE_PATTERNS:
        match = pattern.search(lowered)
        if not match:
            continue
        groups = match.groups()
        try:
            candidate_day = int(groups[0])
        except (TypeError, ValueError):
            continue
        candidate_month = _resolve_month(groups[1]) if len(groups) > 1 else None
        if candidate_month is None and len(groups) > 2 and groups[1]:
            # patron numerico: dia/mes
            try:
                candidate_month = int(groups[1])
            except ValueError:
                candidate_month = None
        if not candidate_month or not 1 <= candidate_day <= 31 or not 1 <= candidate_month <= 12:
            continue
        day, month = candidate_day, candidate_month
        if len(groups) > 2 and groups[2]:
            hint = int(groups[2])
            year_hint = hint + 2000 if hint < 100 else hint
        break

    if day is None or month is None:
        return "", hour

    year = year_hint or now.year
    if not year_hint:
        if month < now.month - 6:
            year += 1
        elif month > now.month + 6:
            year -= 1
    try:
        date = datetime(year, month, day)
    except ValueError:
        return "", hour
    if rolls_to_next_day:
        date += timedelta(days=1)
    return date.strftime("%Y-%m-%d"), hour


def fetch_html(url=URL):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) LigaMaestros/1.0",
        "Accept-Language": "es-ES,es;q=0.9",
    }
    response = requests.get(url, headers=headers, timeout=25)
    response.raise_for_status()
    return response.text


def scrape_quiz(url=URL):
    soup = BeautifulSoup(fetch_html(url), "html.parser")
    page_text = soup.get_text("\n", strip=True)
    jornada_match = re.search(r"Jornada\s+(\d+)", page_text, flags=re.I)
    if not jornada_match:
        raise RuntimeError("No he podido detectar la jornada en Quiniela15.")
    jornada = int(jornada_match.group(1))

    cierre = ""
    cierre_match = re.search(r"Cierre:\s*(.*?)\s*\.\s*Participan", clean(page_text), flags=re.I)
    if cierre_match:
        cierre = clean(cierre_match.group(1))

    rows = soup.find_all("tr")
    segunda_positions = load_segunda_position_map()
    partidos = []
    horarios = {}
    probabilities = {}
    q15_base_signs = []

    for pos, row in enumerate(rows):
        cells = [clean(td.get_text(" ", strip=True)) for td in row.find_all("td")]
        if len(cells) < 9 or not cells[0].isdigit():
            continue
        num = int(cells[0])
        if not 1 <= num <= 15:
            continue

        local, fuerza_local = split_team_force(cells[1])
        visitante, fuerza_visitante = split_team_force(cells[2])
        local = resolve_hypermotion_placeholder(local, segunda_positions)
        visitante = resolve_hypermotion_placeholder(visitante, segunda_positions)
        sistema = cells[7] or "-"

        detail_text = ""
        for nxt in rows[pos + 1 : pos + 4]:
            classes = nxt.get("class") or []
            if "matchinfo" in classes:
                detail_cells = [clean(td.get_text(" ", strip=True)) for td in nxt.find_all("td")]
                detail_text = " ".join(detail_cells)
                break
        fecha, hora = parse_detail_datetime(detail_text)

        pronostic_text = cells[8]
        q15 = extract_percent_block("Q15", pronostic_text)
        lae = extract_percent_block("LAE", pronostic_text)
        apu = extract_percent_block("APU", pronostic_text)
        score_probs = extract_score_probs(pronostic_text)

        comunidad = "-"
        if num == 15 and score_probs:
            comunidad = score_probs[0]["score"]
        elif pronostic_text:
            comunidad = pronostic_text.split(" ", 1)[0]

        historico = {
            "total": cells[3],
            "1": cells[4],
            "X": cells[5],
            "2": cells[6],
        }
        partido = {
            "num": num,
            "local": local,
            "visitante": visitante,
            "fuerza_local": fuerza_local,
            "fuerza_visitante": fuerza_visitante,
            "historico": historico,
            "sistema": sistema,
            "comunidad": comunidad,
            "q15": q15,
            "lae": lae,
            "apu": apu,
            "marcadores_q15": score_probs,
            "fecha": fecha,
            "hora": hora,
            "detalle": detail_text,
        }
        partidos.append(partido)
        horarios[str(num)] = {"fecha": fecha, "hora": hora}
        if q15:
            probabilities[str(num)] = {
                "num": num,
                "probabilidades": q15,
                "fuente": "quiniela15_q15",
            }
        q15_base_signs.append(sistema if num == 15 else sign_from_probs(q15))

    if len(partidos) != 15:
        raise RuntimeError(f"Esperaba 15 partidos y he extraído {len(partidos)}.")

    return {
        "jornada": jornada,
        "source_url": url,
        # Sello en hora de Madrid: el resto de la app compara esta marca con
        # `today_madrid()` para decidir si el boleto sigue siendo fresco.
        "scraped_at": datetime.now(MADRID_TZ).isoformat(timespec="seconds"),
        "cierre": cierre,
        "partidos": partidos,
        "horarios": horarios,
        "probabilidades": probabilities,
        "q15_base_signs": q15_base_signs,
    }


def write_outputs(payload, write_program=True):
    jornada = payload["jornada"]
    data_dir = ROOT / "data"
    data_dir.mkdir(exist_ok=True)
    (data_dir / f"quiniela15_J{jornada}_scrape.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (data_dir / f"horarios_J{jornada}.json").write_text(
        json.dumps(payload["horarios"], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    if write_program:
        datos_dir = PROGRAM_DIR / "DATOS"
        salidas_dir = PROGRAM_DIR / "SALIDAS"
        datos_dir.mkdir(parents=True, exist_ok=True)
        salidas_dir.mkdir(parents=True, exist_ok=True)
        (datos_dir / f"QUINIELA15_J{jornada}.json").write_text(
            json.dumps(
                {
                    "jornada": jornada,
                    "source_url": payload["source_url"],
                    "scraped_at": payload["scraped_at"],
                    "cierre": payload["cierre"],
                    "partidos": payload["partidos"],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (datos_dir / f"PROBABILIDADES_J{jornada}.json").write_text(
            json.dumps(payload["probabilidades"], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (salidas_dir / f"quiniela_programa_J{jornada}_q15_base.json").write_text(
            json.dumps(
                {
                    "jornada": jornada,
                    "fuente": "quiniela15_sistema_base",
                    "signos": payload["q15_base_signs"],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )


def main():
    parser = argparse.ArgumentParser(
        description="Scrapea la próxima quiniela desde Quiniela15 y genera JSON de entrada."
    )
    parser.add_argument("--url", default=URL)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-program", action="store_true", help="No escribe en PROGRAMA_QUINIELA/DATOS.")
    args = parser.parse_args()

    payload = scrape_quiz(args.url)
    print(f"Jornada {payload['jornada']} | {len(payload['partidos'])} partidos | cierre: {payload['cierre'] or '-'}")
    for partido in payload["partidos"]:
        print(
            f"{partido['num']:>2}. {partido['local']} - {partido['visitante']} "
            f"{partido['fecha']} {partido['hora']} | Sis {partido['sistema']} | Com {partido['comunidad']}"
        )
    if not args.dry_run:
        write_outputs(payload, write_program=not args.no_program)
        print("OK: JSON generados.")


if __name__ == "__main__":
    main()
