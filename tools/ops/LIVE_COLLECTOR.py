import argparse
import json
import shutil
import sqlite3
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

_tools_root = str(Path(__file__).resolve().parent.parent)
if _tools_root not in sys.path:
    sys.path.insert(0, _tools_root)
_scrapers_dir = str(Path(__file__).resolve().parent.parent / "scrapers")
if _scrapers_dir not in sys.path:
    sys.path.insert(0, _scrapers_dir)
if str(Path(__file__).resolve().parent.parent.parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from SCRAPE_QUINIELA15_DIRECTO import scrape as scrape_q15_directo  # noqa: E402

import config  # noqa: E402
from config.quiniela15_jornadas import Q15_BOLETO_DATE_TOLERANCE_DAYS, q15_jornada  # noqa: E402
from liga_maestros import utils  # noqa: E402
from liga_maestros.db.connection import get_db  # noqa: E402
from liga_maestros.middleware.json_lock import write_json_locked  # noqa: E402
from liga_maestros.services import (  # noqa: E402
    HIGHLIGHTLY_REFRESH_ENABLED,
    compute_refresh_window,
    get_highlightly_circuit,
    get_highlightly_usage,
    madrid_now,
    parse_madrid_datetime,
    refresh_current_matches_from_highlightly,
    validate_q15_payload,
)
from liga_maestros.services.live_state import (  # noqa: E402
    CLOSE_FINAL,
    FINAL_MINUTE,
    FINAL_STATUS,
    FULL_MATCH_WINDOW,
    KEEP,
    NO_UPDATE_TIMEOUT,
    RESET_TO_SCHEDULED,
    closes_live,
    evaluate_match_state,
    is_live_status,
)

DATA_DIR = Path(config.DATA_DIR)
# Suelo de seguridad para aceptar el FT de la quiniela15 (ver apply_q15_results_to_db).
Q15_MIN_FT_WINDOW = timedelta(minutes=60)
LOG_PATH = DATA_DIR / "LIVE_COLLECTOR.log"
HEALTH_PATH = DATA_DIR / "LIVE_COLLECTOR_HEALTH.json"
BACKUP_DIR = DATA_DIR / "backups"
LAST_HIGHLIGHTLY_RUN = 0
LAST_BACKUP_DATE = ""
MADRID_TZ = ZoneInfo("Europe/Madrid")


def log_line(message):
    line = f"{madrid_now():%Y-%m-%d %H:%M:%S} {message}"
    print(line, flush=True)
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        pass


def write_health(status, window=None, error=None, metrics=None):
    metrics = metrics or {}
    previous = utils.safe_read_json(str(HEALTH_PATH), {})
    previous_q15 = previous.get("q15") if isinstance(previous, dict) else {}
    now = madrid_now()
    usage = get_highlightly_usage()
    circuit = {key: value for key, value in get_highlightly_circuit().items() if key != "path"}
    if circuit.get("open_until"):
        try:
            circuit["open_until_iso"] = datetime.fromtimestamp(
                float(circuit["open_until"]),
                tz=MADRID_TZ,
            ).isoformat(timespec="seconds")
        except Exception:
            circuit["open_until_iso"] = ""
    blocked_by_circuit = bool(circuit.get("open"))
    q15_ok = metrics.get("q15_status") == "ok"
    stuck_live_count = int(metrics.get("stuck_live_count") or 0)
    snapshot_at = now.isoformat(timespec="seconds")
    snapshot_age_seconds = 0
    operational_status = (
        "q15_ok_api_paused"
        if blocked_by_circuit and q15_ok
        else "circuit_open"
        if blocked_by_circuit
        else "degraded"
        if stuck_live_count
        else "degraded"
        if status == "error" or metrics.get("q15_status") == "error"
        else "idle"
        if status == "idle"
        else "healthy"
    )
    payload = {
        "status": status,
        "operational_status": operational_status,
        "updated_at": snapshot_at,
        "snapshot_at": snapshot_at,
        "snapshot_age_seconds": snapshot_age_seconds,
        "stale": False,
        "source_priority": ["highlightly", "quiniela15", "highlightly_cache"],
        "jornada": (window or {}).get("jornada"),
        "reason": (window or {}).get("reason"),
        "live_now": bool((window or {}).get("live_now")),
        "error": str(error) if error else "",
        "highlightly": {
            "enabled": bool(HIGHLIGHTLY_REFRESH_ENABLED),
            "blocked_by_circuit": blocked_by_circuit,
            "next_retry_at": circuit.get("open_until_iso", "") if blocked_by_circuit else "",
            "usage": usage,
            "circuit": circuit,
        },
        "q15": {
            "status": metrics.get("q15_status", "unknown"),
            "fallback_used": bool(blocked_by_circuit and q15_ok),
            "matches": metrics.get("q15_matches", "-"),
            "duration_ms": metrics.get("q15_duration_ms"),
            "parse_errors": metrics.get("q15_parse_errors", 0),
            "last_success_per_match": metrics.get("last_success_per_match", {}),
        },
        "metrics": metrics,
    }
    if status == "idle" and previous_q15:
        previous_snapshot = previous.get("snapshot_at") or previous.get("updated_at")
        if previous_snapshot:
            try:
                previous_dt = datetime.fromisoformat(str(previous_snapshot))
                if previous_dt.tzinfo is None:
                    previous_dt = previous_dt.replace(tzinfo=MADRID_TZ)
                payload["previous_q15_age_seconds"] = max(0, int((now - previous_dt).total_seconds()))
            except Exception:
                pass
        payload["q15"]["status"] = "idle"
        payload["q15"]["last_success_per_match"] = {}
        payload["metrics"]["previous_q15_preserved"] = False
    write_json_locked(str(HEALTH_PATH), payload)


def _row_updated_at(row):
    """Best-effort read of the freshness stamp (column may not exist yet)."""
    try:
        raw = row["updated_at"]
    except (IndexError, KeyError):
        return None
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(str(raw))
    except ValueError:
        return None
    return parsed.replace(tzinfo=MADRID_TZ) if parsed.tzinfo is None else parsed


def detect_stuck_live_matches(jornada, grace_minutes=None):
    """Return live rows that cannot legitimately be live any more.

    Three independent signals are checked (see ``services.live_state``): a
    kickoff still in the future, a broadcast minute ahead of the real clock,
    and no provider update for 30 minutes. The schedule alone is not enough:
    a row stuck at LIVE minute 90 with a 17:00 kickoff never expires by time.
    """
    if not jornada:
        return []
    stuck = []
    with get_db() as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(resultados)").fetchall()}
        updated_at_select = "updated_at" if "updated_at" in columns else "NULL AS updated_at"
        rows = conn.execute(
            f"""
            SELECT partido_id, local, visitante, fecha, hora, status, minuto, {updated_at_select}
            FROM resultados
            WHERE jornada = ?
            ORDER BY partido_id
            """,  # noqa: S608 - column name comes from a local allowlist, never user input
            (jornada,),
        ).fetchall()
    now = madrid_now()
    for row in rows:
        if not is_live_status(row["status"]):
            continue
        kickoff_at = parse_madrid_datetime(row["fecha"], row["hora"])
        decision = evaluate_match_state(
            row["status"],
            kickoff_at,
            now,
            last_update_at=_row_updated_at(row),
            minute=row["minuto"],
            no_update_timeout=timedelta(minutes=grace_minutes) if grace_minutes else NO_UPDATE_TIMEOUT,
        )
        if not closes_live(decision["action"]):
            continue
        stuck.append(
            {
                "id": int(row["partido_id"]),
                "local": row["local"],
                "visitante": row["visitante"],
                "status": row["status"],
                "minuto": row["minuto"],
                "kickoff_at": kickoff_at.isoformat(timespec="minutes") if kickoff_at else "",
                "action": decision["action"],
                "reason": decision["reason"],
                "new_status": decision["status"],
                "new_minute": decision["minute"],
            }
        )
    return stuck


def close_stuck_live_matches(jornada, grace_minutes=None):
    """Persistently close live DB rows that are impossible or frozen.

    Last-resort path for a missed provider FT event or a corrupted snapshot.
    Runs on every collector pass (not only once the jornada window closes) so
    a single stuck match cannot keep Directo open while others continue.

    The written state depends on why the row is being closed: a match whose
    full window elapsed is finalised (FT + sign), one that is merely frozen or
    inconsistent is marked STALE (score kept, no sign invented), and one that
    was never actually playing goes back to NS.
    """
    stuck = detect_stuck_live_matches(jornada, grace_minutes=grace_minutes)
    if not stuck:
        return []
    with get_db() as conn:
        conn.execute("PRAGMA busy_timeout = 30000")
        conn.execute("BEGIN IMMEDIATE")
        for match in stuck:
            action = match.get("action") or CLOSE_FINAL
            new_status = match.get("new_status") or FINAL_STATUS
            new_minute = match.get("new_minute")
            if new_minute is None:
                new_minute = FINAL_MINUTE
            row = conn.execute(
                "SELECT goles_local, goles_visitante FROM resultados WHERE jornada = ? AND partido_id = ?",
                (jornada, match["id"]),
            ).fetchone()
            if action == RESET_TO_SCHEDULED:
                # Never played: drop the phantom score so the fixture can be
                # repopulated cleanly when it really kicks off.
                conn.execute(
                    """
                    UPDATE resultados
                    SET status = ?, minuto = ?, goles_local = NULL, goles_visitante = NULL, signo_actual = '-'
                    WHERE jornada = ? AND partido_id = ?
                    """,
                    (new_status, new_minute, jornada, match["id"]),
                )
                continue
            if action == CLOSE_FINAL:
                signo = utils.signo_for_match(
                    match["id"],
                    row["goles_local"] if row else None,
                    row["goles_visitante"] if row else None,
                )
                conn.execute(
                    "UPDATE resultados SET status = ?, minuto = ?, signo_actual = ? WHERE jornada = ? AND partido_id = ?",
                    (new_status, new_minute, signo, jornada, match["id"]),
                )
                continue
            # CLOSE_NO_DATA: stop showing it live but do not invent a result.
            conn.execute(
                "UPDATE resultados SET status = ?, minuto = ? WHERE jornada = ? AND partido_id = ?",
                (new_status, new_minute, jornada, match["id"]),
            )
        conn.commit()
    log_line(
        "auto_close="
        + str(len(stuck))
        + " "
        + " ".join(f"{match['id']}:{match.get('reason', 'desconocido')}" for match in stuck)
    )
    return stuck


_CATCHUP_PENDING_STATUS = frozenset(
    {
        "NS",
        "SCHEDULED",
        "",
        "LIVE",
        "IN PLAY",
        "HT",
        "HALF TIME BREAK",
        "EN JUEGO",
        "STALE",
        "PENDING_OVERDUE",
    }
)
# J1#5 (Celta-Osasuna) fue a sorteo LAE y se cura a mano: el catchup nunca
# debe rellenarlo con el marcador del partido aplazado.
_CATCHUP_EXCLUDED_JORNADAS = frozenset({1})
_CATCHUP_MAX_JORNADAS_PER_PASS = 2
_CATCHUP_OVERDUE_AFTER = timedelta(hours=3)


def overdue_catchup_jornadas(conn, exclude=None, limit=_CATCHUP_MAX_JORNADAS_PER_PASS):
    """Jornadas 1..42 (distintas de ``exclude``) con filas pendientes de un
    saque ya pasado.

    Red de seguridad para que un fin de semana sin colector (despliegue a
    medias, scraper bloqueado, jornada no vigilada) se cure solo en pasadas
    posteriores en vez de dejar NS/LIVE eternos. Solo se propone una jornada
    si al menos una de sus filas pendientes debio terminar hace mas de
    ``_CATCHUP_OVERDUE_AFTER``; los NS futuros no se tocan.
    """
    try:
        rows = conn.execute(
            """SELECT jornada, fecha, hora, status FROM resultados
               WHERE jornada BETWEEN 1 AND 42"""
        ).fetchall()
    except Exception:
        return []
    now = madrid_now().replace(tzinfo=None)
    overdue = set()
    for row in rows:
        try:
            jornada = int(row["jornada"])
        except (TypeError, ValueError):
            continue
        if jornada in _CATCHUP_EXCLUDED_JORNADAS or (exclude is not None and jornada == exclude):
            continue
        if str(row["status"] or "").upper() not in _CATCHUP_PENDING_STATUS:
            continue
        kickoff = parse_madrid_datetime(row["fecha"], row["hora"])
        if kickoff is None:
            overdue.add(jornada)
            continue
        if kickoff.tzinfo is not None:
            kickoff = kickoff.replace(tzinfo=None)
        if kickoff < now - _CATCHUP_OVERDUE_AFTER:
            overdue.add(jornada)
    return sorted(overdue)[: max(0, int(limit or 0))]


def cleanup_old_backups(retention_days=14):
    cutoff = madrid_now() - timedelta(days=max(1, int(retention_days or 14)))
    for path in BACKUP_DIR.glob("*"):
        if not path.is_file():
            continue
        try:
            if datetime.fromtimestamp(path.stat().st_mtime, tz=MADRID_TZ) < cutoff:
                path.unlink()
        except Exception as exc:
            log_line(f"backup_cleanup_error={path.name}:{exc}")


def backup_runtime_state(force=False, window=None):
    global LAST_BACKUP_DATE
    today = madrid_now().strftime("%Y-%m-%d")
    if not force and LAST_BACKUP_DATE == today:
        return False
    if not force and window and window.get("live_now"):
        log_line("backup_skip=live_window")
        return False

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = madrid_now().strftime("%Y%m%d_%H%M%S")
    db_source = Path(config.DB_PATH)
    if db_source.exists():
        db_target = BACKUP_DIR / f"LIGA_MAESTROS_PRO_{stamp}.db"
        source_conn = sqlite3.connect(str(db_source), timeout=30)
        target_conn = sqlite3.connect(str(db_target), timeout=30)
        try:
            source_conn.execute("PRAGMA busy_timeout=30000")
            source_conn.execute("PRAGMA wal_checkpoint(PASSIVE)")
            source_conn.backup(target_conn)
        finally:
            target_conn.close()
            source_conn.close()
        log_line(f"backup_db={db_target.name}")

    copied = 0
    for path in DATA_DIR.glob("*.json"):
        if path.name.startswith("quiniela15_directo_") or path.name in {
            "API_USAGE_HIGHLIGHTLY.json",
            "HIGHLIGHTLY_CIRCUIT.json",
            "LIVE_COLLECTOR_HEALTH.json",
            "RADAR_NOTICIAS.json",
        }:
            shutil.copy2(path, BACKUP_DIR / f"{path.stem}_{stamp}{path.suffix}")
            copied += 1
    if copied:
        log_line(f"backup_json={copied}")
    cleanup_old_backups()
    LAST_BACKUP_DATE = today
    return True


def choose_refresh_window(conn, jornada=None):
    if jornada:
        return compute_refresh_window(conn, jornada)

    jornadas = [
        row[0]
        for row in conn.execute("SELECT DISTINCT jornada FROM resultados ORDER BY jornada DESC").fetchall()
        if row[0] is not None
    ]
    if not jornadas:
        return {"enabled": False, "reason": "sin_jornada"}

    windows = [compute_refresh_window(conn, jornada_id) for jornada_id in jornadas]
    enabled = [w for w in windows if w.get("enabled")]
    if enabled:
        return sorted(
            enabled,
            key=lambda w: (
                not bool(w.get("live_now")),
                w.get("next_kickoff") or w.get("first_kickoff") or datetime.max,
            ),
        )[0]

    now = madrid_now().replace(tzinfo=None)
    upcoming = [w for w in windows if w.get("next_kickoff") and w.get("next_kickoff") >= now - timedelta(minutes=5)]
    if upcoming:
        return sorted(upcoming, key=lambda w: w.get("next_kickoff"))[0]

    return windows[0]


def should_refresh(jornada=None):
    with get_db() as conn:
        window = choose_refresh_window(conn, jornada)
    return bool(window.get("enabled")), window


def _q15_numero_para_boleto(boleto):
    """Numero de quiniela15 que reproduce este boleto.

    Primero la tabla de equivalencias (``config/quiniela15_jornadas``). Si ahi
    no esta, se mira si el numero pelado y sus vecinos traen los mismos equipos:
    asi un boleto extraordinario nuevo (otra Copa que descuadra la numeracion)
    se resuelve solo en vez de dejar la jornada sin resultados hasta que alguien
    edite la tabla. La sonda solo se hace fuera de la ventana de un partido en
    juego y con un presupuesto de peticiones, para no gastar tiempo cuando la
    jornada ya esta alineada.
    """
    boleto = int(boleto)
    fijado = q15_jornada(boleto)
    if int(fijado) != boleto:
        return int(fijado), f"tabla:{fijado}"
    candidatos = [boleto, boleto + 1, boleto - 1]
    for numero in candidatos:
        if numero <= 0:
            continue
        try:
            payload = scrape_q15_directo(int(numero))
        except Exception as exc:
            log_line(f"q15_sonda_error j={boleto} q15={numero} error={exc}")
            continue
        cubiertas, total = _q15_boleto_coverage(boleto, payload)
        if total and cubiertas >= max(2, (total * 3) // 5):
            if numero != boleto:
                log_line(f"q15_jornada_autodetectada j={boleto} q15={numero} equipos={cubiertas}/{total}")
                return int(numero), f"autodetectada:{cubiertas}/{total}"
            return int(numero), f"alineada:{cubiertas}/{total}"
    return boleto, "sin_equivalencia"


def scrape_q15_boleto(jornada):
    """Raspa en quiniela15 la jornada que corresponde al boleto ``jornada``.

    La numeracion de quiniela15 no siempre es la del boleto (ver
    ``config/quiniela15_jornadas.py``): con el numero pelado se descargaba la
    quiniela de la Copa del Rey y el boleto se quedaba sin resultados. Aqui se
    aplica la equivalencia y se comprueba que la jornada descargada cae en las
    fechas del boleto; si no, el payload se marca como no fiable y el llamador
    no escribe nada en la BD (el cache del directo se queda como estaba).
    """
    boleto = int(jornada)
    numero_q15, origen = _q15_numero_para_boleto(boleto)
    payload = scrape_q15_directo(int(numero_q15))
    payload["boleto_jornada"] = boleto
    payload["q15_jornada"] = int(numero_q15)
    payload["q15_origen"] = origen
    # Cuando la equivalencia no se ha podido confirmar (numero pelado sin
    # equipos en comun, o tabla sin verificar) hay que comprobarlo igual: si no,
    # el payload de otra quiniela se aplicaria a ciegas.
    confirmado = origen.startswith("alineada:")
    if not confirmado:
        trusted, reason = _q15_payload_matches_boleto(boleto, payload)
        payload["boleto_comprobado"] = trusted
        if not trusted:
            log_line(f"q15_jornada_no_confirma_boleto j={boleto} q15={numero_q15} reason={reason}")
            payload["matches"] = []
            payload["mismatch_reason"] = reason
            return payload
        log_line(f"q15_jornada_equivalente j={boleto} q15={numero_q15} reason={reason}")
    return payload


def _q15_boleto_coverage(boleto, payload):
    """Cuántas de las casillas del boleto aparecen en el payload de quiniela15.

    Se recorren las filas DEL BOLETO (no las del payload) y se busca su pareja.
    Con la quiniela equivocada casi ninguna coincide: la Copa del Rey repite
    "Levante - Atletico" y "Rayo - Celta", pero no Betis-Malaga ni el resto.
    """
    with get_db() as conn:
        rows = conn.execute(
            "SELECT local, visitante, fecha FROM resultados WHERE jornada = ?",
            (int(boleto),),
        ).fetchall()
    matches = payload.get("matches") or []
    cubiertas = 0
    for row in rows:
        local_boleto = row["local"]
        visit_boleto = row["visitante"]
        for match in matches:
            local_q15 = match.get("local")
            visit_q15 = match.get("visitante")
            if (
                utils.team_keys_compatible(local_q15, local_boleto)
                and utils.team_keys_compatible(visit_q15, visit_boleto)
            ) or (
                utils.team_keys_compatible(local_q15, visit_boleto)
                and utils.team_keys_compatible(visit_q15, local_boleto)
            ):
                cubiertas += 1
                break
    return cubiertas, len(rows)


def _q15_payload_matches_boleto(boleto, payload):
    """True si las fechas que publica quiniela15 caen en las del boleto."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT local, visitante, fecha FROM resultados WHERE jornada = ?",
            (int(boleto),),
        ).fetchall()
    boleto_teams = set()
    boleto_dates = []
    for row in rows:
        for name in (row["local"], row["visitante"]):
            key = utils.clean_team_key(name)
            if key:
                boleto_teams.add(key)
                boleto_teams.add(key.replace(" F", "").strip())
        fecha = str(row["fecha"] or "").strip()[:10]
        if len(fecha) == 10:
            boleto_dates.append(fecha)
    if not boleto_teams:
        return False, "boleto_sin_filas"

    matches = payload.get("matches") or []
    if not matches:
        return False, "q15_sin_partidos"

    # 1) Los equipos: se cuentan las casillas DEL BOLETO que la jornada
    #    descargada reproduce.
    boleto_cubiertas, total = _q15_boleto_coverage(boleto, payload)
    umbral = max(2, (total * 3) // 5)  # 60% de las casillas del boleto
    if boleto_cubiertas >= umbral:
        return True, f"equipos={boleto_cubiertas}/{total}"

    # 2) Si no hay equipos en comun, al menos que las fechas se solapen.
    q15_dates = sorted({str(m.get("fecha") or "").strip()[:10] for m in matches if str(m.get("fecha") or "")[:10]})
    if boleto_dates and q15_dates:
        try:
            boleto_first = datetime.strptime(min(boleto_dates), "%Y-%m-%d")
            boleto_last = datetime.strptime(max(boleto_dates), "%Y-%m-%d")
            tolerance = timedelta(days=Q15_BOLETO_DATE_TOLERANCE_DAYS)
            q15_first = datetime.strptime(min(q15_dates), "%Y-%m-%d")
            q15_last = datetime.strptime(max(q15_dates), "%Y-%m-%d")
        except ValueError:
            return False, "fechas_ilegibles"
        if q15_first <= boleto_last + tolerance and q15_last >= boleto_first - tolerance:
            return True, f"fechas={q15_first:%Y-%m-%d}..{q15_last:%Y-%m-%d}"
    return False, f"equipos={boleto_cubiertas}/{total}"


def write_q15_directo_cache(jornada):
    if not jornada:
        return {"matches": 0, "last_success_per_match": {}}
    started_at = time.time()
    payload = scrape_q15_boleto(jornada)
    try:
        matches = validate_q15_payload(payload, payload.get("q15_jornada", jornada))
    except ValueError as exc:
        # Un boleto con 14 filas parseadas vale mas que cero: la validacion
        # estricta dejaba la jornada entera sin resultados por una sola fila
        # que la web de origen cambiara. Se aplica lo parseado y se avisa.
        matches = payload.get("matches") or []
        if not matches:
            raise
        log_line(f"q15_partial_payload={len(matches)}/15 reason={exc}")
    fetched_at = madrid_now().isoformat(timespec="seconds")
    payload["fetched_at"] = fetched_at
    if payload.get("boleto_comprobado") is False:
        # La quiniela descargada no es la del boleto: no se pisa el cache buneo
        # (el panel del directo lo lee) ni se escribe en la BD. Se devuelve el
        # error para que la salud del colector lo enseñe.
        log_line(
            f"q15_cache_conservado j={int(jornada)} q15={payload.get('q15_jornada')} "
            f"reason={payload.get('mismatch_reason')}"
        )
        return {
            "matches": 0,
            "duration_ms": int((time.time() - started_at) * 1000),
            "last_success_per_match": {},
            "error": f"q15_jornada_no_confirmada:{payload.get('mismatch_reason')}",
        }
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / f"quiniela15_directo_J{int(jornada)}.json"
    write_json_locked(str(path), payload)
    match_count = len(matches)
    updates = apply_q15_results_to_db(int(jornada), payload)
    if updates:
        log_line(f"q15_result_updates={updates}")
    last_success_per_match = {}
    parse_errors = 0
    for match in payload.get("matches") or []:
        match_id = match.get("id")
        if match_id is None:
            continue
        if match.get("status") in ("LIVE", "FT") and not match.get("events"):
            parse_errors += 1
        last_success_per_match[str(match_id)] = {
            "updated_at": fetched_at,
            "status": match.get("status") or "",
            "score": (
                f"{match.get('score_home')}-{match.get('score_away')}"
                if match.get("score_home") is not None and match.get("score_away") is not None
                else ""
            ),
        }
    return {
        "matches": match_count,
        "duration_ms": int((time.time() - started_at) * 1000),
        "parse_errors": parse_errors,
        "last_success_per_match": last_success_per_match,
    }


def _q15_kickoff_order_plausible(match, row, tolerance_days=Q15_BOLETO_DATE_TOLERANCE_DAYS):
    """False si la fecha del partido en quiniela15 no puede ser la del boleto.

    Es la ultima red contra las numeraciones cruzadas: la quiniela de la Copa
    del Rey numera "Levante - Atletico" en la casilla 1 igual que el boleto,
    pero la juega otra noche. Si quiniela15 publica fecha y esta cae fuera del
    margen del boleto, no es el mismo partido y no se aplica el marcador.

    Sin fecha en la fuente (quiniela15 no siempre la publica en la tabla) se
    acepta: el cruce de nombres ya ha pasado.
    """
    q15_fecha = str(match.get("fecha") or "").strip()[:10]
    boleto_fecha = str(row["fecha"] or "").strip()[:10]
    if len(q15_fecha) != 10 or len(boleto_fecha) != 10:
        return True
    try:
        q15_day = datetime.strptime(q15_fecha, "%Y-%m-%d").date()
        boleto_day = datetime.strptime(boleto_fecha, "%Y-%m-%d").date()
    except ValueError:
        return True
    return abs((q15_day - boleto_day).days) <= int(tolerance_days)


def apply_q15_results_to_db(jornada, payload):
    matches = payload.get("matches") or []
    if not matches:
        return 0
    # Si el payload viene de otra numeracion de quiniela15 y no se pudo
    # confirmar que es el boleto, no se escribe nada: aplicar marcadores de
    # partidos que no son (Copa del Rey sobre LaLiga) es peor que no tenerlos.
    if payload.get("boleto_comprobado") is False:
        log_line(f"q15_payload_no_confirmado j={jornada} reason={payload.get('mismatch_reason')}")
        return 0
    updates = 0
    now = madrid_now()
    stamp = now.isoformat(timespec="seconds")
    with get_db() as conn:
        conn.execute("PRAGMA busy_timeout = 30000")
        conn.execute("BEGIN IMMEDIATE")
        current = {
            int(row["partido_id"]): row
            for row in conn.execute(
                """
                SELECT partido_id, local, visitante, fecha, hora, goles_local, goles_visitante, status, minuto
                FROM resultados
                WHERE jornada = ?
                """,
                (jornada,),
            ).fetchall()
        }
        for match in matches:
            try:
                partido_id = int(match.get("id"))
            except Exception:
                continue
            row = current.get(partido_id)
            if not row:
                continue
            if not _q15_kickoff_order_plausible(match, row):
                # Con numeraciones cruzadas la casilla 1 de la quiniela de la
                # Copa del Rey tambien se llama "Levante - Atletico": si su
                # partido se jugo en otra fecha que el del boleto, no puede ser
                # el mismo partido.
                log_line(
                    f"q15_kickoff_fuera_de_orden id={partido_id} q15={match.get('local')}|{match.get('visitante')} "
                    f"fecha_q15={match.get('fecha') or ''} fecha_boleto={row['fecha'] or ''}"
                )
                continue
            home_goals = match.get("score_home")
            away_goals = match.get("score_away")
            if home_goals is None or away_goals is None:
                continue
            try:
                home_goals = int(str(home_goals).strip().replace("?", ""))
                away_goals = int(str(away_goals).strip().replace("?", ""))
            except (TypeError, ValueError):
                log_line(f"q15_corrupt_score_skipped id={match.get('id')}")
                continue
            q15_home = utils.normalize_team_key(match.get("local"))
            q15_away = utils.normalize_team_key(match.get("visitante"))
            db_home = utils.normalize_team_key(row["local"])
            db_away = utils.normalize_team_key(row["visitante"])
            # Cruce por nombre tolerante: la quiniela publica "Edf Logrono",
            # "Sporting Gijon" o "Alaves Femenino" donde la BD guarda
            # "Logrono (F)", "Sporting" o "Alaves (F)". La igualdad estricta
            # descartaba el resultado para siempre (partidos que "no salian").
            if not utils.team_keys_compatible(match.get("local"), row["local"]) or not utils.team_keys_compatible(
                match.get("visitante"), row["visitante"]
            ):
                log_line(
                    "q15_team_mismatch_skipped "
                    f"id={partido_id} q15={match.get('local')}|{match.get('visitante')} "
                    f"db={row['local']}|{row['visitante']}"
                )
                continue
            minute = str(row["minuto"] or "")
            if minute.upper().startswith("SUSPENDIDO LAE"):
                continue
            signo = utils.signo_for_match(partido_id, home_goals, away_goals)
            q15_status = str(match.get("status") or "").upper()
            if q15_status in ("LIVE", "IN PLAY"):
                status = "LIVE"
            elif q15_status in ("HT", "HALF TIME BREAK"):
                status = "HT"
            elif q15_status in ("FT", "FINISHED", "TERMINADO"):
                # La quiniela15 solo enseña marcador sin parpadeo cuando el
                # partido ha acabado, asi que el FT ya no se deduce por reloj.
                # Suelo de seguridad: un FT antes de este margen casi siempre es
                # un partido suspendido o un parpadeo que se ha caido, y cerrarlo
                # congelaria un marcador parcial como resultado definitivo.
                kickoff_at = parse_madrid_datetime(row["fecha"], row["hora"])
                if kickoff_at and madrid_now() < kickoff_at + Q15_MIN_FT_WINDOW:
                    log_line(f"q15_ft_demasiado_pronto id={partido_id} kickoff={row['fecha']} {row['hora']}")
                    continue
                status = "FT"
            elif q15_status == "STALE":
                kickoff_at = parse_madrid_datetime(row["fecha"], row["hora"])
                # Umbral = ventana completa de partido: con 105' se marcaba FT
                # un partido aun en juego (saque retrasado, muchas parajes) y
                # el marcador parcial quedaba congelado como resultado final.
                if not kickoff_at or madrid_now() < kickoff_at + FULL_MATCH_WINDOW:
                    continue
                status = "FT"
            else:
                continue
            match_minute = str(match.get("minute") or ("Finalizado" if status == "FT" else "")).strip()

            # A provider snapshot must never (re)open an impossible live state,
            # e.g. LIVE minute 90 on a match that kicks off later today, nor
            # overwrite a good row with a skipped/incoherent snapshot.
            if is_live_status(status):
                decision = evaluate_match_state(
                    status,
                    parse_madrid_datetime(row["fecha"], row["hora"]),
                    now,
                    last_update_at=now,
                    minute=match_minute,
                )
                if decision["action"] != KEEP:
                    log_line(f"q15_live_incoherente_descartado id={partido_id} reason={decision['reason']}")
                    continue

            unchanged = (
                row["goles_local"] == home_goals
                and row["goles_visitante"] == away_goals
                and str(row["status"] or "").upper() == status
                and str(row["minuto"] or "") == match_minute
            )
            if unchanged:
                # Same values still mean "the provider confirmed this row now":
                # refresh the freshness stamp so a legitimately quiet 0-0 is
                # not closed by the 30-minute no-update rule.
                conn.execute(
                    "UPDATE resultados SET updated_at = ? WHERE jornada = ? AND partido_id = ?",
                    (stamp, jornada, partido_id),
                )
                continue
            conn.execute(
                """
                UPDATE resultados
                SET goles_local = ?, goles_visitante = ?, status = ?, minuto = ?, signo_actual = ?,
                    updated_at = ?
                WHERE jornada = ? AND partido_id = ?
                """,
                (int(home_goals), int(away_goals), status, match_minute, signo, stamp, jornada, partido_id),
            )
            updates += 1
        conn.commit()
    return updates


def next_sleep_seconds(window, base_interval):
    """Refresco adaptativo: rapido en directo, lento fuera de ventana."""
    circuit = get_highlightly_circuit()
    if not window.get("enabled") and window.get("reason") == "ventana_jornada":
        return max(60, min(int(base_interval or 300), 300))
    if circuit.get("open"):
        try:
            remaining = int(float(circuit.get("open_until") or 0) - time.time())
        except Exception:
            remaining = 0
        if remaining > 0:
            return max(60, min(remaining, 900))
    if window.get("live_now"):
        return max(60, min(int(base_interval or 120), 120))
    if window.get("needs_result_catchup"):
        return 900
    if not window.get("enabled"):
        next_kickoff = window.get("next_kickoff")
        if next_kickoff and next_kickoff > madrid_now().replace(tzinfo=None) + timedelta(minutes=20):
            return 900
        return max(60, min(int(base_interval or 300), 300))
    now = madrid_now().replace(tzinfo=None)
    next_kickoff = window.get("next_kickoff") or window.get("first_kickoff")
    if next_kickoff and next_kickoff > now + timedelta(minutes=20):
        return 900
    return max(60, min(int(base_interval or 120), 120))


LAST_STANDINGS_UPDATE = 0


def _update_spanish_standings_from_matches():
    """Calculate La Liga and Segunda standings from all collected matches."""
    global LAST_STANDINGS_UPDATE
    now = time.time()
    # Only update every 30 minutes
    if now - LAST_STANDINGS_UPDATE < 1800:
        return
    LAST_STANDINGS_UPDATE = now

    matches_path = DATA_DIR / "LIVE_ALL_MATCHES_V3.json"
    if not matches_path.exists():
        return
    try:
        with matches_path.open(encoding="utf-8") as f:
            all_matches = json.load(f)
    except Exception:
        return
    if not all_matches:
        return

    from liga_maestros.services.standings_calculator import calculate_standings_from_matches

    result = calculate_standings_from_matches(all_matches)
    leagues = result.get("leagues", [])

    for league in leagues:
        name = league.get("name", "").upper()
        teams = league.get("teams", [])
        if not teams:
            continue

        if "LA LIGA" in name:
            filename = "STANDINGS_LALIGA_BASE.json"
            category = "primera"
        elif "SEGUNDA" in name:
            filename = "STANDINGS_SEGUNDA_BASE.json"
            category = "segunda"
        else:
            continue

        from liga_maestros.services.season_rosters import merge_official_stats, official_name_set, official_names

        incoming = {str(t.get("n") or "").strip() for t in teams}
        if incoming - official_name_set(category):
            log_line(f"standings_skip={name} reason=roster_not_2026_27")
            continue
        base_teams = merge_official_stats(official_names(category), teams)

        path = DATA_DIR / filename
        try:
            with path.open("w", encoding="utf-8") as f:
                json.dump(base_teams, f, ensure_ascii=False, indent=2)
            log_line(f"standings_updated={name} teams={len(base_teams)}")
        except Exception as exc:
            log_line(f"standings_write_error={filename} err={exc}")


def run_once(force=False, q15=True, jornada=None, highlightly_interval=60):
    global LAST_HIGHLIGHTLY_RUN
    started_at = time.time()
    enabled, window = should_refresh(jornada)
    backup_runtime_state(window=window)
    target_jornada = window.get("jornada") or jornada
    auto_closed = []
    # Red de seguridad multi-jornada: aunque la ventana activa este al dia,
    # otras jornadas pueden tener pendientes de un saque ya pasado (fin de
    # semana sin colector, scraper bloqueado, jornada que dejo de vigilarse).
    # Se repescan aqui (max 2 por pasada, nunca en pleno directo) en vez de
    # dejar NS/LIVE eternos hasta que alguien lo rellene a mano.
    catchup_jornadas = []
    catchup_matches = 0
    if q15 and not window.get("live_now"):
        try:
            with get_db() as _catchup_conn:
                catchup_jornadas = overdue_catchup_jornadas(_catchup_conn, exclude=target_jornada)
        except Exception as exc:
            log_line(f"catchup_detect_error={exc}")
            catchup_jornadas = []
        for _catchup_jornada in catchup_jornadas:
            try:
                _detail = write_q15_directo_cache(_catchup_jornada)
                catchup_matches += int(_detail.get("matches") or 0)
                log_line(f"catchup_jornada={_catchup_jornada} q15={_detail.get('matches')}")
            except Exception as exc:
                log_line(f"catchup_error={_catchup_jornada}:{exc}")

    def _close_stuck_everywhere():
        closed = []
        for _jornada_cierre in [target_jornada] + [j for j in catchup_jornadas if j != target_jornada]:
            if not _jornada_cierre:
                continue
            try:
                closed.extend(close_stuck_live_matches(_jornada_cierre))
            except Exception as exc:
                log_line(f"auto_ft_error={exc}")
        return closed

    q15_catchup = bool(q15 and window.get("jornada") and window.get("reason") == "ventana_jornada" and enabled)
    if not force and not enabled and not q15_catchup:
        log_line(f"skip jornada={window.get('jornada')} reason={window.get('reason')}")
        auto_closed = _close_stuck_everywhere()
        stuck_live = detect_stuck_live_matches(target_jornada)
        write_health(
            "idle",
            window=window,
            metrics={
                "duration_ms": int((time.time() - started_at) * 1000),
                "stuck_live_count": len(stuck_live),
                "stuck_live_matches": stuck_live,
                "auto_closed_count": len(auto_closed),
                "auto_closed_matches": auto_closed,
                "catchup_jornadas": catchup_jornadas,
                "catchup_q15_matches": catchup_matches,
            },
        )
        return 0, window

    q15_matches = "-"
    q15_status = "disabled"
    q15_detail = {}
    if q15:
        try:
            q15_detail = write_q15_directo_cache(window.get("jornada"))
            q15_matches = q15_detail.get("matches", 0)
            q15_status = "ok"
        except Exception as exc:
            q15_matches = f"error:{exc}"
            q15_status = "error"

    updates = 0
    highlightly_status = "disabled"
    if HIGHLIGHTLY_REFRESH_ENABLED and (enabled or force):
        now_ts = time.time()
        api_interval = max(60, int(highlightly_interval or 300))
        if window.get("needs_result_catchup") and not window.get("live_now"):
            api_interval = max(api_interval, 900)
        circuit = get_highlightly_circuit()
        if circuit.get("open"):
            highlightly_status = "circuit_open"
            try:
                until = datetime.fromtimestamp(float(circuit.get("open_until") or 0)).strftime("%H:%M:%S")
            except Exception:
                until = "desconocido"
            log_line(f"highlightly_skip=circuit_open until={until}")
        elif force or now_ts - LAST_HIGHLIGHTLY_RUN >= api_interval:
            highlightly_status = "refresh_api"
            updates = refresh_current_matches_from_highlightly(
                force=True,
                jornada=window.get("jornada") or jornada,
            )
            LAST_HIGHLIGHTLY_RUN = now_ts
        else:
            highlightly_status = "throttle"
            log_line("highlightly_skip=throttle")
    else:
        highlightly_status = "window_closed"
        log_line("highlightly_skip=window_closed")

    # Provider/Q15 refreshes can return a stale LIVE snapshot and reopen a row.
    # Apply the hard deadline afterwards so the same pass always ends closed.
    auto_closed = _close_stuck_everywhere()

    # Update Spanish league standings from all collected matches
    if updates > 0 or highlightly_status == "refresh_api":
        try:
            _update_spanish_standings_from_matches()
        except Exception as exc:
            log_line(f"standings_update_error={exc}")

    usage = get_highlightly_usage()
    log_line(
        f"updates={updates} live={window.get('live_now')} "
        f"calls={usage.get('calls')}/{usage.get('limit')} "
        f"usable={usage.get('usable_remaining')} "
        f"q15={q15_matches}"
    )
    stuck_live = detect_stuck_live_matches(window.get("jornada") or jornada)
    if stuck_live:
        log_line(f"stuck_live={len(stuck_live)} ids={','.join(str(item['id']) for item in stuck_live)}")
    write_health(
        "ok",
        window=window,
        metrics={
            "duration_ms": int((time.time() - started_at) * 1000),
            "highlightly_status": highlightly_status,
            "highlightly_updates": updates,
            "q15_status": q15_status,
            "q15_matches": q15_matches,
            "q15_duration_ms": q15_detail.get("duration_ms"),
            "q15_parse_errors": q15_detail.get("parse_errors", 0),
            "last_success_per_match": q15_detail.get("last_success_per_match", {}),
            "stuck_live_count": len(stuck_live),
            "stuck_live_matches": stuck_live,
            "auto_closed_count": len(auto_closed),
            "auto_closed_matches": auto_closed,
            "catchup_jornadas": catchup_jornadas,
            "catchup_q15_matches": catchup_matches,
        },
    )
    return updates, window


def main():
    parser = argparse.ArgumentParser(description="Actualiza cache live sin depender del refresco de usuarios.")
    parser.add_argument("--once", action="store_true", help="Ejecuta una sola pasada.")
    parser.add_argument("--force", action="store_true", help="Ignora ventana horaria.")
    parser.add_argument(
        "--interval", type=int, default=60, help="Segundos entre pasadas cuando hay partidos en ventana."
    )
    parser.add_argument(
        "--highlightly-interval", type=int, default=60, help="Segundos minimos entre pasadas a Highlightly."
    )
    parser.add_argument("--jornada", type=int, help="Jornada concreta a vigilar.")
    parser.add_argument("--no-q15", action="store_true", help="No actualiza el cache de directo de Quiniela15.")
    parser.add_argument("--backup-now", action="store_true", help="Crea backup local de DB y JSON y sale.")
    args = parser.parse_args()

    if args.backup_now:
        backup_runtime_state(force=True)
        return

    if args.once:
        run_once(
            force=args.force, q15=not args.no_q15, jornada=args.jornada, highlightly_interval=args.highlightly_interval
        )
        return

    while True:
        try:
            _, window = run_once(
                force=args.force,
                q15=not args.no_q15,
                jornada=args.jornada,
                highlightly_interval=args.highlightly_interval,
            )
            sleep_seconds = next_sleep_seconds(window, args.interval)
        except Exception as exc:
            log_line(f"collector_error={exc}")
            write_health("error", error=exc)
            sleep_seconds = max(60, min(int(args.interval or 60), 300))
        time.sleep(sleep_seconds)


if __name__ == "__main__":
    main()
