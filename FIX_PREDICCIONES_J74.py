"""
FIX PREDICCIONES J74 - Corrige las predicciones de todos los maestros y la peña
"""
import sqlite3

DB_PATH = "C:/Users/Mortadelo/Desktop/QUINIELAs/LIGA_MAESTROS/DATOS/LIGA_MAESTROS_PRO.db"

# Predicciones correctas del archivo J74_MAESTROS_RESUMEN.md
CORRECT_PREDICTIONS = {
    # MAESTROS
    "programa":  "11X222112X1211X",
    "chatgpt":   "11X222112X1211X",
    "gemini":    "111222112X12111",
    "grok":      "11X2X2112X1211X",
    "copilot":   "11X222112X1211X",
    "claude":    "112222112X121X1",
    "oraculo":   "1X121X1112X1211X",  # 15 signs (will fix below)
    
    # LA PEÑA
    "baidu":     "1X122X1121121X2",
    "geli":      "1112X21X2212111",
    "kimi":      "11X222112112111",
    "pepe":      "111222112112111",
    "profe":     "111222112112111",
    "chipi":     "111222112112111",
    "fortu":     "111222112112111",
    "gema":      "111222112112111",
    "jimmy":     "111222112112111",
    "sesudo":    "111222112112111",
    "fistro":    "111222112112111",
}

# Nombres correctos
CORRECT_NAMES = {
    "programa": "Programa",
    "chatgpt": "ChatGPT",
    "gemini": "Gemini",
    "grok": "Grok",
    "copilot": "Copilot",
    "claude": "Claude",
    "oraculo": "ORÁCULO",
    "baidu": "BAIDU",
    "geli": "GELO",
    "kimi": "KIMI",
    "pepe": "PERPLEXITY",
    "profe": "META",
    "chipi": "DEEPSEEK",
    "fortu": "QWEN",
    "gema": "GEMA",
    "jimmy": "JIMMY",
    "sesudo": "SESUDO",
    "fistro": "FISTRO",
}

def fix_predictions():
    conn = sqlite3.connect(DB_PATH)
    
    print("=" * 60)
    print("CORRECCIÓN DE PREDICCIONES J74")
    print("=" * 60)
    
    for user_id, signs in CORRECT_PREDICTIONS.items():
        # Ensure exactly 15 signs
        if len(signs) != 15:
            print(f"⚠️  {user_id}: {len(signs)} signos (esperados 15)")
            signs = signs[:15]  # Truncate to 15
        
        # Delete existing predictions
        conn.execute("DELETE FROM predicciones WHERE user_id=? AND jornada=74", (user_id,))
        
        # Insert correct predictions
        for idx, sign in enumerate(signs, start=1):
            conn.execute(
                "INSERT INTO predicciones (user_id, jornada, partido_id, signo) VALUES (?, 74, ?, ?)",
                (user_id, idx, sign)
            )
        
        name = CORRECT_NAMES.get(user_id, user_id)
        print(f"✓ {name:15s}: {' '.join(signs)}")
    
    conn.commit()
    conn.close()
    
    print("\n" + "=" * 60)
    print("✅ CORRECCIÓN COMPLETADA")
    print("=" * 60)

if __name__ == "__main__":
    fix_predictions()
