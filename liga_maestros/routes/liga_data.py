"""Liga data route: the main data endpoint."""
import os, re, json
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, session

import config
from ..db.connection import get_db
from ..utils import (
    normalize_team_key, load_team_logos, build_team_contract,
    load_standings_override, parse_score_text, parse_any_match_datetime,
)
from ..services.teams import (
    build_participant_contract, canonical_contest_id, prediction_source_priority,
    is_scored_status, is_live_scored_status,
)
from ..services.contest import CONTEST_DYNAMIC_START_JORNADA
from ..services.ticket import (
    compute_ticket_close_info, load_match_info_for_jornada, madrid_now, today_madrid,
)
from ..services.highlightly import resolve_jornada
from ..scoring import score_prediction

bp = Blueprint("liga_data", __name__)

MAX_DOBLES_PER_TICKET = int(os.getenv("MAX_DOBLES_PER_TICKET", "14"))
MAX_TRIPLES_PER_TICKET = int(os.getenv("MAX_TRIPLES_PER_TICKET", "14"))
GOOGLE_AUTH_ENABLED = bool(os.getenv("GOOGLE_CLIENT_ID") and os.getenv("GOOGLE_CLIENT_SECRET"))


def _is_admin_request():
    from flask import session, request as req
    user = session.get("user") or {}
    email = str(user.get("email") or "").strip().lower()
    allow_local = os.getenv("ALLOW_LOCAL_ADMIN", "0").strip().lower() in ("1", "true", "yes", "on")
    is_local = req.remote_addr in ("127.0.0.1", "::1", "localhost")
    admin_emails = {e.strip().lower() for e in os.getenv("ADMIN_EMAILS", "").split(",") if e.strip()}
    return (allow_local and is_local) or (email and email in admin_emails)


@bp.route('/api/liga/data')
def get_liga_data():
    j = request.args.get('j', '')
    conn = get_db()
    team_logos = load_team_logos()

    def logo_for(team_name):
        return team_logos.get(normalize_team_key(team_name), "")

    max_j_row = conn.execute("SELECT MAX(jornada) FROM resultados").fetchone()
    if not max_j_row or max_j_row[0] is None:
        conn.close()
        return jsonify({"status": "error", "message": "No hay jornadas cargadas en resultados"}), 404
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
            if r.get("fecha") == today_madrid():
                marcador = f"{hora_label}h" if hora_label else "Horario pendiente"
            else:
                marcador = f"{fecha_limpia} {hora_label}h".strip() if hora_label else (fecha_limpia or "Horario pendiente")
        else:
            minuto_num = ""
            marcador_base = f"{gh}-{ga}" if gh is not None and ga is not None else ""
            marcador = f"{gh}-{ga}" if gh is not None and ga is not None else "-:-"

        partidos.append({
            "id": p_id, "local": r["local"], "visitante": r["visitante"],
            "logo_local": logo_for(r["local"]), "logo_visitante": logo_for(r["visitante"]),
            "marcador": marcador, "status": status, "marcador_base": marcador_base,
            "minuto_live": minuto_num, "fecha_raw": r.get("fecha", ""),
            "hora": r.get("hora", "-"), "signo_actual": signo,
            "goles_local": gh, "goles_visitante": ga,
        })

    partidos_by_id = {}
    for partido in partidos:
        try:
            partidos_by_id[int(partido.get("id"))] = partido
        except (TypeError, ValueError):
            continue
    partidos = [
        partidos_by_id.get(i, {
            "id": i, "local": "-", "visitante": "-", "logo_local": "", "logo_visitante": "",
            "marcador": "Pendiente", "status": "NS", "marcador_base": "", "minuto_live": "",
            "fecha_raw": "", "hora": "-", "signo_actual": "-", "goles_local": None, "goles_visitante": None,
        })
        for i in range(1, 16)
    ]

    standings_raw = conn.execute("SELECT * FROM clasificacion ORDER BY pos ASC").fetchall()
    standings = {"primera": [], "segunda": []}
    standings_db = {"primera": {}, "segunda": {}}
    for s in standings_raw:
        cat = "primera" if s['division'] == 1 else "segunda"
        item = {
            "n": s['equipo'], "pj": s['pj'], "pts": s['pts'], "pos": s['pos'],
            "pg": s['pg'], "pe": s['pe'], "pp": s['pp'], "gf": s['gf'], "gc": s['gc'],
            "racha": s["racha"] if "racha" in s.keys() else "", "source": "db",
        }
        standings_db[cat][normalize_team_key(s['equipo'])] = item
        standings[cat].append(item)

    standings_override = load_standings_override()
    if standings_override:
        for cat in ("primera", "segunda"):
            official_rows = []
            for item in standings_override.get(cat, []):
                official_rows.append({
                    "n": item.get("n"), "pj": item.get("pj", 0), "pts": item.get("pts", 0),
                    "pos": item.get("pos", 0), "pg": item.get("pg"), "pe": item.get("pe"),
                    "pp": item.get("pp"), "gf": item.get("gf"), "gc": item.get("gc"),
                    "racha": item.get("racha", ""), "base_oficial": True, "source": "official",
                })
            if official_rows:
                standings[cat] = official_rows

    def _apply_finished(standings_data, matches):
        category_by_key = {}
        row_by_key = {}
        for cat, rows in standings_data.items():
            for row in rows:
                key = normalize_team_key(row.get("n"))
                if key:
                    category_by_key[key] = cat
                    row_by_key[key] = row
        max_pj = {"primera": 38, "segunda": 42}
        for match in matches:
            if str(match.get("status") or "").upper() not in ("FT", "FINISHED", "TERMINADO"):
                continue
            home_key = normalize_team_key(match.get("local"))
            away_key = normalize_team_key(match.get("visitante"))
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
                gh, ga = parse_score_text(match.get("marcador_base") or match.get("marcador"))
            if gh is None or ga is None:
                continue

            def _add(row, gf, gc, points, result_key):
                row["pj"] = int(row.get("pj") or 0) + 1
                row["gf"] = int(row.get("gf") or 0) + int(gf)
                row["gc"] = int(row.get("gc") or 0) + int(gc)
                row["pts"] = int(row.get("pts") or 0) + int(points)
                row[result_key] = int(row.get(result_key) or 0) + 1

            if int(gh) > int(ga):
                _add(home, gh, ga, 3, "pg"); _add(away, ga, gh, 0, "pp")
            elif int(gh) < int(ga):
                _add(home, gh, ga, 0, "pp"); _add(away, ga, gh, 3, "pg")
            else:
                _add(home, gh, ga, 1, "pe"); _add(away, ga, gh, 1, "pe")
        for cat, rows in standings_data.items():
            rows.sort(key=lambda row: (-int(row.get("pts") or 0), -(int(row.get("gf") or 0) - int(row.get("gc") or 0)), -int(row.get("gf") or 0), str(row.get("n") or "")))
            for idx, row in enumerate(rows, start=1):
                row["pos"] = idx

    _apply_finished(standings, partidos)

    preds = {}
    preds_raw = conn.execute("SELECT user_id, partido_id, signo FROM predicciones WHERE jornada = ?", (j,)).fetchall()
    for p in preds_raw:
        uid = p['user_id']
        if uid not in preds: preds[uid] = {"signos": ["-"] * 15}
        p_idx = p['partido_id'] - 1
        if 0 <= p_idx < 15:
            preds[uid]["signos"][p_idx] = p['signo']

    participant_contract = build_participant_contract()
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
                "id": partido_id, "ganador": "-", "p1": 0, "px": 0, "p2": 0,
                "total": 0, "votes": votes, "fuente": "pena",
            })
            continue
        p1 = round(votes["1"] * 100 / total)
        px = round(votes["X"] * 100 / total)
        p2 = round(votes["2"] * 100 / total)
        max_votes = max(votes.values())
        tied = [sign for sign in ("1", "X", "2") if votes[sign] == max_votes]
        winner = tied[0]
        consenso.append({
            "id": partido_id, "ganador": winner, "p1": p1, "px": px, "p2": p2,
            "total": total, "votes": votes, "fuente": "pena",
        })

    final_res_map = {}
    current_res_map = {}
    all_res = conn.execute("""
        SELECT jornada, partido_id, signo_actual, goles_local, goles_visitante, status
        FROM resultados WHERE signo_actual IS NOT NULL AND signo_actual != '-'
    """).fetchall()
    for r in all_res:
        status = r["status"]
        is_final = is_scored_status(status)
        is_live = is_live_scored_status(status)
        if not is_final and not is_live:
            continue
        real = r['signo_actual']
        if int(r['partido_id'] or 0) == 15 and r['goles_local'] is not None and r['goles_visitante'] is not None:
            real = f"{int(r['goles_local'])}-{int(r['goles_visitante'])}"
        key = (int(r['jornada']), int(r['partido_id']))
        if is_final:
            final_res_map[key] = real
        if str(r['jornada']) == str(j):
            current_res_map[key] = real

    ranking = {}
    all_preds = conn.execute("""
        SELECT rowid AS pred_rowid, user_id, jornada, partido_id, signo
        FROM predicciones WHERE jornada >= ?
    """, (CONTEST_DYNAMIC_START_JORNADA,)).fetchall()
    seen_ranking_predictions = set()
    ordered_preds = sorted(all_preds, key=lambda p: (int(p["jornada"]), int(p["partido_id"]), prediction_source_priority(p["user_id"]), -int(p["pred_rowid"] or 0)))
    for p in ordered_preds:
        uid = canonical_contest_id(p['user_id'])
        pred_key = (uid, int(p['jornada']), int(p['partido_id']))
        if pred_key in seen_ranking_predictions:
            continue
        seen_ranking_predictions.add(pred_key)
        if uid not in ranking:
            ranking[uid] = {"total": 0, "jornada": 0, "jornada_final": 0, "jornada_live": 0}
        key = (int(p['jornada']), int(p['partido_id']))
        final_real = final_res_map.get(key)
        current_real = current_res_map.get(key)
        if score_prediction(p['partido_id'], p['signo'], final_real):
            ranking[uid]["total"] += 1
            if str(p['jornada']) == str(j):
                ranking[uid]["jornada_final"] += 1
        if str(p['jornada']) == str(j) and score_prediction(p['partido_id'], p['signo'], current_real):
            ranking[uid]["jornada_live"] += 1

    for stats in ranking.values():
        stats["jornada"] = stats.get("jornada_live", 0)

    extra_users = conn.execute("SELECT id, puntos_acumulados FROM usuarios").fetchall()
    extra_points = {}
    for u in extra_users:
        uid = canonical_contest_id(u['id'])
        extra_points[uid] = max(int(extra_points.get(uid, 0) or 0), int(u['puntos_acumulados'] or 0))
    for uid, points in extra_points.items():
        if uid not in ranking:
            ranking[uid] = {"total": points, "bonus": points, "jornada": 0, "jornada_final": 0, "jornada_live": 0}
        else:
            ranking[uid]["bonus"] = points
            ranking[uid]["total"] += points

    jornada_liga_detectada = ""
    try:
        liga_row = conn.execute("SELECT AVG(pj) as avg_pj FROM clasificacion WHERE division = 1").fetchone()
        if liga_row and liga_row["avg_pj"] is not None:
            jornada_liga_detectada = str(int(round(liga_row["avg_pj"])))
    except Exception:
        jornada_liga_detectada = ""

    all_league_matches = []
    candidate_match_paths = [
        os.path.join(config.DATA_DIR, "LIVE_ALL_MATCHES_V3.json"),
        os.path.join(config.BASE_DIR, "LIVE_ALL_MATCHES_V3.json"),
        os.path.abspath(os.path.join(config.BASE_DIR, "..", "AUDITORIA", "data", "LIVE_ALL_MATCHES_V3.json")),
        os.path.join(config.DATA_DIR, "LIVE_ALL_MATCHES.json"),
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

    def infer_match_competition(match):
        home_key = normalize_team_key(match.get("local"))
        away_key = normalize_team_key(match.get("visitante"))
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
                "id": f"quiniela-{j}-{m['id']}", "fixture_id": f"quiniela-{j}-{m['id']}",
                "competition_name": comp, "competition": {"name": comp},
                "local": m["local"], "visitante": m["visitante"],
                "home": {"name": m["local"]}, "away": {"name": m["visitante"]},
                "home_logo": m.get("logo_local", ""), "away_logo": m.get("logo_visitante", ""),
                "status": m["status"], "time": m.get("minuto") or "",
                "score": m["marcador"] if m["status"] not in ("NS", "SCHEDULED") else "",
                "marcador": m["marcador"], "added": f"{fecha} {hora}".strip(),
                "scheduled": hora, "fecha_raw": fecha, "hora": hora,
            })

    quiniela_pairs = {(normalize_team_key(m.get("local")), normalize_team_key(m.get("visitante"))) for m in quiniela_league_matches}
    quiniela_datetimes = [dt for dt in (parse_any_match_datetime(m) for m in quiniela_league_matches) if dt]
    if quiniela_datetimes:
        window_start = min(quiniela_datetimes) - timedelta(days=1)
        window_end = max(quiniela_datetimes) + timedelta(days=1)
        today_str = today_madrid()

        def keep_external_match(match):
            dt = parse_any_match_datetime(match)
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
            and (normalize_team_key(m.get("local") or m.get("home_name") or (m.get("home") or {}).get("name")), normalize_team_key(m.get("visitante") or m.get("away_name") or (m.get("away") or {}).get("name"))) in quiniela_pairs
        )
    ]
    all_league_matches = quiniela_league_matches + all_league_matches
    for m in all_league_matches:
        home_name = m.get("local") or m.get("home_name") or (m.get("home") or {}).get("name")
        away_name = m.get("visitante") or m.get("away_name") or (m.get("away") or {}).get("name")
        m["home_logo"] = m.get("home_logo") or (m.get("home") or {}).get("logo") or logo_for(home_name)
        m["away_logo"] = m.get("away_logo") or (m.get("away") or {}).get("logo") or logo_for(away_name)

    close_info = compute_ticket_close_info(partidos, source=f"api_liga_data_j{j}")
    first_kickoff = close_info["first_kickoff"]
    close_at = close_info["close_at"]
    first_kickoff_started = bool(close_at and madrid_now() >= close_at)
    is_locked = first_kickoff_started or any((m.get('status') or '') in ('LIVE', 'FT', 'FINISHED') for m in partidos)
    match_info = load_match_info_for_jornada(j)
    for match in partidos:
        info = match_info.get(str(match.get("id")))
        if not info:
            continue
        detail = info.get("detalle") or ""
        if "Hypermotion" in detail:
            detail = detail.replace("6º Hypermotion", match.get("local") or "Local").replace("3º Hypermotion", match.get("visitante") or "Visitante").replace("5º Hypermotion", match.get("local") or "Local").replace("4º Hypermotion", match.get("visitante") or "Visitante")
            info["detalle"] = detail

    conn.close()
    return jsonify({
        "jornada": j, "jornada_liga": jornada_liga_detectada, "max_jornada": max_jornada,
        "today_madrid": today_madrid(), "is_locked": is_locked,
        "edit_deadline": close_at.strftime("%Y-%m-%d %H:%M") if close_at else "",
        "kickoff_at": first_kickoff.strftime("%Y-%m-%d %H:%M") if first_kickoff else "",
        "partidos": partidos, "all_league_matches": all_league_matches, "standings": standings,
        "team_logos": team_logos, "team_contract": build_team_contract(),
        "participant_contract": participant_contract, "match_info": match_info,
        "predicciones_actuales": preds, "consenso_pena": consenso, "ranking_maestros": ranking,
        "auth_enabled": GOOGLE_AUTH_ENABLED, "is_admin": _is_admin_request(),
        "ticket_policy": {"max_dobles": MAX_DOBLES_PER_TICKET, "max_triples": MAX_TRIPLES_PER_TICKET},
    })
