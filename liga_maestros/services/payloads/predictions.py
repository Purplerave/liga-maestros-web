"""Build predictions, La Pena consensus and ranking payloads."""

from ...scoring import score_prediction
from ...services.contest import CONTEST_DYNAMIC_START_JORNADA
from ...services.teams import (
    build_participant_contract,
    canonical_contest_id,
    is_live_scored_status,
    is_scored_status,
    prediction_source_priority,
)


def build_predictions_payload(conn, jornada, current_user_id=None, reveal_all=False):
    preds = _load_predictions(conn, jornada)
    participant_contract = build_participant_contract()
    consenso = _build_pena_consensus(preds, participant_contract)
    ranking = _build_ranking(conn, jornada)
    return {
        "predicciones_actuales": _filter_public_predictions(preds, participant_contract, current_user_id, reveal_all),
        "participant_contract": participant_contract,
        "consenso_pena": consenso,
        "ranking_maestros": ranking,
    }


def _load_predictions(conn, jornada):
    preds = {}
    rows = conn.execute(
        "SELECT user_id, partido_id, signo FROM predicciones WHERE jornada = ?",
        (jornada,),
    ).fetchall()
    for row in rows:
        uid = row["user_id"]
        preds.setdefault(uid, {"signos": ["-"] * 15})
        p_idx = row["partido_id"] - 1
        if 0 <= p_idx < 15:
            preds[uid]["signos"][p_idx] = row["signo"]
    return preds


def _build_pena_consensus(preds, participant_contract):
    visible_master_ids = {
        canonical_contest_id(column.get("id"))
        for column in participant_contract.get("visible_ai_columns", [])
    }
    visible_master_ids.update({
        canonical_contest_id(uid)
        for uid in participant_contract.get("hidden_ids", [])
    })
    visible_master_ids.update({"programa", "v260_omnisciente", "consejo_ias", "consenso"})

    pena_votes = {pid: {"1": 0, "X": 0, "2": 0} for pid in range(1, 15)}
    seen_pena_votes = set()
    for raw_uid, data in preds.items():
        uid = canonical_contest_id(raw_uid)
        if str(uid).lower() in visible_master_ids:
            continue
        for partido_id, raw_sign in enumerate(data.get("signos", []), start=1):
            if partido_id >= 15:
                continue
            sign = str(raw_sign or "").strip().upper()
            if sign not in ("1", "X", "2"):
                continue
            vote_key = (uid, partido_id)
            if vote_key in seen_pena_votes:
                continue
            seen_pena_votes.add(vote_key)
            pena_votes[partido_id][sign] += 1

    consenso = []
    for partido_id in range(1, 15):
        votes = pena_votes[partido_id]
        total = sum(votes.values())
        if not total:
            consenso.append({
                "id": partido_id,
                "ganador": "-",
                "p1": 0,
                "px": 0,
                "p2": 0,
                "total": 0,
                "votes": votes,
                "fuente": "pena",
            })
            continue

        p1 = round(votes["1"] * 100 / total)
        px = round(votes["X"] * 100 / total)
        p2 = round(votes["2"] * 100 / total)
        max_votes = max(votes.values())
        tied = [sign for sign in ("1", "X", "2") if votes[sign] == max_votes]
        consenso.append({
            "id": partido_id,
            "ganador": tied[0],
            "p1": p1,
            "px": px,
            "p2": p2,
            "total": total,
            "votes": votes,
            "fuente": "pena",
        })
    return consenso


def _official_prediction_ids(participant_contract):
    official = {
        canonical_contest_id(column.get("id"))
        for column in participant_contract.get("visible_ai_columns", [])
    }
    official.update({
        canonical_contest_id(uid)
        for uid in participant_contract.get("hidden_ids", [])
    })
    official.update({"programa", "v260_omnisciente", "consejo_ias", "consenso"})
    return {str(uid).lower() for uid in official if uid}


def _filter_public_predictions(preds, participant_contract, current_user_id=None, reveal_all=False):
    if reveal_all:
        return preds
    official_ids = _official_prediction_ids(participant_contract)
    current_user_text = str(current_user_id or "").strip()
    public_preds = {}
    for raw_uid, data in preds.items():
        canonical = canonical_contest_id(raw_uid)
        if str(canonical).lower() in official_ids or str(raw_uid) == current_user_text:
            public_preds[raw_uid] = data
    return public_preds


def _build_ranking(conn, jornada):
    final_res_map, current_res_map = _build_result_maps(conn, jornada)
    ranking = {}
    all_preds = conn.execute("""
        SELECT rowid AS pred_rowid, user_id, jornada, partido_id, signo
        FROM predicciones
        WHERE jornada >= ?
    """, (CONTEST_DYNAMIC_START_JORNADA,)).fetchall()

    seen_ranking_predictions = set()
    ordered_preds = sorted(
        all_preds,
        key=lambda p: (
            int(p["jornada"]),
            int(p["partido_id"]),
            prediction_source_priority(p["user_id"]),
            -int(p["pred_rowid"] or 0),
        ),
    )
    for pred in ordered_preds:
        uid = canonical_contest_id(pred["user_id"])
        pred_key = (uid, int(pred["jornada"]), int(pred["partido_id"]))
        if pred_key in seen_ranking_predictions:
            continue
        seen_ranking_predictions.add(pred_key)
        ranking.setdefault(uid, {"total": 0, "jornada": 0, "jornada_final": 0, "jornada_live": 0})

        key = (int(pred["jornada"]), int(pred["partido_id"]))
        final_real = final_res_map.get(key)
        current_real = current_res_map.get(key)
        if score_prediction(pred["partido_id"], pred["signo"], final_real):
            ranking[uid]["total"] += 1
            if str(pred["jornada"]) == str(jornada):
                ranking[uid]["jornada_final"] += 1
        if str(pred["jornada"]) == str(jornada) and score_prediction(pred["partido_id"], pred["signo"], current_real):
            ranking[uid]["jornada_live"] += 1

    for stats in ranking.values():
        stats["jornada"] = stats.get("jornada_live", 0)

    _apply_user_bonus_points(conn, ranking)
    return ranking


def _build_result_maps(conn, jornada):
    final_res_map = {}
    current_res_map = {}
    rows = conn.execute("""
        SELECT jornada, partido_id, signo_actual, goles_local, goles_visitante, status
        FROM resultados
        WHERE signo_actual IS NOT NULL AND signo_actual != '-'
    """).fetchall()
    for row in rows:
        status = row["status"]
        is_final = is_scored_status(status)
        is_live = is_live_scored_status(status)
        if not is_final and not is_live:
            continue
        real = row["signo_actual"]
        if int(row["partido_id"] or 0) == 15 and row["goles_local"] is not None and row["goles_visitante"] is not None:
            real = f"{int(row['goles_local'])}-{int(row['goles_visitante'])}"
        key = (int(row["jornada"]), int(row["partido_id"]))
        if is_final:
            final_res_map[key] = real
        if str(row["jornada"]) == str(jornada):
            current_res_map[key] = real
    return final_res_map, current_res_map


def _apply_user_bonus_points(conn, ranking):
    rows = conn.execute("SELECT id, puntos_acumulados FROM usuarios").fetchall()
    extra_points = {}
    for row in rows:
        uid = canonical_contest_id(row["id"])
        extra_points[uid] = max(int(extra_points.get(uid, 0) or 0), int(row["puntos_acumulados"] or 0))

    for uid, points in extra_points.items():
        if uid not in ranking:
            ranking[uid] = {"total": points, "bonus": points, "jornada": 0, "jornada_final": 0, "jornada_live": 0}
        else:
            ranking[uid]["bonus"] = points
            ranking[uid]["total"] += points
