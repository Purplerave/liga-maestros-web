import json
import re
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT = "https://www.quiniela15.com/"
UA = {"User-Agent": "Mozilla/5.0"}
BASE_DIR = Path(__file__).resolve().parent
TEAM_LOGOS = BASE_DIR / "data" / "TEAM_LOGOS.json"
OUT_JSON = BASE_DIR / "data" / "TEAM_LOGOS_QUINIELA15.json"


def normalize_key(text: str) -> str:
    text = (text or "").upper()
    repl = {
        "?": "A", "?": "E", "?": "I", "?": "O", "?": "U", "?": "U", "?": "N",
    }
    for a, b in repl.items():
        text = text.replace(a, b)
    text = re.sub(r"[^A-Z0-9 ]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def nearest_team_text(img):
    for node in [img.parent, getattr(img.parent, 'parent', None), getattr(getattr(img.parent, 'parent', None), 'parent', None)]:
        if not node:
            continue
        txt = ' '.join(node.get_text(' ', strip=True).split())
        if txt and len(txt) < 60 and not re.search(r"(quiniela|resultado|hoy|pts|liga|comunidad)", txt, re.I):
            return txt
    return ''


def scrape_home():
    r = requests.get(ROOT, headers=UA, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, 'html.parser')
    mapping = {}
    for img in soup.find_all('img'):
        src = img.get('src', '')
        if 'team-flags' not in src:
            continue
        if src.startswith('/'):
            src = 'https://www.quiniela15.com' + src
        name = nearest_team_text(img)
        if not name:
            alt = (img.get('alt') or '').strip()
            if alt:
                name = alt
        if not name:
            continue
        mapping[normalize_key(name)] = src
    return mapping


def merge_into_team_logos(new_map):
    current = json.loads(TEAM_LOGOS.read_text(encoding='utf-8', errors='replace')) if TEAM_LOGOS.exists() else {}
    existing_norm = {normalize_key(k): k for k in current.keys()}
    updated = dict(current)
    added = 0
    replaced = 0
    for norm_name, src in new_map.items():
        if norm_name in existing_norm:
            key = existing_norm[norm_name]
            if not updated.get(key):
                updated[key] = src
                replaced += 1
        else:
            updated[norm_name] = src
            added += 1
    OUT_JSON.write_text(json.dumps(new_map, ensure_ascii=False, indent=2), encoding='utf-8')
    TEAM_LOGOS.write_text(json.dumps(updated, ensure_ascii=False, indent=2), encoding='utf-8')
    return added, replaced, len(new_map)


if __name__ == '__main__':
    scraped = scrape_home()
    added, replaced, total = merge_into_team_logos(scraped)
    print(json.dumps({
        'scraped': total,
        'added': added,
        'filled_empty': replaced,
        'out': str(OUT_JSON),
        'team_logos': str(TEAM_LOGOS),
    }, ensure_ascii=False))
