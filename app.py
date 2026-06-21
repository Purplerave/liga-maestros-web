import sqlite3, os, sys, threading, time, logging, requests, json, re
import urllib.request, urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, send_from_directory
from authlib.integrations.flask_client import OAuth
from dotenv import load_dotenv

import config
import utils
from SCRAPE_QUINIELA15_DIRECTO import scrape as scrape_q15_directo

# Cargar configuración
load_dotenv()

app = Flask(__name__)
SECRET_KEY = os.getenv("SECRET_KEY", "").strip()
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY no configurada. Define SECRET_KEY en .env antes de arrancar Liga de Maestros.")
app.secret_key = SECRET_KEY
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE=os.getenv("SESSION_COOKIE_SAMESITE", "Lax"),
    SESSION_COOKIE_SECURE=os.getenv("SESSION_COOKIE_SECURE", "0").strip().lower() in ("1", "true", "yes", "on"),
)


HIGHLIGHTLY_API_KEY = os.getenv("HIGHLIGHTLY_API_KEY", "").strip()

_highlightly_refresh_lock = threading.Lock()
_highlightly_last_refresh = 0
_highlightly_refresh_thread = None
_highlightly_refresh_started_at = 0
_sqlite_pragma_lock = threading.Lock()
_sqlite_wal_ready = False
_highlightly_usage_lock = threading.Lock()
CONTEST_DYNAMIC_START_JORNADA = 58
HIGHLIGHTLY_REFRESH_ENABLED = os.getenv("HIGHLIGHTLY_REFRESH_ENABLED", "1").strip().lower() in ("1", "true", "yes", "on")
HIGHLIGHTLY_DAILY_CALL_LIMIT = int(os.getenv("HIGHLIGHTLY_DAILY_CALL_LIMIT", "7500"))
HIGHLIGHTLY_DAILY_CALL_RESERVE = int(os.getenv("HIGHLIGHTLY_DAILY_CALL_RESERVE", "250"))
PREDICTION_CLOSE_MINUTES_BEFORE_KICKOFF = int(os.getenv("PREDICTION_CLOSE_MINUTES_BEFORE_KICKOFF", "15"))
ALLOW_LOCAL_ADMIN = os.getenv("ALLOW_LOCAL_ADMIN", "1").strip().lower() in ("1", "true", "yes", "on")
ADMIN_EMAILS = {
    email.strip().lower()
    for email in os.getenv("ADMIN_EMAILS", "").split(",")
    if email.strip()
}
HIGHLIGHTLY_CIRCUIT_FAILURE_LIMIT = int(os.getenv("HIGHLIGHTLY_CIRCUIT_FAILURE_LIMIT", "3"))
HIGHLIGHTLY_CIRCUIT_COOLDOWN_SECONDS = int(os.getenv("HIGHLIGHTLY_CIRCUIT_COOLDOWN_SECONDS", "600"))

# Configuración OAuth
oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'}
)


class ClosingConnection(sqlite3.Connection):
    def __exit__(self, exc_type, exc, tb):
        result = super().__exit__(exc_type, exc, tb)
        self.close()
        return result

def get_db():
    global _sqlite_wal_ready
    conn = sqlite3.connect(config.DB_PATH, timeout=10, factory=ClosingConnection)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 10000")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA synchronous = NORMAL")
    if not _sqlite_wal_ready:
        with _sqlite_pragma_lock:
            if not _sqlite_wal_ready:
                try:
                    conn.execute("PRAGMA journal_mode = WAL")
                    _sqlite_wal_ready = True
                except sqlite3.Error as exc:
                    app.logger.warning("SQLite WAL setup failed: %s", exc)
    return conn


def is_local_request():
    return request.remote_addr in ("127.0.0.1", "::1", "localhost")


def is_admin_request():
    user = session.get("user") or {}
    email = str(user.get("email") or "").strip().lower()
    return (ALLOW_LOCAL_ADMIN and is_local_request()) or (email and email in ADMIN_EMAILS)
















    for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            dt = datetime.strptime(raw, fmt)
            if dt.tzinfo:
                dt = dt.astimezone(ZoneInfo("Europe/Madrid"))
            return dt.strftime("%Y-%m-%d %H:%M")
        except Exception:
            continue






def fetch_feed_items(feed):
    req = urllib.request.Request(
        feed["url"],
        headers={"User-Agent": "Mozilla/5.0 LigaMaestrosRadar/1.0", "Accept": "application/rss+xml, application/xml, text/xml;q=0.9, */*;q=0.8"}
    )
    with urllib.request.urlopen(req, timeout=12) as response:
        payload = utils.sanitize_xml_payload(response.read())
    root = ET.fromstring(payload)
    items = []
    for item in root.findall(".//item"):
        title = utils.strip_html(item.findtext("title", ""))
        link = utils.strip_html(item.findtext("link", ""))
        desc = utils.strip_html(item.findtext("description", ""))
        pub = utils.parse_rfc822_to_iso(item.findtext("pubDate", ""))
        joined = f"{title} {desc}".strip()
        score = utils.news_relevance_score(joined)
        if not title or not link:
            continue
        items.append({
            "source": feed["name"],
            "source_id": feed["id"],
            "title": title,
            "link": link,
            "summary": desc[:220],
            "published_at": pub,
            "score": score,
        })
    return items


def build_news_radar(force=False):
    cache = utils.safe_read_json(config.NEWS_CACHE_PATH, {})
    now = time.time()
    fetched_at = float(cache.get("fetched_at_ts") or 0)
    if not force and cache and now - fetched_at < config.NEWS_REFRESH_SECONDS:
        return cache

    merged = []
    errors = []
    for feed in config.NEWS_FEEDS:
        try:
            merged.extend(fetch_feed_items(feed))
        except Exception as exc:
            errors.append(f"{feed['name']}: {exc}")

    dedup = {}
    for item in merged:
        key = utils.normalize_news_text(item["title"])
        prev = dedup.get(key)
        if not prev or item["score"] > prev["score"]:
            dedup[key] = item

    selected = sorted(dedup.values(), key=lambda x: (x["score"], x["published_at"]), reverse=True)
    selected = [item for item in selected if item["score"] > 0][:8]
    payload = {
        "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "fetched_at_ts": now,
        "items": selected,
        "sources": [feed["name"] for feed in config.NEWS_FEEDS],
        "errors": errors[:5],
    }
    utils.safe_write_json(config.NEWS_CACHE_PATH, payload)
    return payload




















def resolve_jornada(conn, jornada=None):
    raw = str(jornada or "").strip()
    if raw.isdigit():
        return int(raw)
    row = conn.execute("SELECT MAX(jornada) FROM resultados").fetchone()
    return row[0] if row and row[0] is not None else None


def compute_refresh_window(conn, jornada=None):
    target_jornada = resolve_jornada(conn, jornada)
    if not target_jornada:
        return {"enabled": False, "reason": "sin_jornada"}

    rows = conn.execute("""
        SELECT fecha, hora, status
        FROM resultados
        WHERE jornada = ?
        ORDER BY partido_id ASC
    """, (target_jornada,)).fetchall()
    if not rows:
        return {"enabled": False, "reason": "sin_partidos", "jornada": target_jornada}

    match_times = [dt for dt in (utils.parse_db_match_datetime(r["fecha"], r["hora"]) for r in rows) if dt]
    live_now = any(str(r["status"] or "").upper() in ("LIVE", "IN PLAY", "HT", "HALF TIME BREAK", "EN JUEGO") for r in rows)
    has_pending = any(str(r["status"] or "").upper() in ("NS", "SCHEDULED", "NOT STARTED") for r in rows)
    needs_result_catchup = False

    if not match_times:
        return {
            "enabled": live_now,
            "reason": "solo_estados",
            "jornada": target_jornada,
            "live_now": live_now,
            "has_pending": has_pending,
        }

    first_kickoff = min(match_times)
    last_kickoff = max(match_times)
    now = datetime.now()
    active_windows = []
    for row in rows:
        kickoff = utils.parse_db_match_datetime(row["fecha"], row["hora"])
        if not kickoff:
            continue
        status = str(row["status"] or "").upper()
        if status in ("FT", "FINISHED", "TERMINADO"):
            continue
        window_start = kickoff - timedelta(minutes=2)
        window_end = kickoff + timedelta(hours=3)
        if window_start <= now <= window_end:
            active_windows.append((window_start, window_end, kickoff))
        elif kickoff < now <= kickoff + timedelta(hours=24):
            needs_result_catchup = True

    enabled = live_now or bool(active_windows) or needs_result_catchup
    if active_windows:
        current_window_start = min(item[0] for item in active_windows)
        current_window_end = max(item[1] for item in active_windows)
        next_kickoff = min(item[2] for item in active_windows)
    elif needs_result_catchup:
        current_window_start = first_kickoff - timedelta(minutes=2)
        current_window_end = last_kickoff + timedelta(hours=3)
        future_times = [dt for dt in match_times if dt >= now]
        next_kickoff = min(future_times) if future_times else None
    else:
        current_window_start = first_kickoff - timedelta(minutes=2)
        current_window_end = last_kickoff + timedelta(hours=3)
        future_times = [dt for dt in match_times if dt >= now]
        next_kickoff = min(future_times) if future_times else None
    return {
        "enabled": enabled,
        "reason": "ventana_jornada",
        "jornada": target_jornada,
        "live_now": live_now,
        "has_pending": has_pending,
        "needs_result_catchup": needs_result_catchup,
        "first_kickoff": first_kickoff,
        "last_kickoff": last_kickoff,
        "next_kickoff": next_kickoff,
        "window_start": current_window_start,
        "window_end": current_window_end,
    }


def get_highlightly_usage():
    path = os.path.join(config.BASE_DIR, "data", "API_USAGE_HIGHLIGHTLY.json")
    today = datetime.now().strftime("%Y-%m-%d")
    data = utils.safe_read_json(path, {})
    if data.get("date") != today:
        data = {"date": today, "calls": 0, "limit": HIGHLIGHTLY_DAILY_CALL_LIMIT}
    data["limit"] = HIGHLIGHTLY_DAILY_CALL_LIMIT
    data["reserve"] = HIGHLIGHTLY_DAILY_CALL_RESERVE
    data["remaining"] = max(0, HIGHLIGHTLY_DAILY_CALL_LIMIT - int(data.get("calls") or 0))
    data["usable_remaining"] = max(0, data["remaining"] - HIGHLIGHTLY_DAILY_CALL_RESERVE)
    return data


def record_highlightly_call(count=1):
    path = os.path.join(config.BASE_DIR, "data", "API_USAGE_HIGHLIGHTLY.json")
    with _highlightly_usage_lock:
        data = get_highlightly_usage()
        data["calls"] = int(data.get("calls") or 0) + int(count or 0)
        data["remaining"] = max(0, HIGHLIGHTLY_DAILY_CALL_LIMIT - data["calls"])
        data["usable_remaining"] = max(0, data["remaining"] - HIGHLIGHTLY_DAILY_CALL_RESERVE)
        utils.safe_write_json(path, data)
        return data


def reserve_highlightly_calls(count=1):
    count = max(1, int(count or 1))
    path = os.path.join(config.BASE_DIR, "data", "API_USAGE_HIGHLIGHTLY.json")
    with _highlightly_usage_lock:
        data = get_highlightly_usage()
        if count > int(data.get("usable_remaining") or 0):
            return None
        data["calls"] = int(data.get("calls") or 0) + count
        data["remaining"] = max(0, HIGHLIGHTLY_DAILY_CALL_LIMIT - data["calls"])
        data["usable_remaining"] = max(0, data["remaining"] - HIGHLIGHTLY_DAILY_CALL_RESERVE)
        utils.safe_write_json(path, data)
        return data


def can_spend_highlightly_calls(count):
    usage = get_highlightly_usage()
    return int(count or 0) <= int(usage.get("usable_remaining") or 0)


def get_highlightly_circuit():
    path = os.path.join(config.BASE_DIR, "data", "HIGHLIGHTLY_CIRCUIT.json")
    state = utils.safe_read_json(path, {})
    now = time.time()
    until = float(state.get("open_until") or 0)
    return {
        "path": path,
        "failures": int(state.get("failures") or 0),
        "open_until": until,
        "open": until > now,
        "last_error": state.get("last_error", ""),
    }


def record_highlightly_success():
    path = os.path.join(config.BASE_DIR, "data", "HIGHLIGHTLY_CIRCUIT.json")
    utils.safe_write_json(path, {
        "failures": 0,
        "open_until": 0,
        "last_error": "",
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    })


def record_highlightly_failure(exc):
    circuit = get_highlightly_circuit()
    failures = int(circuit.get("failures") or 0) + 1
    open_until = 0
    if failures >= HIGHLIGHTLY_CIRCUIT_FAILURE_LIMIT:
        open_until = time.time() + HIGHLIGHTLY_CIRCUIT_COOLDOWN_SECONDS
    utils.safe_write_json(circuit["path"], {
        "failures": failures,
        "open_until": open_until,
        "last_error": str(exc),
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    })


def _local_league_status_for_date(conn, jornada, date_text, league_name):
    league = str(league_name or "").upper()
    if league not in ("LA LIGA", "SEGUNDA DIVISION"):
        return {"known": False, "all_finished": False}

    target_division = 1 if league == "LA LIGA" else 2
    teams = {
        utils.normalize_team_key(row["equipo"])
        for row in conn.execute(
            "SELECT equipo FROM clasificacion WHERE division = ?",
            (target_division,),
        ).fetchall()
    }
    if not teams:
        return {"known": False, "all_finished": False}

    rows = conn.execute(
        """
        SELECT local, visitante, status
        FROM resultados
        WHERE jornada = ? AND substr(COALESCE(fecha, ''), 1, 10) = ?
        """,
        (jornada, date_text),
    ).fetchall()
    league_rows = [
        row for row in rows
        if (
            utils.normalize_team_key(row["local"]) in teams
            and utils.normalize_team_key(row["visitante"]) in teams
        )
    ]
    if not league_rows:
        return {"known": False, "all_finished": False}

    final_statuses = {"FT", "FINISHED", "TERMINADO"}
    return {
        "known": True,
        "all_finished": all(str(row["status"] or "").upper() in final_statuses for row in league_rows),
    }


def fetch_highlightly_matches(date_text, conn=None, jornada=None):
    circuit = get_highlightly_circuit()
    if circuit.get("open"):
        app.logger.warning(
            "Highlightly circuit open until %s; skipping %s",
            datetime.fromtimestamp(circuit["open_until"]).strftime("%H:%M:%S"),
            date_text,
        )
        return []
    headers = {
        "x-rapidapi-key": HIGHLIGHTLY_API_KEY,
    }
    matches = []
    for league_name, league_id in config.HIGHLIGHTLY_LEAGUES.items():
        if conn is not None and jornada is not None:
            local_status = _local_league_status_for_date(conn, jornada, date_text, league_name)
            if local_status["known"] and local_status["all_finished"]:
                app.logger.info("Highlightly skip local finalizado: %s %s", date_text, league_name)
                continue
        if not reserve_highlightly_calls(1):
            app.logger.warning("Highlightly daily call budget exhausted; skipping %s %s", date_text, league_name)
            break
        url = f"https://{config.HIGHLIGHTLY_HOST}/matches?date={date_text}&leagueId={league_id}"
        try:
            response = requests.get(url, headers=headers, timeout=8)
            response.raise_for_status()
            record_highlightly_success()
            for match in response.json().get("data", []):
                match["_competition_name"] = league_name
                matches.append(match)
        except requests.RequestException as exc:
            record_highlightly_failure(exc)
            app.logger.warning("Highlightly request failed for %s %s: %s", date_text, league_name, exc)
    return matches


def refresh_dates_for_jornada(conn, jornada=None):
    """Consulta hoy y fechas de partidos pendientes para no dejar huecos del dia anterior."""
    target_jornada = resolve_jornada(conn, jornada)
    today = datetime.now().strftime("%Y-%m-%d")
    dates = {today}
    if not target_jornada:
        return sorted(dates)
    rows = conn.execute("""
        SELECT fecha, status, goles_local, goles_visitante
        FROM resultados
        WHERE jornada = ?
    """, (target_jornada,)).fetchall()
    for row in rows:
        fecha = str(row["fecha"] or "").strip()[:10]
        if not fecha or fecha > today:
            continue
        status = str(row["status"] or "").upper()
        has_score = row["goles_local"] is not None and row["goles_visitante"] is not None
        if not has_score or status in ("NS", "SCHEDULED", "NOT STARTED", "LIVE", "IN PLAY", "HT", "EN JUEGO"):
            dates.add(fecha)
    return sorted(dates)


def refresh_dates_for_current_jornada(conn):
    return refresh_dates_for_jornada(conn)


def refresh_current_matches_from_highlightly(force=False, jornada=None):
    global _highlightly_last_refresh
    if not HIGHLIGHTLY_REFRESH_ENABLED or not HIGHLIGHTLY_API_KEY:
        return 0
    now = time.time()
    if not force and now - _highlightly_last_refresh < 35:
        return 0
    if not _highlightly_refresh_lock.acquire(blocking=False):
        return 0
    try:
        _highlightly_last_refresh = now
        updates = 0
        api_matches = []
        with get_db() as conn:
            target_jornada = resolve_jornada(conn, jornada)
            if not target_jornada:
                return 0

            for date_text in refresh_dates_for_jornada(conn, target_jornada):
                api_matches.extend(fetch_highlightly_matches(date_text, conn=conn, jornada=target_jornada))

            feed = {}
            logos = {}
            for match in api_matches:
                home_team = match.get("homeTeam") or {}
                away_team = match.get("awayTeam") or {}
                home_name = home_team.get("name")
                away_name = away_team.get("name")
                if home_name and away_name:
                    home_key = utils.normalize_team_key(home_name)
                    away_key = utils.normalize_team_key(away_name)
                    feed[(home_key, away_key)] = (match, False)
                    feed[(away_key, home_key)] = (match, True)
                if home_name and home_team.get("logo"):
                    logos[home_name.upper()] = home_team["logo"]
                if away_name and away_team.get("logo"):
                    logos[away_name.upper()] = away_team["logo"]

            panel_matches = [utils.highlightly_match_to_panel(match) for match in api_matches if match.get("id")]
            if panel_matches:
                panel_path = os.path.join(config.BASE_DIR, "data", "LIVE_ALL_MATCHES_V3.json")
                merged_matches = {}
                try:
                    with open(panel_path, "r", encoding="utf-8") as fh:
                        for item in json.load(fh) or []:
                            item_id = str(item.get("id") or "").strip()
                            if item_id:
                                merged_matches[item_id] = item
                except Exception:
                    merged_matches = {}
                for item in panel_matches:
                    item_id = str(item.get("id") or "").strip()
                    if item_id:
                        merged_matches[item_id] = item
                with open(panel_path, "w", encoding="utf-8") as fh:
                    json.dump(list(merged_matches.values()), fh, ensure_ascii=False, indent=2)

            rows = conn.execute("""
                SELECT partido_id, local, visitante, status, minuto, goles_local, goles_visitante
                FROM resultados
                WHERE jornada = ?
            """, (target_jornada,)).fetchall()
            for row in rows:
                if str(row["minuto"] or "").upper().startswith("SUSPENDIDO LAE"):
                    continue
                feed_item = feed.get((utils.normalize_team_key(row["local"]), utils.normalize_team_key(row["visitante"])))
                if not feed_item:
                    continue
                match, reversed_match = feed_item
                state = match.get("state") or {}
                score_text = ((state.get("score") or {}).get("current") or "")
                home_goals, away_goals = utils.parse_score_text(score_text)
                if reversed_match:
                    home_goals, away_goals = away_goals, home_goals
                status, minute = utils.highlightly_status(state)
                signo = utils.signo_for_match(row["partido_id"], home_goals, away_goals)
                conn.execute("""
                    UPDATE resultados
                    SET goles_local = ?, goles_visitante = ?, status = ?, minuto = ?, signo_actual = ?
                    WHERE jornada = ? AND partido_id = ?
                """, (home_goals, away_goals, status, minute, signo, target_jornada, row["partido_id"]))
                updates += 1

        if logos:
            logo_path = os.path.join(config.BASE_DIR, "data", "TEAM_LOGOS.json")
            try:
                with open(logo_path, "r", encoding="utf-8") as fh:
                    existing = json.load(fh)
            except Exception:
                existing = {}
            existing.update(logos)
            with open(logo_path, "w", encoding="utf-8") as fh:
                json.dump(existing, fh, ensure_ascii=False, indent=2)
        return updates
    except Exception as exc:
        app.logger.warning("Highlightly refresh failed: %s", exc)
        return 0
    finally:
        _highlightly_refresh_lock.release()


def trigger_highlightly_refresh_async(force=False, jornada=None):
    global _highlightly_refresh_thread, _highlightly_refresh_started_at
    if not HIGHLIGHTLY_REFRESH_ENABLED or not HIGHLIGHTLY_API_KEY:
        return False
    now = time.time()
    if not force and now - _highlightly_last_refresh < 35:
        return False
    thread = _highlightly_refresh_thread
    if thread and thread.is_alive():
        if now - _highlightly_refresh_started_at < 300:
            return False
        _highlightly_refresh_thread = None

    def _runner():
        try:
            refresh_current_matches_from_highlightly(force=force, jornada=jornada)
        finally:
            pass

    _highlightly_refresh_started_at = now
    _highlightly_refresh_thread = threading.Thread(
        target=_runner,
        name="highlightly-refresh",
        daemon=True,
    )
    _highlightly_refresh_thread.start()
    return True

@app.route('/')
def index():
    """
    Página principal de la Quiniela. Calcula la jornada más reciente y
    renderiza la plantilla HTML. Si el fichero de plantilla no existe
    (por ejemplo, durante el desarrollo), devuelve un mensaje de texto
    explicativo para evitar un error 500.
    """
    user = session.get('user')
    conn = get_db()
    max_j_row = conn.execute("SELECT MAX(jornada) FROM resultados").fetchone()
    max_j = max_j_row[0] if max_j_row else '62'
    conn.close()
    j = request.args.get('j', str(max_j))
    try:
        return render_template('liga_index.html', jornada=j, user=user, assets_v=int(time.time()))
    except Exception:
        return f"La plantilla no se encontró. Jornada actual: {j}", 200

@app.route('/api/user/status')
def user_status():
    user = session.get('user')
    return jsonify({"user": user})

@app.route('/api/live/ticker')
def get_live_ticker():
    """
    Devuelve el contenido del ticker en directo. Intenta primero leer
    `data/LIVE_TICKER.json`. Si no existe, intenta buscarlo en la raíz
    del proyecto. Este enfoque permite que la ruta funcione aunque la
    estructura de carpetas sea distinta.
    """
    ticker_path = os.path.join(config.BASE_DIR, "data", "LIVE_TICKER.json")
    if not os.path.exists(ticker_path):
        ticker_path = os.path.join(config.BASE_DIR, "LIVE_TICKER.json")
    if os.path.exists(ticker_path):
        try:
            with open(ticker_path, 'r', encoding='utf-8') as f:
                return jsonify(json.load(f))
        except Exception:
            pass
    return jsonify({"matches": []})

@app.route('/api/q15/directo')
def q15_directo():
    jornada = request.args.get("j", "").strip()
    if not jornada.isdigit():
        return jsonify({"matches": []})
    path = os.path.join(config.BASE_DIR, "data", f"quiniela15_directo_J{jornada}.json")
    if not os.path.exists(path):
        return jsonify({"jornada": int(jornada), "matches": [], "cached": False})
    try:
        with open(path, "r", encoding="utf-8") as fh:
            payload = json.load(fh)
        payload["cached"] = True
        return jsonify(payload)
    except Exception as exc:
        app.logger.warning("Q15 directo cache read failed: %s", exc)
        return jsonify({"jornada": int(jornada), "matches": [], "cached": False})


def repair_mojibake(text):
    if not isinstance(text, str):
        return text
    if "Ã" not in text and "Â" not in text:
        return text
    try:
        return text.encode("latin1").decode("utf-8")
    except Exception:
        return text


def load_match_info_for_jornada(jornada):
    info = {}
    j_text = str(jornada)
    scrape_path = os.path.join(config.BASE_DIR, "data", f"quiniela15_J{j_text}_scrape.json")
    if os.path.exists(scrape_path):
        try:
            with open(scrape_path, "r", encoding="utf-8") as fh:
                q15_data = json.load(fh)
            for item in q15_data.get("partidos") or []:
                pid = int(item.get("num") or item.get("id") or 0)
                if not pid:
                    continue
                info[pid] = {
                    "q15": item.get("q15"),
                    "lae": item.get("lae"),
                    "apu": item.get("apu"),
                    "historico": item.get("historico"),
                    "fuerza_local": item.get("fuerza_local"),
                    "fuerza_visitante": item.get("fuerza_visitante"),
                    "detalle": repair_mojibake(item.get("detalle") or ""),
                }
        except Exception as exc:
            app.logger.warning("Q15 jornada info read failed: %s", exc)

    parent_dir = os.path.abspath(os.path.join(config.BASE_DIR, ".."))
    prediction_candidates = [
        os.path.join(parent_dir, f"PREDICCIONES_J{j_text}_DEFINITIVO.json"),
        os.path.join(parent_dir, f"PREDICCIONES_J{j_text}_FINAL.json"),
        os.path.join(config.BASE_DIR, "data", f"PREDICCIONES_J{j_text}_DEFINITIVO.json"),
        os.path.join(config.BASE_DIR, "data", f"PREDICCIONES_J{j_text}_FINAL.json"),
    ]
    for path in prediction_candidates:
        if not os.path.exists(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as fh:
                pred_data = json.load(fh)
            for item in pred_data.get("maestra") or []:
                pid = int(item.get("p") or item.get("id") or 0)
                if not pid:
                    continue
                info.setdefault(pid, {})
                info[pid]["maestra"] = {
                    "signo": repair_mojibake(item.get("s") or ""),
                    "razon": repair_mojibake(item.get("r") or ""),
                }
            break
        except Exception as exc:
            app.logger.warning("Prediction jornada info read failed: %s", exc)
    return {str(k): v for k, v in info.items()}


@app.route('/login/google')
def login():
    redirect_uri = url_for('authorize', _external=True)
    return google.authorize_redirect(redirect_uri)

@app.route('/authorize')
def authorize():
    token = google.authorize_access_token()
    user_info = token.get('userinfo')
    if user_info:
        # Registrar o actualizar usuario en la DB
        conn = get_db()
        conn.execute("""
            INSERT INTO usuarios (id, nombre, email) 
            VALUES (?, ?, ?) 
            ON CONFLICT(id) DO UPDATE SET nombre=excluded.nombre, email=excluded.email
        """, (user_info['sub'], user_info['name'], user_info['email']))
        conn.commit()
        conn.close()
        session['user'] = {'id': user_info['sub'], 'name': user_info['name'], 'email': user_info['email']}
    return redirect('/')

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect('/')

@app.route('/api/sync/status')
def sync_status():
    conn = get_db()
    target_jornada = resolve_jornada(conn, request.args.get("j"))
    refresh_window = compute_refresh_window(conn, target_jornada)
    today = datetime.now().strftime("%Y-%m-%d")
    # Contar partidos vivos
    live = conn.execute("""
        SELECT COUNT(*) FROM resultados
        WHERE jornada = ? AND fecha = ? AND status IN ('LIVE', 'IN PLAY', 'HT', 'EN JUEGO')
    """, (target_jornada, today)).fetchone()[0] if target_jornada else 0
    pending = conn.execute("""
        SELECT COUNT(*) FROM resultados
        WHERE jornada = ? AND status IN ('NS', 'SCHEDULED', 'NOT STARTED')
    """, (target_jornada,)).fetchone()[0] if target_jornada else 0
    panel_path = os.path.join(config.BASE_DIR, "data", "LIVE_ALL_MATCHES_V3.json")
    last_sync = "--:--"
    try:
        if os.path.exists(panel_path):
            last_sync = datetime.fromtimestamp(os.path.getmtime(panel_path)).strftime("%H:%M")
    except Exception:
        pass
    api_usage = get_highlightly_usage()
    q15_cache = {"available": False, "last_sync": "--:--", "matches": 0}
    q15_path = os.path.join(config.BASE_DIR, "data", f"quiniela15_directo_J{target_jornada}.json") if target_jornada else ""
    if q15_path and os.path.exists(q15_path):
        try:
            with open(q15_path, "r", encoding="utf-8") as fh:
                q15_payload = json.load(fh)
            q15_cache = {
                "available": True,
                "last_sync": datetime.fromtimestamp(os.path.getmtime(q15_path)).strftime("%H:%M"),
                "matches": len(q15_payload.get("matches") or []),
            }
        except Exception:
            pass
    
    conn.close()
    return jsonify({
        "jornada": target_jornada,
        "live_matches": live,
        "pending_matches": pending,
        "last_sync": last_sync,
        "auto_refresh": False,
        "refresh_available": bool(HIGHLIGHTLY_REFRESH_ENABLED and refresh_window.get("enabled")),
        "refresh_reason": refresh_window.get("reason", "cache-only"),
        "api_usage": api_usage,
        "q15_cache": q15_cache
    })


@app.route('/api/live/health')
def live_health():
    health_path = os.path.join(config.BASE_DIR, "data", "LIVE_COLLECTOR_HEALTH.json")
    exists = os.path.exists(health_path)
    health = utils.safe_read_json(health_path, {}) if exists else {}
    age_seconds = None
    if exists:
        try:
            age_seconds = int(time.time() - os.path.getmtime(health_path))
        except Exception:
            age_seconds = None
    return jsonify({
        "status": "ok",
        "collector": health or {"status": "missing", "error": "LIVE_COLLECTOR_HEALTH.json no existe"},
        "health_file": exists,
        "age_seconds": age_seconds,
        "stale": bool(age_seconds is None or age_seconds > 300),
        "api_usage": get_highlightly_usage(),
        "highlightly_circuit": {
            key: value
            for key, value in get_highlightly_circuit().items()
            if key != "path"
        },
    })


@app.route('/api/teams/canonical')
def teams_canonical():
    return jsonify({
        "status": "ok",
        "contract": utils.build_team_contract(),
    })


@app.route('/api/liga/data')
def get_liga_data():
    j = request.args.get('j', '')
    conn = get_db()
    team_logos = utils.load_team_logos()

    def logo_for(team_name):
        return team_logos.get(utils.normalize_team_key(team_name), "")

    max_j_row = conn.execute("SELECT MAX(jornada) FROM resultados").fetchone()
    if not max_j_row or max_j_row[0] is None:
        conn.close()
        return jsonify({
            "status": "error",
            "message": "No hay jornadas cargadas en resultados"
        }), 404
    max_jornada = max_j_row[0]
    
    if not j:
        j = max_jornada
    
    rows = conn.execute("SELECT partido_id as id, local, visitante, goles_local, goles_visitante, status, fecha, hora, minuto FROM resultados WHERE jornada = ? ORDER BY partido_id ASC", (j,)).fetchall()
    partidos = []
    for row in rows:
        r = dict(row)
        p_id = r['id']
        gh, ga = r.get("goles_local"), r.get("goles_visitante")
        status = r.get("status") or "NS"
        minuto = (r.get("minuto") or "").replace("min. ", "").replace("min.", "").strip()
        
        signo = "-"
        if (status in ['FT', 'LIVE', 'FINISHED', 'IN PLAY', 'HT', 'HALF TIME BREAK', 'EN JUEGO', 'TERMINADO']) and gh is not None and ga is not None:
            if gh > ga: signo = "1"
            elif gh < ga: signo = "2"
            else: signo = "X"

        fecha_limpia = ""
        if r.get('fecha'):
            try:
                fecha_dt = datetime.strptime(str(r['fecha'])[:10], "%Y-%m-%d")
                dias = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
                fecha_limpia = f"{dias[fecha_dt.weekday()]} {fecha_dt.strftime('%d/%m')}"
            except Exception:
                fecha_limpia = str(r['fecha']).replace("2026-", "").replace("/2026", "")
            
        if status in ['LIVE', 'IN PLAY', 'HT', 'HALF TIME BREAK', 'EN JUEGO']:
            minuto_num = ''.join(ch for ch in minuto if ch.isdigit())
            marcador_base = f"{gh}-{ga}" if gh is not None and ga is not None else "-:-"
            if minuto_num:
                marcador = f"{marcador_base}\u00a0({minuto_num}')"
            elif minuto.upper() in ("HT", "DESCANSO"):
                marcador = f"{marcador_base}\u00a0(Desc.)"
            else:
                marcador = marcador_base
        elif status == 'NS' or status == 'SCHEDULED':
            minuto_num = ""
            marcador_base = ""
            hora_label = (r.get("hora") or "").strip()
            if r.get("fecha") == datetime.now().strftime("%Y-%m-%d"):
                marcador = f"{hora_label}h" if hora_label else "Horario pendiente"
            else:
                marcador = f"{fecha_limpia} {hora_label}h".strip() if hora_label else (fecha_limpia or "Horario pendiente")
        else:
            minuto_num = ""
            marcador_base = f"{gh}-{ga}" if gh is not None and ga is not None else ""
            marcador = f"{gh}-{ga}" if gh is not None and ga is not None else "-:-"
            
        partidos.append({
            "id": p_id, "local": r["local"], "visitante": r["visitante"],
            "logo_local": logo_for(r["local"]),
            "logo_visitante": logo_for(r["visitante"]),
            "marcador": marcador, "status": status,
            "marcador_base": marcador_base,
            "minuto_live": minuto_num,
            "fecha_raw": r.get("fecha", ""),
            "hora": r.get("hora", "-"), 
            "signo_actual": signo,
            "goles_local": gh,
            "goles_visitante": ga
        })
    
    standings_raw = conn.execute("SELECT * FROM clasificacion ORDER BY pos ASC").fetchall()
    standings = {"primera": [], "segunda": []}
    standings_db = {"primera": {}, "segunda": {}}
    for s in standings_raw:
        cat = "primera" if s['division'] == 1 else "segunda"
        item = {
            "n": s['equipo'],
            "pj": s['pj'],
            "pts": s['pts'],
            "pos": s['pos'],
            "pg": s['pg'],
            "pe": s['pe'],
            "pp": s['pp'],
            "gf": s['gf'],
            "gc": s['gc'],
            "racha": s["racha"] if "racha" in s.keys() else "",
            "source": "db"
        }
        standings_db[cat][utils.normalize_team_key(s['equipo'])] = item
        standings[cat].append(item)

    # Criterio estable:
    # 1) la clasificación base oficial manda
    # 2) la BD local queda solo como respaldo si falta algún equipo
    standings_override = utils.load_standings_override()
    if standings_override:
        for cat in ("primera", "segunda"):
            official_rows = []
            seen = set()
            for item in standings_override.get(cat, []):
                key = utils.normalize_team_key(item.get("n"))
                seen.add(key)
                official_rows.append({
                    "n": item.get("n"),
                    "pj": item.get("pj", 0),
                    "pts": item.get("pts", 0),
                    "pos": item.get("pos", 0),
                    "pg": item.get("pg"),
                    "pe": item.get("pe"),
                    "pp": item.get("pp"),
                    "gf": item.get("gf"),
                    "gc": item.get("gc"),
                    "racha": item.get("racha", ""),
                    "base_oficial": True,
                    "source": "official"
                })
            if official_rows:
                standings[cat] = official_rows

    def apply_finished_matches_to_standings(standings_data, matches):
        category_by_key = {}
        row_by_key = {}
        for cat, rows in standings_data.items():
            for row in rows:
                key = utils.normalize_team_key(row.get("n"))
                if key:
                    category_by_key[key] = cat
                    row_by_key[key] = row

        max_pj = {"primera": 38, "segunda": 42}
        for match in matches:
            if str(match.get("status") or "").upper() not in ("FT", "FINISHED", "TERMINADO"):
                continue
            home_key = utils.normalize_team_key(match.get("local"))
            away_key = utils.normalize_team_key(match.get("visitante"))
            cat = category_by_key.get(home_key)
            if not cat or cat != category_by_key.get(away_key):
                continue
            home = row_by_key.get(home_key)
            away = row_by_key.get(away_key)
            if not home or not away:
                continue
            target_pj = max_pj.get(cat)
            if target_pj and (int(home.get("pj") or 0) >= target_pj or int(away.get("pj") or 0) >= target_pj):
                continue
            gh = match.get("goles_local")
            ga = match.get("goles_visitante")
            if gh is None or ga is None:
                gh, ga = utils.parse_score_text(match.get("marcador_base") or match.get("marcador"))
            if gh is None or ga is None:
                continue

            def add_match(row, gf, gc, points, result_key):
                row["pj"] = int(row.get("pj") or 0) + 1
                row["gf"] = int(row.get("gf") or 0) + int(gf)
                row["gc"] = int(row.get("gc") or 0) + int(gc)
                row["pts"] = int(row.get("pts") or 0) + int(points)
                row[result_key] = int(row.get(result_key) or 0) + 1

            if int(gh) > int(ga):
                add_match(home, gh, ga, 3, "pg")
                add_match(away, ga, gh, 0, "pp")
            elif int(gh) < int(ga):
                add_match(home, gh, ga, 0, "pp")
                add_match(away, ga, gh, 3, "pg")
            else:
                add_match(home, gh, ga, 1, "pe")
                add_match(away, ga, gh, 1, "pe")

        for cat, rows in standings_data.items():
            rows.sort(key=lambda row: (
                -int(row.get("pts") or 0),
                -(int(row.get("gf") or 0) - int(row.get("gc") or 0)),
                -int(row.get("gf") or 0),
                str(row.get("n") or "")
            ))
            for idx, row in enumerate(rows, start=1):
                row["pos"] = idx

    apply_finished_matches_to_standings(standings, partidos)

    preds = {}
    preds_raw = conn.execute("SELECT user_id, partido_id, signo FROM predicciones WHERE jornada = ?", (j,)).fetchall()
    for p in preds_raw:
        uid = p['user_id']
        if uid not in preds: preds[uid] = {"signos": ["-"] * 15}
        # Aseguramos que el índice no desborde
        p_idx = p['partido_id'] - 1
        if 0 <= p_idx < 15:
            preds[uid]["signos"][p_idx] = p['signo']

    consenso = []
    cons_raw = conn.execute("SELECT partido_id, ganador, p1, px, p2 FROM consenso WHERE jornada = ?", (j,)).fetchall()
    for c in cons_raw:
        consenso.append({"id": c['partido_id'], "ganador": c['ganador'], "p1": c['p1'], "px": c['px'], "p2": c['p2']})

    # Calcular ranking completo. Se normalizan aliases para no duplicar
    # entradas como GROK/grok o programa/v260_omnisciente en la UI.
    res_map = {}
    all_res = conn.execute("""
        SELECT jornada, partido_id, signo_actual, goles_local, goles_visitante
        FROM resultados
        WHERE signo_actual IS NOT NULL AND signo_actual != '-'
    """).fetchall()
    for r in all_res:
        real = r['signo_actual']
        if int(r['partido_id'] or 0) == 15 and r['goles_local'] is not None and r['goles_visitante'] is not None:
            real = f"{int(r['goles_local'])}-{int(r['goles_visitante'])}"
        res_map[(r['jornada'], r['partido_id'])] = real
    
    ranking = {}
    # Obtenemos TODOS los user_ids de predicciones para que no falte nadie
    all_preds = conn.execute("""
        SELECT user_id, jornada, partido_id, signo
        FROM predicciones
        WHERE jornada >= ?
    """, (CONTEST_DYNAMIC_START_JORNADA,)).fetchall()
    for p in all_preds:
        uid = canonical_contest_id(p['user_id'])
        if uid not in ranking: ranking[uid] = {"total": 0, "jornada": 0}
        real = res_map.get((p['jornada'], p['partido_id']))
        if score_prediction(p['partido_id'], p['signo'], real):
            ranking[uid]["total"] += 1
            if str(p['jornada']) == str(j): ranking[uid]["jornada"] += 1
    
    # Bloque historico cerrado; el calculo dinamico solo suma desde J61.
    extra_users = conn.execute("SELECT id, puntos_acumulados FROM usuarios").fetchall()
    extra_points = {}
    for u in extra_users:
        uid = canonical_contest_id(u['id'])
        extra_points[uid] = max(int(extra_points.get(uid, 0) or 0), int(u['puntos_acumulados'] or 0))
    for uid, points in extra_points.items():
        if uid not in ranking:
            ranking[uid] = {"total": points, "jornada": 0}
        else:
            ranking[uid]["total"] += points
                
    # Detección de jornada de liga aproximada
    jornada_liga_detectada = "37"
    if j == "61": jornada_liga_detectada = "37"
    elif j == "60": jornada_liga_detectada = "36"

    all_league_matches = []
    # Cargar los partidos de otras ligas. Igual que con la base de datos,
    # intentamos la ruta estándar y, en caso de no existir, una ruta en la
    # raíz del proyecto.
    candidate_match_paths = [
        os.path.join(config.BASE_DIR, "data", "LIVE_ALL_MATCHES_V3.json"),
        os.path.join(config.BASE_DIR, "LIVE_ALL_MATCHES_V3.json"),
        os.path.abspath(os.path.join(config.BASE_DIR, "..", "AUDITORIA", "data", "LIVE_ALL_MATCHES_V3.json")),
        os.path.join(config.BASE_DIR, "data", "LIVE_ALL_MATCHES.json"),
    ]
    for all_matches_path in candidate_match_paths:
        if not os.path.exists(all_matches_path):
            continue
        try:
            with open(all_matches_path, 'r', encoding='utf-8') as f:
                loaded_matches = json.load(f)
            if loaded_matches:
                all_league_matches = loaded_matches
                break
        except Exception:
            pass

    # La quiniela oficial ya contiene la jornada completa de Primera y Segunda.
    # La usamos como fuente estable para esas pestañas, porque los feeds externos
    # a veces devuelven solo una parte del fin de semana.
    def infer_match_competition(match):
        home_key = utils.normalize_team_key(match.get("local"))
        away_key = utils.normalize_team_key(match.get("visitante"))
        if "HYPERMOTION" in home_key or "HYPERMOTION" in away_key:
            return "SEGUNDA DIVISION"
        if home_key in standings_db.get("primera", {}) and away_key in standings_db.get("primera", {}):
            return "LA LIGA"
        if home_key in standings_db.get("segunda", {}) and away_key in standings_db.get("segunda", {}):
            return "SEGUNDA DIVISION"
        return "FRIENDLIES"

    quiniela_league_matches = []
    for m in partidos:
        comp = infer_match_competition(m)
        if comp:
            fecha = m.get("fecha_raw") or ""
            hora = m.get("hora") or ""
            quiniela_league_matches.append({
                "id": f"quiniela-{j}-{m['id']}",
                "fixture_id": f"quiniela-{j}-{m['id']}",
                "competition_name": comp,
                "competition": {"name": comp},
                "local": m["local"],
                "visitante": m["visitante"],
                "home": {"name": m["local"]},
                "away": {"name": m["visitante"]},
                "home_logo": m.get("logo_local", ""),
                "away_logo": m.get("logo_visitante", ""),
                "status": m["status"],
                "time": m.get("minuto") or "",
                "score": m["marcador"] if m["status"] not in ("NS", "SCHEDULED") else "",
                "marcador": m["marcador"],
                "added": f"{fecha} {hora}".strip(),
                "scheduled": hora,
                "fecha_raw": fecha,
                "hora": hora
            })

    quiniela_pairs = {
        (
            utils.normalize_team_key(m.get("local")),
            utils.normalize_team_key(m.get("visitante"))
        )
        for m in quiniela_league_matches
    }

    quiniela_datetimes = [dt for dt in (utils.parse_any_match_datetime(m) for m in quiniela_league_matches) if dt]
    if quiniela_datetimes:
        window_start = min(quiniela_datetimes) - timedelta(days=1)
        window_end = max(quiniela_datetimes) + timedelta(days=1)
        today_str = datetime.now().strftime("%Y-%m-%d")

        def keep_external_match(match):
            dt = utils.parse_any_match_datetime(match)
            if dt and window_start <= dt <= window_end:
                return True
            raw_status = str(match.get("status") or "").upper()
            raw_score = str(match.get("score") or match.get("marcador") or "").strip()
            match_date = str(match.get("added") or match.get("fecha_raw") or "")[:10]
            has_score = bool(re.search(r"\d+\s*-\s*\d+", raw_score))
            looks_live = raw_status in ("LIVE", "IN PLAY", "HT", "EN JUEGO")
            return match_date == today_str and (looks_live or has_score)

        all_league_matches = [m for m in all_league_matches if keep_external_match(m)]

    all_league_matches = [
        m for m in all_league_matches
        if not (
            (m.get("competition_name") or m.get("competition", {}).get("name") or "").upper() in ("LA LIGA", "SEGUNDA DIVISION")
            and (
                utils.normalize_team_key(m.get("local") or m.get("home_name") or (m.get("home") or {}).get("name")),
                utils.normalize_team_key(m.get("visitante") or m.get("away_name") or (m.get("away") or {}).get("name"))
            ) in quiniela_pairs
        )
    ]
    all_league_matches = quiniela_league_matches + all_league_matches
    for m in all_league_matches:
        home_name = m.get("local") or m.get("home_name") or (m.get("home") or {}).get("name")
        away_name = m.get("visitante") or m.get("away_name") or (m.get("away") or {}).get("name")
        m["home_logo"] = m.get("home_logo") or (m.get("home") or {}).get("logo") or logo_for(home_name)
        m["away_logo"] = m.get("away_logo") or (m.get("away") or {}).get("logo") or logo_for(away_name)

    # Detectar si la jornada está bloqueada
    def parse_match_datetime(match):
        fecha = str(match.get("fecha_raw") or "").strip()[:10]
        hora = str(match.get("hora") or "").strip()[:5]
        if not fecha or not hora or hora == "-":
            return None
        try:
            return datetime.strptime(f"{fecha} {hora}", "%Y-%m-%d %H:%M")
        except Exception:
            return None

    kickoff_times = [dt for dt in (parse_match_datetime(m) for m in partidos) if dt]
    first_kickoff = min(kickoff_times) if kickoff_times else None
    first_kickoff_started = bool(first_kickoff and datetime.now() >= first_kickoff)

    is_locked = first_kickoff_started or any((m.get('status') or '') in ('LIVE', 'FT', 'FINISHED') for m in partidos)
    match_info = load_match_info_for_jornada(j)
    for match in partidos:
        info = match_info.get(str(match.get("id")))
        if not info:
            continue
        detail = info.get("detalle") or ""
        if "Hypermotion" in detail:
            detail = (
                detail
                .replace("6º Hypermotion", match.get("local") or "Local")
                .replace("3º Hypermotion", match.get("visitante") or "Visitante")
                .replace("5º Hypermotion", match.get("local") or "Local")
                .replace("4º Hypermotion", match.get("visitante") or "Visitante")
            )
            info["detalle"] = detail

    conn.close()
    return jsonify({
        "jornada": j,
        "jornada_liga": jornada_liga_detectada,
        "max_jornada": max_jornada,
        "is_locked": is_locked,
        "edit_deadline": first_kickoff.strftime("%Y-%m-%d %H:%M") if first_kickoff else "",
        "partidos": partidos,
        "all_league_matches": all_league_matches,
        "standings": standings,
        "team_logos": team_logos,
        "team_contract": utils.build_team_contract(),
        "match_info": match_info,
        "predicciones_actuales": preds,
        "consenso_pena": consenso,
        "ranking_maestros": ranking
    })

@app.route('/api/live/refresh', methods=['POST'])
def manual_live_refresh():
    if not is_admin_request():
        return jsonify({
            "status": "forbidden",
            "message": "Refresco externo limitado a entorno local/admin"
        }), 403
    if not HIGHLIGHTLY_REFRESH_ENABLED:
        return jsonify({
            "status": "disabled",
            "message": "Refresco externo desactivado para no gastar llamadas innecesarias"
        }), 409
    if not HIGHLIGHTLY_API_KEY:
        return jsonify({
            "status": "disabled",
            "message": "Highlightly no tiene API key configurada"
        }), 409
    payload = request.get_json(silent=True) or {}
    jornada = request.args.get("j") or payload.get("j")
    started = trigger_highlightly_refresh_async(force=True, jornada=jornada)
    return jsonify({
        "status": "ok" if started else "busy",
        "started": bool(started)
    })

@app.route('/api/live/probe', methods=['POST'])
def live_probe():
    if not is_admin_request():
        return jsonify({
            "status": "forbidden",
            "message": "Sondeo manual limitado a entorno local/admin"
        }), 403
    payload_json = request.get_json(silent=True) or {}
    requested_jornada = request.args.get("j") or payload_json.get("j")
    conn = get_db()
    target_jornada = resolve_jornada(conn, requested_jornada)
    refresh_window = compute_refresh_window(conn, target_jornada)
    conn.close()

    q15_status = {"ok": False, "matches": 0, "message": "sin_jornada"}
    if target_jornada:
        try:
            payload = scrape_q15_directo(int(target_jornada))
            q15_path = os.path.join(config.BASE_DIR, "data", f"quiniela15_directo_J{target_jornada}.json")
            utils.safe_write_json(q15_path, payload)
            q15_status = {
                "ok": True,
                "matches": len(payload.get("matches") or []),
                "last_sync": datetime.fromtimestamp(os.path.getmtime(q15_path)).strftime("%H:%M"),
            }
        except Exception as exc:
            q15_status = {"ok": False, "matches": 0, "message": str(exc)}

    highlightly_started = False
    highlightly_skipped = "fuera_de_ventana"
    if HIGHLIGHTLY_REFRESH_ENABLED and refresh_window.get("enabled"):
        highlightly_started = trigger_highlightly_refresh_async(force=True, jornada=target_jornada)
        highlightly_skipped = ""

    return jsonify({
        "status": "ok",
        "jornada": target_jornada,
        "q15": q15_status,
        "highlightly": {
            "started": bool(highlightly_started),
            "skipped": highlightly_skipped,
            "window_enabled": bool(refresh_window.get("enabled")),
            "reason": refresh_window.get("reason"),
        },
        "api_usage": get_highlightly_usage(),
    })


def is_scored_status(status):
    return str(status or "").upper() in ("FT", "FINISHED", "TERMINADO")


def pleno_score_key(value):
    raw = str(value or "").strip().upper().replace(" ", "")
    match = re.search(r"([0-9M]+)-([0-9M]+)", raw)
    if not match:
        return ""

    def bucket(part):
        if part == "M":
            return "M"
        try:
            goals = int(part)
        except Exception:
            return ""
        return "M" if goals >= 3 else str(goals)

    home = bucket(match.group(1))
    away = bucket(match.group(2))
    return f"{home}-{away}" if home and away else ""


def normalize_prediction_sign(partido_id, value):
    raw = str(value or "").strip().upper().replace(" ", "")
    if not raw or raw == "-":
        return "-"
    try:
        match_id = int(partido_id)
    except Exception:
        return ""
    if match_id == 15:
        return pleno_score_key(raw)
    if match_id < 1 or match_id > 14:
        return ""
    if any(ch not in "1X2" for ch in raw):
        return ""
    chars = "".join(ch for ch in "1X2" if ch in set(raw))
    return chars if chars else ""


def score_prediction(partido_id, prediction, real_sign):
    pred = str(prediction or "").strip().upper()
    real = str(real_sign or "").strip().upper()
    if not pred or not real or real == "-":
        return 0
    if int(partido_id or 0) == 15:
        return 1 if pleno_score_key(pred) == pleno_score_key(real) else 0
    return 1 if real in pred else 0


def public_contest_name(uid, users):
    names = {
        "v260_omnisciente": "PROGRAMA",
        "programa": "PROGRAMA",
        "consejo_ias": "CONSEJO IA",
        "gemini": "GEMINI",
        "grok": "GROK",
        "claude": "CLAUDE",
        "copilot": "COPILOT",
        "chatgpt": "CHATGPT",
        "chipi": "CHIPI",
        "deepseek": "CHIPI",
        "kimi": "KIMI",
        "profe": "PROFE",
    }
    if uid in names:
        return names[uid]
    user_name = (users.get(uid) or "").strip()
    if user_name:
        return user_name.split()[0][:16]
    return str(uid or "").split("@")[0][:16].upper()


def canonical_contest_id(uid):
    value = str(uid or "").strip()
    low = value.lower()
    if low in ("v260_omnisciente", "programa"):
        return "programa"
    if low in ("deepseek", "chipi"):
        return "chipi"
    if low in (
        "gemini", "grok", "claude", "copilot", "chatgpt", "kimi", "profe",
        "ernie", "fortu", "geli", "mrpurple", "oraculo", "pepe", "consenso",
        "hermes", "jenova", "momo", "manu", "manus", "qwen", "gwen", "meta",
        "perplexity", "glm5", "geli_glm5", "chema_cohere", "momo_molbot",
        "tecnotron", "consejo_ias",
    ):
        return low
    return value


def contest_month_key(date_text):
    raw = str(date_text or "").strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(raw[:10], fmt).strftime("%Y-%m")
        except Exception:
            continue
    return raw[:7] if raw else "sin-mes"


def build_contest_payload(current_jornada=None, current_user_id=None):
    hidden_ids = {"hermes", "molbot", "jenova", "pena", "consenso", "momo", "manu", "manus"}
    conn = get_db()
    user_rows = conn.execute("SELECT id, nombre, puntos_acumulados FROM usuarios").fetchall()
    users = {row["id"]: row["nombre"] for row in user_rows}
    extra_points = {}
    for row in user_rows:
        uid = canonical_contest_id(row["id"])
        extra_points[uid] = max(int(extra_points.get(uid, 0) or 0), int(row["puntos_acumulados"] or 0))

    result_rows = conn.execute("""
        SELECT jornada, partido_id, signo_actual, fecha, status
        FROM resultados
        WHERE signo_actual IS NOT NULL AND signo_actual != '-'
    """).fetchall()
    results = {}
    jornada_dates = {}
    for row in result_rows:
        if not is_scored_status(row["status"]):
            continue
        key = (int(row["jornada"]), int(row["partido_id"]))
        results[key] = row["signo_actual"]
        jornada_dates.setdefault(int(row["jornada"]), str(row["fecha"] or "")[:10])

    pred_rows = conn.execute("""
        SELECT user_id, jornada, partido_id, signo
        FROM predicciones
        WHERE jornada >= ?
    """, (CONTEST_DYNAMIC_START_JORNADA,)).fetchall()
    conn.close()

    totals = {}
    played = {}
    jornada_scores = {}
    monthly_scores = {}
    ballots = {}
    seen_predictions = set()
    for pred in pred_rows:
        uid = canonical_contest_id(pred["user_id"])
        if uid.lower() in hidden_ids:
            continue
        jornada = int(pred["jornada"])
        partido_id = int(pred["partido_id"])
        pred_key = (uid, jornada, partido_id)
        if pred_key in seen_predictions:
            continue
        seen_predictions.add(pred_key)
        real = results.get((jornada, partido_id))
        if not real:
            continue
        hit = score_prediction(partido_id, pred["signo"], real)
        totals[uid] = totals.get(uid, 0) + hit
        jornada_scores.setdefault(jornada, {})
        jornada_scores[jornada][uid] = jornada_scores[jornada].get(uid, 0) + hit
        ballots.setdefault((uid, jornada), {})[partido_id] = str(pred["signo"] or "-").strip().upper()
        date_key = contest_month_key(jornada_dates.get(jornada))
        monthly_scores.setdefault(date_key, {})
        monthly_scores[date_key][uid] = monthly_scores[date_key].get(uid, 0) + hit

    for (uid, jornada), signs in ballots.items():
        played[uid] = played.get(uid, 0) + 1

    for uid, points in extra_points.items():
        if uid.lower() not in hidden_ids and points:
            totals[uid] = totals.get(uid, 0) + points

    def rows_from_scores(scores, limit=None):
        rows = []
        for uid, score in scores.items():
            rows.append({
                "id": uid,
                "name": public_contest_name(uid, users),
                "points": int(score or 0),
                "played": int(played.get(uid, 0)),
                "is_user": bool(current_user_id and uid == current_user_id),
            })
        rows.sort(key=lambda item: (-item["points"], item["name"]))
        for idx, item in enumerate(rows, 1):
            item["pos"] = idx
        return rows[:limit] if limit else rows

    def profile_for(uid):
        if not uid:
            return None
        uid = canonical_contest_id(uid)
        user_rows_rank = rows_from_scores(totals)
        mine = next((item for item in user_rows_rank if item["id"] == uid), None)
        my_jornadas = []
        for jornada in sorted(jornada_scores.keys()):
            rows = rows_from_scores(jornada_scores[jornada])
            found = next((item for item in rows if item["id"] == uid), None)
            if not found:
                continue
            ballot = ballots.get((uid, jornada), {})
            ticket = [ballot.get(i, "-") for i in range(1, 16)]
            my_jornadas.append({
                "jornada": jornada,
                "ticket": ticket,
                "points": found["points"],
                "pos": found["pos"],
            })
        total_predictions = len(my_jornadas) * 15
        total_hits = int(mine["points"] if mine else 0)
        profile_name = public_contest_name(uid, users)
        profile_awards = []
        for jornada in sorted(jornada_scores.keys(), reverse=True):
            rows = rows_from_scores(jornada_scores[jornada])
            if rows and rows[0]["id"] == uid:
                profile_awards.append({
                    "jornada": jornada,
                    "winner": rows[0]["name"],
                    "points": rows[0]["points"],
                    "date": jornada_dates.get(jornada, ""),
                })
        return {
            "id": uid,
            "name": profile_name,
            "position": mine["pos"] if mine else None,
            "played": len(my_jornadas),
            "predictions": total_predictions,
            "hits": total_hits,
            "hit_rate": round((total_hits / total_predictions) * 100, 2) if total_predictions else 0,
            "hits_per_jornada": round(total_hits / len(my_jornadas), 2) if my_jornadas else 0,
            "best_position": min((row["pos"] for row in my_jornadas), default=None),
            "results": my_jornadas[-24:],
            "awards": profile_awards[:20],
        }

    general = rows_from_scores(totals)
    selected_jornada = int(current_jornada or max(jornada_scores.keys() or [0]))
    jornada_rows = rows_from_scores(jornada_scores.get(selected_jornada, {}))
    latest_month = sorted(monthly_scores.keys())[-1] if monthly_scores else ""
    monthly_rows = rows_from_scores(monthly_scores.get(latest_month, {}))

    galardones_jornada = []
    for jornada in sorted(jornada_scores.keys(), reverse=True):
        rows = rows_from_scores(jornada_scores[jornada])
        winner = rows[0] if rows else None
        if not winner:
            continue
        galardones_jornada.append({
            "jornada": jornada,
            "winner": winner["name"],
            "points": winner["points"],
            "date": jornada_dates.get(jornada, ""),
        })

    galardones_mes = []
    for month in sorted(monthly_scores.keys(), reverse=True):
        rows = rows_from_scores(monthly_scores[month])
        winner = rows[0] if rows else None
        if winner:
            galardones_mes.append({"month": month, "winner": winner["name"], "points": winner["points"]})

    profile = profile_for(current_user_id) if current_user_id else None

    return {
        "general": general,
        "jornada": {"jornada": selected_jornada, "rows": jornada_rows},
        "monthly": {"month": latest_month, "rows": monthly_rows},
        "galardones": {
            "jornadas": galardones_jornada,
            "meses": galardones_mes,
        },
        "profile": profile,
    }


@app.route('/api/concurso')
def get_contest():
    user = session.get('user') or {}
    jornada = request.args.get("j") or None
    payload = build_contest_payload(jornada, user.get("id"))
    return jsonify(payload)


@app.route('/api/concurso/perfil/<uid>')
def get_contest_profile(uid):
    user = session.get('user') or {}
    jornada = request.args.get("j") or None
    payload = build_contest_payload(jornada, user.get("id"))
    target = canonical_contest_id(uid)
    profile = None
    for row in payload.get("general", []):
        if row.get("id") == target:
            profile_payload = build_contest_payload(jornada, target)
            profile = profile_payload.get("profile")
            break
    if not profile:
        profile_payload = build_contest_payload(jornada, target)
        profile = profile_payload.get("profile")
    if not profile:
        return jsonify({"status": "error", "message": "Perfil no encontrado"}), 404
    return jsonify({"status": "ok", "profile": profile})


@app.route('/api/ligas/disponibles')
def get_ligas_disponibles():
    # Solo las ligas requeridas: Quiniela (por defecto), La Liga, Hypermotion, Premier, Alemana, Francesa
    ligas = ["LA LIGA", "SEGUNDA DIVISION", "PREMIER LEAGUE", "BUNDESLIGA", "LIGUE 1"]
    return jsonify({"ligas": ligas})



@app.route('/api/predicciones/save', methods=['POST'])
def save_predictions():
    user = session.get('user')
    if not user:
        return jsonify({"status": "error", "message": "Debes iniciar sesión"}), 401
    
    data = request.get_json(silent=True) or {}
    uid = data.get('user_id')
    j = data.get('jornada')
    signos = data.get('signos')
    
    if not uid or not j or not signos:
        return jsonify({"status": "error", "message": "Datos incompletos"}), 400
    if not isinstance(signos, list) or len(signos) != 15:
        return jsonify({"status": "error", "message": "La quiniela debe tener 15 signos."}), 400

    normalized_signs = []
    for i, signo in enumerate(signos, 1):
        normalized = normalize_prediction_sign(i, signo)
        if not normalized:
            return jsonify({
                "status": "error",
                "message": f"Signo invalido en el partido {i}."
            }), 400
        normalized_signs.append(normalized)
    
    if str(uid) != str(user['id']):
        return jsonify({"status": "error", "message": "No autorizado"}), 403
        
    conn = get_db()
    transaction_started = False
    try:
        rows = conn.execute("SELECT fecha, hora, status FROM resultados WHERE jornada = ?", (j,)).fetchall()
        kickoff_times = []
        for row in rows:
            fecha = str(row["fecha"] or "").strip()[:10]
            hora = str(row["hora"] or "").strip()[:5]
            if fecha and hora and hora != "-":
                try:
                    kickoff_times.append(datetime.strptime(f"{fecha} {hora}", "%Y-%m-%d %H:%M"))
                except Exception:
                    pass
        first_kickoff = min(kickoff_times) if kickoff_times else None
        close_at = first_kickoff - timedelta(minutes=max(0, PREDICTION_CLOSE_MINUTES_BEFORE_KICKOFF)) if first_kickoff else None
        already_closed = bool(close_at and datetime.now() >= close_at)
        already_closed = already_closed or any((row["status"] or "") in ("LIVE", "IN PLAY", "HT", "FT", "FINISHED", "TERMINADO") for row in rows)
        if already_closed:
            if close_at:
                close_label = close_at.strftime("%d/%m %H:%M")
                message = f"La quiniela ya esta cerrada: el cierre era el {close_label}."
            else:
                message = "La quiniela ya esta cerrada: empezo el primer partido."
            return jsonify({"status": "error", "message": message}), 403

        conn.execute("BEGIN IMMEDIATE")
        transaction_started = True
        conn.execute("DELETE FROM predicciones WHERE user_id = ? AND jornada = ?", (uid, j))
        for i, signo in enumerate(normalized_signs, 1):
            if signo != "-":
                conn.execute("INSERT INTO predicciones (user_id, jornada, partido_id, signo) VALUES (?, ?, ?, ?)",
                            (uid, j, i, signo))
        conn.commit()
        return jsonify({"status": "ok", "message": "Quiniela guardada correctamente"})
    except Exception as e:
        if transaction_started:
            conn.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()

def ensure_comments_table(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS comentarios_jornada (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            jornada INTEGER NOT NULL,
            user_id TEXT NOT NULL,
            nombre TEXT NOT NULL,
            texto TEXT NOT NULL,
            etiqueta TEXT NOT NULL DEFAULT 'Bar',
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_comentarios_jornada_created ON comentarios_jornada(jornada, created_at)")

@app.route('/api/comentarios')
def get_comments():
    j = request.args.get('j', '')
    if not j:
        return jsonify({"comentarios": []})

    conn = get_db()
    try:
        ensure_comments_table(conn)
        rows = conn.execute("""
            SELECT id, jornada, nombre, texto, etiqueta, created_at
            FROM comentarios_jornada
            WHERE jornada = ?
            ORDER BY datetime(created_at) DESC, id DESC
            LIMIT 60
        """, (j,)).fetchall()
        comments = [dict(row) for row in rows]
        comments.reverse()
        return jsonify({"comentarios": comments})
    finally:
        conn.close()

@app.route('/api/comentarios', methods=['POST'])
def post_comment():
    user = session.get('user')
    if not user:
        return jsonify({"status": "error", "message": "Entra con Google para comentar"}), 401

    data = request.get_json(silent=True) or {}
    jornada = data.get('jornada')
    texto = (data.get('texto') or '').strip()
    etiqueta = (data.get('etiqueta') or 'Bar').strip()
    allowed_tags = {"Bar", "Sorpresa", "Fijo", "Duda", "Contra la IA"}

    if not jornada or not texto:
        return jsonify({"status": "error", "message": "Comentario incompleto"}), 400
    if len(texto) > 240:
        return jsonify({"status": "error", "message": "Máximo 240 caracteres"}), 400
    if etiqueta not in allowed_tags:
        etiqueta = "Bar"

    conn = get_db()
    try:
        ensure_comments_table(conn)
        conn.execute("""
            INSERT INTO comentarios_jornada (jornada, user_id, nombre, texto, etiqueta, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            jornada,
            user.get('id'),
            (user.get('name') or 'Maestro').split(' ')[0],
            texto,
            etiqueta,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))
        conn.commit()
        return jsonify({"status": "ok"})
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500
    finally:
        conn.close()

@app.route('/api/user/stats')
def get_user_stats():
    uid = request.args.get('uid')
    if not uid: return jsonify({})
    
    conn = get_db()
    stats = conn.execute("""
        SELECT COUNT(*) as aciertos 
        FROM predicciones p
        JOIN resultados r ON p.jornada = r.jornada AND p.partido_id = r.partido_id
        WHERE p.user_id = ?
        AND UPPER(COALESCE(r.status, '')) IN ('FT', 'FINISHED', 'TERMINADO', 'LIVE', 'IN PLAY', 'HT', 'HALF TIME BREAK', 'EN JUEGO')
        AND (
            (r.goles_local > r.goles_visitante AND p.signo = '1') OR
            (r.goles_local < r.goles_visitante AND p.signo = '2') OR
            (r.goles_local = r.goles_visitante AND p.signo = 'X')
        )
    """, (uid,)).fetchone()
    
    best = conn.execute("""
        SELECT jornada, COUNT(*) as aciertos 
        FROM (
            SELECT p.jornada, p.partido_id 
            FROM predicciones p
            JOIN resultados r ON p.jornada = r.jornada AND p.partido_id = r.partido_id
            WHERE p.user_id = ?
            AND UPPER(COALESCE(r.status, '')) IN ('FT', 'FINISHED', 'TERMINADO', 'LIVE', 'IN PLAY', 'HT', 'HALF TIME BREAK', 'EN JUEGO')
            AND (
                (r.goles_local > r.goles_visitante AND p.signo = '1') OR
                (r.goles_local < r.goles_visitante AND p.signo = '2') OR
                (r.goles_local = r.goles_visitante AND p.signo = 'X')
            )
        ) GROUP BY jornada ORDER BY aciertos DESC LIMIT 1
    """, (uid,)).fetchone()
    
    conn.close()
    return jsonify({
        "total_aciertos": stats['aciertos'] if stats else 0,
        "mejor_jornada": best['aciertos'] if best else 0,
        "posicion": "TOP" 
    })

@app.route('/api/noticias/radar')
def get_news_radar():
    force = request.args.get("force", "").strip().lower() in ("1", "true", "yes")
    return jsonify(build_news_radar(force=force))

# Rutas estáticas personalizadas
@app.route('/static/<path:filename>')
def static_files(filename):
    """
    Permite servir ficheros CSS y JavaScript situados en la raíz del proyecto
    sin necesidad de moverlos a una carpeta `static`. Flask por defecto
    sirve desde `static/`, pero aquí ampliamos para que archivos como
    `quantum.css` y `quantum_final.js` puedan ser entregados correctamente.
    """
    response = send_from_directory(os.path.join(config.BASE_DIR, "static"), filename, max_age=0)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

@app.route('/api/user/evolution')
def get_evolution():
    uid = request.args.get('uid')
    if not uid: return jsonify({"status": "error", "message": "UID requerido"}), 400
    
    conn = get_db()
    rows = conn.execute("""
        SELECT p.user_id, p.jornada, p.partido_id, p.signo, r.signo_actual, r.goles_local, r.goles_visitante
        FROM predicciones p
        JOIN resultados r ON p.jornada = r.jornada AND p.partido_id = r.partido_id
        WHERE UPPER(COALESCE(r.status, '')) IN ('FT', 'FINISHED', 'TERMINADO')
        ORDER BY p.jornada ASC, p.partido_id ASC
    """).fetchall()
    conn.close()

    series_ids = {
        "user": {uid},
        "programa": {"programa", "v260_omnisciente"},
        "consenso": {"consejo_ias", "consenso"},
    }
    scores = {key: {} for key in series_ids}
    for row in rows:
        real = row["signo_actual"]
        if int(row["partido_id"] or 0) == 15 and row["goles_local"] is not None and row["goles_visitante"] is not None:
            real = f"{int(row['goles_local'])}-{int(row['goles_visitante'])}"
        for key, ids in series_ids.items():
            if row["user_id"] not in ids:
                continue
            if score_prediction(row["partido_id"], row["signo"], real):
                jornada = int(row["jornada"])
                scores[key][jornada] = scores[key].get(jornada, 0) + 1

    jornadas = sorted(set().union(*(set(values.keys()) for values in scores.values())))
    return jsonify({
        "labels": [f"J{jornada}" for jornada in jornadas],
        "user": [scores["user"].get(jornada, 0) for jornada in jornadas],
        "programa": [scores["programa"].get(jornada, 0) for jornada in jornadas],
        "consenso": [scores["consenso"].get(jornada, 0) for jornada in jornadas],
    })


if __name__ == '__main__':
    app.run(debug=True, port=5000, use_reloader=True)
