"""
ACTUALIZAR PREDICCIONES - Script que siempre actualiza las predicciones de J74
Ejecutar después de IMPORTAR_J74_COMPLETO.py para corregir datos
"""
import sqlite3
import sys
from pathlib import Path

# Usar config para obtener la ruta correcta de la BD
try:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import config
    DB_PATH = Path(config.DB_PATH)
except Exception:
    DB_PATH = Path(__file__).resolve().parent / "DATOS" / "LIGA_MAESTROS_PRO.db"

# Predicciones CORRECTAS del J74_MAESTROS_RESUMEN.md
CORRECT_PREDICTIONS = {
    # MAESTROS
    "programa":  "11X222112X1211X",
    "chatgpt":   "11X222112X1211X",
    "gemini":    "111222112X12111",
    "grok":      "11X2X2112X1211X",
    "copilot":   "11X222112X1211X",
    "claude":    "112222112X121X1",
    "oraculo":   "1X121X1112X1211X",
    
    # LA PEÑA
    "baidu":     "1X122X1121121X2",
    "geli":      "1112X21X2212111",
    "kimi":      "11X222112112111",
    "pepe":      "111222112112111",
    "profe":     "11122211211211X",
    "chipi":     "111222112X1X111",
    "fortu":     "1112X2112X1211X",
    "gema":      "11X222112X1211X",
    "jimmy":     "2X12221121121X1",
    "sesudo":    "111222112X121X1",
    "fistro":    "1112221122121X1",
}

def update_predictions():
    if not DB_PATH.exists():
        print(f"BD no encontrada: {DB_PATH}")
        return
    
    conn = sqlite3.connect(str(DB_PATH))
    updated = 0
    
    for user_id, signs in CORRECT_PREDICTIONS.items():
        if len(signs) != 15:
            signs = signs[:15]
        
        # Verificar si hay predicciones actuales
        current = conn.execute(
            "SELECT signo FROM predicciones WHERE user_id=? AND jornada=74 ORDER BY partido_id",
            (user_id,)
        ).fetchall()
        current_signs = "".join([r[0] for r in current]) if current else ""
        
        # Solo actualizar si son diferentes
        if current_signs != signs:
            conn.execute("DELETE FROM predicciones WHERE user_id=? AND jornada=74", (user_id,))
            for idx, sign in enumerate(signs, start=1):
                conn.execute(
                    "INSERT INTO predicciones (user_id, jornada, partido_id, signo) VALUES (?, 74, ?, ?)",
                    (user_id, idx, sign)
                )
            updated += 1
            print(f"  ✓ {user_id}: actualizado")
    
    conn.commit()
    conn.close()
    print(f"\n{updated} usuarios actualizados")

if __name__ == "__main__":
    update_predictions()
