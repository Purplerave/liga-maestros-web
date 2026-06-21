import argparse
import json
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

import config

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent
DB_PATH = Path(config.DB_PATH)
PROGRAMA_DIR = PROJECT_ROOT / "PROGRAMA_QUINIELA"


def signo_from_probs(probs):
    if not probs:
        return "-"
    return max(("1", "X", "2"), key=lambda sign: float(probs.get(sign, 0)))


def load_json(path):
    if not path.exists():
        raise FileNotFoundError(f"No encuentro {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_horarios(jornada):
    path = ROOT / "data" / f"horarios_J{jornada}.json"
    return load_json(path) if path.exists() else {}


def backup_db():
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = DB_PATH.with_suffix(f".bak_import_programa_{stamp}.db")
    shutil.copy2(DB_PATH, backup)
    return backup


def import_jornada(jornada, dry_run=False, allow_q15_base=False):
    q15_path = PROGRAMA_DIR / "DATOS" / f"QUINIELA15_J{jornada}.json"
    programa_path = PROGRAMA_DIR / "SALIDAS" / f"quiniela_programa_J{jornada}.json"
    q15_base_path = PROGRAMA_DIR / "SALIDAS" / f"quiniela_programa_J{jornada}_q15_base.json"
    probs_path = PROGRAMA_DIR / "DATOS" / f"PROBABILIDADES_J{jornada}.json"

    q15 = load_json(q15_path)
    if programa_path.exists():
        programa = load_json(programa_path)
        programa_source = "programa"
    elif allow_q15_base and q15_base_path.exists():
        programa = load_json(q15_base_path)
        programa_source = "q15_base"
    else:
        raise FileNotFoundError(f"No encuentro {programa_path}. Ejecuta el programa o usa --usar-q15-base.")
    probs = load_json(probs_path) if probs_path.exists() else {}
    horarios = load_horarios(jornada)

    partidos = q15.get("partidos", [])
    signos = programa.get("signos", [])
    if len(partidos) != 15:
        raise ValueError(f"QUINIELA15_J{jornada}.json debe traer 15 partidos y trae {len(partidos)}.")
    if len(signos) != 15:
        raise ValueError(f"quiniela_programa_J{jornada}.json debe traer 15 signos y trae {len(signos)}.")

    if dry_run:
        print(f"DRY RUN J{jornada}")
        print("Partidos:", len(partidos))
        print(f"Programa ({programa_source}):", " ".join(signos))
        print("Consenso:", len(probs))
        return None

    backup = backup_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO usuarios (id, nombre, email, puntos_acumulados, notificaciones, peso)
            VALUES (?, ?, ?, 0, 1, 1.0)
            ON CONFLICT(id) DO UPDATE SET nombre=excluded.nombre
            """,
            ("programa", "Programa Quiniela Maestro", "programa@example.com"),
        )

        conn.execute("DELETE FROM resultados WHERE jornada = ?", (jornada,))
        for match in partidos:
            horario = horarios.get(str(match["num"]), {})
            conn.execute(
                """
                INSERT INTO resultados (
                    jornada, partido_id, local, visitante, goles_local, goles_visitante,
                    status, fecha, hora, minuto, signo_actual, jornada_liga
                )
                VALUES (?, ?, ?, ?, NULL, NULL, 'NS', ?, ?, '', '-', NULL)
                """,
                (
                    jornada,
                    int(match["num"]),
                    match["local"],
                    match["visitante"],
                    horario.get("fecha", ""),
                    horario.get("hora", ""),
                ),
            )

        conn.execute("DELETE FROM predicciones WHERE user_id = ? AND jornada = ?", ("programa", jornada))
        for idx, signo in enumerate(signos, start=1):
            conn.execute(
                "INSERT INTO predicciones (user_id, jornada, partido_id, signo) VALUES (?, ?, ?, ?)",
                ("programa", jornada, idx, signo),
            )

        conn.execute("DELETE FROM consenso WHERE jornada = ?", (jornada,))
        for key, item in probs.items():
            p = item.get("probabilidades") or {}
            conn.execute(
                "INSERT INTO consenso (jornada, partido_id, ganador, p1, px, p2) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    jornada,
                    int(item.get("num") or key),
                    signo_from_probs(p),
                    round(float(p.get("1", 0))),
                    round(float(p.get("X", 0))),
                    round(float(p.get("2", 0))),
                ),
            )

        conn.commit()
    print(f"OK: J{jornada} importada en web.")
    print(f"Backup: {backup}")
    print(f"Programa ({programa_source}):", " ".join(signos))
    return backup


def main():
    parser = argparse.ArgumentParser(description="Importa una jornada del Programa Quiniela a la web Liga Maestros.")
    parser.add_argument("--jornada", type=int, required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--usar-q15-base", action="store_true", help="Usa la columna base scrapeada de Quiniela15 si no existe salida del programa.")
    args = parser.parse_args()
    import_jornada(args.jornada, dry_run=args.dry_run, allow_q15_base=args.usar_q15_base)


if __name__ == "__main__":
    main()
