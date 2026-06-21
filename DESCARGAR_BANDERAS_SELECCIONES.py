import json
import re
import unicodedata
from pathlib import Path

import requests


ROOT = Path(__file__).resolve().parent
LOGOS_DIR = ROOT / "static" / "img" / "team_logos"
MANIFEST_PATH = LOGOS_DIR / "manifest.json"
TEAM_LOGOS_PATH = ROOT / "data" / "TEAM_LOGOS.json"
PLAYOFF_LOGO_PATH = LOGOS_DIR / "GEN_PLAYOFF.svg"


NATIONAL_TEAMS = {
    "Alemania": ("de", ["Germany"]),
    "Arabia Saudí": ("sa", ["Saudi Arabia", "Arabia Saudi", "Saudi"]),
    "Australia": ("au", []),
    "Bélgica": ("be", ["Belgium"]),
    "Bolivia": ("bo", []),
    "Brasil": ("br", ["Brazil"]),
    "Cabo Verde": ("cv", ["Cape Verde"]),
    "Chile": ("cl", []),
    "Chipre": ("cy", ["Cyprus"]),
    "Costa de Marfil": ("ci", ["Ivory Coast", "Cote d'Ivoire", "Côte d'Ivoire"]),
    "Curaçao": ("cw", ["Curacao"]),
    "Croacia": ("hr", ["Croatia"]),
    "Dinamarca": ("dk", ["Denmark"]),
    "Ecuador": ("ec", []),
    "Egipto": ("eg", ["Egypt"]),
    "EE.UU.": ("us", ["Estados Unidos", "EE UU", "USA", "United States", "USMNT"]),
    "Escocia": ("gb-sct", ["Scotland"]),
    "Eslovenia": ("si", ["Slovenia"]),
    "España": ("es", ["Spain"]),
    "Estonia": ("ee", []),
    "Finlandia": ("fi", ["Finland"]),
    "Francia": ("fr", ["France"]),
    "Gales": ("gb-wls", ["Wales"]),
    "Grecia": ("gr", ["Greece"]),
    "Haití": ("ht", ["Haiti"]),
    "Holanda": ("nl", ["Países Bajos", "Paises Bajos", "Netherlands", "The Netherlands"]),
    "Inglaterra": ("gb-eng", ["England"]),
    "Irán": ("ir", ["Iran"]),
    "Islandia": ("is", ["Iceland"]),
    "Islas Feroe": ("fo", ["Faroe Islands", "Faroe"]),
    "Italia": ("it", ["Italy"]),
    "Japón": ("jp", ["Japan"]),
    "Letonia": ("lv", ["Latvia"]),
    "Liechtenstein": ("li", []),
    "Lituania": ("lt", ["Lithuania"]),
    "Marruecos": ("ma", ["Morocco"]),
    "México": ("mx", ["Mexico"]),
    "Noruega": ("no", ["Norway"]),
    "Nueva Zelanda": ("nz", ["New Zealand"]),
    "Paraguay": ("py", []),
    "Portugal": ("pt", []),
    "Qatar": ("qa", []),
    "Rumanía": ("ro", ["Romania"]),
    "Senegal": ("sn", []),
    "Suecia": ("se", ["Sweden"]),
    "Suiza": ("ch", ["Switzerland"]),
    "Túnez": ("tn", ["Tunisia"]),
    "Turquía": ("tr", ["Turkey", "Turkiye", "Türkiye"]),
    "Ucrania": ("ua", ["Ukraine"]),
    "Uruguay": ("uy", []),
}

SPECIAL_LOGOS = {
    "GEN_PLAYOFF.svg": [
        "Finalista 1 Playoff",
        "Finalista 2 Playoff",
        "3º Hypermotion",
        "4º Hypermotion",
        "5º Hypermotion",
        "6º Hypermotion",
        "3 Hypermotion",
        "4 Hypermotion",
        "5 Hypermotion",
        "6 Hypermotion",
    ],
}

PLAYOFF_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <defs>
    <linearGradient id="g" x1="0" x2="1" y1="0" y2="1">
      <stop offset="0" stop-color="#2dd4ff"/>
      <stop offset="1" stop-color="#f5c451"/>
    </linearGradient>
  </defs>
  <rect width="64" height="64" rx="32" fill="#08111f"/>
  <path d="M18 10h28l-3 12 6 5-7 25H22l-7-25 6-5-3-12z" fill="#101b2d" stroke="url(#g)" stroke-width="3"/>
  <path d="M24 22h16M22 31h20M25 40h14" stroke="#f5c451" stroke-width="3" stroke-linecap="round"/>
  <text x="32" y="56" text-anchor="middle" font-family="Arial, sans-serif" font-size="10" font-weight="900" fill="#38d9ff">PO</text>
</svg>
"""


def logo_key(name):
    text = unicodedata.normalize("NFD", str(name or "").upper())
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = re.sub(r"[^A-Z0-9]+", "_", text).strip("_")
    return text or "TEAM"


def mojibake(text):
    try:
        return str(text).encode("utf-8").decode("latin-1")
    except Exception:
        return str(text)


def unique_names(names):
    expanded = []
    for name in names:
        if not name:
            continue
        expanded.append(str(name))
        broken = mojibake(name)
        if broken != name:
            expanded.append(broken)
    return list(dict.fromkeys(expanded))


def load_json(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_json(path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def download_flag(code, destination):
    url = f"https://flagcdn.com/{code}.svg"
    response = requests.get(url, timeout=20)
    response.raise_for_status()
    destination.write_bytes(response.content)


def ensure_special_logos(manifest, team_logos):
    if not PLAYOFF_LOGO_PATH.exists():
        PLAYOFF_LOGO_PATH.write_text(PLAYOFF_SVG, encoding="utf-8")

    for filename, names in SPECIAL_LOGOS.items():
        rel = f"img/team_logos/{filename}"
        for name in unique_names(names):
            manifest[name] = rel
            team_logos[name] = f"/static/{rel}"


def main():
    LOGOS_DIR.mkdir(parents=True, exist_ok=True)
    manifest = load_json(MANIFEST_PATH)
    team_logos = load_json(TEAM_LOGOS_PATH)

    downloaded = 0
    failed = []
    for spanish_name, (code, aliases) in NATIONAL_TEAMS.items():
        filename = f"NAT_{logo_key(spanish_name)}.svg"
        destination = LOGOS_DIR / filename
        if not destination.exists():
            try:
                download_flag(code, destination)
                downloaded += 1
            except Exception as exc:
                failed.append(f"{spanish_name} ({code}): {exc}")
                continue

        rel = f"img/team_logos/{filename}"
        for name in unique_names([spanish_name, *aliases]):
            manifest[name] = rel
            team_logos[name] = f"/static/{rel}"

    ensure_special_logos(manifest, team_logos)

    save_json(MANIFEST_PATH, manifest)
    save_json(TEAM_LOGOS_PATH, team_logos)
    print(f"OK: {len(NATIONAL_TEAMS)} selecciones registradas; {downloaded} banderas descargadas.")
    if failed:
        print("Fallos:")
        for item in failed:
            print(f"- {item}")


if __name__ == "__main__":
    main()
