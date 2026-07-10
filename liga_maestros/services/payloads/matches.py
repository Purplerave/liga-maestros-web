"""Build the 15-match jornada payload."""
from datetime import datetime

from ...services.ticket import today_madrid
from ...utils import normalize_team_key


def build_jornada_matches(conn, jornada, team_logos):
    def logo_for(team_name):
        return team_logos.get(normalize_team_key(team_name), "")

    rows = conn.execute("""
        SELECT partido_id as id, local, visitante, goles_local, goles_visitante,
               status, fecha, hora, minuto
        FROM resultados
        WHERE jornada = ?
        ORDER BY partido_id ASC
    """, (jornada,)).fetchall()

    partidos = []
    for row in rows:
        r = dict(row)
        p_id = r["id"]
        gh, ga = r.get("goles_local"), r.get("goles_visitante")
        status = r.get("status") or "NS"
        minuto = (r.get("minuto") or "").replace("min. ", "").replace("min.", "").strip()

        signo = "-"
        if status in ("FT", "LIVE", "FINISHED", "IN PLAY", "HT", "HALF TIME BREAK", "EN JUEGO", "TERMINADO") and gh is not None and ga is not None:
            if gh > ga:
                signo = "1"
            elif gh < ga:
                signo = "2"
            else:
                signo = "X"

        fecha_limpia = ""
        if r.get("fecha"):
            try:
                fecha_dt = datetime.strptime(str(r["fecha"])[:10], "%Y-%m-%d")
                dias = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]
                fecha_limpia = f"{dias[fecha_dt.weekday()]} {fecha_dt.strftime('%d/%m')}"
            except Exception:
                fecha_limpia = str(r["fecha"]).replace("2026-", "").replace("/2026", "")

        if status in ("LIVE", "IN PLAY", "HT", "HALF TIME BREAK", "EN JUEGO"):
            minuto_num = "".join(ch for ch in minuto if ch.isdigit())
            marcador_base = f"{gh}-{ga}" if gh is not None and ga is not None else "-:-"
            if minuto_num:
                marcador = f"{marcador_base}\u00a0({minuto_num}')"
            elif minuto.upper() in ("HT", "DESCANSO"):
                marcador = f"{marcador_base}\u00a0(Desc.)"
            else:
                marcador = marcador_base
        elif status in ("NS", "SCHEDULED"):
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
            "id": p_id,
            "local": r["local"],
            "visitante": r["visitante"],
            "logo_local": logo_for(r["local"]),
            "logo_visitante": logo_for(r["visitante"]),
            "marcador": marcador,
            "status": status,
            "marcador_base": marcador_base,
            "minuto_live": minuto_num,
            "fecha_raw": r.get("fecha", ""),
            "hora": r.get("hora", "-"),
            "signo_actual": signo,
            "goles_local": gh,
            "goles_visitante": ga,
        })

    partidos_by_id = {}
    for partido in partidos:
        try:
            partidos_by_id[int(partido.get("id"))] = partido
        except (TypeError, ValueError):
            continue

    return [
        partidos_by_id.get(i, {
            "id": i,
            "local": "-",
            "visitante": "-",
            "logo_local": "",
            "logo_visitante": "",
            "marcador": "Pendiente",
            "status": "NS",
            "marcador_base": "",
            "minuto_live": "",
            "fecha_raw": "",
            "hora": "-",
            "signo_actual": "-",
            "goles_local": None,
            "goles_visitante": None,
        })
        for i in range(1, 16)
    ]

