"""Porra routes: match score predictions."""
import os
from datetime import datetime
from flask import Blueprint, request, jsonify, session

from ..db.connection import get_db
from ..middleware.rate_limit import is_rate_limited
from ..services.ticket import madrid_now, parse_madrid_datetime
from ..db.migrations import ensure_porra_table

bp = Blueprint("porra", __name__)


def _porra_target_match(conn, jornada):
    rows = conn.execute("""
        SELECT partido_id, local, visitante, fecha, hora, status, goles_local, goles_visitante
        FROM resultados WHERE jornada = ? ORDER BY partido_id ASC
    """, (jornada,)).fetchall()
    if not rows:
        return None
    matches = [dict(row) for row in rows]

    def is_open(match):
        status = str(match.get("status") or "").upper()
        kickoff = parse_madrid_datetime(match.get("fecha"), match.get("hora"))
        return status in ("", "NS", "SCHEDULED", "NOT STARTED") and (
            not kickoff or madrid_now() < kickoff
        )

    open_matches = [match for match in matches if is_open(match)]

    # El Pleno al 15 ya es un pronostico de marcador exacto y debe ser la
    # porra principal mientras admita participaciones.
    pleno = next(
        (match for match in open_matches if int(match["partido_id"]) == 15),
        None,
    )
    if pleno:
        return pleno

    existing = conn.execute("""
        SELECT partido_id, MIN(created_at) AS first_entry
        FROM porra_entries
        WHERE jornada = ?
        GROUP BY partido_id
        ORDER BY datetime(first_entry) ASC, partido_id ASC
        LIMIT 1
    """, (jornada,)).fetchone()
    if existing:
        target_id = int(existing["partido_id"])
        fixed_match = next(
            (match for match in open_matches if int(match["partido_id"]) == target_id),
            None,
        )
        if fixed_match:
            return fixed_match

    candidates = [match for match in open_matches if int(match["partido_id"]) <= 14]
    if not candidates:
        return None

    # Una sola porra por fecha: entre los partidos del dia mas cercano se
    # elige el que tenga las opiniones mas repartidas.
    dated_candidates = [
        (parse_madrid_datetime(match.get("fecha"), match.get("hora")), match)
        for match in candidates
    ]
    known_dates = [kickoff.date() for kickoff, _match in dated_candidates if kickoff]
    if known_dates:
        nearest_day = min(known_dates)
        candidates = [
            match for kickoff, match in dated_candidates
            if kickoff and kickoff.date() == nearest_day
        ]

    prediction_rows = conn.execute("""
        SELECT partido_id, signo
        FROM predicciones
        WHERE jornada = ? AND partido_id BETWEEN 1 AND 14 AND signo NOT IN ('', '-')
    """, (jornada,)).fetchall()
    votes_by_match = {}
    for row in prediction_rows:
        counts = votes_by_match.setdefault(int(row["partido_id"]), {"1": 0, "X": 0, "2": 0})
        raw_sign = str(row["signo"] or "").upper()
        for sign in counts:
            if sign in raw_sign:
                counts[sign] += 1

    def interest_score(match):
        counts = votes_by_match.get(int(match["partido_id"]), {})
        total = sum(counts.values())
        if not total:
            return (-1, 0, -int(match["partido_id"]))
        balance = 1 - (max(counts.values()) / total)
        return (balance, total, -int(match["partido_id"]))

    return max(candidates, key=interest_score)


def _porra_presentation(match):
    if int(match.get("partido_id") or 0) == 15:
        return {"kind": "pleno15", "label": "Porra del Pleno al 15"}
    kickoff = parse_madrid_datetime(match.get("fecha"), match.get("hora"))
    label = "Porra del dia" if kickoff and kickoff.date() == madrid_now().date() else "Proxima porra"
    return {"kind": "daily", "label": label}


def _porra_is_locked(match):
    if not match:
        return True
    status = str(match.get("status") or "").upper()
    if status not in ("", "NS", "SCHEDULED", "NOT STARTED"):
        return True
    kickoff = parse_madrid_datetime(match.get("fecha"), match.get("hora"))
    return bool(kickoff and madrid_now() >= kickoff)


@bp.route('/api/porra')
def get_porra():
    user = session.get("user") or {}
    raw_j = request.args.get("j") or request.args.get("jornada") or ""
    try:
        jornada = int(raw_j)
    except (TypeError, ValueError):
        return jsonify({"status": "error", "message": "Jornada invalida"}), 400

    conn = get_db()
    try:
        ensure_porra_table(conn)
        match = _porra_target_match(conn, jornada)
        if not match:
            return jsonify({"status": "ok", "enabled": False, "message": "Sin partido de porra"})
        presentation = _porra_presentation(match)
        entries = conn.execute("""
            SELECT nombre, goles_local, goles_visitante, updated_at
            FROM porra_entries WHERE jornada = ? AND partido_id = ?
            ORDER BY datetime(updated_at) DESC LIMIT 20
        """, (jornada, match["partido_id"])).fetchall()
        distribution_rows = conn.execute("""
            SELECT goles_local, goles_visitante, COUNT(*) AS total
            FROM porra_entries WHERE jornada = ? AND partido_id = ?
            GROUP BY goles_local, goles_visitante
            ORDER BY total DESC, goles_local ASC, goles_visitante ASC LIMIT 6
        """, (jornada, match["partido_id"])).fetchall()
        total_entries = conn.execute("SELECT COUNT(*) AS total FROM porra_entries WHERE jornada = ? AND partido_id = ?", (jornada, match["partido_id"])).fetchone()
        porra_total = int(total_entries["total"] or 0) if total_entries else 0
        distribution = []
        for row in distribution_rows:
            item = dict(row)
            total = int(item.get("total") or 0)
            item["percent"] = round((total * 100 / porra_total), 1) if porra_total else 0
            distribution.append(item)
        mine = None
        if user.get("id"):
            mine_row = conn.execute("SELECT goles_local, goles_visitante, updated_at FROM porra_entries WHERE jornada = ? AND partido_id = ? AND user_id = ?", (jornada, match["partido_id"], user.get("id"))).fetchone()
            mine = dict(mine_row) if mine_row else None
        return jsonify({
            "status": "ok", "enabled": True, "jornada": jornada, "match": match,
            **presentation,
            "locked": _porra_is_locked(match),
            "prize": os.getenv("PORRA_PRIZE_TEXT", "Premio symbolico: insignia semanal"),
            "entries": [dict(row) for row in entries], "distribution": distribution,
            "total_entries": porra_total, "mine": mine, "auth": bool(user.get("id")),
        })
    finally:
        conn.close()


@bp.route('/api/porra', methods=['POST'])
def post_porra():
    user = session.get("user")
    if not user:
        return jsonify({"status": "error", "message": "Entra con Google para jugar la porra."}), 401
    if is_rate_limited("porra_post", user.get("id"), 5):
        return jsonify({"status": "error", "message": "Espera unos segundos antes de guardar otra porra."}), 429
    data = request.get_json(silent=True) or {}
    try:
        jornada = int(data.get("jornada"))
        gl = int(data.get("goles_local"))
        gv = int(data.get("goles_visitante"))
    except (TypeError, ValueError):
        return jsonify({"status": "error", "message": "Marcador invalido."}), 400
    if gl < 0 or gv < 0 or gl > 15 or gv > 15:
        return jsonify({"status": "error", "message": "Marcador fuera de rango."}), 400

    conn = get_db()
    try:
        ensure_porra_table(conn)
        match = _porra_target_match(conn, jornada)
        if not match:
            return jsonify({"status": "error", "message": "No hay partido de porra."}), 404
        if _porra_is_locked(match):
            return jsonify({"status": "error", "message": "La porra de esta jornada ya esta cerrada."}), 400
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute("""
            INSERT INTO porra_entries (jornada, partido_id, user_id, nombre, goles_local, goles_visitante, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, jornada, partido_id) DO UPDATE SET
                nombre = excluded.nombre, goles_local = excluded.goles_local,
                goles_visitante = excluded.goles_visitante, updated_at = excluded.updated_at
        """, (jornada, match["partido_id"], user.get("id"), (user.get("name") or "Maestro").split(" ")[0], gl, gv, now, now))
        conn.commit()
        return jsonify({"status": "ok", "goles_local": gl, "goles_visitante": gv})
    finally:
        conn.close()
