import argparse
import json
import os
import re
import time
from datetime import datetime

import requests
from bs4 import BeautifulSoup

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(BASE_DIR, "data")
REQUEST_HEADERS = {"User-Agent": "Mozilla/5.0"}


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
    raise last_error


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
    match = re.search(r"\bmin\.\s*([0-9]+(?:\+[0-9]+)?')", value, flags=re.I)
    return match.group(1) if match else ""


def signo_for_score(match_id, home_goals, away_goals):
    if home_goals is None or away_goals is None:
        return "-"
    if int(match_id) == 15:
        return f"{home_goals}-{away_goals}"
    if home_goals > away_goals:
        return "1"
    if home_goals < away_goals:
        return "2"
    return "X"


def parse_match_title(text):
    match = re.match(r"^\s*(\d+)\s+(.+?)\s+\([^)]+\)\s*-\s*(.+?)\s+\([^)]+\)", text)
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
            minute = clean(parent.find("span", class_=re.compile("font-bold")).get_text(" ", strip=True) if parent else "")
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
    status = "LIVE" if minute else ("FT" if score_home is not None and score_away is not None else "NS")
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
        prev = detail.find_previous_sibling("tr")
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
        status = "LIVE" if minute else ("FT" if score_home is not None and score_away is not None else "NS")
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
