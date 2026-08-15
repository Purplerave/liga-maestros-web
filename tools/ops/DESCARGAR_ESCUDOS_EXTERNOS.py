#!/usr/bin/env python3
"""Descarga a local los escudos que hoy se sirven desde dominios ajenos.

Motivo: varios equipos apuntan a `https://www.quiniela15.com/...`. Eso es
hotlinking a un tercero: si cambian la ruta, bloquean el referer o se caen,
la quiniela aparece con huecos. Además filtra tráfico de nuestros usuarios
hacia otro dominio.

Este script recorre los TEAM_LOGOS*.json, se baja cada imagen remota a
`static/img/team_logos/` y reescribe el JSON para que apunte a la ruta local.
Es idempotente: lo ya descargado se salta.

Uso:
    python tools/ops/DESCARGAR_ESCUDOS_EXTERNOS.py            # aplica cambios
    python tools/ops/DESCARGAR_ESCUDOS_EXTERNOS.py --dry-run  # solo informa
"""

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import requests  # noqa: E402

import config  # noqa: E402

LOGO_DIR = os.path.join(config.BASE_DIR, "static", "img", "team_logos")
LOGO_FILES = ["TEAM_LOGOS.json", "TEAM_LOGOS_QUINIELA15.json"]
LOCAL_PREFIX = "/static/img/team_logos/"
TIMEOUT = 20
ALLOWED_CONTENT = ("image/png", "image/jpeg", "image/svg+xml", "image/webp", "image/gif")
EXTENSIONS = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/svg+xml": ".svg",
    "image/webp": ".webp",
    "image/gif": ".gif",
}


def slug_for(team_key):
    return re.sub(r"[^A-Za-z0-9]+", "_", str(team_key)).strip("_").upper() or "ESCUDO"


def safe_filename(team_key, content_type):
    return slug_for(team_key) + EXTENSIONS.get(content_type, ".png")


def existing_local_file(team_key):
    """Escudo ya presente en disco para esa clave, si lo hay.

    La mayoría de equipos ya tienen su PNG descargado: el JSON simplemente
    seguía apuntando al dominio externo. Reutilizarlo evita descargas
    innecesarias y arregla el hotlinking incluso sin conexión.
    """
    slug = slug_for(team_key)
    for extension in (".png", ".jpg", ".svg", ".webp", ".gif"):
        if os.path.isfile(os.path.join(LOGO_DIR, slug + extension)):
            return slug + extension
    return None


def download(url, team_key, dry_run=False):
    if dry_run:
        return None, "dry-run"
    try:
        response = requests.get(url, timeout=TIMEOUT, headers={"User-Agent": "LigaMaestros/1.0"})
        response.raise_for_status()
    except Exception as exc:
        return None, f"error de red: {exc}"

    content_type = (response.headers.get("Content-Type") or "").split(";")[0].strip().lower()
    if content_type not in ALLOWED_CONTENT:
        return None, f"tipo no permitido: {content_type or 'desconocido'}"
    if not response.content:
        return None, "respuesta vacia"

    os.makedirs(LOGO_DIR, exist_ok=True)
    filename = safe_filename(team_key, content_type)
    with open(os.path.join(LOGO_DIR, filename), "wb") as handle:
        handle.write(response.content)
    return filename, None


def process(path, dry_run=False):
    if not os.path.isfile(path):
        print(f"  (no existe: {path})")
        return 0, 0

    with open(path, encoding="utf-8") as handle:
        logos = json.load(handle)

    remote = {key: url for key, url in logos.items() if isinstance(url, str) and url.startswith("http")}
    if not remote:
        print("  Sin escudos externos. Nada que hacer.")
        return 0, 0

    print(f"  {len(remote)} escudos externos encontrados.")
    done = failed = reused = 0
    for team_key, url in sorted(remote.items()):
        local = existing_local_file(team_key)
        if local:
            if not dry_run:
                logos[team_key] = LOCAL_PREFIX + local
            reused += 1
            done += 1
            continue

        filename, error = download(url, team_key, dry_run=dry_run)
        if error and error != "dry-run":
            print(f"  [FALLO] {team_key}: {error}")
            failed += 1
            continue
        if dry_run:
            print(f"  [DRY ] {team_key} <- {url}")
            done += 1
            continue
        logos[team_key] = LOCAL_PREFIX + filename
        print(f"  [OK  ] {team_key} -> {LOCAL_PREFIX}{filename}")
        done += 1

    if reused:
        print(f"  {reused} reutilizaban un escudo que ya estaba en disco.")
    if not dry_run and done:
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(logos, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
    return done, failed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="No descarga ni escribe; solo informa.")
    args = parser.parse_args()

    total_done = total_failed = 0
    for name in LOGO_FILES:
        print(f"\n{name}:")
        done, failed = process(os.path.join(config.SEED_DATA_DIR, name), dry_run=args.dry_run)
        total_done += done
        total_failed += failed

    print(f"\nResumen: {total_done} procesados, {total_failed} fallidos.")
    if total_failed:
        print("Los fallidos conservan su URL externa; vuelve a ejecutarlo cuando haya red.")
    return 1 if total_failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
