"""Corregir predicciones de La Peña J74 con datos reales del archivo original"""
import sqlite3

DB_PATH = "C:/Users/Mortadelo/Desktop/QUINIELAs/LIGA_MAESTROS/DATOS/LIGA_MAESTROS_PRO.db"

# Predicciones CORRECTAS del J74_MAESTROS_RESUMEN.md
CORRECT_PREDICTIONS = {
    "baidu":    "1X122X1121121X2",
    "geli":     "1112X21X2212111",
    "kimi":     "11X222112112111",
    "pepe":     "111222112112111",
    "profe":    "11122211211211X",  # META
    "chipi":    "111222112X1X111",  # DEEPSEEK
    "fortu":    "1112X2112X1211X",  # QWEN
    "gema":     "11X222112X1211X",  # GEMA
    "jimmy":    "2X12221121121X1",  # JIMMY
    "sesudo":   "111222112X121X1",  # SESUDO
    "fistro":   "1112221122121X1",  # FISTRO
}

def fix_penya():
    conn = sqlite3.connect(DB_PATH)
    print("=== CORRECCIÓN PREDICCIONES LA PEÑA J74 ===\n")
    
    for user_id, signs in CORRECT_PREDICTIONS.items():
        if len(signs) != 15:
            print(f"⚠️  {user_id}: {len(signs)} signos (esperados 15)")
            signs = signs[:15]
        
        conn.execute("DELETE FROM predicciones WHERE user_id=? AND jornada=74", (user_id,))
        for idx, sign in enumerate(signs, start=1):
            conn.execute(
                "INSERT INTO predicciones (user_id, jornada, partido_id, signo) VALUES (?, 74, ?, ?)",
                (user_id, idx, sign)
            )
        print(f"✓ {user_id:12s}: {' '.join(signs)}")
    
    conn.commit()
    conn.close()
    print("\n✅ Predicciones La Peña corregidas")

if __name__ == "__main__":
    fix_penya()
