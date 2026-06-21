import argparse
import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path

import utils


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "DATOS" / "LIGA_MAESTROS_PRO.db"
ROLES_PATH = BASE_DIR / "data" / "ECOSISTEMA_PARTICIPANTES.json"
LOGOS_PATH = BASE_DIR / "data" / "TEAM_LOGOS.json"
OUT_DIR = BASE_DIR / "data" / "auditorias"


def load_json(path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def canonical_id(uid):
    value = str(uid or "").strip()
    low = value.lower()
    aliases = {
        "v260_omnisciente": "programa",
        "consenso": "consejo_ias",
        "deepseek": "chipi",
    }
    return aliases.get(low, low)


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


def result_sign(row):
    gl = row["goles_local"]
    gv = row["goles_visitante"]
    if gl is None or gv is None:
        return str(row["signo_actual"] or "-").strip().upper() or "-"
    if int(row["partido_id"]) == 15:
        return pleno_score_key(f"{gl}-{gv}") or str(row["signo_actual"] or "-").strip().upper()
    if gl > gv:
        return "1"
    if gl < gv:
        return "2"
    return "X"


def score_prediction(partido_id, prediction, real):
    pred = str(prediction or "").strip().upper()
    real = str(real or "").strip().upper()
    if not pred or pred == "-" or not real or real == "-":
        return 0
    if int(partido_id) == 15:
        return int(pleno_score_key(pred) == pleno_score_key(real))
    return int(real in pred)


def is_finished(row):
    return str(row["status"] or "").upper() in {"FT", "FINISHED", "TERMINADO"}


def fetch_rows(conn, query, args=()):
    conn.row_factory = sqlite3.Row
    return [dict(row) for row in conn.execute(query, args).fetchall()]


def detect_jornada(conn, requested):
    if requested:
        return int(requested)
    row = conn.execute("SELECT MAX(jornada) AS jornada FROM resultados").fetchone()
    return int(row["jornada"]) if row and row["jornada"] is not None else 0


def build_audit(jornada):
    roles = load_json(ROLES_PATH, {})
    names = roles.get("nombres_publicos", {})
    official_masters = [canonical_id(uid) for uid in roles.get("maestros_oficiales", [])]
    pena_aliases = set(canonical_id(uid) for uid in roles.get("pena_aliases", []))
    obsolete_ids = set(canonical_id(uid) for uid in roles.get("ids_obsoletos", []))
    logos = utils.load_team_logos()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    jornada = detect_jornada(conn, jornada)

    results = fetch_rows(
        conn,
        """
        SELECT partido_id, local, visitante, goles_local, goles_visitante,
               signo_actual, status, fecha, hora, minuto
        FROM resultados
        WHERE jornada = ?
        ORDER BY partido_id
        """,
        (jornada,),
    )
    prediction_rows = fetch_rows(
        conn,
        "SELECT user_id, partido_id, signo FROM predicciones WHERE jornada = ? ORDER BY user_id, partido_id",
        (jornada,),
    )
    consensus_rows = fetch_rows(
        conn,
        "SELECT partido_id, ganador, p1, px, p2 FROM consenso WHERE jornada = ? ORDER BY partido_id",
        (jornada,),
    )
    users = {
        row["id"]: row["nombre"]
        for row in fetch_rows(conn, "SELECT id, nombre FROM usuarios")
    }
    conn.close()

    expected_ids = set(range(1, 16))
    preds_by_user = {}
    duplicate_predictions = []
    seen = set()
    for row in prediction_rows:
        uid = canonical_id(row["user_id"])
        key = (uid, int(row["partido_id"]))
        if key in seen:
            duplicate_predictions.append({"user_id": uid, "partido_id": int(row["partido_id"])})
        seen.add(key)
        preds_by_user.setdefault(uid, {})[int(row["partido_id"])] = str(row["signo"] or "-").strip().upper()

    prediction_status = {}
    for uid, signs in sorted(preds_by_user.items()):
        missing = sorted(expected_ids - set(signs.keys()))
        extra = sorted(set(signs.keys()) - expected_ids)
        prediction_status[uid] = {
            "name": names.get(uid) or users.get(uid) or uid,
            "count": len(signs),
            "missing": missing,
            "extra": extra,
            "role": (
                "programa" if uid == "programa"
                else "consejo" if uid == "consejo_ias"
                else "pena" if uid in pena_aliases
                else "obsoleto" if uid in obsolete_ids
                else "maestro" if uid in official_masters
                else "usuario"
            ),
        }

    result_ids = {int(row["partido_id"]) for row in results}
    missing_results = sorted(expected_ids - result_ids)
    finished_results = [row for row in results if is_finished(row)]
    live_results = [
        row for row in results
        if str(row["status"] or "").upper() in {"LIVE", "IN PLAY", "HT", "EN JUEGO"}
    ]
    scheduled_results = [
        row for row in results
        if str(row["status"] or "").upper() in {"NS", "SCHEDULED", "NOT STARTED", ""}
    ]

    scoreboard = {}
    real_by_match = {
        int(row["partido_id"]): result_sign(row)
        for row in finished_results
    }
    for uid, signs in preds_by_user.items():
        hits = 0
        played = 0
        misses = []
        for partido_id, real in real_by_match.items():
            if partido_id not in signs:
                misses.append(partido_id)
                continue
            played += 1
            hits += score_prediction(partido_id, signs[partido_id], real)
        scoreboard[uid] = {
            "name": names.get(uid) or users.get(uid) or uid,
            "hits": hits,
            "played": played,
            "missing_played": misses,
        }

    logo_missing = []
    for row in results:
        for side in ("local", "visitante"):
            name = row.get(side) or ""
            key = utils.normalize_team_key(name)
            if "FINALISTA" in key or not key:
                continue
            if key not in logos:
                logo_missing.append(name)

    pleno_warnings = []
    for uid, signs in preds_by_user.items():
        pleno = signs.get(15)
        if pleno and not pleno_score_key(pleno):
            pleno_warnings.append({"user_id": uid, "signo": pleno})

    def count_double_and_triples(signs):
        doubles = 0
        triples = []
        for partido_id in range(1, 15):
            sign = str(signs.get(partido_id, "-")).upper()
            chars = [ch for ch in "1X2" if ch in set(sign)]
            if len(chars) == 2:
                doubles += 1
            elif len(chars) > 2:
                triples.append(partido_id)
        return doubles, triples

    reference_doubles, _ = count_double_and_triples(
        preds_by_user.get("programa") or preds_by_user.get("consejo_ias") or {}
    )
    expected_pena_doubles = reference_doubles if reference_doubles else 2

    pena_budget_warnings = []
    for uid, status in prediction_status.items():
        if status["role"] != "pena":
            continue
        signs = preds_by_user.get(uid, {})
        doubles, triples = count_double_and_triples(signs)
        if triples:
            pena_budget_warnings.append(f"{status['name']} tiene triples en partidos {triples}.")
        if doubles != expected_pena_doubles:
            pena_budget_warnings.append(
                f"{status['name']} tiene {doubles} dobles; esperado {expected_pena_doubles}."
            )

    critical = []
    warnings = []
    if len(results) != 15:
        critical.append(f"La jornada {jornada} tiene {len(results)}/15 partidos cargados.")
    if missing_results:
        critical.append(f"Faltan partidos en resultados: {missing_results}.")
    for required in ("programa", "consejo_ias"):
        status = prediction_status.get(required)
        if not status:
            critical.append(f"Falta la columna obligatoria {names.get(required, required)}.")
        elif status["count"] != 15:
            critical.append(f"{status['name']} tiene {status['count']}/15 signos. Faltan: {status['missing']}.")
    for uid in official_masters:
        status = prediction_status.get(uid)
        if not status:
            warnings.append(f"No hay quiniela individual para {names.get(uid, uid)}.")
        elif status["count"] != 15:
            warnings.append(f"{status['name']} tiene {status['count']}/15 signos.")
    for uid, status in prediction_status.items():
        if status["role"] == "obsoleto":
            warnings.append(f"ID obsoleto todavia presente: {uid}.")
        if status["extra"]:
            warnings.append(f"{status['name']} tiene partidos fuera de 1-15: {status['extra']}.")
    if duplicate_predictions:
        warnings.append(f"Hay predicciones duplicadas: {duplicate_predictions}.")
    if pleno_warnings:
        warnings.append(f"Pleno con formato no Quiniela: {pleno_warnings}.")
    warnings.extend(pena_budget_warnings)
    if logo_missing:
        warnings.append(f"Escudos sin resolver: {sorted(set(logo_missing))}.")
    if len(consensus_rows) not in (0, 14, 15):
        warnings.append(f"La tabla consenso tiene {len(consensus_rows)} filas; esperado 14 o 15.")

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "jornada": jornada,
        "summary": {
            "partidos": len(results),
            "finalizados": len(finished_results),
            "directo": len(live_results),
            "pendientes": len(scheduled_results),
            "participantes_con_prediccion": len(preds_by_user),
            "consenso_rows": len(consensus_rows),
            "estado": "OK" if not critical else "REVISAR",
        },
        "critical": critical,
        "warnings": warnings,
        "prediction_status": prediction_status,
        "scoreboard": dict(sorted(
            scoreboard.items(),
            key=lambda item: (-item[1]["hits"], item[1]["name"].lower())
        )),
        "missing_logos": sorted(set(logo_missing)),
        "matches": results,
    }


def md_table(rows, headers):
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(h, "")) for h in headers) + " |")
    return "\n".join(lines)


def render_markdown(audit):
    status_rows = []
    for uid, status in sorted(audit["prediction_status"].items(), key=lambda item: (item[1]["role"], item[1]["name"])):
        status_rows.append({
            "Rol": status["role"],
            "ID": uid,
            "Nombre": status["name"],
            "Signos": f'{status["count"]}/15',
            "Faltan": ", ".join(map(str, status["missing"])) or "-",
        })

    score_rows = []
    for uid, score in audit["scoreboard"].items():
        if score["played"] == 0:
            continue
        score_rows.append({
            "ID": uid,
            "Nombre": score["name"],
            "Aciertos": f'{score["hits"]}/{score["played"]}',
            "Sin signo en jugados": ", ".join(map(str, score["missing_played"])) or "-",
        })

    match_rows = []
    for row in audit["matches"]:
        score = "-"
        if row["goles_local"] is not None and row["goles_visitante"] is not None:
            score = f'{row["goles_local"]}-{row["goles_visitante"]}'
        match_rows.append({
            "#": row["partido_id"],
            "Partido": f'{row["local"]} - {row["visitante"]}',
            "Hora": f'{row["fecha"]} {row["hora"]}',
            "Estado": row["status"] or "-",
            "Resultado": score,
            "Signo": result_sign(row),
        })

    lines = [
        f"# Auditoria Jornada {audit['jornada']}",
        "",
        f"Generado: {audit['generated_at']}",
        "",
        f"Estado: **{audit['summary']['estado']}**",
        "",
        "## Resumen",
        "",
        md_table([{
            "Partidos": audit["summary"]["partidos"],
            "Finalizados": audit["summary"]["finalizados"],
            "Directo": audit["summary"]["directo"],
            "Pendientes": audit["summary"]["pendientes"],
            "Participantes": audit["summary"]["participantes_con_prediccion"],
            "Consenso": audit["summary"]["consenso_rows"],
        }], ["Partidos", "Finalizados", "Directo", "Pendientes", "Participantes", "Consenso"]),
        "",
        "## Critico",
        "",
        "\n".join(f"- {item}" for item in audit["critical"]) if audit["critical"] else "- Sin bloqueos.",
        "",
        "## Avisos",
        "",
        "\n".join(f"- {item}" for item in audit["warnings"]) if audit["warnings"] else "- Sin avisos.",
        "",
        "## Predicciones",
        "",
        md_table(status_rows, ["Rol", "ID", "Nombre", "Signos", "Faltan"]),
        "",
        "## Aciertos Con Resultados Cerrados",
        "",
        md_table(score_rows, ["ID", "Nombre", "Aciertos", "Sin signo en jugados"]) if score_rows else "- Aun no hay partidos cerrados puntuables.",
        "",
        "## Partidos",
        "",
        md_table(match_rows, ["#", "Partido", "Hora", "Estado", "Resultado", "Signo"]),
        "",
    ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Audita una jornada de Liga de Maestros.")
    parser.add_argument("--jornada", "-j", type=int, default=None, help="Jornada a auditar. Por defecto, la maxima.")
    args = parser.parse_args()

    audit = build_audit(args.jornada)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = OUT_DIR / f"J{audit['jornada']}_estado.json"
    md_path = OUT_DIR / f"J{audit['jornada']}_estado.md"
    json_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(audit), encoding="utf-8")

    print(f"Jornada {audit['jornada']}: {audit['summary']['estado']}")
    print(f"Markdown: {md_path}")
    print(f"JSON: {json_path}")
    if audit["critical"]:
        print("Critico:")
        for item in audit["critical"]:
            print(f" - {item}")
    if audit["warnings"]:
        print("Avisos:")
        for item in audit["warnings"]:
            print(f" - {item}")


if __name__ == "__main__":
    main()
