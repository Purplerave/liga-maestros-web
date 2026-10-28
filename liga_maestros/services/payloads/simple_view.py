"""Vista simple por columnas de la portada (J17 «en simple»).

Una fila por casilla, solo tres columnas de participantes por defecto y
aciertos/fallos ya decididos en el servidor. La regla de puntuacion vive
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
from ...services.teams import canonical_contest_id, public_contest_name, signo_desde_goles

# Columnas que se muestran por defecto: los tres contendientes reales de la
# temporada. Si alguien mas manda linea la semana en juego, se anade su
# columna (sin perseguir a nadie); el historico se ve con las mismas tres.
BASE_COLUMNS = ("mrpurple", "programa", "tecnotron")


def load_ticket_metadata(jornada):
    """Metadatos del boleto (SELAE, concurso, cierre) desde el scrape de la jornada.

    Solo la J17 los trae verificados; el resto de jornadas devuelven ``{}`` y
    la vista se limita a pintar el numero de jornada. Sin importe de bote en
    ningun caso: si no esta confirmado, no se muestra.
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
        boleto = data.get("boleto")
        return boleto if isinstance(boleto, dict) else {}
    return {}


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
    """Columnas visibles: las tres por defecto + quien manda linea esta semana.

    El filtro usa el mecanismo que ya tiene la pagina (``hidden_ids`` del
    contrato de participantes): se OCULTA en la vista, nunca se borra de la BD.
    El «esta semana» es a proposito: en el historico J1-J16 se comparan los
    tres contendientes, no las veinte lineas que aquella jornada acumulo.

    Ademas, el participante registrado con sesion ve SIEMPRE su propia columna
    en la jornada en juego (``es_mia``): aunque todavia no haya mandado linea,
    la pagina necesita la columna para ofrecerle el editor de su quiniela.
    """
    hidden = {str(uid).lower() for uid in contract.get("hidden_ids", [])}
    oficial = {str(col.get("id", "")).lower() for col in contract.get("visible_ai_columns", [])}
    oficial.update(str(uid).lower() for uid in contract.get("pena_ids", []))

    ids = [uid for uid in BASE_COLUMNS if uid not in hidden]
    en_juego = str(jornada) == str(max_jornada) if max_jornada not in (None, "") else True
    if en_juego:
        for uid in sorted(signs):
            if uid in oficial and uid not in hidden and uid not in ids:
                ids.append(uid)
        me = str(current_user_id or "").strip().lower()
        if me and me not in hidden and me not in ids:
            ids.append(me)
    return ids


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
    """Signo real (casillas 1-14) o marcador exacto (pleno); '' si no hay resultado."""
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
    column_ids = _column_ids(contract, signs_by_column, jornada, max_jornada, current_user_id)
    yo = str(current_user_id or "").strip().lower()

    columns = []
    for uid in column_ids:
        line = signs_by_column.get(uid) or []
        columns.append(
            {
                "id": uid,
                "name": names.get(uid) or public_contest_name(uid, {}),
                "es_pena": uid in {str(x).lower() for x in contract.get("pena_ids", [])},
                "es_mia": bool(yo) and uid == yo,
                "sin_linea": not any(str(s) not in ("", "-") for s in line),
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
