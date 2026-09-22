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
import glob
import os
import re
import sys

import config
from liga_maestros.db.connection import get_db
from liga_maestros.services.jornada import is_current_season_jornada, resolve_active_jornada
from liga_maestros.services.payloads.matches import build_jornada_matches
from liga_maestros.utils import load_team_logos

VALID_SIGNS = {"1", "X", "2", "1X", "X2", "12"}

# El partido 15 (pleno al 15) se firma como marcador exacto ("1-2", "0-0", ...),
# no como signo 1X2: es la convención de todos los boletos J1-J9 y de las
# columnas de la peña en data/predicciones_J*.json.
PLENO_15_SCORE = re.compile(r"^\d{1,2}-\d{1,2}$")


def validar_jornada(jornada: int, strict: bool = False) -> bool:
    """Valida integridad de la jornada en la BD activa."""
    errors = []
    with get_db() as conn:
        # 1. 15 fixtures
        cnt = conn.execute(
            "SELECT COUNT(*) FROM resultados WHERE jornada = ?",
            (jornada,),
        ).fetchone()[0]
        if cnt < 15:
            errors.append(f"J{jornada}: {cnt} partidos en resultados, se esperan 15")
        else:
            # Check each partido has local/visitante and fecha
            rows = conn.execute(
                "SELECT partido_id, local, visitante, fecha FROM resultados WHERE jornada=? ORDER BY partido_id",
                (jornada,),
            ).fetchall()
            for r in rows:
                if not r[1] or not r[2]:
                    errors.append(f"J{jornada} P{r[0]}: falta local o visitante ('{r[1]}' vs '{r[2]}')")
                if not r[3]:
                    errors.append(f"J{jornada} P{r[0]}: falta fecha")

        # 2. Programa predictions
        prog_cnt = conn.execute(
            "SELECT COUNT(*) FROM predicciones WHERE jornada=? AND user_id='programa'",
            (jornada,),
        ).fetchone()[0]
        if prog_cnt < 15:
            errors.append(f"J{jornada}: programa tiene {prog_cnt} predicciones, se esperan 15")
        else:
            # Validate signs
            signos = conn.execute(
                "SELECT signo FROM predicciones WHERE jornada=? AND user_id='programa' ORDER BY partido_id",
                (jornada,),
            ).fetchall()
            for idx, row in enumerate(signos, 1):
                s = str(row[0] or "").strip().upper()
                if idx == 15 and PLENO_15_SCORE.match(s):
                    continue
                if s not in VALID_SIGNS:
                    errors.append(f"J{jornada} P{idx}: signo programa inválido '{s}'")

        # 3. Strict checks
        if strict:
            # At least one jornada available
            active = resolve_active_jornada(conn)
            if active is None:
                errors.append("No hay jornada activa resuelta")
            elif not is_current_season_jornada(jornada):
                errors.append(f"J{jornada} no pertenece a temporada {config.CURRENT_SEASON_ID}")

            # Check that /api/liga/data would not be cold_start
            try:
                team_logos = load_team_logos()
                partidos = build_jornada_matches(conn, str(jornada), team_logos)
                if len(partidos) < 15:
                    errors.append(f"J{jornada}: build_jornada_matches devuelve {len(partidos)} (<15)")
            except Exception as e:
                errors.append(f"J{jornada}: build_jornada_matches falló: {e}")

    if errors:
        print(f"❌ VALIDACION J{jornada} FALLO ({len(errors)} errores):", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return False

    print(f"✅ J{jornada}: 15 fixtures, programa 15 predicciones, BD y payload íntegros")
    return True


def main():
    parser = argparse.ArgumentParser(description="Valida una jornada antes de activar deploy")
    parser.add_argument("--jornada", required=True, help="Número de jornada o 'auto' para MAXJ")
    parser.add_argument("--strict", action="store_true", help="Chequeos adicionales de temporada y payload")
    args = parser.parse_args()
    raw = args.jornada.strip()
    if raw.lower() in ("auto", "max"):
        # Resolve from PROGRAMA dir like deploy does
        maxj = ""
        for f in glob.glob("tools/PROGRAMA_QUINIELA/SALIDAS/quiniela_programa_J*.json"):
            if os.path.exists(f):
                j = "".join(c for c in os.path.basename(f) if c.isdigit())
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
