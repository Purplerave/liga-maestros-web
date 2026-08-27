"""
RESTAURAR_RESULTADOS_BACKUP.py — Pana de emergencia post-importacion.

Problema que resuelve: IMPORTAR_PROGRAMA_JORNADA borra y recrea los
resultados de una jornada como NS. Si por error se importa una jornada
ya jugada, se pierden sus goles/estado.

Este tool busca en runtime/backups y junto a la BD el backup mas ANTIGUO
que contenga resultados RELLENOS (goles_local NOT NULL) para las jornadas
indicadas, hace ATTACH y restaura SOLO esas filas de resultados.
No toca predicciones ni consenso ni ninguna otra jornada.

Uso: python RESTAURAR_RESULTADOS_BACKUP.py --jornadas 1,2 [--dry-run]
"""

from __future__ import annotations

import argparse
import glob
import os
import sqlite3

import config


def candidatos() -> list[str]:
    rutas = []
    rutas += glob.glob(os.path.join(config.DATA_DIR, "backups", "*.db"))
    rutas += glob.glob(os.path.join(config.DATA_DIR, "*.bak_import_programa_*.db"))
    rutas += glob.glob(os.path.join(os.path.dirname(config.DB_PATH), "*.bak_import_programa_*.db"))
    return sorted(set(rutas), key=os.path.getmtime)


def tiene_resultados(ruta: str, jornadas: list[int]) -> bool:
    try:
        conn = sqlite3.connect(f"file:{ruta}?mode=ro", uri=True)
        cur = conn.cursor()
        for j in jornadas:
            n = cur.execute(
                "SELECT COUNT(*) FROM resultados WHERE jornada=? AND goles_local IS NOT NULL", (j,)
            ).fetchone()[0]
            if n == 0:
                conn.close()
                return False
        conn.close()
        return True
    except Exception:
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jornadas", required=True, help="p.ej. 1,2")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    jornadas = [int(x) for x in args.jornadas.split(",") if x.strip()]

    vivo = config.DB_PATH
    donador = None
    for ruta in candidatos():
        if os.path.abspath(ruta) == os.path.abspath(vivo):
            continue
        if tiene_resultados(ruta, jornadas):
            donador = ruta
            break
    if not donador:
        print("Sin backup valido con esas jornadas rellenas.")
        raise SystemExit(1)
    print("Donante:", donador)

    if args.dry_run:
        conn = sqlite3.connect(f"file:{donador}?mode=ro", uri=True)
        for j in jornadas:
            filas = conn.execute(
                "SELECT COUNT(*), SUM(goles_local IS NOT NULL) FROM resultados WHERE jornada=?", (j,)
            ).fetchone()
            print(f"  J{j}: {filas[0]} partidos ({filas[1]} con goles)")
        conn.close()
        return

    conn = sqlite3.connect(vivo)
    conn.execute("ATTACH DATABASE ? AS bk", (donador,))
    restauradas = 0
    for j in jornadas:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(resultados)")]
        colsn = ",".join(cols)
        sel = ",".join(f"bk.resultados.{c}" for c in cols)
        conn.execute("DELETE FROM resultados WHERE jornada=?", (j,))
        conn.execute(
            f"INSERT INTO main.resultados ({colsn}) SELECT {sel} FROM bk.resultados WHERE bk.resultados.jornada=?", (j,)
        )
        restauradas += conn.execute("SELECT COUNT(*) FROM resultados WHERE jornada=?", (j,)).fetchone()[0]
    conn.commit()
    conn.close()
    print(f"Restauradas {restauradas} filas de resultados para jornadas {jornadas}")


if __name__ == "__main__":
    main()
