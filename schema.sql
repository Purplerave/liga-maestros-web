-- SQLite schema snapshot for Liga de Maestros.
-- Generated from DATOS/LIGA_MAESTROS_PRO.db (fresh migrations).
-- Keep this file updated before database migrations.
-- NOTE: usuarios.email is deprecated, always NULL, kept for compatibility.

-- table: api_rate_limit
CREATE TABLE api_rate_limit (
            scope TEXT NOT NULL, identity TEXT NOT NULL, last_seen REAL NOT NULL, PRIMARY KEY (scope, identity)
        );

-- table: arcade_scores
CREATE TABLE arcade_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT, game_id TEXT NOT NULL, user_id TEXT NOT NULL,
            nombre TEXT NOT NULL, score INTEGER NOT NULL, created_at TEXT NOT NULL
        );

-- table: clasificacion
CREATE TABLE clasificacion (
            equipo TEXT UNIQUE, pj INTEGER, pts INTEGER, division INTEGER, pos INTEGER,
            pg INTEGER DEFAULT 0, pe INTEGER DEFAULT 0, pp INTEGER DEFAULT 0,
            gf INTEGER DEFAULT 0, gc INTEGER DEFAULT 0, racha TEXT
        );

-- table: comentarios_jornada
CREATE TABLE comentarios_jornada (
            id INTEGER PRIMARY KEY AUTOINCREMENT, jornada INTEGER NOT NULL, user_id TEXT NOT NULL,
            nombre TEXT NOT NULL, texto TEXT NOT NULL, etiqueta TEXT NOT NULL DEFAULT 'Bar', created_at TEXT NOT NULL
        );

-- table: consenso
CREATE TABLE consenso (
            jornada INTEGER, partido_id INTEGER, ganador TEXT, p1 INTEGER, px INTEGER, p2 INTEGER
        );

-- table: equipo_aliases
CREATE TABLE equipo_aliases (alias TEXT PRIMARY KEY, equipo_nombre TEXT);

-- table: equipos
CREATE TABLE equipos (
            id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT UNIQUE, division INTEGER
        );

-- table: equipos_aliases
CREATE TABLE equipos_aliases (
            id INTEGER PRIMARY KEY AUTOINCREMENT, equipo_id INTEGER, alias TEXT UNIQUE, nombre_canonico TEXT
        );

-- table: historico
CREATE TABLE historico (jornada INTEGER, fecha DATE, resultado TEXT);

-- table: porra_entries
CREATE TABLE porra_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT, jornada INTEGER NOT NULL, partido_id INTEGER NOT NULL,
            user_id TEXT NOT NULL, nombre TEXT NOT NULL, goles_local INTEGER NOT NULL,
            goles_visitante INTEGER NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
            changes INTEGER NOT NULL DEFAULT 0
        );

-- table: porra_puntos
CREATE TABLE porra_puntos (
            id INTEGER PRIMARY KEY AUTOINCREMENT, jornada INTEGER NOT NULL, partido_id INTEGER NOT NULL,
            user_id TEXT NOT NULL, puntos INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(jornada, partido_id, user_id)
        );

-- table: predicciones
CREATE TABLE predicciones (
            user_id TEXT, jornada INTEGER, partido_id INTEGER, signo TEXT
        );

-- table: quiz_participaciones
CREATE TABLE quiz_participaciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT, jornada INTEGER NOT NULL, user_id TEXT NOT NULL,
            nombre TEXT NOT NULL, respuestas TEXT NOT NULL, aciertos INTEGER NOT NULL DEFAULT 0,
            total_preguntas INTEGER NOT NULL DEFAULT 10, puntos INTEGER NOT NULL DEFAULT 0,
            tiempo_total_ms INTEGER DEFAULT 0, racha_max INTEGER DEFAULT 0, created_at TEXT NOT NULL
        );

-- table: quiz_preguntas
CREATE TABLE quiz_preguntas (
            id INTEGER PRIMARY KEY AUTOINCREMENT, jornada INTEGER NOT NULL,
            tipo TEXT NOT NULL DEFAULT 'multiple', enunciado TEXT NOT NULL,
            opcion_a TEXT NOT NULL, opcion_b TEXT NOT NULL, opcion_c TEXT NOT NULL,
            respuesta_correcta TEXT NOT NULL, explicacion TEXT DEFAULT '',
            dificultad INTEGER DEFAULT 1, tema TEXT DEFAULT '', activa INTEGER DEFAULT 1, created_at TEXT NOT NULL
        );

-- table: resultados
CREATE TABLE resultados (
            jornada INTEGER, partido_id INTEGER, local TEXT, visitante TEXT,
            goles_local INTEGER, goles_visitante INTEGER, status TEXT, fecha DATE, hora TEXT,
            minuto TEXT, posesion_h INTEGER, posesion_a INTEGER, tiros_h INTEGER, tiros_a INTEGER,
            signo_actual TEXT, jornada_liga INTEGER, api_id INTEGER, updated_at TEXT
        );

-- table: schema_migrations
CREATE TABLE schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
            description TEXT
        );

-- table: snake_scores
CREATE TABLE snake_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT NOT NULL, nombre TEXT NOT NULL,
            score INTEGER NOT NULL, created_at TEXT NOT NULL
        );

-- table: usuarios
CREATE TABLE usuarios (
            id TEXT PRIMARY KEY, nombre TEXT, email TEXT,
            puntos_acumulados INTEGER DEFAULT 0, notificaciones INTEGER DEFAULT 1, peso REAL DEFAULT 1.0
        );

-- index: idx_arcade_game_score
CREATE INDEX idx_arcade_game_score ON arcade_scores(game_id, score DESC, created_at ASC);

-- index: idx_clasificacion_div_pos
CREATE INDEX idx_clasificacion_div_pos ON clasificacion(division, pos);

-- index: idx_porra_jornada_match
CREATE INDEX idx_porra_jornada_match ON porra_entries(jornada, partido_id);

-- index: idx_quiz_participaciones_jornada
CREATE INDEX idx_quiz_participaciones_jornada ON quiz_participaciones(jornada, puntos DESC);

-- index: idx_quiz_preguntas_jornada
CREATE INDEX idx_quiz_preguntas_jornada ON quiz_preguntas(jornada, activa);

-- index: idx_rate_limit_last_seen
CREATE INDEX idx_rate_limit_last_seen ON api_rate_limit(last_seen);

-- index: idx_resultados_api_id
CREATE INDEX idx_resultados_api_id ON resultados(api_id);

-- index: idx_resultados_jornada_partido
CREATE INDEX idx_resultados_jornada_partido ON resultados(jornada, partido_id);

-- index: idx_snake_scores_top
CREATE INDEX idx_snake_scores_top ON snake_scores(score DESC, created_at ASC);

-- index: idx_snake_scores_user
CREATE INDEX idx_snake_scores_user ON snake_scores(user_id, score DESC);

-- index: ux_porra_user_jornada
CREATE UNIQUE INDEX ux_porra_user_jornada ON porra_entries(user_id, jornada);

-- index: ux_predicciones_user_jornada_partido
CREATE UNIQUE INDEX ux_predicciones_user_jornada_partido
        ON predicciones(user_id, jornada, partido_id)
    ;

-- index: ux_quiz_user_jornada
CREATE UNIQUE INDEX ux_quiz_user_jornada ON quiz_participaciones(user_id, jornada);
