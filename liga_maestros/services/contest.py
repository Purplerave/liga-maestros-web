"""Contest engine: ranking, profiles, streaks, awards."""
import threading
from datetime import datetime

import config
from ..db.connection import get_db
from ..scoring import score_prediction
from .teams import canonical_contest_id, public_contest_name, is_scored_status, is_live_scored_status

CONTEST_DYNAMIC_START_JORNADA = 58
Q15_EXPECTED_MATCHES = 15

_contest_cache_lock = threading.Lock()
_contest_payload_cache = {}


def contest_month_key(date_text):
    raw = str(date_text or "").strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(raw[:10], fmt).strftime("%Y-%m")
        except Exception:
            continue
    return raw[:7] if raw else "sin-mes"


def contest_cache_signature():
    conn = get_db()
    pred = conn.execute("""
        SELECT COUNT(*) AS n, COALESCE(MAX(rowid), 0) AS max_rowid
        FROM predicciones WHERE jornada >= ?
    """, (CONTEST_DYNAMIC_START_JORNADA,)).fetchone()
    results = conn.execute("""
        SELECT COUNT(*) AS n, COALESCE(MAX(rowid), 0) AS max_rowid,
            COALESCE(SUM(COALESCE(goles_local, -99) * 31 + COALESCE(goles_visitante, -99) * 17), 0) AS goals_sig,
            COALESCE(SUM(LENGTH(COALESCE(status, '')) + LENGTH(COALESCE(signo_actual, ''))), 0) AS state_sig
        FROM resultados
    """).fetchone()
    users = conn.execute("""
        SELECT COUNT(*) AS n, COALESCE(MAX(rowid), 0) AS max_rowid,
            COALESCE(SUM(COALESCE(puntos_acumulados, 0)), 0) AS points_sig
        FROM usuarios
    """).fetchone()
    return (
        int(pred["n"] or 0), int(pred["max_rowid"] or 0),
        int(results["n"] or 0), int(results["max_rowid"] or 0),
        int(results["goals_sig"] or 0), int(results["state_sig"] or 0),
        int(users["n"] or 0), int(users["max_rowid"] or 0), int(users["points_sig"] or 0),
    )


def build_contest_payload(current_jornada=None, current_user_id=None):
    signature = contest_cache_signature()
    key = (str(current_jornada or ""), canonical_contest_id(current_user_id or ""), signature)
    with _contest_cache_lock:
        cached = _contest_payload_cache.get(key)
        if cached:
            return cached

    payload = _build_contest_payload_uncached(current_jornada, current_user_id)
    with _contest_cache_lock:
        _contest_payload_cache[key] = payload
        if len(_contest_payload_cache) > 64:
            for old_key in list(_contest_payload_cache.keys())[:16]:
                _contest_payload_cache.pop(old_key, None)
    return payload


def _build_contest_payload_uncached(current_jornada=None, current_user_id=None):
    hidden_ids = {"hermes", "molbot", "jenova", "pena", "consenso", "momo", "manu", "manus"}
    conn = get_db()
    user_rows = conn.execute("SELECT id, nombre, puntos_acumulados FROM usuarios").fetchall()
    users = {row["id"]: row["nombre"] for row in user_rows}
    extra_points = {}
    for row in user_rows:
        uid = canonical_contest_id(row["id"])
        extra_points[uid] = max(int(extra_points.get(uid, 0) or 0), int(row["puntos_acumulados"] or 0))

    result_rows = conn.execute("""
        SELECT jornada, partido_id, local, visitante, signo_actual, goles_local, goles_visitante, fecha, status
        FROM resultados WHERE signo_actual IS NOT NULL AND signo_actual != '-'
    """).fetchall()
    results = {}
    jornada_dates = {}
    match_labels = {}
    for row in result_rows:
        if not is_scored_status(row["status"]):
            continue
        jornada = int(row["jornada"])
        partido_id = int(row["partido_id"])
        key = (jornada, partido_id)
        real = row["signo_actual"]
        if partido_id == 15 and row["goles_local"] is not None and row["goles_visitante"] is not None:
            real = f"{int(row['goles_local'])}-{int(row['goles_visitante'])}"
        results[key] = real
        jornada_dates.setdefault(jornada, str(row["fecha"] or "")[:10])
        match_labels[key] = {"local": row["local"] or "", "visitante": row["visitante"] or ""}

    pred_rows = conn.execute("""
        SELECT rowid AS pred_rowid, user_id, jornada, partido_id, signo
        FROM predicciones WHERE jornada >= ?
    """, (CONTEST_DYNAMIC_START_JORNADA,)).fetchall()

    totals = {}
    raw_hits = {}
    evaluated_predictions = {}
    played = {}
    jornada_scores = {}
    monthly_scores = {}
    ballots = {}
    seen_predictions = set()
    ordered_pred_rows = sorted(
        pred_rows,
        key=lambda pred: (
            int(pred["jornada"]), int(pred["partido_id"]),
            _prediction_source_priority(pred["user_id"]),
            -int(pred["pred_rowid"] or 0),
        )
    )
    for pred in ordered_pred_rows:
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
            # Si no hay resultado, registrar la predicción pero sin puntos
            jornada_scores.setdefault(jornada, {})
            if uid not in jornada_scores[jornada]:
                jornada_scores[jornada][uid] = 0
            continue
        hit = score_prediction(partido_id, pred["signo"], real)
        evaluated_predictions[uid] = evaluated_predictions.get(uid, 0) + 1
        raw_hits[uid] = raw_hits.get(uid, 0) + hit
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

    def streak_metrics(items, threshold=8):
        ordered = sorted(items, key=lambda item: int(item["jornada"]))
        current = 0
        for item in reversed(ordered):
            if int(item["points"] or 0) >= threshold:
                current += 1
            else:
                break
        best = 0
        run = 0
        improving = 0
        previous = None
        for item in ordered:
            points = int(item["points"] or 0)
            if points >= threshold:
                run += 1
                best = max(best, run)
            else:
                run = 0
            if previous is not None and points > previous:
                improving += 1
            elif previous is not None:
                improving = 0
            previous = points
        return {"threshold": threshold, "current": current, "best": best, "improving": improving}

    def peer_average_for(jornada, exclude_uid=None):
        scores = [
            int(score or 0)
            for peer_uid, score in jornada_scores.get(jornada, {}).items()
            if peer_uid != exclude_uid and peer_uid.lower() not in hidden_ids
        ]
        return round(sum(scores) / len(scores), 2) if scores else None

    def rivalry_rows(uid, my_jornadas, limit=8):
        if not uid or not my_jornadas:
            return []
        recent_jornadas = [int(item["jornada"]) for item in sorted(my_jornadas, key=lambda item: int(item["jornada"]))[-5:]]
        peers = sorted({
            peer_uid
            for jornada in recent_jornadas
            for peer_uid in jornada_scores.get(jornada, {}).keys()
            if peer_uid != uid and peer_uid.lower() not in hidden_ids
        })
        rows = []
        for peer_uid in peers:
            wins = losses = draws = diff = common = 0
            for jornada in recent_jornadas:
                scores = jornada_scores.get(jornada, {})
                if uid not in scores or peer_uid not in scores:
                    continue
                common += 1
                mine_points = int(scores.get(uid, 0) or 0)
                peer_points = int(scores.get(peer_uid, 0) or 0)
                diff += mine_points - peer_points
                if mine_points > peer_points:
                    wins += 1
                elif mine_points < peer_points:
                    losses += 1
                else:
                    draws += 1
            if not common:
                continue
            rows.append({
                "id": peer_uid, "name": public_contest_name(peer_uid, users),
                "wins": wins, "losses": losses, "draws": draws, "diff": diff, "common": common,
            })
        rows.sort(key=lambda item: (-(item["wins"] - item["losses"]), -item["diff"], item["name"]))
        return rows[:limit]

    def build_jornada_moments(jornada, limit=3):
        moments = []
        for partido_id in range(1, Q15_EXPECTED_MATCHES + 1):
            real = results.get((jornada, partido_id))
            if not real:
                continue
            picks = []
            for (uid, ballot_jornada), signs in ballots.items():
                if ballot_jornada != jornada or uid.lower() in hidden_ids:
                    continue
                sign = signs.get(partido_id)
                if sign and sign != "-":
                    picks.append((uid, sign))
            if len(picks) < 3:
                continue
            hitters = [uid for uid, sign in picks if score_prediction(partido_id, sign, real) > 0]
            if not hitters:
                continue
            rarity = len(hitters) / len(picks)
            if rarity > 0.34 and len(hitters) > 2:
                continue
            label = match_labels.get((jornada, partido_id), {})
            moments.append({
                "jornada": jornada, "partido_id": partido_id,
                "match": f"{label.get('local') or 'Local'} - {label.get('visitante') or 'Visitante'}",
                "real": real,
                "hitters": [public_contest_name(hit_uid, users) for hit_uid in hitters[:4]],
                "hit_count": len(hitters), "pool": len(picks),
                "rarity": round(rarity * 100, 1),
            })
        moments.sort(key=lambda item: (item["hit_count"], -item["pool"], item["partido_id"]))
        return moments[:limit]

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
            ticket = [ballot.get(i, "-") for i in range(1, Q15_EXPECTED_MATCHES + 1)]
            my_jornadas.append({
                "jornada": jornada, "ticket": ticket, "points": found["points"],
                "pos": found["pos"], "pena_avg": peer_average_for(jornada, uid),
            })
        total_predictions = int(evaluated_predictions.get(uid, 0))
        total_hits = int(raw_hits.get(uid, 0))
        total_points = int(mine["points"] if mine else 0)
        bonus_points = int(extra_points.get(uid, 0) or 0)
        peer_rows = [row for row in user_rows_rank if row["id"] != uid]
        peer_avg_points = round(sum(row["points"] for row in peer_rows) / len(peer_rows), 2) if peer_rows else 0
        above_peers = sum(1 for row in peer_rows if total_points > row["points"])
        below_peers = sum(1 for row in peer_rows if total_points < row["points"])
        profile_name = public_contest_name(uid, users)
        profile_awards = []
        for jornada in sorted(jornada_scores.keys(), reverse=True):
            rows = rows_from_scores(jornada_scores[jornada])
            if rows and any(row["id"] == uid and row["points"] == rows[0]["points"] for row in rows):
                profile_awards.append({
                    "jornada": jornada, "winner": public_contest_name(uid, users),
                    "points": rows[0]["points"], "date": jornada_dates.get(jornada, ""),
                })
        return {
            "id": uid, "name": profile_name, "position": mine["pos"] if mine else None,
            "played": len(my_jornadas), "predictions": total_predictions, "hits": total_hits,
            "points": total_points, "bonus": bonus_points,
            "hit_rate": round((total_hits / total_predictions) * 100, 2) if total_predictions else 0,
            "hits_per_jornada": round(total_hits / len(my_jornadas), 2) if my_jornadas else 0,
            "best_position": min((row["pos"] for row in my_jornadas), default=None),
            "streak": streak_metrics(my_jornadas),
            "vs_pena": {
                "average_points": peer_avg_points,
                "diff": round(total_points - peer_avg_points, 2),
                "ahead_of": above_peers, "behind": below_peers, "pool": len(peer_rows),
            },
            "rivalries": rivalry_rows(uid, my_jornadas),
            "results": my_jornadas[-24:],
            "awards": profile_awards[:20],
        }

    general = rows_from_scores(totals)
    # Si hay jornada solicitada, usarla; si no tiene scores, usar la última CON datos
    if current_jornada:
        requested = int(current_jornada)
        # Si la jornada solicitada tiene scores, usarla
        if requested in jornada_scores and jornada_scores[requested]:
            selected_jornada = requested
        # Si no tiene scores pero tiene predicciones, usarla (mostrar predicciones pendientes)
        elif jornada_scores:
            selected_jornada = max(jornada_scores.keys())
        else:
            selected_jornada = requested
    elif jornada_scores:
        selected_jornada = max(jornada_scores.keys())
    else:
        selected_jornada = 0
    jornada_rows = rows_from_scores(jornada_scores.get(selected_jornada, {}))
    latest_month = sorted(monthly_scores.keys())[-1] if monthly_scores else ""
    monthly_rows = rows_from_scores(monthly_scores.get(latest_month, {}))

    galardones_jornada = []
    for jornada in sorted(jornada_scores.keys(), reverse=True):
        rows = rows_from_scores(jornada_scores[jornada])
        if not rows:
            continue
        top_score = rows[0]["points"]
        winners = [row for row in rows if row["points"] == top_score]
        galardones_jornada.append({
            "jornada": jornada,
            "winner": ", ".join(row["name"] for row in winners),
            "winners": winners, "tie_count": len(winners),
            "points": top_score, "date": jornada_dates.get(jornada, ""),
        })

    galardones_mes = []
    for month in sorted(monthly_scores.keys(), reverse=True):
        rows = rows_from_scores(monthly_scores[month])
        if rows:
            top_score = rows[0]["points"]
            winners = [row for row in rows if row["points"] == top_score]
            galardones_mes.append({
                "month": month,
                "winner": ", ".join(row["name"] for row in winners),
                "winners": winners, "tie_count": len(winners), "points": top_score,
            })

    profile = profile_for(current_user_id) if current_user_id else None

    return {
        "general": general,
        "jornada": {"jornada": selected_jornada, "rows": jornada_rows},
        "monthly": {"month": latest_month, "rows": monthly_rows},
        "moments": build_jornada_moments(selected_jornada),
        "galardones": {"jornadas": galardones_jornada, "meses": galardones_mes},
        "profile": profile,
    }


def _prediction_source_priority(uid):
    low = str(uid or "").strip().lower()
    if low == "programa":
        return 0
    if low == "v260_omnisciente":
        return 1
    if low == "chipi":
        return 0
    if low == "deepseek":
        return 1
    canonical = canonical_contest_id(low)
    return 0 if low == canonical else 1
