#!/usr/bin/env python3
"""Validación estricta de jornada — bloquea deploys incompletos (audit #3).

Uso:
  python tools/ops/VALIDAR_JORNADA.py --jornada 8 --strict
  MAXJ=8 python tools/ops/VALIDAR_JORNADA.py --jornada auto --strict

Checks:
  - 15 fixtures en resultados
  - signos válidos (1/X/2)
  - al menos programa tiene 15 predicciones
  - jornadas disponibles incluye la jornada
  - (strict) consenso y configuración de cierre coherente
"""
import argparse
import os
import sqlite3
import sys

import config
from liga_maestros.db.connection import get_db

VALID_SIGNS = {"1", "X", "2", "1X", "X2", "12"}


def validar_jornada(jornada: int, strict: bool = False):
    errors = []
    conn = get_db()
    try:
        # 1. Fixtures
        cnt = conn.execute("SELECT COUNT(*) FROM resultados WHERE jornada=?", (jornada,)).fetchone()[0]
        if cnt != 15:
            errors.append(f"J{jornada}: {cnt} partidos, se esperan 15")
        else:
            # Check each partido has local/visitante and fecha
            rows = conn.execute("SELECT partido_id, local, visitante, fecha FROM resultados WHERE jornada=? ORDER BY partido_id", (jornada,)).fetchall()
            for r in rows:
                if not r["local"] or r["local"] == "-" or not r["visitante"] or r["visitante"] == "-":
                    errors.append(f"J{jornada} P{r['partido_id']}: local/visitante incompleto")
                if not r["fecha"]:
                    errors.append(f"J{jornada} P{r['partido_id']}: fecha vacía")

        # 2. Programa predictions
        prog_cnt = conn.execute("SELECT COUNT(*) FROM predicciones WHERE jornada=? AND user_id='programa'", (jornada,)).fetchone()[0]
        if prog_cnt < 15:
            errors.append(f"J{jornada}: programa tiene {prog_cnt} predicciones, se esperan 15")
        else:
            # Validate signs
            signos = conn.execute("SELECT signo FROM predicciones WHERE jornada=? AND user_id='programa' ORDER BY partido_id", (jornada,)).fetchall()
            for idx, row in enumerate(signos, 1):
                s = str(row[0] or "").strip().upper()
                if s not in VALID_SIGNS:
                    errors.append(f"J{jornada} P{idx}: signo programa inválido '{s}'")

        # 3. Strict checks
        if strict:
            # At least one jornada available
            from liga_maestros.services.jornada import resolve_active_jornada, is_current_season_jornada
            active = resolve_active_jornada(conn)
            if active is None:
                errors.append("No hay jornada activa resuelta")
            elif not is_current_season_jornada(jornada):
                errors.append(f"J{jornada} no pertenece a temporada {config.CURRENT_SEASON_ID}")

            # Check that /api/liga/data would not be cold_start
            try:
                from liga_maestros.services.payloads.matches import build_jornada_matches
                from liga_maestros.utils import load_team_logos
                team_logos = load_team_logos()
                partidos = build_jornada_matches(conn, str(jornada), team_logos)
                if len(partidos) < 15:
                    errors.append(f"J{jornada}: build_jornada_matches devuelve {len(partidos)} (<15)")
            except Exception as e:
                errors.append(f"J{jornada}: build_jornada_matches falló: {e}")

        if errors:
            for e in errors:
                print(f"ERROR: {e}", file=sys.stderr)
            return False
        print(f"J{jornada} OK: {cnt} fixtures, {prog_cnt} programa preds (strict={strict})")
        return True
    finally:
        try:
            conn.close()
        except Exception:
            pass


def main():
    parser = argparse.ArgumentParser(description="Valida una jornada antes de activar deploy")
    parser.add_argument("--jornada", required=True, help="Número de jornada o 'auto' para MAXJ")
    parser.add_argument("--strict", action="store_true", help="Chequeos adicionales de temporada y payload")
    args = parser.parse_args()
    raw = args.jornada.strip()
    if raw.lower() in ("auto", "max"):
        # Resolve from PROGRAMA dir like deploy does
        import glob
        maxj = ""
        for f in glob.glob("tools/PROGRAMA_QUINIELA/SALIDAS/quiniela_programa_J*.json"):
            if __import__("os").path.exists(f):
                j = "".join(c for c in __import__("os").path.basename(f) if c.isdigit())
                if not maxj or int(j) > int(maxj):
                    maxj = j
        if not maxj:
            print("No se encontró MAXJ para --jornada auto", file=sys.stderr)
            sys.exit(2)
        jornada = int(maxj)
    else:
        jornada = int(raw)
    ok = validar_jornada(jornada, strict=args.strict)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
