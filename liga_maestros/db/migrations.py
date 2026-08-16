import json
import os
import sqlite3

import config

from ..utils import clean_team_key
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
            api_id INTEGER,
            updated_at TEXT
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
        CREATE TABLE IF NOT EXISTS api_rate_limit (
            scope TEXT NOT NULL,
            identity TEXT NOT NULL,
            last_seen REAL NOT NULL,
            PRIMARY KEY (scope, identity)
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
            updated_at TEXT NOT NULL,
            changes INTEGER NOT NULL DEFAULT 0
        )
    """)
    try:
        conn.execute("DROP INDEX IF EXISTS ux_porra_user_match")
    except Exception:
        pass
    conn.execute("""
        DELETE FROM porra_entries
        WHERE id NOT IN (
            SELECT MAX(id)
            FROM porra_entries
            GROUP BY user_id, jornada
        )
    """)
    try:
        conn.execute("ALTER TABLE porra_entries ADD COLUMN changes INTEGER NOT NULL DEFAULT 0")
    except Exception:
        pass
    conn.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS ux_porra_user_jornada
        ON porra_entries(user_id, jornada)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_porra_jornada_match
        ON porra_entries(jornada, partido_id)
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS porra_puntos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            jornada INTEGER NOT NULL,
            partido_id INTEGER NOT NULL,
            user_id TEXT NOT NULL,
            puntos INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(jornada, partido_id, user_id)
        )
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


def ensure_resultados_updated_at(conn):
    columns = {row[1] for row in conn.execute("PRAGMA table_info(resultados)").fetchall()}
    if "updated_at" not in columns:
        conn.execute("ALTER TABLE resultados ADD COLUMN updated_at TEXT")
    conn.commit()


def ensure_missing_indexes(conn):
    conn.execute("CREATE INDEX IF NOT EXISTS idx_resultados_api_id ON resultados(api_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_resultados_jornada_partido ON resultados(jornada, partido_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_clasificacion_div_pos ON clasificacion(division, pos)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_rate_limit_last_seen ON api_rate_limit(last_seen)")
    conn.commit()


def minimize_stored_personal_data(conn):
    conn.execute("UPDATE usuarios SET email = NULL WHERE email IS NOT NULL")
    conn.commit()
