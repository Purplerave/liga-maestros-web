import os
import sqlite3

import config

from .connection import ClosingConnection, ensure_db_file


def ensure_core_tables(conn):
    """Create the complete baseline schema required by a fresh deployment."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id TEXT PRIMARY KEY,
            nombre TEXT,
            email TEXT,
            puntos_acumulados INTEGER DEFAULT 0,
            notificaciones INTEGER DEFAULT 1,
            peso REAL DEFAULT 1.0
        );
        CREATE TABLE IF NOT EXISTS resultados (
            jornada INTEGER,
            partido_id INTEGER,
            local TEXT,
            visitante TEXT,
            goles_local INTEGER,
            goles_visitante INTEGER,
            status TEXT,
            fecha DATE,
            hora TEXT,
            minuto TEXT,
            posesion_h INTEGER,
            posesion_a INTEGER,
            tiros_h INTEGER,
            tiros_a INTEGER,
            signo_actual TEXT,
            jornada_liga INTEGER,
            api_id INTEGER
        );
        CREATE TABLE IF NOT EXISTS predicciones (
            user_id TEXT,
            jornada INTEGER,
            partido_id INTEGER,
            signo TEXT
        );
        CREATE TABLE IF NOT EXISTS consenso (
            jornada INTEGER,
            partido_id INTEGER,
            ganador TEXT,
            p1 INTEGER,
            px INTEGER,
            p2 INTEGER
        );
        CREATE TABLE IF NOT EXISTS historico (
            jornada INTEGER,
            fecha DATE,
            resultado TEXT
        );
        CREATE TABLE IF NOT EXISTS clasificacion (
            equipo TEXT UNIQUE,
            pj INTEGER,
            pts INTEGER,
            division INTEGER,
            pos INTEGER,
            pg INTEGER DEFAULT 0,
            pe INTEGER DEFAULT 0,
            pp INTEGER DEFAULT 0,
            gf INTEGER DEFAULT 0,
            gc INTEGER DEFAULT 0,
            racha TEXT
        );
        CREATE TABLE IF NOT EXISTS equipos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT UNIQUE,
            division INTEGER
        );
        CREATE TABLE IF NOT EXISTS equipo_aliases (
            alias TEXT PRIMARY KEY,
            equipo_nombre TEXT
        );
        CREATE TABLE IF NOT EXISTS equipos_aliases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            equipo_id INTEGER,
            alias TEXT UNIQUE,
            nombre_canonico TEXT
        );
        CREATE TABLE IF NOT EXISTS comentarios_jornada (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            jornada INTEGER NOT NULL,
            user_id TEXT NOT NULL,
            nombre TEXT NOT NULL,
            texto TEXT NOT NULL,
            etiqueta TEXT NOT NULL DEFAULT 'Bar',
            created_at TEXT NOT NULL
        );
    """)
    conn.commit()


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


def ensure_arcade_table(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS arcade_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            nombre TEXT NOT NULL,
            score INTEGER NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_arcade_game_score
        ON arcade_scores(game_id, score DESC, created_at ASC)
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


def minimize_stored_personal_data(conn):
    """Email is used during OAuth authorization but is not needed at rest."""
    conn.execute("UPDATE usuarios SET email = NULL WHERE email IS NOT NULL")
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
            ensure_core_tables(conn)
            ensure_quiz_tables(conn)
            from .seed import apply_fixture_corrections, import_profile_history, import_public_seed_if_empty

            import_public_seed_if_empty(conn)
            apply_fixture_corrections(conn)
            ensure_predicciones_unique_index(conn)
            import_profile_history(conn)
            ensure_porra_table(conn)
            ensure_snake_table(conn)
            ensure_arcade_table(conn)
            ensure_jornada_75(conn)
            ensure_missing_indexes(conn)
            minimize_stored_personal_data(conn)
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass
            _unlock_file(lock_fh)


def ensure_jornada_75(conn):
    """Import the public J75 fixture only after the preceding jornada exists."""
    has_previous = conn.execute("SELECT 1 FROM resultados WHERE jornada = 74 LIMIT 1").fetchone()
    if not has_previous:
        return

    j75_matches = [
        (75, 1, "VPS Vaasa", "Inter Turku", "2026-08-02", "14:00"),
        (75, 2, "TPS Turku", "IFK Mariehamn", "2026-08-01", "14:00"),
        (75, 3, "AC Oulu", "Ilves Tampere", "2026-08-02", "16:00"),
        (75, 4, "FC Lahti", "FF Jaro", "2026-08-01", "17:00"),
        (75, 5, "IF Gnistan", "KuPS Kuopio", "2026-08-01", "18:00"),
        (75, 6, "Fredrikstad", "Sandefjord", "2026-08-01", "16:00"),
        (75, 7, "Start", "Viking", "2026-08-01", "18:00"),
        (75, 8, "Molde FK", "Sarpsborg", "2026-08-02", "17:00"),
        (75, 9, "KFUM Oslo", "Kristiansund", "2026-08-02", "17:00"),
        (75, 10, "Aalesunds FK", "Tromsø IL", "2026-08-02", "17:00"),
        (75, 11, "Brann", "Rosenborg", "2026-08-02", "19:15"),
        (75, 12, "Häcken", "Kalmar FF", "2026-08-01", "15:00"),
        (75, 13, "IFK Göteborg", "Degerfors IF", "2026-08-02", "14:00"),
        (75, 14, "Brommapojkarna", "Malmoe", "2026-08-02", "14:00"),
        (75, 15, "AIK", "Orgryte IS", "2026-08-02", "16:30"),
    ]

    conn.executemany(
        """
            INSERT INTO resultados (jornada, partido_id, local, visitante, status, fecha, hora, goles_local, goles_visitante)
            SELECT ?, ?, ?, ?, 'NS', ?, ?, NULL, NULL
            WHERE NOT EXISTS (
                SELECT 1 FROM resultados WHERE jornada = ? AND partido_id = ?
            )
        """,
        [match + (match[0], match[1]) for match in j75_matches],
    )

    # Publicamos solo la columna conocida del Programa. Los Maestros se
    # incorporan cuando entregan sus pronosticos; nunca se clonan.
    j75_signs = ["2", "1", "X", "1", "2", "1", "2", "1", "1", "2", "1", "1", "1", "2", "2-0"]
    conn.executemany(
        """
            INSERT INTO predicciones (user_id, jornada, partido_id, signo)
            VALUES ('programa', 75, ?, ?)
            ON CONFLICT(user_id, jornada, partido_id) DO NOTHING
        """,
        enumerate(j75_signs, start=1),
    )

    conn.commit()
