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
