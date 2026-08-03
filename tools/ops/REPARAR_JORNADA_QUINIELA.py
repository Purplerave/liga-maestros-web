#!/usr/bin/env python3
"""Repara una jornada de la quiniela que no muestra los 15 partidos.

Diagnostico y reparacion en un solo comando:

    python tools/ops/REPARAR_JORNADA_QUINIELA.py --jornada 75

Solo diagnostico (no escribe nada):

    python tools/ops/REPARAR_JORNADA_QUINIELA.py --jornada 75 --check

Que hace:
  1. Localiza la base de datos (DB_PATH, DATA_DIR o DATOS/LIGA_MAESTROS_PRO.db).
  2. Lee el boleto oficial data/quiniela15_J{N}_scrape.json (ya esta en el repo).
  3. Inserta los partidos que falten y rellena filas vacias ('-') o sin fecha.
  4. NUNCA toca goles, estados ni minutos de partidos jugados o en directo.
  5. Hace una copia de seguridad de la BD antes de escribir.

Es standalone a proposito: funciona aunque el resto del codigo este desactualizado.
"""

import argparse
import json
import os
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
EXPECTED_IDS = set(range(1, 16))


def find_db_path(explicit=None):
    candidates = []
    if explicit:
        candidates.append(Path(explicit))
    env_db = os.getenv("DB_PATH", "").strip()
    if env_db:
        candidates.append(Path(env_db))
    env_data = os.getenv("DATA_DIR", "").strip()
    if env_data:
        candidates.append(Path(env_data) / "LIGA_MAESTROS_PRO.db")
    candidates.append(ROOT / "DATOS" / "LIGA_MAESTROS_PRO.db")
    candidates.append(Path("/var/data/LIGA_MAESTROS_PRO.db"))
    for path in candidates:
        if path.exists():
            return path
    return candidates[-1] if candidates else None


def load_scrape_matches(jornada):
    """Devuelve [(num, local, visitante, fecha, hora)] desde el scrape del repo."""
    path = DATA_DIR / f"quiniela15_J{jornada}_scrape.json"
    if not path.exists():
        raise FileNotFoundError(
            f"No encuentro {path}. Ejecuta antes tools/scrapers/SCRAPE_QUINIELA15_PROXIMA.py "
            f"para generar el boleto de la J{jornada}."
        )
    data = json.loads(path.read_text(encoding="utf-8"))
    if int(data.get("jornada") or 0) != int(jornada):
        raise ValueError(f"{path.name} es de la J{data.get('jornada')}, no de la J{jornada}.")
    partidos = data.get("partidos") or []
    if len(partidos) != 15:
        raise ValueError(f"{path.name} trae {len(partidos)} partidos, esperaba 15.")
    horarios = data.get("horarios") or {}
    matches = []
    for item in partidos:
        num = int(item.get("num") or item.get("id") or 0)
        local = str(item.get("local") or "").strip()
        visitante = str(item.get("visitante") or "").strip()
        horario = horarios.get(str(num)) or {}
        fecha = str(horario.get("fecha") or item.get("fecha") or "").strip()[:10]
        hora = str(horario.get("hora") or item.get("hora") or "").strip()[:5]
        matches.append((num, local, visitante, fecha, hora))
    if {m[0] for m in matches} != EXPECTED_IDS:
        raise ValueError(f"{path.name} no cubre los partidos 1-15.")
    return sorted(matches, key=lambda m: m[0])


def _row_quality(r):
    score = 0
    if r[6] is not None or r[7] is not None:
        score += 4
    if str(r[5] or "").upper() not in ("", "NS", "SCHEDULED"):
        score += 2
    if str(r[1] or "").strip() not in ("", "-"):
        score += 1
    return score


def diagnose(conn, jornada):
    """Devuelve (by_id, missing, broken, duplicate_rowids) para la jornada."""
    rows = conn.execute(
        """
        SELECT partido_id, local, visitante, fecha, hora, status, goles_local, goles_visitante, rowid
        FROM resultados WHERE jornada = ? ORDER BY partido_id
        """,
        (jornada,),
    ).fetchall()
    by_id = {}
    duplicates = []
    for r in rows:
        pid = int(r[0])
        if pid in by_id:
            candidates = [by_id[pid], r]
            keep = max(candidates, key=_row_quality)
            drop = candidates[0] if keep is candidates[1] else candidates[1]
            duplicates.append(drop[8])
            by_id[pid] = keep
        else:
            by_id[pid] = r
    missing = sorted(EXPECTED_IDS - set(by_id))
    broken = []
    for num, r in sorted(by_id.items()):
        local, visitante, fecha = str(r[1] or "").strip(), str(r[2] or "").strip(), str(r[3] or "").strip()
        if not local or local == "-" or not visitante or visitante == "-" or not fecha:
            broken.append(num)
    return by_id, missing, broken, duplicates


def fix_jornada(conn, jornada, matches, by_id):
    changed = 0
    for num, local, visitante, fecha, hora in matches:
        row = by_id.get(num)
        if row is None:
            conn.execute(
                """
                INSERT INTO resultados (
                    jornada, partido_id, local, visitante, status, fecha, hora,
                    goles_local, goles_visitante, minuto, signo_actual
                ) VALUES (?, ?, ?, ?, 'NS', ?, ?, NULL, NULL, '', '-')
                """,
                (jornada, num, local, visitante, fecha, hora),
            )
            print(f"  + insertado #{num:>2}: {local} - {visitante} ({fecha} {hora})")
            changed += 1
            continue

        status = str(row[5] or "").upper()
        has_result = row[6] is not None or row[7] is not None
        in_play = status in ("LIVE", "IN PLAY", "HT", "HALF TIME BREAK", "FT", "FINISHED", "TERMINADO")
        cur_local, cur_visitante = str(row[1] or "").strip(), str(row[2] or "").strip()
        cur_fecha, cur_hora = str(row[3] or "").strip()[:10], str(row[4] or "").strip()[:5]
        incomplete = not cur_local or cur_local == "-" or not cur_visitante or cur_visitante == "-" or not cur_fecha
        identity_differs = (cur_local, cur_visitante) != (local, visitante)
        schedule_differs = bool(fecha) and (cur_fecha, cur_hora) != (fecha, hora)
        if in_play and has_result:
            continue
        if not incomplete and not (not in_play and (identity_differs or schedule_differs)):
            continue
        conn.execute(
            """
            UPDATE resultados SET local = ?, visitante = ?, fecha = ?, hora = ?
            WHERE jornada = ? AND partido_id = ?
            """,
            (local, visitante, fecha or cur_fecha, hora or cur_hora, jornada, num),
        )
        print(f"  ~ corregido #{num:>2}: {cur_local or '-'} - {cur_visitante or '-'} -> {local} - {visitante}")
        changed += 1
    return changed


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--jornada", type=int, required=True, help="Jornada a reparar (p. ej. 75).")
    parser.add_argument("--db", default="", help="Ruta explicita a la base de datos.")
    parser.add_argument("--check", action="store_true", help="Solo diagnostica, no escribe.")
    args = parser.parse_args()

    db_path = find_db_path(args.db or None)
    if not db_path or not db_path.exists():
        print(f"ERROR: no encuentro la base de datos (probe {db_path}). Usa --db o DB_PATH.")
        return 1

    matches = load_scrape_matches(args.jornada)
    conn = sqlite3.connect(db_path)
    try:
        by_id, missing, broken, duplicates = diagnose(conn, args.jornada)
        ok = sorted(set(by_id) - set(broken))
        print(f"BD: {db_path}")
        print(f"J{args.jornada} en BD: {len(by_id)}/15 partidos")
        print(f"  - correctos:   {len(ok)}" + (f" (ids {ok})" if len(ok) != 15 else ""))
        print(f"  - ausentes:    {len(missing)}" + (f" (ids {missing})" if missing else ""))
        print(f"  - vacios '-':  {len(broken)}" + (f" (ids {broken})" if broken else ""))
        print(f"  - duplicados:  {len(duplicates)}")

        if not missing and not broken and not duplicates:
            print("\nOK: la jornada esta completa, no hay nada que reparar.")
            return 0
        if args.check:
            print("\nModo --check: no he escrito nada. Ejecuta sin --check para reparar.")
            return 2

        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = db_path.with_suffix(f".bak_fix_jornada_{stamp}.db")
        shutil.copy2(db_path, backup)
        print(f"\nBackup: {backup}")

        for rowid in duplicates:
            conn.execute("DELETE FROM resultados WHERE rowid = ?", (rowid,))
        if duplicates:
            print(f"  - eliminadas {len(duplicates)} filas duplicadas")
        changed = fix_jornada(conn, args.jornada, matches, by_id)
        conn.commit()

        by_id_after, missing_after, broken_after, dupes_after = diagnose(conn, args.jornada)
        print(f"\nReparacion aplicada: {changed} filas insertadas/corregidas, {len(duplicates)} duplicados eliminados.")
        print(
            f"Estado final J{args.jornada}: {len(by_id_after)}/15 partidos"
            + (f", ausentes {missing_after}" if missing_after else "")
            + (f", vacios {broken_after}" if broken_after else "")
            + (f", duplicados {len(dupes_after)}" if dupes_after else "")
        )
        if missing_after or broken_after or len(by_id_after) != 15:
            print("AVISO: sigue sin estar completa; revisa el scrape de la jornada.")
            return 3
        print("OK: jornada completa 15/15. Recarga la web para verla.")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
