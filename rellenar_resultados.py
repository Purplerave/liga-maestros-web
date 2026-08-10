# Restaura una jornada de la quiniela en la BD: partidos que falten (desde el
# boleto del repo) + resultados oficiales (desde quiniela15.com). Idempotente.
# Uso:   python rellenar_resultados.py --jornada 74
import argparse
import json
import os
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument("--jornada", type=int, required=True)
parser.add_argument("--solo-resultados", action="store_true", help="No inserta partidos, solo rellena marcadores.")
args = parser.parse_args()
J = args.jornada

DB = Path(os.getenv("DB_PATH", "").strip() or (ROOT / "DATOS" / "LIGA_MAESTROS_PRO.db"))
SCRAPE_JSON = ROOT / "data" / f"quiniela15_J{J}_scrape.json"

sys.path.insert(0, str(ROOT / "tools" / "scrapers"))
try:
    from SCRAPE_QUINIELA15_DIRECTO import scrape
except Exception as exc:
    print(f"ERROR importando el scraper del repo: {exc}")
    print("Ejecuta primero:  pip install requests beautifulsoup4")
    sys.exit(1)

if not DB.exists():
    print(f"ERROR: no encuentro la base de datos {DB}")
    sys.exit(1)

fixture = []
if SCRAPE_JSON.exists():
    data = json.loads(SCRAPE_JSON.read_text(encoding="utf-8"))
    if int(data.get("jornada") or 0) == J:
        horarios = data.get("horarios") or {}
        for p in data.get("partidos") or []:
            num = int(p.get("num") or p.get("id") or 0)
            h = horarios.get(str(num)) or {}
            fixture.append(
                (
                    num,
                    str(p.get("local") or "").strip(),
                    str(p.get("visitante") or "").strip(),
                    str(h.get("fecha") or p.get("fecha") or "").strip()[:10],
                    str(h.get("hora") or p.get("hora") or "").strip()[:5],
                )
            )
        fixture.sort(key=lambda m: m[0])


def signo(pid, gh, ga):
    if pid == 15:
        return f"{gh}-{ga}"
    return "1" if gh > ga else ("2" if gh < ga else "X")


print(f"Descargando resultados oficiales de quiniela15.com (jornada {J}) ...")
payload = scrape(J)
matches = [m for m in (payload.get("matches") or []) if m.get("id")]
if int(payload.get("jornada") or 0) != J or len(matches) != 15:
    print(f"ERROR: la pagina devolvio jornada={payload.get('jornada')} con {len(matches)} partidos")
    sys.exit(1)

conn = sqlite3.connect(DB)
rows = conn.execute(
    "SELECT partido_id, local, visitante, goles_local, goles_visitante, status, fecha, hora, rowid"
    " FROM resultados WHERE jornada = ?",
    (J,),
).fetchall()
by_id = {int(r[0]): r for r in rows}
print(f"Estado previo J{J}: {len(by_id)}/15 partidos en BD")

backup = DB.with_suffix(f".bak_relleno_{datetime.now():%Y%m%d_%H%M%S}.db")
shutil.copy2(DB, backup)
print(f"Backup creado: {backup}\n")

cambios = 0
if not args.solo_resultados:
    if len(fixture) != 15:
        print(f"AVISO: no hay boleto del repo para la J{J} ({SCRAPE_JSON.name}); no inserto partidos.")
    else:
        for num, local, visitante, fecha, hora in fixture:
            row = by_id.get(num)
            if row is None:
                conn.execute(
                    "INSERT INTO resultados (jornada, partido_id, local, visitante, status, fecha, hora,"
                    " goles_local, goles_visitante, minuto, signo_actual)"
                    " VALUES (?, ?, ?, ?, 'NS', ?, ?, NULL, NULL, '', '-')",
                    (J, num, local, visitante, fecha, hora),
                )
                print(f"  + partido #{num:>2}: {local} - {visitante}")
                cambios += 1
            elif (not str(row[6] or "").strip() or str(row[7] or "").strip() in ("", "-")) and fecha:
                conn.execute(
                    "UPDATE resultados SET fecha = ?, hora = ? WHERE jornada = ? AND partido_id = ?",
                    (fecha, hora, J, num),
                )
        conn.commit()
        rows = conn.execute(
            "SELECT partido_id, local, visitante, goles_local, goles_visitante, status, fecha, hora, rowid"
            " FROM resultados WHERE jornada = ?",
            (J,),
        ).fetchall()
        by_id = {int(r[0]): r for r in rows}

if len(by_id) != 15:
    print(f"ERROR: la J{J} sigue con {len(by_id)}/15 partidos; sin boleto del repo no puedo completarla.")
    conn.close()
    sys.exit(1)

for m in sorted(matches, key=lambda x: x["id"]):
    gh, ga = m.get("score_home"), m.get("score_away")
    pid = int(m["id"])
    if gh is None or ga is None:
        print(f"  ! #{pid:>2}: quiniela15 aun no publica marcador; no se toca")
        continue
    row = by_id[pid]
    gh, ga = int(gh), int(ga)
    sgn = signo(pid, gh, ga)
    if row[3] == gh and row[4] == ga and str(row[5] or "").upper() == "FT":
        continue
    conn.execute(
        "UPDATE resultados SET goles_local = ?, goles_visitante = ?, status = 'FT',"
        " minuto = 'Finalizado', signo_actual = ? WHERE jornada = ? AND partido_id = ?",
        (gh, ga, sgn, J, pid),
    )
    print(f"  ~ #{pid:>2}: {row[1]} - {row[2]}  =>  {gh}-{ga} ({sgn}) FT")
    cambios += 1

conn.commit()
fin = conn.execute(
    "SELECT COUNT(*), SUM(CASE WHEN goles_local IS NOT NULL AND status = 'FT' THEN 1 ELSE 0 END)"
    " FROM resultados WHERE jornada = ?",
    (J,),
).fetchone()
conn.close()
print(f"\nCambios aplicados: {cambios}")
print(f"Estado final J{J}: {fin[0]}/15 partidos, {fin[1]}/15 con marcador FT")
print("OK - recarga la web." if fin[0] == 15 and fin[1] == 15 else "AVISO: revisa las lineas de arriba.")
