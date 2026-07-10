import os, sqlite3
import config
from .connection import ClosingConnection, ensure_db_file


def ensure_predicciones_unique_index(conn):
    conn.execute("""
        DELETE FROM predicciones
        WHERE rowid NOT IN (
            SELECT MAX(rowid)
            FROM predicciones
            GROUP BY user_id, jornada, partido_id
        )
    """)
    conn.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS ux_predicciones_user_jornada_partido
        ON predicciones(user_id, jornada, partido_id)
    """)
    conn.commit()


def ensure_porra_table(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS porra_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            jornada INTEGER NOT NULL,
            partido_id INTEGER NOT NULL,
            user_id TEXT NOT NULL,
            nombre TEXT NOT NULL,
            goles_local INTEGER NOT NULL,
            goles_visitante INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS ux_porra_user_match
        ON porra_entries(user_id, jornada, partido_id)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_porra_jornada_match
        ON porra_entries(jornada, partido_id)
    """)
    conn.commit()


def ensure_snake_table(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS snake_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            nombre TEXT NOT NULL,
            score INTEGER NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_snake_scores_top
        ON snake_scores(score DESC, created_at ASC)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_snake_scores_user
        ON snake_scores(user_id, score DESC)
    """)
    conn.commit()


def ensure_quiz_tables(conn):
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
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_quiz_preguntas_jornada
        ON quiz_preguntas(jornada, activa)
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS quiz_participaciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            jornada INTEGER NOT NULL,
            user_id TEXT NOT NULL,
            nombre TEXT NOT NULL,
            respuestas TEXT NOT NULL,
            aciertos INTEGER NOT NULL DEFAULT 0,
            total_preguntas INTEGER NOT NULL DEFAULT 10,
            puntos INTEGER NOT NULL DEFAULT 0,
            tiempo_total_ms INTEGER DEFAULT 0,
            racha_max INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS ux_quiz_user_jornada
        ON quiz_participaciones(user_id, jornada)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_quiz_participaciones_jornada
        ON quiz_participaciones(jornada, puntos DESC)
    """)
    conn.commit()


def ensure_missing_indexes(conn):
    conn.execute("CREATE INDEX IF NOT EXISTS idx_resultados_api_id ON resultados(api_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_clasificacion_div_pos ON clasificacion(division, pos)")
    conn.commit()


def run_startup_migrations():
    ensure_db_file()
    lock_path = f"{config.DB_PATH}.schema.lock"
    os.makedirs(os.path.dirname(lock_path) or ".", exist_ok=True)

    from ..middleware.json_lock import _lock_file, _unlock_file

    with open(lock_path, "a+b") as lock_fh:
        _lock_file(lock_fh)
        conn = None
        try:
            conn = sqlite3.connect(config.DB_PATH, timeout=30, factory=ClosingConnection)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA busy_timeout = 30000")
            ensure_predicciones_unique_index(conn)
            ensure_porra_table(conn)
            ensure_snake_table(conn)
            ensure_quiz_tables(conn)
            ensure_missing_indexes(conn)
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass
            _unlock_file(lock_fh)
