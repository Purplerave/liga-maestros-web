-- SQLite schema snapshot for Liga de Maestros.
-- Generated from DATOS/LIGA_MAESTROS_PRO.db.
-- Keep this file updated before database migrations.

-- table: clasificacion
CREATE TABLE clasificacion 
                      (equipo TEXT UNIQUE, pj INTEGER, pts INTEGER, division INTEGER, pos INTEGER, pg INTEGER DEFAULT 0, pe INTEGER DEFAULT 0, pp INTEGER DEFAULT 0, gf INTEGER DEFAULT 0, gc INTEGER DEFAULT 0, racha TEXT);

-- table: comentarios_jornada
CREATE TABLE comentarios_jornada (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    jornada INTEGER NOT NULL,
    user_id TEXT NOT NULL,
    nombre TEXT NOT NULL,
    texto TEXT NOT NULL,
    etiqueta TEXT NOT NULL DEFAULT 'Bar',
    created_at TEXT NOT NULL
);

-- table: consenso
CREATE TABLE consenso 
                      (jornada INTEGER, partido_id INTEGER, ganador TEXT, p1 INTEGER, px INTEGER, p2 INTEGER);

-- table: equipo_aliases
CREATE TABLE equipo_aliases (
            alias TEXT PRIMARY KEY,
            equipo_nombre TEXT
        );

-- table: equipos
CREATE TABLE equipos 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT UNIQUE, division INTEGER);

-- table: equipos_aliases
CREATE TABLE equipos_aliases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            equipo_id INTEGER,
            alias TEXT UNIQUE,
            nombre_canonico TEXT
        );

-- table: historico
CREATE TABLE historico 
                      (jornada INTEGER, fecha DATE, resultado TEXT);

-- table: predicciones
CREATE TABLE predicciones 
                      (user_id TEXT, jornada INTEGER, partido_id INTEGER, signo TEXT);

-- table: resultados
CREATE TABLE resultados 
                      (jornada INTEGER, partido_id INTEGER, local TEXT, visitante TEXT, 
                       goles_local INTEGER, goles_visitante INTEGER, status TEXT, fecha DATE, hora TEXT, minuto TEXT, posesion_h INTEGER, posesion_a INTEGER, tiros_h INTEGER, tiros_a INTEGER, signo_actual TEXT, jornada_liga INTEGER, api_id INTEGER);

-- table: usuarios
CREATE TABLE usuarios (
                id TEXT PRIMARY KEY,
                nombre TEXT,
                email TEXT,
                puntos_acumulados INTEGER DEFAULT 0,
                notificaciones INTEGER DEFAULT 1
            , peso REAL DEFAULT 1.0);

-- index: idx_comentarios_jornada_created
CREATE INDEX idx_comentarios_jornada_created ON comentarios_jornada(jornada, created_at);

-- index: idx_consenso_jornada_partido
CREATE INDEX idx_consenso_jornada_partido ON consenso(jornada, partido_id);

-- index: idx_predicciones_jornada_partido
CREATE INDEX idx_predicciones_jornada_partido ON predicciones(jornada, partido_id);

-- index: idx_predicciones_user_jornada
CREATE INDEX idx_predicciones_user_jornada ON predicciones(user_id, jornada);

-- index: idx_resultados_jornada_partido
CREATE INDEX idx_resultados_jornada_partido ON resultados(jornada, partido_id);

-- index: idx_resultados_status_fecha
CREATE INDEX idx_resultados_status_fecha ON resultados(status, fecha);
