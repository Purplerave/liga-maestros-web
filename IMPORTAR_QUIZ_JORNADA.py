"""
IMPORTAR_QUIZ_JORNADA.py

Importa un banco de preguntas de quiz a la BD de Liga de Maestros.

Formato del JSON de entrada (QUIZ_BANK_J{N}.json):

{
  "jornada": 72,
  "generated_at": "2026-07-05T12:00:00",
  "preguntas": [
    {
      "tipo": "multiple",
      "enunciado": "Quien llega lider a esta jornada?",
      "opcion_a": "Barcelona",
      "opcion_b": "Real Madrid",
      "opcion_c": "Atletico Madrid",
      "respuesta_correcta": "B",
      "explicacion": "El Real Madrid llega lider con 72 puntos.",
      "dificultad": 1,
      "tema": "actualidad"
    },
    ...
  ]
}

respuesta_correcta: "A", "B" o "C"

Uso:
    python IMPORTAR_QUIZ_JORNADA.py --jornada 72
    python IMPORTAR_QUIZ_JORNADA.py --jornada 72 --dry-run
    python IMPORTAR_QUIZ_JORNADA.py --jornada 72 --archivo mi_quiz.json
"""
import argparse
import json
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

import config

ROOT = Path(__file__).resolve().parent
DB_PATH = Path(config.DB_PATH)
QUIZ_DIR = ROOT / "data"


def backup_db():
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = DB_PATH.with_suffix(f".bak_quiz_J{stamp}.db")
    shutil.copy2(DB_PATH, backup)
    return backup


def load_quiz_json(jornada, custom_path=None):
    if custom_path:
        path = Path(custom_path)
    else:
        path = QUIZ_DIR / f"QUIZ_BANK_J{jornada}.json"
    
    if not path.exists():
        raise FileNotFoundError(f"No encuentro {path}. Genera el JSON de preguntas primero.")
    
    data = json.loads(path.read_text(encoding="utf-8"))
    
    preguntas = data.get("preguntas", [])
    if len(preguntas) != 10:
        raise ValueError(f"Se esperan 10 preguntas y hay {len(preguntas)}.")
    
    for i, p in enumerate(preguntas, 1):
        for campo in ("enunciado", "opcion_a", "opcion_b", "opcion_c", "respuesta_correcta"):
            if not p.get(campo):
                raise ValueError(f"Pregunta {i}: falta el campo '{campo}'.")
        respuesta = p["respuesta_correcta"].strip().upper()
        if respuesta not in ("A", "B", "C"):
            raise ValueError(f"Pregunta {i}: respuesta_correcta debe ser A, B o C, no '{respuesta}'.")
    
    return data


def import_quiz(jornada, custom_path=None, dry_run=False):
    data = load_quiz_json(jornada, custom_path)
    preguntas = data["preguntas"]
    
    if dry_run:
        print(f"DRY RUN Quiz J{jornada}")
        print(f"Preguntas: {len(preguntas)}")
        for i, p in enumerate(preguntas, 1):
            correct = p["respuesta_correcta"].strip().upper()
            opts = {"A": p["opcion_a"], "B": p["opcion_b"], "C": p["opcion_c"]}
            print(f"  {i}. [{p['tema']}] {p['enunciado']}")
            print(f"     A) {p['opcion_a']}")
            print(f"     B) {p['opcion_b']}")
            print(f"     C) {p['opcion_c']}")
            print(f"     -> {correct}) {opts[correct]}")
        return None
    
    backup = backup_db()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS quiz_preguntas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                jornada INTEGER NOT NULL,
                tipo TEXT NOT NULL DEFAULT 'multiple',
                enunciado TEXT NOT NULL,
                opcion_a TEXT NOT NULL,
                opcion_b TEXT NOT NULL,
                opcion_c TEXT NOT NULL,
                respuesta_correcta TEXT NOT NULL,
                explicacion TEXT DEFAULT '',
                dificultad INTEGER DEFAULT 1,
                tema TEXT DEFAULT '',
                activa INTEGER DEFAULT 1,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_quiz_preguntas_jornada ON quiz_preguntas(jornada, activa)")
        
        conn.execute("DELETE FROM quiz_preguntas WHERE jornada = ?", (jornada,))
        
        for p in preguntas:
            conn.execute("""
                INSERT INTO quiz_preguntas
                (jornada, tipo, enunciado, opcion_a, opcion_b, opcion_c,
                 respuesta_correcta, explicacion, dificultad, tema, activa, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
            """, (
                jornada,
                p.get("tipo", "multiple"),
                p["enunciado"],
                p["opcion_a"],
                p["opcion_b"],
                p["opcion_c"],
                p["respuesta_correcta"].strip().upper(),
                p.get("explicacion", ""),
                p.get("dificultad", 1),
                p.get("tema", ""),
                now,
            ))
        
        conn.commit()
    finally:
        conn.close()
    
    print(f"OK: Quiz J{jornada} importado ({len(preguntas)} preguntas)")
    print(f"Backup: {backup}")
    return backup


def main():
    parser = argparse.ArgumentParser(description="Importa preguntas de quiz a Liga de Maestros.")
    parser.add_argument("--jornada", "-j", type=int, required=True)
    parser.add_argument("--archivo", "-a", type=str, default=None, help="Ruta custom al JSON de preguntas")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    import_quiz(args.jornada, custom_path=args.archivo, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
