import argparse
import json
import re
from datetime import datetime, timedelta
from pathlib import Path

import requests
from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent
PROGRAM_DIR = PROJECT_ROOT / "PROGRAMA_QUINIELA"
URL = "https://www.quiniela15.com/pronostico-quiniela"

MONTHS = {
    "ene": 1, "enero": 1,
    "feb": 2, "febrero": 2,
    "mar": 3, "marzo": 3,
    "abr": 4, "abril": 4,
    "may": 5, "mayo": 5,
    "jun": 6, "junio": 6,
    "jul": 7, "julio": 7,
    "ago": 8, "agosto": 8,
    "sep": 9, "sept": 9, "septiembre": 9,
    "oct": 10, "octubre": 10,
    "nov": 11, "noviembre": 11,
    "dic": 12, "diciembre": 12,
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
    return [
        {"score": score, "pct": int(pct)}
        for score, pct in re.findall(r"\b([0-2M]-[0-2M])\s+(\d+)%", tail)
    ][:6]


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
            mapping = {
                int(row["pos"]): row["n"]
                for row in rows
                if str(row.get("pos", "")).isdigit() and row.get("n")
            }
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


def parse_detail_datetime(text, now=None):
    now = now or datetime.now()
    match = re.search(
        r"\b(?:lunes|martes|miércoles|miercoles|jueves|viernes|sábado|sabado|domingo)\s+"
        r"(\d{1,2})\s+([a-záéíóúñ]+)\s+(\d{1,2}:\d{2})h",
        text,
        flags=re.I,
    )
    if not match:
        return "", ""
    day = int(match.group(1))
    month = MONTHS.get(match.group(2).lower())
    hour = match.group(3)
    if not month:
        return "", hour
    year = now.year
    if month < now.month - 6:
        year += 1
    date = datetime(year, month, day)
    if hour == "24:00":
        date += timedelta(days=1)
        hour = "00:00"
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
        for nxt in rows[pos + 1: pos + 4]:
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
        "scraped_at": datetime.now().isoformat(timespec="seconds"),
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
            json.dumps({
                "jornada": jornada,
                "source_url": payload["source_url"],
                "scraped_at": payload["scraped_at"],
                "cierre": payload["cierre"],
                "partidos": payload["partidos"],
            }, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (datos_dir / f"PROBABILIDADES_J{jornada}.json").write_text(
            json.dumps(payload["probabilidades"], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (salidas_dir / f"quiniela_programa_J{jornada}_q15_base.json").write_text(
            json.dumps({
                "jornada": jornada,
                "fuente": "quiniela15_sistema_base",
                "signos": payload["q15_base_signs"],
            }, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def main():
    parser = argparse.ArgumentParser(description="Scrapea la próxima quiniela desde Quiniela15 y genera JSON de entrada.")
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
