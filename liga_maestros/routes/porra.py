"""Porra routes: exact-score predictions on any open match chosen by the user."""

from datetime import datetime

from flask import Blueprint, jsonify, request, session

from ..db.connection import get_db
from ..db.migrations import ensure_porra_table
from ..middleware.rate_limit import is_rate_limited
from ..services.ticket import madrid_now, parse_madrid_datetime

bp = Blueprint("porra", __name__)


def check_and_award_porra_points(conn, jornada):
    """Check if any porra predictions were correct and award 1 point to the user.

    This should be called after match results are updated.
    """
    # Get all finished matches for this jornada
    finished_matches = conn.execute(
        """
        SELECT partido_id, goles_local, goles_visitante
        FROM resultados
        WHERE jornada = ? AND status IN ('FT', 'FINISHED', 'TERMINADO')
        AND goles_local IS NOT NULL AND goles_visitante IS NOT NULL
        """,
        (jornada,),
    ).fetchall()

    if not finished_matches:
        return 0

    awarded = 0
    for match in finished_matches:
        partido_id = match["partido_id"]
        gl = match["goles_local"]
        gv = match["goles_visitante"]

        # Find all porra entries for this match that predicted the exact score
        correct_entries = conn.execute(
            """
            SELECT user_id FROM porra_entries
            WHERE jornada = ? AND partido_id = ? AND goles_local = ? AND goles_visitante = ?
            """,
            (jornada, partido_id, gl, gv),
        ).fetchall()

        for entry in correct_entries:
            user_id = entry["user_id"]
            # Check if we already awarded points for this porra
            already_awarded = conn.execute(
                """
                SELECT 1 FROM porra_puntos
                WHERE jornada = ? AND partido_id = ? AND user_id = ?
                """,
                (jornada, partido_id, user_id),
            ).fetchone()

            if not already_awarded:
                # Award 1 point to the user
                conn.execute(
                    """
                    UPDATE usuarios SET puntos_acumulados = puntos_acumulados + 1
                    WHERE id = ?
                    """,
                    (user_id,),
                )
                # Record that we awarded points
                conn.execute(
                    """
                    INSERT OR IGNORE INTO porra_puntos (jornada, partido_id, user_id, puntos)
                    VALUES (?, ?, ?, 1)
                    """,
                    (jornada, partido_id, user_id),
                )
                awarded += 1

    if awarded:
        conn.commit()

    return awarded


def _porra_available_matches(conn, jornada):
    """Return all open matches for a jornada that can be used for porra."""
    rows = conn.execute(
        """
        SELECT partido_id, local, visitante, fecha, hora, status
        FROM resultados WHERE jornada = ? ORDER BY partido_id ASC
    """,
        (jornada,),
    ).fetchall()
    if not rows:
        return []

    def is_open(match):
        status = str(match.get("status") or "").upper()
        kickoff = parse_madrid_datetime(match.get("fecha"), match.get("hora"))
        return status in ("", "NS", "SCHEDULED", "NOT STARTED") and (not kickoff or madrid_now() < kickoff)

    return [dict(row) for row in rows if is_open(dict(row))]


def _porra_target_match(conn, jornada, partido_id=None):
    """Get a specific match or auto-select the most interesting one."""
    if partido_id:
        row = conn.execute(
            """
            SELECT partido_id, local, visitante, fecha, hora, status, goles_local, goles_visitante
            FROM resultados WHERE jornada = ? AND partido_id = ?
        """,
            (jornada, partido_id),
        ).fetchone()
        if row:
            return dict(row)
        return None

    # Fallback: auto-select (original behavior)
    rows = conn.execute(
        """
        SELECT partido_id, local, visitante, fecha, hora, status, goles_local, goles_visitante
        FROM resultados WHERE jornada = ? ORDER BY partido_id ASC
    """,
        (jornada,),
    ).fetchall()
    if not rows:
        return None
    matches = [dict(row) for row in rows]

    def is_open(match):
        status = str(match.get("status") or "").upper()
        kickoff = parse_madrid_datetime(match.get("fecha"), match.get("hora"))
        return status in ("", "NS", "SCHEDULED", "NOT STARTED") and (not kickoff or madrid_now() < kickoff)

    open_matches = [match for match in matches if is_open(match)]

    existing = conn.execute(
        """
        SELECT partido_id, MIN(created_at) AS first_entry
        FROM porra_entries
        WHERE jornada = ? AND partido_id BETWEEN 1 AND 14
        GROUP BY partido_id
        ORDER BY datetime(first_entry) ASC, partido_id ASC
        LIMIT 1
    """,
        (jornada,),
    ).fetchone()
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

    dated_candidates = [(parse_madrid_datetime(match.get("fecha"), match.get("hora")), match) for match in candidates]
    known_dates = [kickoff.date() for kickoff, _match in dated_candidates if kickoff]
    if known_dates:
        nearest_day = min(known_dates)
        candidates = [match for kickoff, match in dated_candidates if kickoff and kickoff.date() == nearest_day]

    prediction_rows = conn.execute(
        """
        SELECT partido_id, signo
        FROM predicciones
        WHERE jornada = ? AND partido_id BETWEEN 1 AND 14 AND signo NOT IN ('', '-')
    """,
        (jornada,),
    ).fetchall()
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


def _jornada_is_locked(conn, jornada):
    """Check if ANY match in the jornada has started - locks everything."""
    first_match = conn.execute(
        """
        SELECT fecha, hora, status FROM resultados
        WHERE jornada = ?
        ORDER BY fecha ASC, hora ASC
        LIMIT 1
        """,
        (jornada,),
    ).fetchone()
    if not first_match:
        return True
    status = str(first_match["status"] or "").upper()
    if status not in ("", "NS", "SCHEDULED", "NOT STARTED"):
        return True
    kickoff = parse_madrid_datetime(first_match["fecha"], first_match["hora"])
    return bool(kickoff and madrid_now() >= kickoff)


@bp.route("/api/porra")
def get_porra():
    user = session.get("user") or {}
    raw_j = request.args.get("j") or request.args.get("jornada") or ""
    raw_pid = request.args.get("pid") or request.args.get("partido_id") or ""
    try:
        jornada = int(raw_j)
    except (TypeError, ValueError):
        return jsonify({"status": "error", "message": "Jornada invalida"}), 400

    partido_id = None
    if raw_pid:
        try:
            partido_id = int(raw_pid)
        except (TypeError, ValueError):
            pass

    conn = get_db()
    try:
        ensure_porra_table(conn)

        # Get all available matches for the dropdown
        available = _porra_available_matches(conn, jornada)

        # A registered user can make a porra for any match which has not started.
        # Keep all their entries: one exact-score prediction per match, not a
        # single journal-wide entry silently forced by the server.
        user_entries = []
        user_entry = None
        if user.get("id"):
            user_entries = [
                dict(row)
                for row in conn.execute(
                    """
                SELECT partido_id, goles_local, goles_visitante, changes
                FROM porra_entries
                WHERE jornada = ? AND user_id = ?
                ORDER BY datetime(updated_at) DESC, partido_id ASC
                """,
                    (jornada, user.get("id")),
                ).fetchall()
            ]
            if user_entries:
                user_entry = user_entries[0]
            # On first load, show the user's most recently saved porra. The
            # selector still exposes every currently open match.
            if partido_id is None and user_entries:
                partido_id = user_entries[0]["partido_id"]

        # Get the selected match (or a useful default for anonymous visitors).
        match = _porra_target_match(conn, jornada, partido_id)
        if not match:
            return jsonify(
                {"status": "ok", "enabled": False, "message": "Sin partido de porra", "available": available}
            )

        presentation = _porra_presentation(match)
        entries = conn.execute(
            """
            SELECT nombre, goles_local, goles_visitante, updated_at
            FROM porra_entries WHERE jornada = ? AND partido_id = ?
            ORDER BY datetime(updated_at) DESC LIMIT 20
        """,
            (jornada, match["partido_id"]),
        ).fetchall()
        distribution_rows = conn.execute(
            """
            SELECT goles_local, goles_visitante, COUNT(*) AS total
            FROM porra_entries WHERE jornada = ? AND partido_id = ?
            GROUP BY goles_local, goles_visitante
            ORDER BY total DESC, goles_local ASC, goles_visitante ASC LIMIT 6
        """,
            (jornada, match["partido_id"]),
        ).fetchall()
        total_entries = conn.execute(
            "SELECT COUNT(*) AS total FROM porra_entries WHERE jornada = ? AND partido_id = ?",
            (jornada, match["partido_id"]),
        ).fetchone()
        porra_total = int(total_entries["total"] or 0) if total_entries else 0
        distribution = []
        for row in distribution_rows:
            item = dict(row)
            total = int(item.get("total") or 0)
            item["percent"] = round((total * 100 / porra_total), 1) if porra_total else 0
            distribution.append(item)
        mine = next(
            (entry for entry in user_entries if int(entry["partido_id"]) == int(match["partido_id"])),
            None,
        )
        jornada_locked = _jornada_is_locked(conn, jornada)
        return jsonify(
            {
                "status": "ok",
                "enabled": True,
                "jornada": jornada,
                "match": match,
                "available": available,
                **presentation,
                "locked": jornada_locked or _porra_is_locked(match),
                "jornada_locked": jornada_locked,
                "prize": "1 punto extra si aciertas el marcador exacto",
                "entries": [dict(row) for row in entries],
                "distribution": distribution,
                "total_entries": porra_total,
                "mine": mine,
                "my_entries": user_entries,
                "my_changes": user_entry.get("changes", 0) if user_entry else 0,
                "can_change": (user_entry.get("changes", 0) < 1) if user_entry else True,
                "auth": bool(user.get("id")),
            }
        )
    finally:
        conn.close()


@bp.route("/api/porra", methods=["POST"])
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

    try:
        partido_id = int(data.get("partido_id"))
    except (TypeError, ValueError):
        return jsonify({"status": "error", "message": "Elige un partido para tu porra."}), 400

    if gl < 0 or gv < 0 or gl > 15 or gv > 15:
        return jsonify({"status": "error", "message": "Marcador fuera de rango."}), 400

    conn = get_db()
    try:
        ensure_porra_table(conn)

        # Check if jornada is locked (first match started)
        if _jornada_is_locked(conn, jornada):
            return jsonify(
                {"status": "error", "message": "La jornada ya ha empezado. No se puede modificar la porra."}
            ), 400

        match = _porra_target_match(conn, jornada, partido_id)
        if not match:
            return jsonify({"status": "error", "message": "No hay partido de porra."}), 404
        if _porra_is_locked(match):
            return jsonify({"status": "error", "message": "La porra de esta jornada ya esta cerrada."}), 400

        # Check if user already has a porra for this jornada
        existing_entry = conn.execute(
            "SELECT partido_id, changes FROM porra_entries WHERE jornada = ? AND user_id = ?",
            (jornada, user.get("id")),
        ).fetchone()

        # If user has already changed once, don't allow another change
        if existing_entry and existing_entry["changes"] >= 1:
            return jsonify(
                {"status": "error", "message": "Ya cambiaste tu porra una vez. No puedes cambiarla más."}
            ), 400

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        changes = 1 if existing_entry else 0

        conn.execute(
            """
            INSERT INTO porra_entries (jornada, partido_id, user_id, nombre, goles_local, goles_visitante, created_at, updated_at, changes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, jornada) DO UPDATE SET
                partido_id = excluded.partido_id,
                nombre = excluded.nombre, goles_local = excluded.goles_local,
                goles_visitante = excluded.goles_visitante, updated_at = excluded.updated_at,
                changes = porra_entries.changes + 1
        """,
            (
                jornada,
                match["partido_id"],
                user.get("id"),
                (user.get("name") or "Maestro").split(" ")[0],
                gl,
                gv,
                now,
                now,
                changes,
            ),
        )
        conn.commit()

        if existing_entry:
            return jsonify(
                {
                    "status": "ok",
                    "partido_id": match["partido_id"],
                    "goles_local": gl,
                    "goles_visitante": gv,
                    "message": "Porra actualizada. Ya no podrás cambiarla más.",
                }
            )
        else:
            return jsonify(
                {
                    "status": "ok",
                    "partido_id": match["partido_id"],
                    "goles_local": gl,
                    "goles_visitante": gv,
                    "message": "Porra guardada. Podrás cambiarla una vez más.",
                }
            )
    finally:
        conn.close()


@bp.route("/api/porra/check-points", methods=["POST"])
def check_porra_points():
    """Check and award porra points for a jornada. Admin only."""
    user = session.get("user")
    if not user:
        return jsonify({"status": "error", "message": "No autorizado."}), 401

    # Check if user is admin
    from ..middleware.authz import is_admin_request

    if not is_admin_request():
        return jsonify({"status": "error", "message": "Solo admin puede verificar puntos de porra."}), 403

    data = request.get_json(silent=True) or {}
    jornada = data.get("jornada")
    if not jornada:
        return jsonify({"status": "error", "message": "Jornada requerida."}), 400

    try:
        jornada = int(jornada)
    except (TypeError, ValueError):
        return jsonify({"status": "error", "message": "Jornada invalida."}), 400

    conn = get_db()
    try:
        ensure_porra_table(conn)
        awarded = check_and_award_porra_points(conn, jornada)
        return jsonify(
            {
                "status": "ok",
                "jornada": jornada,
                "puntos_otorgados": awarded,
                "message": f"Se otorgaron {awarded} puntos de porra.",
            }
        )
    finally:
        conn.close()
