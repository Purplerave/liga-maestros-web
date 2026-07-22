import json
import re
from pathlib import Path
import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
URL = "https://www.quiniela15.com/pronostico-quiniela/jornada-75"

MONTHS = {
    "ene": 1, "enero": 1, "feb": 2, "febrero": 2, "mar": 3, "marzo": 3,
    "abr": 4, "abril": 4, "may": 5, "mayo": 5, "jun": 6, "junio": 6,
    "jul": 7, "julio": 7, "ago": 8, "agosto": 8, "sep": 9, "sept": 9,
    "oct": 10, "octubre": 10, "nov": 11, "noviembre": 11, "dic": 12, "diciembre": 12,
}

def clean(text):
    return re.sub(r"\s+", " ", str(text or "")).strip()

def scrape_j75():
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) LigaMaestros/1.0"}
    r = requests.get(URL, headers=headers, timeout=25)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    page_text = soup.get_text("\n", strip=True)
    
    jornada_match = re.search(r"Jornada\s+(\d+)", page_text, flags=re.I)
    if not jornada_match:
        print("No se encontro jornada")
        return
    
    jornada = int(jornada_match.group(1))
    print(f"Jornada: {jornada}")
    
    cierre = ""
    cierre_match = re.search(r"Cierre:\s*(.*?)\s*\.\s*Participan", clean(page_text), flags=re.I)
    if cierre_match:
        cierre = clean(cierre_match.group(1))
    print(f"Cierre: {cierre}")
    
    rows = soup.find_all("tr")
    partidos = []
    
    for row in rows:
        cells = row.find_all("td")
        if len(cells) < 5:
            continue
        
        num_text = clean(cells[0].get_text())
        if not num_text.isdigit():
            continue
        
        num = int(num_text)
        
        teams = cells[1].find_all("span")
        if len(teams) >= 2:
            local = clean(teams[0].get_text())
            visitante = clean(teams[1].get_text())
        else:
            text = clean(cells[1].get_text())
            parts = text.split(" - ")
            if len(parts) == 2:
                local, visitante = clean(parts[0]), clean(parts[1])
            else:
                continue
        
        probs_text = clean(cells[2].get_text()) if len(cells) > 2 else ""
        probs = {}
        for sign in ["1", "X", "2"]:
            match = re.search(rf"{sign}:\s*(\d+)%", probs_text)
            if match:
                probs[sign] = int(match.group(1))
        
        sistema = clean(cells[3].get_text()) if len(cells) > 3 else ""
        comunidad = clean(cells[4].get_text()) if len(cells) > 4 else ""
        
        partido = {
            "num": num,
            "local": local,
            "visitante": visitante,
            "sistema": sistema,
            "comunidad": comunidad,
            "q15": probs,
        }
        partidos.append(partido)
        print(f"  {num}. {local} - {visitante}")
    
    output = {
        "jornada": jornada,
        "source_url": URL,
        "scraped_at": __import__("datetime").datetime.now().isoformat(),
        "cierre": cierre,
        "partidos": partidos,
    }
    
    out_path = ROOT / "data" / f"quiniela15_J{jornada}_scrape.json"
    out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"OK: JSON guardado en {out_path}")

if __name__ == "__main__":
    scrape_j75()
