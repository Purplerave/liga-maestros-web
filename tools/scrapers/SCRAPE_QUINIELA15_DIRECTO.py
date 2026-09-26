import argparse
import json
import os
import re
import time
from datetime import datetime

import requests
from bs4 import BeautifulSoup

from liga_maestros import utils

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(BASE_DIR, "data")
# Cabeceras de navegador reales: el UA pelado "Mozilla/5.0" es facil de
# bloquear y dejaba el directo de la quiniela sin datos toda la jornada.
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
}


def fetch_page(url, attempts=3):
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            response = requests.get(url, timeout=25, headers=REQUEST_HEADERS)
            response.raise_for_status()
            response.encoding = "utf-8"
            return response
        except requests.RequestException as exc:
            last_error = exc
            if attempt < attempts:
                time.sleep(1.5 * attempt)
    if last_error:
        raise last_error
    raise RuntimeError(f"No se pudo descargar {url}: attempts={attempts}")


def clean(text):
    return re.sub(r"\s+", " ", str(text or "")).strip()


def parse_score(text):
    match = re.search(r"\b(\d+)\s*-\s*(\d+)\b", clean(text))
    if not match:
        return None, None
    return int(match.group(1)), int(match.group(2))


def parse_live_minute(text):
    value = clean(text)
    if re.search(r"\b(descanso|medio\s+tiempo|half\s*time|ht)\b", value, flags=re.I):
        return "Descanso"
    match = re.search(r"\bmin\.\s*([0-9]+(?:\+[0-9]+)?'?)", value, flags=re.I)
    if not match:
        return ""
    minute = match.group(1)
    return minute if minute.endswith("'") else f"{minute}'"


def has_final_signal(text):
    value = clean(text)
    return bool(re.search(r"\b(finalizado|terminado|final|ft|fin)\b", value, flags=re.I))


# La quiniela15 no escribe la palabra "finalizado" en ningun sitio: mientras el
# partido corre, el marcador late (clase `blink_me`) y la celda de minuto dice
# "min. 67'". En cuanto acaba, desaparecen el parpadeo y el minuto y solo queda
# el marcador. Antes se deducía el final por reloj (`FULL_MATCH_WINDOW`, 2h30
# despues del saque) y la fila se quedaba STALE con el ultimo marcador en vivo.
_Q15_LIVE_CLASS = re.compile(r"\bblink", flags=re.I)


def q15_row_live_markup(row):
    """True si la fila muestra el marcador parpadeando (partido en juego)."""
    return bool(row.select("[class*=blink]"))


def q15_row_is_scheduled_placeholder(row):
    """True si la celda de marcador es la fecha de juego, no un resultado."""
    cells = row.find_all("td")
    if len(cells) < 3:
        return False
    score_cell = cells[2]
    if score_cell.select_one(".matchdate"):
        return True
    return parse_score(score_cell.get_text(" ", strip=True)) == (None, None)


def status_for_q15(score_home, score_away, minute, text, live_markup=False, scheduled_placeholder=False):
    if minute:
        return "HT" if str(minute).lower().startswith("descanso") else "LIVE"
    if live_markup:
        return "LIVE"
    if score_home is None or score_away is None:
        return "NS"
    if scheduled_placeholder:
        return "NS"
    # Marcador sin parpadeo y sin minuto: la quiniela15 solo enseña el
    # resultado cuando el partido ya ha acabado.
    return "FT"


def signo_for_score(match_id, home_goals, away_goals):
    return utils.signo_for_match(match_id, home_goals, away_goals)


def parse_match_title(text):
    # La fuerza15 va entre parentesis Y contiene digitos: (1666.4). El marker
    # femenino "(F)" tambien va entre parentesis, y la version anterior se lo
    # tragaba como si fuera la fuerza del visitante: "Barcelona (F) (2017.7)"
    # llegaba como visitante "Barcelona", el cruce con la BD ("Barcelona (F)")
    # se descartaba por mezclar masculino/femenino y el resultado del partido
    # no entraba nunca. Exigir un digito dentro del parentesis distingue la
    # fuerza15 del genero.
    fuerza = r"\((?=[^)]*\d)[^)]+\)"
    match = re.match(rf"^\s*(\d+)\s+(.+?)\s+{fuerza}\s*-\s*(.+?)\s+{fuerza}", text)
    if match:
        return int(match.group(1)), clean(match.group(2)), clean(match.group(3))
    match = re.match(r"^\s*(\d+)\s+(.+?)\s+-\s+(.+?)(?:\s+\d|$)", text)
    if match:
        return int(match.group(1)), clean(match.group(2)), clean(match.group(3))
    return None, "", ""


def parse_events(detail_row):
    groups = []
    for column in detail_row.select(".grid .flex.flex-col.gap-2"):
        title = clean(column.find("div").get_text(" ", strip=True) if column.find("div") else "")
        if not title.lower().startswith("eventos "):
            continue
        team = clean(re.sub(r"^Eventos\s+", "", title, flags=re.I))
        events = []
        for event_node in column.select(".events"):
            parent = event_node.parent
            minute_node = parent.find("span", class_=re.compile("font-bold")) if parent else None
            minute = clean(minute_node.get_text(" ", strip=True) if minute_node else "")
            spans = parent.find_all("span") if parent else []
            player = clean(spans[-1].get_text(" ", strip=True) if spans else "")
            kind = clean(event_node.get("title") or "")
            if minute or player:
                events.append({"minute": minute, "player": player, "type": kind})
        groups.append({"team": team, "events": events})
    return groups


def parse_probs(detail_row):
    tables = []
    for table in detail_row.find_all("table"):
        rows = []
        for tr in table.find_all("tr"):
            cells = [clean(td.get_text(" ", strip=True)) for td in tr.find_all(["td", "th"])]
            if cells:
                rows.append(cells)
        if rows:
            tables.append(rows)
    return tables


def parse_main_row(row):
    number_cell = row.select_one("td.tnum")
    if not number_cell:
        return None
    try:
        index = int(clean(number_cell.get_text(" ", strip=True)))
    except Exception:
        return None

    cells = row.find_all("td")
    if len(cells) < 3:
        return None

    index_from_text, home, away = parse_match_title(row.get_text(" ", strip=True))
    if index_from_text and index_from_text != index:
        return None
    if not home or not away:
        return None

    score_home, score_away = parse_score(cells[2].get_text(" ", strip=True))
    minute = ""
    if len(cells) >= 4:
        minute = parse_live_minute(cells[3].get_text(" ", strip=True))
    if not minute:
        minute = parse_live_minute(row.get_text(" ", strip=True))
    row_text = row.get_text(" ", strip=True)
    status = status_for_q15(
        score_home,
        score_away,
        minute,
        row_text,
        live_markup=q15_row_live_markup(row),
        scheduled_placeholder=q15_row_is_scheduled_placeholder(row),
    )
    return {
        "id": index,
        "local": home,
        "visitante": away,
        "score_home": score_home,
        "score_away": score_away,
        "status": status,
        "minute": minute,
        "signo": signo_for_score(index, score_home, score_away),
        "events": [],
        "referee": "",
        "coaches": "",
        "probability_tables": [],
    }


def scrape(jornada):
    url = f"https://www.quiniela15.com/resultados-quiniela/{jornada}"
    response = fetch_page(url)
    soup = BeautifulSoup(response.text, "html.parser")

    by_id = {}
    for row in soup.find_all("tr"):
        parsed = parse_main_row(row)
        if parsed:
            by_id[parsed["id"]] = parsed

    for detail in soup.select("tr.matchinfo"):
        prev = detail.find_previous_sibling(lambda tag: tag.name == "tr" and tag.select_one("td.tnum"))
        index, home, away = parse_match_title(prev.get_text(" ", strip=True) if prev else "")
        if not index:
            continue
        main_cells = prev.find_all("td") if prev else []
        score_home, score_away = (None, None)
        minute = ""
        if len(main_cells) >= 3:
            score_home, score_away = parse_score(main_cells[2].get_text(" ", strip=True))
        if len(main_cells) >= 4:
            minute = parse_live_minute(main_cells[3].get_text(" ", strip=True))
        if not minute:
            minute = parse_live_minute(prev.get_text(" ", strip=True) if prev else "")
        status = status_for_q15(
            score_home,
            score_away,
            minute,
            prev.get_text(" ", strip=True) if prev else "",
            live_markup=q15_row_live_markup(prev) if prev else False,
            scheduled_placeholder=q15_row_is_scheduled_placeholder(prev) if prev else False,
        )
        text = clean(detail.get_text(" ", strip=True))
        referee = ""
        coaches = ""
        referee_match = re.search(r"Árbitro:\s*(.+?)(?:\s+Entrenadores:|\s+Distribución|$)", text)
        coaches_match = re.search(r"Entrenadores:\s*(.+?)(?:\s+Distribución|$)", text)
        if referee_match:
            referee = clean(referee_match.group(1))
        if coaches_match:
            coaches = clean(coaches_match.group(1))
        by_id[index] = {
            **by_id.get(index, {}),
            "id": index,
            "local": home,
            "visitante": away,
            "score_home": score_home,
            "score_away": score_away,
            "status": status,
            "minute": minute,
            "signo": signo_for_score(index, score_home, score_away),
            "events": parse_events(detail),
            "referee": referee,
            "coaches": coaches,
            "probability_tables": parse_probs(detail),
            "source": url,
        }
    for item in by_id.values():
        item.setdefault("source", url)
    matches = [by_id[key] for key in sorted(by_id)]
    return {
        "jornada": int(jornada),
        "source": url,
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
        "matches": matches,
    }


def main():
    parser = argparse.ArgumentParser(description="Cachea detalles en directo de Quiniela15 por jornada.")
    parser.add_argument("jornada", type=int)
    args = parser.parse_args()
    os.makedirs(OUT_DIR, exist_ok=True)
    payload = scrape(args.jornada)
    path = os.path.join(OUT_DIR, f"quiniela15_directo_J{args.jornada}.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    print(f"OK {len(payload['matches'])} partidos -> {path}")


if __name__ == "__main__":
    main()
