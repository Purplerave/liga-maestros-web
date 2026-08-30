# fmt: off
import json
import os
import sqlite3

import config

from ..scoring import normalize_prediction_sign
from ..utils import clean_team_key
from .connection import ClosingConnection, ensure_db_file


def ensure_core_tables(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id TEXT PRIMARY KEY, nombre TEXT, email TEXT,
            puntos_acumulados INTEGER DEFAULT 0, notificaciones INTEGER DEFAULT 1, peso REAL DEFAULT 1.0
        );
        CREATE TABLE IF NOT EXISTS resultados (
            jornada INTEGER, partido_id INTEGER, local TEXT, visitante TEXT,
            goles_local INTEGER, goles_visitante INTEGER, status TEXT, fecha DATE, hora TEXT,
            minuto TEXT, posesion_h INTEGER, posesion_a INTEGER, tiros_h INTEGER, tiros_a INTEGER,
            signo_actual TEXT, jornada_liga INTEGER, api_id INTEGER, updated_at TEXT
        );
        CREATE TABLE IF NOT EXISTS predicciones (
            user_id TEXT, jornada INTEGER, partido_id INTEGER, signo TEXT
        );
        CREATE TABLE IF NOT EXISTS consenso (
            jornada INTEGER, partido_id INTEGER, ganador TEXT, p1 INTEGER, px INTEGER, p2 INTEGER
        );
        CREATE TABLE IF NOT EXISTS historico (jornada INTEGER, fecha DATE, resultado TEXT);
        CREATE TABLE IF NOT EXISTS clasificacion (
            equipo TEXT UNIQUE, pj INTEGER, pts INTEGER, division INTEGER, pos INTEGER,
            pg INTEGER DEFAULT 0, pe INTEGER DEFAULT 0, pp INTEGER DEFAULT 0,
            gf INTEGER DEFAULT 0, gc INTEGER DEFAULT 0, racha TEXT
        );
        CREATE TABLE IF NOT EXISTS equipos (
            id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT UNIQUE, division INTEGER
        );
        CREATE TABLE IF NOT EXISTS equipo_aliases (alias TEXT PRIMARY KEY, equipo_nombre TEXT);
        CREATE TABLE IF NOT EXISTS equipos_aliases (
            id INTEGER PRIMARY KEY AUTOINCREMENT, equipo_id INTEGER, alias TEXT UNIQUE, nombre_canonico TEXT
        );
        CREATE TABLE IF NOT EXISTS comentarios_jornada (
            id INTEGER PRIMARY KEY AUTOINCREMENT, jornada INTEGER NOT NULL, user_id TEXT NOT NULL,
            nombre TEXT NOT NULL, texto TEXT NOT NULL, etiqueta TEXT NOT NULL DEFAULT 'Bar', created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS api_rate_limit (
            scope TEXT NOT NULL, identity TEXT NOT NULL, last_seen REAL NOT NULL, PRIMARY KEY (scope, identity)
        );
    """)
    conn.commit()


def ensure_predicciones_unique_index(conn):
    conn.execute("""
        DELETE FROM predicciones WHERE rowid NOT IN (
            SELECT MAX(rowid) FROM predicciones GROUP BY user_id, jornada, partido_id)
    """)
    conn.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS ux_predicciones_user_jornada_partido
        ON predicciones(user_id, jornada, partido_id)
    """)
    conn.commit()


def ensure_porra_table(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS porra_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT, jornada INTEGER NOT NULL, partido_id INTEGER NOT NULL,
            user_id TEXT NOT NULL, nombre TEXT NOT NULL, goles_local INTEGER NOT NULL,
            goles_visitante INTEGER NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
            changes INTEGER NOT NULL DEFAULT 0
        )
    """)
    try:
        conn.execute("DROP INDEX IF EXISTS ux_porra_user_match")
    except Exception:
        pass
    conn.execute("""
        DELETE FROM porra_entries WHERE id NOT IN (
            SELECT MAX(id) FROM porra_entries GROUP BY user_id, jornada)
    """)
    try:
        conn.execute("ALTER TABLE porra_entries ADD COLUMN changes INTEGER NOT NULL DEFAULT 0")
    except Exception:
        pass
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_porra_user_jornada ON porra_entries(user_id, jornada)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_porra_jornada_match ON porra_entries(jornada, partido_id)")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS porra_puntos (
            id INTEGER PRIMARY KEY AUTOINCREMENT, jornada INTEGER NOT NULL, partido_id INTEGER NOT NULL,
            user_id TEXT NOT NULL, puntos INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(jornada, partido_id, user_id)
        )
    """)
    conn.commit()


def ensure_snake_table(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS snake_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT NOT NULL, nombre TEXT NOT NULL,
            score INTEGER NOT NULL, created_at TEXT NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_snake_scores_top ON snake_scores(score DESC, created_at ASC)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_snake_scores_user ON snake_scores(user_id, score DESC)")
    conn.commit()


def ensure_arcade_table(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS arcade_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT, game_id TEXT NOT NULL, user_id TEXT NOT NULL,
            nombre TEXT NOT NULL, score INTEGER NOT NULL, created_at TEXT NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_arcade_game_score ON arcade_scores(game_id, score DESC, created_at ASC)")
    conn.commit()


def ensure_quiz_tables(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS quiz_preguntas (
            id INTEGER PRIMARY KEY AUTOINCREMENT, jornada INTEGER NOT NULL,
            tipo TEXT NOT NULL DEFAULT 'multiple', enunciado TEXT NOT NULL,
            opcion_a TEXT NOT NULL, opcion_b TEXT NOT NULL, opcion_c TEXT NOT NULL,
            respuesta_correcta TEXT NOT NULL, explicacion TEXT DEFAULT '',
            dificultad INTEGER DEFAULT 1, tema TEXT DEFAULT '', activa INTEGER DEFAULT 1, created_at TEXT NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_quiz_preguntas_jornada ON quiz_preguntas(jornada, activa)")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS quiz_participaciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT, jornada INTEGER NOT NULL, user_id TEXT NOT NULL,
            nombre TEXT NOT NULL, respuestas TEXT NOT NULL, aciertos INTEGER NOT NULL DEFAULT 0,
            total_preguntas INTEGER NOT NULL DEFAULT 10, puntos INTEGER NOT NULL DEFAULT 0,
            tiempo_total_ms INTEGER DEFAULT 0, racha_max INTEGER DEFAULT 0, created_at TEXT NOT NULL
        )
    """)
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_quiz_user_jornada ON quiz_participaciones(user_id, jornada)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_quiz_participaciones_jornada ON quiz_participaciones(jornada, puntos DESC)")
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


def load_scrape_matches(jornada):
    candidates = []
    for base_dir in (getattr(config, "SEED_DATA_DIR", ""), getattr(config, "DATA_DIR", ""), os.path.join(config.BASE_DIR, "data")):
        if base_dir:
            candidates.append(os.path.join(base_dir, f"quiniela15_J{jornada}_scrape.json"))
    # Also prepare horarios candidates (separate file)
    horarios_candidates = []
    for base_dir in (getattr(config, "SEED_DATA_DIR", ""), getattr(config, "DATA_DIR", ""), os.path.join(config.BASE_DIR, "data")):
        if base_dir:
            horarios_candidates.append(os.path.join(base_dir, f"horarios_J{jornada}.json"))

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
        # CEO fix: si el scrape no trae horarios embebidos, leer horarios_J{N}.json externo
        if not horarios:
            for h_path in horarios_candidates:
                if not os.path.exists(h_path):
                    continue
                try:
                    with open(h_path, encoding="utf-8") as fh:
                        ext_hor = json.load(fh)
                    if isinstance(ext_hor, dict) and len(ext_hor) >= 10:
                        horarios = ext_hor
                        break
                except Exception:
                    continue
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
    score = 0
    if row[6] is not None or row[7] is not None:
        score += 4
    if str(row[5] or "").upper() not in ("", "NS", "SCHEDULED"):
        score += 2
    if str(row[1] or "").strip() not in ("", "-"):
        score += 1
    return score


def ensure_jornada_completa(conn, jornada, fallback_matches=None, force=False):
    jornada = int(jornada)
    matches = load_scrape_matches(jornada) or list(fallback_matches or [])
    if len(matches) != 15:
        return 0
    existing = {}
    duplicates = []
    for row in conn.execute(
        "SELECT partido_id, local, visitante, fecha, hora, status, goles_local, goles_visitante, rowid FROM resultados WHERE jornada = ?",
        (jornada,),
    ).fetchall():
        try:
            pid = int(row[0])
        except (TypeError, ValueError):
            continue
        if pid in existing:
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
                """INSERT INTO resultados (jornada, partido_id, local, visitante, status, fecha, hora,
                   goles_local, goles_visitante, minuto, signo_actual)
                   VALUES (?, ?, ?, ?, 'NS', ?, ?, NULL, NULL, '', '-')""",
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
            str(row[1] or "").strip(), str(row[2] or "").strip(),
            str(row[3] or "").strip()[:10], str(row[4] or "").strip()[:5],
        )
        incomplete = (
            not current_identity[0] or current_identity[0] == "-"
            or current_identity[0].lower() in ("local", "equipo local")
            or not current_identity[1] or current_identity[1] == "-"
            or current_identity[1].lower() in ("visitante", "equipo visitante")
            or not current_identity[2]
        )
        identity_differs = (current_identity[0], current_identity[1]) != (local, visitante)
        schedule_differs = bool(fecha) and (current_identity[2], current_identity[3]) != (fecha, hora)
        if not force and not incomplete and not (not in_play and (identity_differs or schedule_differs)):
            continue
        if in_play and not incomplete and not force:
            continue
        conn.execute(
            "UPDATE resultados SET local = ?, visitante = ?, fecha = ?, hora = ? WHERE jornada = ? AND partido_id = ?",
            (local, visitante, fecha or current_identity[2], hora or current_identity[3], jornada, num),
        )
        changed += 1
    conn.commit()
    return changed


def _import_j1_resultados(conn):
    candidates = [
        os.path.join(getattr(config, "SEED_DATA_DIR", "") or "", "quiniela15_J1_resultados.json"),
        os.path.join(getattr(config, "DATA_DIR", "") or "", "quiniela15_J1_resultados.json"),
        os.path.join(config.BASE_DIR, "data", "quiniela15_J1_resultados.json"),
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
            if int(data.get("jornada") or 0) != 1:
                continue
        except (TypeError, ValueError):
            continue
        resultados = data.get("resultados") or []
        if not resultados:
            continue
        applied = 0
        for item in resultados:
            try:
                pid = int(item["id"])
                gh = item.get("goles_local")
                ga = item.get("goles_visitante")
                if gh is None or ga is None:
                    continue
                gh, ga = int(gh), int(ga)
            except (TypeError, ValueError, KeyError):
                continue
            signo = str(item.get("signo") or "").strip()
            if not signo:
                signo = f"{gh}-{ga}" if pid == 15 else ("1" if gh > ga else ("2" if gh < ga else "X"))
            status = str(item.get("status") or "FT").strip().upper() or "FT"
            minuto = str(item.get("minuto") or "Finalizado").strip() or "Finalizado"
            cursor = conn.execute(
                """UPDATE resultados SET goles_local = ?, goles_visitante = ?, status = ?,
                   minuto = ?, signo_actual = ?
                   WHERE jornada = 1 AND partido_id = ?
                   AND (goles_local IS NULL OR goles_visitante IS NULL
                        OR status IS NULL
                        OR UPPER(COALESCE(status, '')) IN
                           ('NS','SCHEDULED','','LIVE','IN PLAY','HT','STALE','PENDING_OVERDUE'))""",
                (gh, ga, status, minuto, signo, pid),
            )
            applied += cursor.rowcount
        if applied:
            conn.commit()
        return applied
    return 0


def _import_j1_pronosticos(conn):
    candidates = [
        os.path.join(config.SEED_DATA_DIR, "inbox", "JORNADA_1_LM_ARENA.json"),
        os.path.join(config.DATA_DIR, "inbox", "JORNADA_1_LM_ARENA.json"),
    ]
    for arena_path in candidates:
        if not arena_path or not os.path.exists(arena_path):
            continue
        try:
            with open(arena_path, encoding="utf-8") as fh:
                arena = json.load(fh)
        except (OSError, ValueError, TypeError):
            continue
        if int(arena.get("jornada") or 0) != 1:
            continue
        for entry in arena.get("pronosticos", []):
            uid = str(entry.get("participante_id") or "").strip()
            if not uid:
                continue
            signos = list(entry.get("signos") or [])[:15]
            for partido_id, raw_sign in enumerate(signos, start=1):
                sign = str(raw_sign or "-").strip().upper()
                if not sign:
                    continue
                conn.execute(
                    "INSERT OR REPLACE INTO predicciones (user_id, jornada, partido_id, signo) VALUES (?, 1, ?, ?)",
                    (uid, partido_id, sign),
                )
        return


J1_OFFICIAL_ORDER_BY_OLD = {
    1: 8, 2: 1, 3: 9, 4: 14, 5: 2, 6: 10, 7: 3, 8: 6, 9: 11, 10: 4, 11: 7, 12: 12, 13: 5, 14: 13, 15: 15,
}


def _import_j1_programa_ticket(conn):
    """Apply Programa's editorial J1 ticket without a hard-coded duplicate.

    ``data/predicciones_J1.json`` is the compact file used by the Programa
    workflow. The inbox remains the source for the full roster (including La
    Peña), while this explicit Programa entry is allowed to replace only that
    one ticket. This makes a corrected double or Pleno survive every restart.
    """
    candidates = [
        os.path.join(config.SEED_DATA_DIR, "predicciones_J1.json"),
        os.path.join(config.DATA_DIR, "predicciones_J1.json"),
    ]
    for path in dict.fromkeys(candidates):
        if not path or not os.path.exists(path):
            continue
        try:
            with open(path, encoding="utf-8") as fh:
                payload = json.load(fh)
            if int(payload.get("jornada") or 0) != 1:
                continue
            raw_signs = list((payload.get("programa") or {}).get("signos") or [])
        except (OSError, ValueError, TypeError, AttributeError):
            continue
        if len(raw_signs) != 15:
            continue

        signos = []
        for partido_id, raw_sign in enumerate(raw_signs, start=1):
            sign = normalize_prediction_sign(partido_id, raw_sign)
            if not sign or sign == "-":
                signos = []
                break
            signos.append(sign)
        if len(signos) != 15:
            continue

        conn.executemany(
            "INSERT OR REPLACE INTO predicciones (user_id, jornada, partido_id, signo) VALUES ('programa', 1, ?, ?)",
            enumerate(signos, start=1),
        )
        return len(signos)
    return 0


def _rekey_j1_partido_ids(conn):
    row = conn.execute("SELECT local, visitante FROM resultados WHERE jornada = 1 AND partido_id = 1").fetchone()
    if row is None:
        return 0
    local = clean_team_key(row[0] or "")
    visitante = clean_team_key(row[1] or "")
    if (local, visitante) == ("ALAVES", "GETAFE"):
        return 0
    if (local, visitante) != ("REAL OVIEDO", "GRANADA"):
        return 0
    changed = 0
    conn.execute("BEGIN IMMEDIATE")
    try:
        for old_id, new_id in J1_OFFICIAL_ORDER_BY_OLD.items():
            if old_id == new_id:
                continue
            temp_id = -(old_id + 1000)
            for table in ("resultados", "predicciones"):
                cursor = conn.execute(
                    f'UPDATE "{table}" SET partido_id = ? WHERE jornada = 1 AND partido_id = ?',
                    (temp_id, old_id),
                )
                changed += cursor.rowcount
        for old_id, new_id in J1_OFFICIAL_ORDER_BY_OLD.items():
            if old_id == new_id:
                continue
            temp_id = -(old_id + 1000)
            for table in ("resultados", "predicciones"):
                cursor = conn.execute(
                    f'UPDATE "{table}" SET partido_id = ? WHERE jornada = 1 AND partido_id = ?',
                    (new_id, temp_id),
                )
                changed += cursor.rowcount
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return changed


def ensure_jornada_1(conn):
    _rekey_j1_partido_ids(conn)
    _import_j1_resultados(conn)
    updated = ensure_jornada_completa(conn, 1)
    if updated:
        conn.commit()
    _import_j1_resultados(conn)
    # Import the signed full roster, then the compact Programa ticket supplied
    # by its editorial workflow. Neither path is hard-coded, so corrections to
    # doubles or the Pleno survive deploys and restarts.
    _import_j1_pronosticos(conn)
    _import_j1_programa_ticket(conn)
    conn.commit()


def _import_compact_prediction_tickets(conn, jornada):
    """Importa los boletos editoriales de una jornada desde predicciones_JN.json."""
    candidates = [
        os.path.join(config.SEED_DATA_DIR, f"predicciones_J{jornada}.json"),
        os.path.join(config.DATA_DIR, f"predicciones_J{jornada}.json"),
    ]
    for path in dict.fromkeys(candidates):
        if not path or not os.path.exists(path):
            continue
        try:
            with open(path, encoding="utf-8") as fh:
                payload = json.load(fh)
            if int(payload.get("jornada") or 0) != int(jornada):
                continue
        except (OSError, ValueError, TypeError, AttributeError):
            continue

        tickets = []
        for raw_uid, entry in payload.items():
            if not isinstance(entry, dict):
                continue
            uid = str(raw_uid or "").strip().lower()
            raw_signs = list(entry.get("signos") or [])
            if not uid or len(raw_signs) != 15:
                continue
            signs = [normalize_prediction_sign(pid, value) for pid, value in enumerate(raw_signs, start=1)]
            if any(not sign or sign == "-" for sign in signs):
                continue
            tickets.append((uid, signs))

        for uid, signs in tickets:
            conn.executemany(
                "INSERT OR REPLACE INTO predicciones (user_id, jornada, partido_id, signo) VALUES (?, ?, ?, ?)",
                ((uid, int(jornada), partido_id, sign) for partido_id, sign in enumerate(signs, start=1)),
            )
        if tickets:
            conn.commit()
        return sum(len(signs) for _, signs in tickets)
    return 0


def ensure_jornada_2(conn):
    updated = ensure_jornada_completa(conn, 2)
    imported = _import_compact_prediction_tickets(conn, 2)
    if updated or imported:
        conn.commit()
    return updated + imported


def ensure_jornada_3(conn):
    """Seed the active 2026-27 Jornada 3 fixture and signed tickets."""
    updated = ensure_jornada_completa(conn, 3)
    imported = _import_compact_prediction_tickets(conn, 3)
    if updated or imported:
        conn.commit()
    return updated + imported


def ensure_jornada_75(conn):
    ensure_jornada_completa(conn, 75, force=True)
    conn.commit()


def ensure_jornada_76(conn):
    ensure_jornada_completa(conn, 76)
    conn.commit()


def ensure_clasificacion_zero(conn):
    try:
        count = conn.execute("SELECT COUNT(*) FROM clasificacion").fetchone()[0]
    except Exception:
        return
    from ..services.season_rosters import replace_clasificacion_from_roster
    if replace_clasificacion_from_roster(conn):
        return
    if count == 0:
        replace_clasificacion_from_roster(conn)
        return
    try:
        row = conn.execute("SELECT MAX(pj) as m FROM clasificacion").fetchone()
        max_pj = int(row[0] or 0) if row else 0
    except Exception:
        max_pj = 0
    if max_pj >= 30:
        conn.execute("UPDATE clasificacion SET pj=0, pts=0, pg=0, pe=0, pp=0, gf=0, gc=0, racha=NULL")
        conn.commit()


def ensure_porra_points_upgrade(conn):
    return


J75_FALLBACK_MATCHES = []
J76_FALLBACK_MATCHES = []


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
            ensure_jornada_1(conn)
            try:
                ensure_jornada_2(conn)
            except Exception as e:
                import sys
                print(f"[migration] ensure_jornada_2 failed (non-fatal): {e}", file=sys.stderr)
            try:
                ensure_jornada_3(conn)
            except Exception as e:
                import sys
                print(f"[migration] ensure_jornada_3 failed (non-fatal): {e}", file=sys.stderr)
            from ..services.season_rosters import sync_runtime_standings_files
            try:
                sync_runtime_standings_files()
            except Exception as e:
                import sys
                print(f"[migration] sync_runtime_standings_files failed (non-fatal): {e}", file=sys.stderr)
            ensure_clasificacion_zero(conn)
            ensure_porra_points_upgrade(conn)
            ensure_resultados_updated_at(conn)
            ensure_missing_indexes(conn)
            minimize_stored_personal_data(conn)
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass
            _unlock_file(lock_fh)
# fmt: on
