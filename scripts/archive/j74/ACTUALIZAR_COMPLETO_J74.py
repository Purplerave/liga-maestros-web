"""ARCHIVED: historical Jornada 74 utility; do not use for new jornadas.

ACTUALIZAR COMPLETO J74 - Predicciones + Plenos
"""
import os
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent
candidates = [
    os.getenv("DB_PATH", ""),
    "/home/ligademaestros/runtime/LIGA_MAESTROS_PRO.db",
    str(ROOT / "DATOS" / "LIGA_MAESTROS_PRO.db"),
]

DB_PATH = None
for candidate in candidates:
    if candidate and Path(candidate).exists():
        DB_PATH = Path(candidate)
        break

if not DB_PATH:
    print("ERROR: No se encontró la base de datos")
    exit(1)

print(f"Usando BD: {DB_PATH}")

# Predicciones COMPLETAS: signos + pleno al 15
# Formato: (signos_15, pleno_15)
ALL_PREDICTIONS = {
    # MAESTROS
    "programa":  ("11X222112X1211X", "1-1"),
    "chatgpt":   ("11X222112X1211X", "1-1"),
    "gemini":    ("111222112X12111", "2-1"),
    "grok":      ("11X2X2112X1211X", "2-2"),
    "copilot":   ("11X222112X1211X", "2-2"),
    "claude":    ("112222112X121X1", "2-1"),
    "oraculo":   ("1X121X1112X1211X", "1-1"),
    
    # LA PEÑA
    "baidu":     ("1X122X1121121X2", "1-2"),
    "geli":      ("1112X21X2212111", "2-1"),
    "kimi":      ("11X222112112111", "2-1"),
    "pepe":      ("111222112112111", "2-1"),
    "profe":     ("11122211211211X", "1-1"),
    "chipi":     ("111222112X1X111", "2-1"),
    "fortu":     ("1112X2112X1211X", "1-1"),
    "gema":      ("11X222112X1211X", "2-1"),
    "jimmy":     ("2X12221121121X1", "1-1"),
    "sesudo":    ("111222112X121X1", "1-1"),
    "fistro":    ("1112221122121X1", "1-1"),
}

def update_all():
    conn = sqlite3.connect(str(DB_PATH))
    updated = 0
    
    for user_id, (signs, pleno) in ALL_PREDICTIONS.items():
        if len(signs) != 15:
            signs = signs[:15]
        
        # La predicción completa es: 14 signos + pleno al 15
        # El pleno va en la posición 15 (partido 15)
        signs_list = list(signs[:14])
        full_signs = signs_list + [pleno]
        
        # Siempre actualizar - eliminar y reinsertar
        conn.execute("DELETE FROM predicciones WHERE user_id=? AND jornada=74", (user_id,))
        for idx, sign in enumerate(full_signs, start=1):
            conn.execute(
                "INSERT INTO predicciones (user_id, jornada, partido_id, signo) VALUES (?, 74, ?, ?)",
                (user_id, idx, sign)
            )
        updated += 1
        print(f"  ✓ {user_id}: {' '.join(full_signs[:14])} | {pleno}")
    
    conn.commit()
    conn.close()
    print(f"\n{updated} usuarios actualizados con plenos")

if __name__ == "__main__":
    update_all()
