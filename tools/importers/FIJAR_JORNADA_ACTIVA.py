"""
FIJAR_JORNADA_ACTIVA.py — Fija la jornada activa en runtime/data/ESTADO_MAESTRO_ACTUAL.json
preservando el resto de claves (ranking, participantes...).

Uso: python FIJAR_JORNADA_ACTIVA.py --jornada 3
Requiere entorno de la web (config resuelve DATA_DIR igual que la app).
"""
from __future__ import annotations

import argparse
import json
import os

import config


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jornada", type=int, required=True)
    args = ap.parse_args()

    ruta = os.path.join(config.DATA_DIR, "ESTADO_MAESTRO_ACTUAL.json")
    try:
        estado = json.load(open(ruta, encoding="utf-8"))
    except Exception:
        estado = {}
    estado.update({
        "jornada_actual": args.jornada,
        "jornada": args.jornada,
        "titulo": "Jornada %d - Liga de Maestros" % args.jornada,
        "fase": "en_curso",
    })
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(estado, f, ensure_ascii=False, indent=2)
    print("ESTADO jornada_activa ->", args.jornada)


if __name__ == "__main__":
    main()
