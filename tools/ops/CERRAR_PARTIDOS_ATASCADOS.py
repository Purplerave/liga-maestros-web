"""Cierra en produccion los partidos atascados en LIVE y lista los pendientes.

El colector ya aplica estas reglas en cada pasada, pero este script permite
repararlo AHORA (sin esperar al siguiente ciclo) y ver que se va a tocar antes
de tocarlo.

Uso:
    python tools/ops/CERRAR_PARTIDOS_ATASCADOS.py            # solo informe
    python tools/ops/CERRAR_PARTIDOS_ATASCADOS.py --aplicar  # escribe cambios
    python tools/ops/CERRAR_PARTIDOS_ATASCADOS.py --jornada 1 --aplicar

Acciones posibles por partido:
    reset_to_scheduled  estaba "en juego" antes de su hora de inicio -> vuelve
                        a pendiente y se descarta el marcador fantasma
    close_no_data       congelado o incoherente -> STALE conservando marcador
    close_final         se agoto la ventana de partido -> FT con signo
    pending_overdue     programado, hora pasada hace horas y sin resultado
                        (solo se informa: hay que revisar el proveedor)
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from liga_maestros.db.connection import get_db  # noqa: E402
from liga_maestros.services.jornada import resolve_active_jornada  # noqa: E402
from liga_maestros.services.live_state import (  # noqa: E402
    PENDING_OVERDUE,
    closes_live,
    evaluate_match_state,
)
from liga_maestros.services.ticket import madrid_now, parse_madrid_datetime  # noqa: E402


def _updated_at(row):
    from datetime import datetime

    try:
        raw = row["updated_at"]
    except (IndexError, KeyError):
        return None
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw))
    except ValueError:
        return None


def audit(jornada=None):
    """Return (jornada, decisions) without writing anything."""
    with get_db() as conn:
        target = int(jornada) if jornada else resolve_active_jornada(conn)
        columns = {row[1] for row in conn.execute("PRAGMA table_info(resultados)").fetchall()}
        updated_at_select = "updated_at" if "updated_at" in columns else "NULL AS updated_at"
        rows = conn.execute(
            f"""
            SELECT partido_id, local, visitante, fecha, hora, status, minuto, {updated_at_select}
            FROM resultados WHERE jornada = ? ORDER BY partido_id
            """,  # noqa: S608 - column name from a local allowlist, never user input
            (target,),
        ).fetchall()

    now = madrid_now()
    decisions = []
    for row in rows:
        kickoff = parse_madrid_datetime(row["fecha"], row["hora"])
        decision = evaluate_match_state(
            row["status"],
            kickoff,
            now,
            last_update_at=_updated_at(row),
            minute=row["minuto"],
        )
        if decision["action"] == PENDING_OVERDUE or closes_live(decision["action"]):
            decisions.append((dict(row), decision))
    return target, decisions


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--jornada", type=int, help="Jornada concreta (por defecto, la activa).")
    parser.add_argument("--aplicar", action="store_true", help="Escribe los cambios (por defecto solo informa).")
    args = parser.parse_args()

    jornada, decisions = audit(args.jornada)
    print(f"Jornada {jornada} - {madrid_now():%Y-%m-%d %H:%M} (Europe/Madrid)")
    if not decisions:
        print("Sin partidos atascados ni pendientes fuera de plazo.")
        return

    for row, decision in decisions:
        print(
            f"  #{row['partido_id']:>2} {row['local']} - {row['visitante']}"
            f" | {row['status']} {row['minuto'] or ''} inicio={row['fecha']} {row['hora']}"
            f" -> {decision['action']} ({decision['reason']})"
        )

    closable = [item for item in decisions if closes_live(item[1]["action"])]
    pending = [item for item in decisions if item[1]["action"] == PENDING_OVERDUE]
    if pending:
        print(f"\n{len(pending)} partido(s) pendientes sin resultado: revisar el proveedor, no se tocan aqui.")

    if not args.aplicar:
        print(f"\nSimulacion: {len(closable)} partido(s) se cerrarian. Repite con --aplicar para escribir.")
        return

    if not closable:
        print("\nNada que cerrar.")
        return

    from LIVE_COLLECTOR import close_stuck_live_matches  # noqa: PLC0415

    closed = close_stuck_live_matches(jornada)
    print(f"\nCerrados {len(closed)} partido(s).")


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    main()
