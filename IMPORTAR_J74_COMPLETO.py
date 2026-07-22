"""
IMPORTAR J74 COMPLETO - Script maestro que importa TODO de la Jornada 74:
- Partidos scrapeados de Quiniela15
- Predicciones de todos los Maestros (ChatGPT, Gemini, Grok, Copilot, Claude)
- Predicciones de La Peña (BAIDU, GELO, KIMI, PERPLEXITY, META, DEEPSEEK, QWEN, GEMA, JIMBY, SESUDO, FISTRO)
- Oráculo (Tarot - MiMo)
- Consenso de la comunidad
"""

import json
import sqlite3
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"

# Try to use config.DB_PATH, fallback to local path
try:
    sys.path.insert(0, str(ROOT))
    import config
    DB_PATH = Path(config.DB_PATH)
except Exception:
    DB_PATH = ROOT / "DATOS" / "LIGA_MAESTROS_PRO.db"

# =============================================================================
# PREDICCIONES DE LOS MAESTROS - J74
# =============================================================================

MAESTROS_PREDICCIONES = {
    "programa": {
        "nombre": "Programa Quiniela",
        "signos": ["1", "1", "X", "2", "2", "2", "1", "1", "2", "X", "1", "2", "1", "1", "X"],
        "pleno": "1-1"
    },
    "chatgpt": {
        "nombre": "ChatGPT",
        "signos": ["1", "1", "X", "2", "2", "2", "1", "1", "2", "X", "1", "2", "1", "1", "X"],
        "pleno": "1-1"
    },
    "gemini": {
        "nombre": "Gemini",
        "signos": ["1", "1", "1", "2", "2", "2", "1", "1", "2", "X", "1", "2", "1", "1", "1"],
        "pleno": "2-1"
    },
    "grok": {
        "nombre": "Grok",
        "signos": ["1", "1", "X", "2", "X", "2", "1", "1", "2", "X", "1", "2", "1", "1", "X"],
        "pleno": "2-2"
    },
    "copilot": {
        "nombre": "Copilot",
        "signos": ["1", "1", "X", "2", "2", "2", "1", "1", "2", "X", "1", "2", "1", "1", "X"],
        "pleno": "2-2"
    },
    "claude": {
        "nombre": "Claude",
        "signos": ["1", "1", "2", "2", "2", "2", "1", "1", "2", "X", "1", "2", "1", "X", "1"],
        "pleno": "2-1"
    },
}

# =============================================================================
# PREDICCIONES DE LA PEÑA (IAs alternativas)
# =============================================================================

PENA_PREDICCIONES = {
    "baidu": {"nombre": "BAIDU", "fuente": "Ernie (Baidu)"},
    "geli": {"nombre": "GELO", "fuente": "GLM-5 (Zhipu AI)"},
    "kimi": {"nombre": "KIMI", "fuente": "Moonshot AI"},
    "pepe": {"nombre": "PERPLEXITY", "fuente": "Perplexity AI"},
    "profe": {"nombre": "META", "fuente": "Llama (Meta)"},
    "chipi": {"nombre": "DEEPSEEK", "fuente": "DeepSeek"},
    "fortu": {"nombre": "QWEN", "fuente": "Qwen (Alibaba)"},
    "gema": {"nombre": "GEMA", "fuente": "Gemma 4B"},
    "jimmy": {"nombre": "JIMMY", "fuente": "???"},
    "sesudo": {"nombre": "SESUDO", "fuente": "Grok 4.5 (LM Arena)"},
    "fistro": {"nombre": "FISTRO", "fuente": "LM Arena Agentic IA"},
}

# =============================================================================
# ORÁCULO (TAROT)
# =============================================================================

ORACULO_PREDICCION = {
    "oraculo": {
        "nombre": "ORÁCULO",
        "signos": ["1", "X", "1", "2", "1X", "1", "1", "1", "2", "X", "1", "2", "1", "1", "X"],
        "pleno": "1-1"
    }
}


def load_scraped_data():
    """Carga los datos scrapeados de J74."""
    path = DATA_DIR / "quiniela15_J74_scrape.json"
    if not path.exists():
        raise FileNotFoundError(f"No encuentro {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_horarios():
    """Carga los horarios de J74."""
    path = DATA_DIR / "horarios_J74.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def backup_db():
    """Crea backup de la base de datos."""
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = DB_PATH.with_suffix(f".bak_j74_{stamp}.db")
    shutil.copy2(DB_PATH, backup)
    return backup


def import_j74():
    """Importa toda la Jornada 74."""
    # Verificar si J74 ya está importada
    if DB_PATH.exists():
        conn_check = sqlite3.connect(str(DB_PATH))
        existing = conn_check.execute("SELECT COUNT(*) FROM resultados WHERE jornada = 74").fetchone()[0]
        conn_check.close()
        if existing > 0:
            print("J74 ya está importada. Saltando.")
            return None

    print("=" * 60)
    print("IMPORTACIÓN COMPLETA JORNADA 74")
    print("=" * 60)
    
    # Cargar datos
    scraped = load_scraped_data()
    horarios = load_horarios()
    partidos = scraped.get("partidos", [])
    
    print(f"\n📋 Partidos encontrados: {len(partidos)}")
    print(f"📅 Cierre: {scraped.get('cierre', 'No especificado')}")
    
    if len(partidos) != 15:
        raise ValueError(f"Se esperaban 15 partidos, hay {len(partidos)}")
    
    # Backup
    backup = backup_db()
    print(f"\n💾 Backup creado: {backup}")
    
    # Conectar a la BD
    with sqlite3.connect(DB_PATH) as conn:
        # 1. Crear/actualizar usuarios
        print("\n👥 Creando usuarios...")
        all_users = {}
        all_users.update(MAESTROS_PREDICCIONES)
        all_users.update(ORACULO_PREDICCION)
        for uid, info in all_users.items():
            conn.execute(
                """INSERT INTO usuarios (id, nombre, email, puntos_acumulados, notificaciones, peso)
                   VALUES (?, ?, ?, 0, 1, 1.0)
                   ON CONFLICT(id) DO UPDATE SET nombre=excluded.nombre""",
                (uid, info["nombre"], f"{uid}@liga-maestros.local")
            )
            print(f"  ✓ {info['nombre']}")
        
        # Usuarios de La Peña (sin predicciones aún)
        for uid, info in PENA_PREDICCIONES.items():
            conn.execute(
                """INSERT INTO usuarios (id, nombre, email, puntos_acumulados, notificaciones, peso)
                   VALUES (?, ?, ?, 0, 1, 1.0)
                   ON CONFLICT(id) DO UPDATE SET nombre=excluded.nombre""",
                (uid, info["nombre"], f"{uid}@liga-maestros.local")
            )
            print(f"  ✓ {info['nombre']} (La Peña)")
        
        # 2. Insertar partidos
        print("\n⚽ Insertando partidos...")
        conn.execute("DELETE FROM resultados WHERE jornada = 74")
        for match in partidos:
            horario = horarios.get(str(match["num"]), {})
            fecha = match.get("fecha", horario.get("fecha", ""))
            hora = match.get("hora", horario.get("hora", ""))
            
            conn.execute(
                """INSERT INTO resultados 
                   (jornada, partido_id, local, visitante, goles_local, goles_visitante,
                    status, fecha, hora, minuto, signo_actual, jornada_liga)
                   VALUES (?, ?, ?, ?, NULL, NULL, 'NS', ?, ?, '', '-', NULL)""",
                (74, int(match["num"]), match["local"], match["visitante"], fecha, hora)
            )
            print(f"  {match['num']:2d}. {match['local']:20s} vs {match['visitante']}")
        
        # 3. Insertar predicciones de Maestros
        print("\n🤖 Insertando predicciones de Maestros...")
        conn.execute("DELETE FROM predicciones WHERE jornada = 74 AND user_id IN ({})".format(
            ",".join(f"'{k}'" for k in MAESTROS_PREDICCIONES.keys())
        ))
        for uid, info in MAESTROS_PREDICCIONES.items():
            for idx, signo in enumerate(info["signos"], start=1):
                conn.execute(
                    "INSERT INTO predicciones (user_id, jornada, partido_id, signo) VALUES (?, ?, ?, ?)",
                    (uid, 74, idx, signo)
                )
            print(f"  ✓ {info['nombre']}: {' '.join(info['signos'])}")
        
        # 4. Insertar predicción del Oráculo
        print("\n🔮 Insertando predicción del Oráculo...")
        for uid, info in ORACULO_PREDICCION.items():
            for idx, signo in enumerate(info["signos"], start=1):
                conn.execute(
                    "INSERT INTO predicciones (user_id, jornada, partido_id, signo) VALUES (?, ?, ?, ?)",
                    (uid, 74, idx, signo)
                )
            print(f"  ✓ {info['nombre']}: {' '.join(info['signos'])}")
        
        # 5. Insertar consenso de la comunidad (de los datos scrapeados)
        print("\n📊 Insertando consenso de la comunidad...")
        conn.execute("DELETE FROM consenso WHERE jornada = 74")
        for match in partidos:
            q15 = match.get("q15") or {}
            lae = match.get("lae") or {}
            apu = match.get("apu") or {}
            
            # Promedio de las tres fuentes
            p1 = round((q15.get("1", 0) + lae.get("1", 0) + apu.get("1", 0)) / 3)
            px = round((q15.get("X", 0) + lae.get("X", 0) + apu.get("X", 0)) / 3)
            p2 = round((q15.get("2", 0) + lae.get("2", 0) + apu.get("2", 0)) / 3)
            
            ganador = "1" if p1 >= px and p1 >= p2 else ("X" if px >= p1 and px >= p2 else "2")
            
            conn.execute(
                "INSERT INTO consenso (jornada, partido_id, ganador, p1, px, p2) VALUES (?, ?, ?, ?, ?, ?)",
                (74, int(match["num"]), ganador, p1, px, p2)
            )
            print(f"  {match['num']:2d}. {match['local']:20s} vs {match['visitante']:20s} → {ganador} ({p1}%/{px}%/{p2}%)")
        
        conn.commit()
    
    print("\n" + "=" * 60)
    print("✅ IMPORTACIÓN COMPLETA FINALIZADA")
    print("=" * 60)
    print(f"\n📋 Resumen:")
    print(f"  • 15 partidos importados")
    print(f"  • {len(MAESTROS_PREDICCIONES)} Maestros con predicciones")
    print(f"  • 1 Oráculo (Tarot) con predicción")
    print(f"  • {len(PENA_PREDICCIONES)} miembros de La Peña registrados (pendientes predicciones)")
    print(f"  • Consenso de comunidad calculado")
    print(f"\n💾 Backup: {backup}")
    print(f"\n🎯 Próximos pasos:")
    print(f"  1. Reiniciar el servidor Flask")
    print(f"  2. Verificar que J74 aparece en la web")
    print(f"  3. Recoger predicciones de La Peña cuando las tengan")


if __name__ == "__main__":
    import_j74()
