import json
import re
from pathlib import Path

import requests


BASE_DIR = Path(__file__).resolve().parent
TEAM_LOGOS_PATH = BASE_DIR / "data" / "TEAM_LOGOS.json"
OUT_DIR = BASE_DIR / "static" / "img" / "team_logos"
MANIFEST_PATH = OUT_DIR / "manifest.json"


def slugify(value: str) -> str:
    value = (value or "").upper()
    repl = {
        "Á": "A", "É": "E", "Í": "I", "Ó": "O", "Ú": "U", "Ü": "U", "Ñ": "N",
        "Ã": "A", "€": "", "™": "",
    }
    for a, b in repl.items():
        value = value.replace(a, b)
    value = re.sub(r"[^A-Z0-9]+", "_", value).strip("_")
    return value or "TEAM"


def extension_for(url: str, content_type: str) -> str:
    if "png" in content_type.lower() or url.lower().endswith(".png"):
        return ".png"
    if "webp" in content_type.lower() or url.lower().endswith(".webp"):
        return ".webp"
    if "svg" in content_type.lower() or url.lower().endswith(".svg"):
        return ".svg"
    if "jpeg" in content_type.lower() or "jpg" in content_type.lower() or url.lower().endswith(".jpg") or url.lower().endswith(".jpeg"):
        return ".jpg"
    return ".img"


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    team_logos = json.loads(TEAM_LOGOS_PATH.read_text(encoding="utf-8", errors="replace"))
    manifest = {}
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})
    downloaded = 0
    failed = []

    for team_name, url in sorted(team_logos.items()):
        if not url or not str(url).startswith(("http://", "https://")):
            continue
        try:
            response = session.get(url, timeout=30)
            response.raise_for_status()
            ext = extension_for(url, response.headers.get("Content-Type", ""))
            filename = f"{slugify(team_name)}{ext}"
            target = OUT_DIR / filename
            target.write_bytes(response.content)
            manifest[team_name] = f"img/team_logos/{filename}"
            downloaded += 1
        except Exception as exc:
            failed.append({"team": team_name, "url": url, "error": str(exc)})

    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    report = {
        "downloaded": downloaded,
        "failed": len(failed),
        "manifest": str(MANIFEST_PATH),
    }
    print(json.dumps(report, ensure_ascii=False))
    if failed:
        print(json.dumps(failed[:20], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
