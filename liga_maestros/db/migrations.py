import json
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
            try:
                ensure_jornada_75(conn)
            except Exception as e:
                import sys
                print(f"[migration] ensure_jornada_75 failed (non-fatal): {e}", file=sys.stderr)
            ensure_jornada_76(conn)
            ensure_missing_indexes(conn)
            minimize_stored_personal_data(conn)
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass
            _unlock_file(lock_fh)


def _import_j75_pronosticos(conn):
    """Import pronosticos from the J75 arena data file into predicciones."""
    arena_path = os.path.join(config.SEED_DATA_DIR, "inbox", "JORNADA_75_LM_ARENA.json")
    if not os.path.exists(arena_path):
        return
    try:
        with open(arena_path, encoding="utf-8") as fh:
            arena = json.load(fh)
    except (OSError, ValueError, TypeError):
        return
    for entry in arena.get("pronosticos", []):
        uid = entry.get("participante_id")
        if not uid:
            continue
        signos = entry.get("signos", [])
        for partido_id, raw_sign in enumerate(signos, start=1):
            sign = str(raw_sign or "-").strip().upper()
            if partido_id > 15:
                continue
            conn.execute(
                """
                INSERT OR REPLACE INTO predicciones (user_id, jornada, partido_id, signo)
                VALUES (?, 75, ?, ?)
                """,
                (uid, partido_id, sign),
            )


# Boleto publico J75 (fallback si falta el JSON del scrape en data/).
J75_FALLBACK_MATCHES = [
    (1, "VPS Vaasa", "Inter Turku", "2026-08-02", "14:00"),
    (2, "TPS Turku", "IFK Mariehamn", "2026-08-01", "14:00"),
    (3, "AC Oulu", "Ilves Tampere", "2026-08-02", "16:00"),
    (4, "FC Lahti", "FF Jaro", "2026-08-01", "17:00"),
    (5, "IF Gnistan", "KuPS Kuopio", "2026-08-01", "18:00"),
    (6, "Fredrikstad", "Sandefjord", "2026-08-01", "16:00"),
    (7, "Start", "Viking", "2026-08-01", "18:00"),
    (8, "Molde FK", "Sarpsborg", "2026-08-02", "17:00"),
    (9, "KFUM Oslo", "Kristiansund", "2026-08-02", "17:00"),
    (10, "Aalesunds FK", "Tromsø IL", "2026-08-02", "17:00"),
    (11, "Brann", "Rosenborg", "2026-08-02", "19:15"),
    (12, "Häcken", "Kalmar FF", "2026-08-01", "15:00"),
    (13, "IFK Göteborg", "Degerfors IF", "2026-08-02", "14:00"),
    (14, "Brommapojkarna", "Malmoe", "2026-08-02", "14:00"),
    (15, "AIK", "Orgryte IS", "2026-08-02", "16:30"),
]

# Boleto publico J76 (fallback si falta el JSON del scrape en data/).
J76_FALLBACK_MATCHES = [
    (1, "Sandefjord", "KFUM Oslo", "2026-08-07", "19:00"),
    (2, "Valerenga", "Bodo-Glimt", "2026-08-08", "14:00"),
    (3, "Viking", "Sarpsborg", "2026-08-08", "16:00"),
    (4, "Start", "Fredrikstad", "2026-08-08", "18:00"),
    (5, "Lillestrom SK", "Rosenborg", "2026-08-09", "14:30"),
    (6, "Ham-Kam", "Aalesunds FK", "2026-08-09", "17:00"),
    (7, "Kristiansund", "Molde FK", "2026-08-09", "19:15"),
    (8, "Orgryte IS", "AIK", "2026-08-08", "15:00"),
    (9, "Mjallby", "Elfsborg", "2026-08-08", "17:30"),
    (10, "Hammarby", "Hacken", "2026-08-09", "14:00"),
    (11, "Malmoe", "Degerfors IF", "2026-08-09", "14:00"),
    (12, "Halmstad", "GAIS Goteborg", "2026-08-09", "16:30"),
    (13, "IFK Goteborg", "Kalmar FF", "2026-08-09", "16:30"),
    (14, "Sirius", "Brommapojkarna", "2026-08-10", "19:00"),
    (15, "Vasteras SK FK", "Djurgardens", "2026-08-10", "19:00"),
]


def load_scrape_matches(jornada):
    """Read the public quiniela15 scrape for a jornada.

    Returns a list of (partido_id, local, visitante, fecha, hora) or None when
    no complete scrape file is available. The scrape files shipped in data/
    are the source of truth for the 15-match fixture.
    """
    candidates = []
    for base_dir in (
        getattr(config, "SEED_DATA_DIR", ""),
        getattr(config, "DATA_DIR", ""),
        os.path.join(config.BASE_DIR, "data"),
    ):
        if base_dir:
            candidates.append(os.path.join(base_dir, f"quiniela15_J{jornada}_scrape.json"))
    for path in candidates:
        if not os.path.exists(path):
            continue
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError, TypeError):
            continue
        try:
            if int(data.get("jornada") or 0) != int(jornada):
                continue
        except (TypeError, ValueError):
            continue
        partidos = data.get("partidos") or []
        if len(partidos) < 15:
            continue
        horarios = data.get("horarios") or {}
        matches = []
        for item in partidos[:15]:
            try:
                num = int(item.get("num") or item.get("id") or 0)
            except (TypeError, ValueError):
                continue
            local = str(item.get("local") or "").strip()
            visitante = str(item.get("visitante") or "").strip()
            if not num or not local or not visitante:
                continue
            horario = horarios.get(str(num)) or {}
            fecha = str(horario.get("fecha") or item.get("fecha") or "").strip()[:10]
            hora = str(horario.get("hora") or item.get("hora") or "").strip()[:5]
            matches.append((num, local, visitante, fecha, hora))
        if len(matches) == 15 and {m[0] for m in matches} == set(range(1, 16)):
            return matches
    return None


def _match_row_quality(row):
    """Score a resultados row: result > live status > identity completeness."""
    score = 0
    if row[6] is not None or row[7] is not None:
        score += 4
    if str(row[5] or "").upper() not in ("", "NS", "SCHEDULED"):
        score += 2
    if str(row[1] or "").strip() not in ("", "-"):
        score += 1
    return score


def ensure_jornada_completa(conn, jornada, fallback_matches=None, force=False):
    """Guarantee the 15 matches of a jornada exist with real fixture data.

    Repairs partial imports: inserts missing matches and backfills identity
    fields (local/visitante/fecha/hora) on rows that are empty or outdated.
    Never touches goals/status/minute and never renames matches that already
    have a result or are live, so running it mid-jornada is safe.

    If force=True, updates all matches even if they already have a complete identity.

    Returns the number of rows inserted or updated.
    """
    jornada = int(jornada)
    matches = load_scrape_matches(jornada) or list(fallback_matches or [])
    if len(matches) != 15:
        return 0

    existing = {}
    duplicates = []
    for row in conn.execute(
        """
        SELECT partido_id, local, visitante, fecha, hora, status, goles_local, goles_visitante, rowid
        FROM resultados
        WHERE jornada = ?
        """,
        (jornada,),
    ).fetchall():
        try:
            pid = int(row[0])
        except (TypeError, ValueError):
            continue
        if pid in existing:
            # Filas duplicadas (importaciones a medias del pasado): nos quedamos
            # con la mas completa (resultado > estado > nombre) y borramos el resto.
            candidates = [existing[pid], row]
            keep = max(candidates, key=_match_row_quality)
            drop = candidates[0] if keep is candidates[1] else candidates[1]
            duplicates.append(drop[8])
            existing[pid] = keep
        else:
            existing[pid] = row
    for rowid in duplicates:
        conn.execute("DELETE FROM resultados WHERE rowid = ?", (rowid,))

    changed = len(duplicates)
    for num, local, visitante, fecha, hora in matches:
        row = existing.get(num)
        if row is None:
            conn.execute(
                """
                INSERT INTO resultados (
                    jornada, partido_id, local, visitante, status, fecha, hora,
                    goles_local, goles_visitante, minuto, signo_actual
                )
                VALUES (?, ?, ?, ?, 'NS', ?, ?, NULL, NULL, '', '-')
                """,
                (jornada, num, local, visitante, fecha, hora),
            )
            changed += 1
            continue

        status = str(row[5] or "").upper()
        has_result = row[6] is not None or row[7] is not None
        in_play = status in ("LIVE", "IN PLAY", "HT", "HALF TIME BREAK", "FT", "FINISHED", "TERMINADO")
        if in_play and has_result:
            continue

        current_identity = (
            str(row[1] or "").strip(),
            str(row[2] or "").strip(),
            str(row[3] or "").strip()[:10],
            str(row[4] or "").strip()[:5],
        )
        # Solo corregimos identidad cuando falta algo o el partido aun no arranco.
        incomplete = (
            not current_identity[0]
            or current_identity[0] == "-"
            or not current_identity[1]
            or current_identity[1] == "-"
            or not current_identity[2]
        )
        identity_differs = (current_identity[0], current_identity[1]) != (local, visitante)
        schedule_differs = bool(fecha) and (current_identity[2], current_identity[3]) != (fecha, hora)
        if not force and not incomplete and not (not in_play and (identity_differs or schedule_differs)):
            continue
        if in_play and not incomplete and not force:
            continue
        conn.execute(
            """
            UPDATE resultados
            SET local = ?, visitante = ?, fecha = ?, hora = ?
            WHERE jornada = ? AND partido_id = ?
            """,
            (local, visitante, fecha or current_identity[2], hora or current_identity[3], jornada, num),
        )
        changed += 1

    conn.commit()
    return changed


def _import_j75_resultados(conn):
    """Backfill verified final results of J75 shipped in data/.

    The live collector covers most matches, but a completed jornada can leave
    uncovered matches (page moved on, transient scrape errors). This file is
    the deterministic last resort: it only fills rows still without a result
    (NS/NULL) and never overwrites existing scores.
    """
    candidates = [
        os.path.join(getattr(config, "SEED_DATA_DIR", "") or "", "quiniela15_J75_resultados.json"),
        os.path.join(getattr(config, "DATA_DIR", "") or "", "quiniela15_J75_resultados.json"),
    ]
    for path in candidates:
        if not path or not os.path.exists(path):
            continue
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError, TypeError):
            continue
        try:
            if int(data.get("jornada") or 0) != 75:
                continue
        except (TypeError, ValueError):
            continue
        resultados = data.get("resultados") or []
        if len(resultados) != 15:
            continue
        applied = 0
        for item in resultados:
            try:
                pid = int(item["id"])
                gh = int(item["goles_local"])
                ga = int(item["goles_visitante"])
            except (TypeError, ValueError, KeyError):
                continue
            signo = str(item.get("signo") or "").strip() or (
                f"{gh}-{ga}" if pid == 15 else ("1" if gh > ga else ("2" if gh < ga else "X"))
            )
            cursor = conn.execute(
                """
                UPDATE resultados
                SET goles_local = ?, goles_visitante = ?, status = 'FT',
                    minuto = 'Finalizado', signo_actual = ?
                WHERE jornada = 75 AND partido_id = ?
                  AND (goles_local IS NULL OR goles_visitante IS NULL)
                  AND (status IS NULL OR status IN ('NS', 'SCHEDULED', ''))
                """,
                (gh, ga, signo, pid),
            )
            applied += cursor.rowcount
        if applied:
            conn.commit()
        return


def ensure_jornada_75(conn):
    """Import the public J75 fixture and pronosticos from arena data.

    Idempotent and self-healing: a partial J75 (previous bug left the jornada
    with fewer than 15 matches whenever any row already existed) is completed
    from the scrape file shipped in data/.
    """
    ensure_jornada_completa(conn, 75, fallback_matches=J75_FALLBACK_MATCHES, force=True)
    _import_j75_resultados(conn)

    # Publicamos solo la columna conocida del Programa. Los Maestros se
    # incorporan cuando entregan sus pronosticos; nunca se clonan.
    j75_signs = ["12", "1", "12", "1", "2", "1", "2", "1", "1", "2", "1", "1", "1", "2", "2-0"]
    try:
        conn.executemany(
            """
                INSERT INTO predicciones (user_id, jornada, partido_id, signo)
                VALUES ('programa', 75, ?, ?)
                ON CONFLICT(user_id, jornada, partido_id)
                DO UPDATE SET signo = excluded.signo
            """,
            enumerate(j75_signs, start=1),
        )
        conn.commit()
    except sqlite3.OperationalError:
        # Indice unico todavia no creado (llamada directa fuera de
        # run_startup_migrations): los signos se aplicaran en el proximo arranque.
        pass

    _import_j75_pronosticos(conn)

    conn.commit()


def ensure_jornada_76(conn):
    """Import the public J76 fixture from arena data.

    Idempotent and self-healing: a partial J76 is completed from the scrape
    file shipped in data/.
    """
    ensure_jornada_completa(conn, 76, fallback_matches=J76_FALLBACK_MATCHES)
    conn.commit()
