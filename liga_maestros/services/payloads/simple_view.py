"""Vista simple por columnas de la portada y clasificación de la competición.

Una fila por casilla, con la composición histórica o los participantes reales
de la jornada abierta y aciertos/fallos decididos en el servidor. La regla de puntuacion vive
UNA sola vez, en ``liga_maestros/scoring.py``: aqui se llama a
``score_prediction`` y el frontend solo pinta el resultado, para que un doble
o el pleno no se puedan llegar a contar distinto en JS y en el ranking.

Los resultados salen de los mismos partidos que pinta el resto de la pagina
(misma tabla ``resultados`` que leen ``_raw_match_statuses`` y
``build_jornada_matches``). Sin marcador verificado no hay resultado: la fila
queda pendiente y jamas se rellena a mano.
"""

import json
import os

import config

from ...scoring import normalize_prediction_sign, score_prediction
from ...services.teams import (
    canonical_contest_id,
    is_live_scored_status,
    is_scored_status,
    public_contest_name,
    signo_desde_goles,
)

# La J17 es histórica: se conserva el elenco que jugó esa jornada. Desde la
# J19, las personas conservan su propia identidad (MrPurple y Sonia) y el
# Programa sigue siendo una columna separada. Las columnas sin línea real se
# ocultan, salvo Programa, que permanece visible como referencia.
HISTORICAL_COLUMNS = ("mrpurple", "programa", "tecnotron", "grok", "sonia")
CURRENT_MASTER_COLUMNS = (
    "mrpurple",
    "sonia",
    "programa",
    "tecnotron",
    "grok",
    "gemini",
    "chatgpt",
    "copilot",
    "meta_ai",
)


def _load_ticket_scrape(jornada):
    """Registro versionado del boleto (fixture y metadatos) de una jornada.

    La vista lee los metadatos versionados para cada jornada. Sin importe de
    bote confirmado, no se muestra.
    """
    name = f"quiniela15_J{int(jornada)}_scrape.json"
    for base_dir in (getattr(config, "SEED_DATA_DIR", ""), getattr(config, "DATA_DIR", ""), config.BASE_DIR):
        if not base_dir:
            continue
        path = os.path.join(base_dir, "data", name) if base_dir == config.BASE_DIR else os.path.join(base_dir, name)
        if not os.path.exists(path):
            continue
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError, TypeError):
            continue
        if int(data.get("jornada") or 0) != int(jornada):
            continue
        return data
    return {}


def load_ticket_metadata(jornada):
    data = _load_ticket_scrape(jornada)
    boleto = data.get("boleto")
    return boleto if isinstance(boleto, dict) else {}


def _prediction_signs_by_column(conn, jornada):
    """Signos de la jornada por participante canónico (tabla ``predicciones``)."""
    rows = conn.execute(
        "SELECT user_id, partido_id, signo FROM predicciones WHERE jornada = ?",
        (int(jornada),),
    ).fetchall()
    signs = {}
    for row in rows:
        uid = canonical_contest_id(row["user_id"])
        try:
            partido_id = int(row["partido_id"])
        except (TypeError, ValueError):
            continue
        if not 1 <= partido_id <= 15:
            continue
        signs.setdefault(str(uid).lower(), ["-"] * 15)[partido_id - 1] = str(row["signo"] or "-")
    return signs


def _column_ids(contract, signs, jornada, max_jornada, current_user_id=None):
    """Columnas históricas J17 o maestros reales de la liga pública desde J19."""
    try:
        jornada_num = int(jornada)
    except (TypeError, ValueError):
        jornada_num = 0
    if jornada_num <= 18:
        return list(HISTORICAL_COLUMNS)

    def has_line(uid):
        return any(str(sign or "").strip() not in ("", "-") for sign in signs.get(uid, []))

    columns = []
    for uid in CURRENT_MASTER_COLUMNS:
        # La J18 europea se muestra explícitamente vacía para Programa.
        if uid == "programa":
            columns.append(uid)
        elif has_line(uid):
            columns.append(uid)
    return columns


def _when_label(match):
    """Fecha y hora de la casilla; vacio cuando la fuente no las verifica."""
    fecha = str(match.get("fecha_limpia") or match.get("fecha") or "").strip()
    hora = str(match.get("hora") or "").strip()
    if hora in ("-", "—"):
        hora = ""
    if not fecha and not hora:
        return ""
    if fecha and hora:
        return f"{fecha} {hora}"
    return fecha or f"{hora} (hora por confirmar)"


def _real_reference(match, is_pleno):
    """Signo o marcador exacto, solo con estado verificado; '' si está pendiente.

    STALE significa que el directo se degradó: aunque conserve el último
    marcador parcial para diagnóstico, no se publica ni se puntúa como fiable.
    """
    status = str(match.get("status") or "").upper()
    if not (is_scored_status(status) or is_live_scored_status(status)):
        return ""
    goles_local = match.get("goles_local")
    goles_visitante = match.get("goles_visitante")
    if goles_local is None or goles_visitante is None:
        return ""
    if is_pleno:
        return f"{int(goles_local)}-{int(goles_visitante)}"
    signo = str(match.get("signo_actual") or "").strip().upper()
    if signo in ("1", "X", "2"):
        return signo
    derived = signo_desde_goles(goles_local, goles_visitante)
    return derived or ""


def _match_is_live(match):
    return str(match.get("status") or "").upper() in ("LIVE", "IN PLAY", "HT", "HALF TIME BREAK", "EN JUEGO")


def build_simple_view_payload(conn, jornada, partidos, participant_contract, max_jornada=None, current_user_id=None):
    """Payload de la vista simple: columnas, filas, marcadores y totals de 14."""
    contract = participant_contract or {}
    names = contract.get("names") or {}
    signs_by_column = _prediction_signs_by_column(conn, jornada)
    # La columna humana es MrPurple: si Pablo ha guardado su boleto desde
    # «Tú», se presenta bajo ese id fijo en vez de dejarla fuera por usar su
    # id privado de Google. No se expone el id de cuenta como columna aparte.
    current_uid = canonical_contest_id(current_user_id) if current_user_id else ""
    if current_uid and current_uid != "mrpurple" and current_uid in signs_by_column:
        signs_by_column["mrpurple"] = signs_by_column[current_uid]
    jornada_num = int(jornada) if str(jornada).isdigit() else 0
    programa_no_juega = jornada_num == 18
    if programa_no_juega:
        signs_by_column["programa"] = ["-"] * 15
    column_ids = _column_ids(contract, signs_by_column, jornada, max_jornada, current_user_id)
    yo = str(current_user_id or "").strip().lower()

    columns = []
    for uid in column_ids:
        line = signs_by_column.get(uid) or []
        columns.append(
            {
                "id": uid,
                "name": names.get(uid) or ("Meta AI" if uid == "meta_ai" else public_contest_name(uid, {})),
                "es_pena": uid in {str(x).lower() for x in contract.get("pena_ids", [])},
                "es_mia": bool(yo) and uid == "mrpurple",
                "sin_linea": not any(str(s) not in ("", "-") for s in line),
                "estado": "no-juega" if uid == "programa" and programa_no_juega else "",
            }
        )

    rows = []
    totals = {uid: {"aciertos": 0, "jugados": 0} for uid in column_ids}
    pleno = {uid: {"acierto": None} for uid in column_ids}

    for match in partidos[:15]:
        try:
            partido_id = int(match.get("id"))
        except (TypeError, ValueError):
            continue
        is_pleno = partido_id == 15
        real = _real_reference(match, is_pleno)
        has_result = bool(real)
        picks = {}
        for uid in column_ids:
            line = signs_by_column.get(uid) or []
            raw = line[partido_id - 1] if len(line) >= partido_id else "-"
            signo = normalize_prediction_sign(partido_id, raw)
            if not signo:
                signo = "-"
            hit = None
            # Casilla sin linea (columna pendiente): no hay acierto ni fallo,
            # aunque el partido ya tenga resultado.
            if has_result and signo != "-":
                hit = bool(score_prediction(partido_id, signo, real))
            if not is_pleno and uid in totals:
                # Solo cuenta quien tiene linea en esa casilla: una columna
                # pendiente no acumula "jugados" ni aciertos a cero falsos.
                if has_result and signo != "-":
                    totals[uid]["jugados"] += 1
                    if hit:
                        totals[uid]["aciertos"] += 1
            elif is_pleno and uid in pleno:
                pleno[uid]["acierto"] = hit
            picks[uid] = {
                "signo": signo,
                "dobles": bool(not is_pleno and len(signo) > 1 and signo != "-"),
                "hit": hit,
            }

        goles_local = match.get("goles_local")
        goles_visitante = match.get("goles_visitante")
        marcador = ""
        if has_result:
            marcador = f"{int(goles_local)}-{int(goles_visitante)}"

        rows.append(
            {
                "id": partido_id,
                "local": str(match.get("local") or ""),
                "visitante": str(match.get("visitante") or ""),
                "fecha": str(match.get("fecha") or "")[:10],
                "hora": "" if str(match.get("hora") or "").strip() in ("-", "—") else str(match.get("hora") or ""),
                "cuando": _when_label(match),
                "status": str(match.get("status") or "NS"),
                "en_juego": _match_is_live(match),
                "minuto": str(match.get("minuto_live") or match.get("minuto") or ""),
                "is_pleno": is_pleno,
                "has_result": has_result,
                "resultado": marcador,
                "signo_real": real,
                "picks": picks,
            }
        )

    rows.sort(key=lambda row: row["id"])
    return {
        "jornada": str(jornada),
        "boleto": load_ticket_metadata(jornada),
        "columns": columns,
        "rows": rows,
        "totals": totals,
        "pleno": pleno,
        "total_casillas": 14,
    }


def build_simple_view_ranking(payload):
    """Clasificación de una jornada, derivada de los hits ya puntuados.

    No vuelve a evaluar signos: reutiliza el resultado de ``score_prediction``
    almacenado por ``build_simple_view_payload`` para que tabla y ranking nunca
    diverjan ante un cambio de marcador.

    Regla del pleno al 15, como en la quiniela de SELAE: el marcador exacto
    solo entra en la clasificación si las **14 casillas previas están
    acertadas**. Un pleno acertado con alguna casilla previa fallada (o aun sin
    resolver) no puntúa: queda visible en su bloque aparte, pero no suma.
    """
    ranking = {}
    rows = (payload or {}).get("rows", [])
    pleno_pick = next((row.get("picks") or {}) for row in rows if row.get("is_pleno"))
    previas = [row for row in rows if not row.get("is_pleno")]

    for column in (payload or {}).get("columns", []):
        uid = str(column.get("id") or "")

        def _picks_de(row, _uid=uid):
            return (row.get("picks") or {}).get(_uid) or {}

        hits = sum(1 for row in previas if _picks_de(row).get("hit") is True)
        quince_previas_acertadas = len(previas) == 14 and all(_picks_de(row).get("hit") is True for row in previas)
        acierta_pleno = pleno_pick is not None and (pleno_pick.get(uid) or {}).get("hit") is True
        total = hits + (1 if quince_previas_acertadas and acierta_pleno else 0)
        ranking[uid] = {
            "total": total,
            "jornada": total,
            "jornada_live": total,
            "jornada_final": total,
        }
    return ranking


def build_two_round_competition_ranking(
    conn,
    current_jornada,
    current_partidos,
    current_payload,
    participant_contract,
    max_jornada,
    jornadas_disponibles,
    current_user_id=None,
    team_logos=None,
):
    """Clasifica solo a quienes compiten en las dos quinielas recientes.

    La clasificación histórica global incluye participantes que ya no están en
    esta competición. Para la portada empezamos en J17 y puntuamos las dos
    jornadas más recientes que tengan boleto SELAE y fixture completo. J18 se
    omite automáticamente porque no tiene scrape/quiniela.
    """
    from .matches import build_jornada_matches

    try:
        current_num = int(current_jornada)
    except (TypeError, ValueError):
        return {"jornadas": [], "rows": []}

    rounds = []
    for value in jornadas_disponibles or []:
        try:
            number = int(value)
        except (TypeError, ValueError):
            continue
        if 17 <= number <= current_num:
            scrape = _load_ticket_scrape(number)
            if len(scrape.get("partidos") or []) == 15:
                rounds.append(number)
    if current_num >= 17 and current_num not in rounds:
        scrape = _load_ticket_scrape(current_num)
        if len(scrape.get("partidos") or []) == 15:
            rounds.append(current_num)
    rounds = sorted(set(rounds), reverse=True)[:2]

    participants = {}
    for number in reversed(rounds):
        if number == current_num:
            payload = current_payload
        else:
            matches = build_jornada_matches(conn, str(number), team_logos or {})
            if len(matches) != 15:
                continue
            payload = build_simple_view_payload(
                conn,
                str(number),
                matches,
                participant_contract,
                max_jornada=max_jornada,
                current_user_id=current_user_id,
            )

        scores = build_simple_view_ranking(payload)
        for column in payload.get("columns", []):
            uid = str(column.get("id") or "").strip().lower()
            if not uid or column.get("sin_linea"):
                continue
            participant = participants.setdefault(
                uid,
                {"id": uid, "name": column.get("name") or public_contest_name(uid, {}), "total": 0, "por_jornada": {}},
            )
            score = int((scores.get(uid) or {}).get("total") or 0)
            participant["por_jornada"][str(number)] = score
            participant["total"] += score

    rows = sorted(participants.values(), key=lambda row: (-row["total"], row["name"].casefold()))
    return {"jornadas": rounds, "rows": rows}


def add_competition_roster_columns(payload, competition_ranking, current_user_id=None):
    """Keep the new-competition roster visible even before this week's pick is saved."""
    payload = payload or {}
    existing = {str(column.get("id") or "").lower() for column in payload.get("columns", [])}
    additions = []
    for participant in (competition_ranking or {}).get("rows", []):
        uid = str(participant.get("id") or "").strip().lower()
        if not uid or uid in existing:
            continue
        additions.append(
            {
                "id": uid,
                "name": participant.get("name") or public_contest_name(uid, {}),
                "es_pena": False,
                "es_mia": uid == str(current_user_id or "").strip().lower(),
                "sin_linea": True,
                "estado": "",
            }
        )
        payload.setdefault("totals", {})[uid] = {"aciertos": 0, "jugados": 0}
        payload.setdefault("pleno", {})[uid] = {"acierto": None}
        for row in payload.get("rows", []):
            row.setdefault("picks", {})[uid] = {"signo": "-", "dobles": False, "hit": None}

    order = {uid: index for index, uid in enumerate(CURRENT_MASTER_COLUMNS)}
    payload["columns"] = sorted(
        [*payload.get("columns", []), *additions],
        key=lambda column: (
            order.get(str(column.get("id") or "").lower(), len(order)),
            str(column.get("name") or "").casefold(),
        ),
    )
    return payload

