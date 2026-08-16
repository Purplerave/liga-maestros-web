"""Build the 15-match jornada payload."""

import logging
from datetime import datetime

from ...services.live_state import RESET_TO_SCHEDULED, closes_live, evaluate_match_state
from ...services.ticket import madrid_now, today_madrid
from ...utils import normalize_team_key, parse_db_match_datetime

logger = logging.getLogger(__name__)


def _scrape_backfill_rows(jornada, present_ids):
    """Fill missing jornada matches from the public quiniela15 scrape.

    A partial jornada in `resultados` used to render as '-'/'Pendiente'
    placeholders on the ticket. When the scrape file for the jornada ships in
    data/, we synthesize NS rows for the missing match ids so the ticket always
    shows the complete 15-match fixture. Returns a list of row dicts.
    """
    try:
        from ...db.migrations import load_scrape_matches
    except Exception:  # pragma: no cover - defensive import guard
        return []
    try:
        matches = load_scrape_matches(jornada)
    except Exception:  # pragma: no cover
        logger.exception("No se pudo leer el scrape de la jornada %s", jornada)
        return []
    rows = []
    for num, local, visitante, fecha, hora in matches or []:
        if num in present_ids:
            continue
        rows.append(
            {
                "id": num,
                "local": local,
                "visitante": visitante,
                "goles_local": None,
                "goles_visitante": None,
                "status": "NS",
                "fecha": fecha,
                "hora": hora,
                "minuto": "",
            }
        )
    return rows


def _display_safe_row(row):
    """Neutralise an impossible or frozen LIVE row before it reaches the page.

    The collector closes these rows persistently, but the web must not depend
    on the collector having run: if it is down, throttled or its last pass
    failed, a stuck LIVE row would still be served. Applying the same rules on
    read means the page is self-healing and never shows, for example, a match
    LIVE at minute 90 whose kickoff is still hours away.
    """
    kickoff = parse_db_match_datetime(row.get("fecha"), row.get("hora"))
    decision = evaluate_match_state(
        row.get("status"),
        kickoff,
        madrid_now().replace(tzinfo=None),
        last_update_at=_parse_updated_at(row.get("updated_at")),
        minute=row.get("minuto"),
    )
    if not closes_live(decision["action"]):
        return row
    safe = dict(row)
    if decision["action"] == RESET_TO_SCHEDULED:
        # Never kicked off: show the fixture with its schedule, no phantom score.
        safe.update({"status": "NS", "minuto": "", "goles_local": None, "goles_visitante": None})
        return safe
    safe["status"] = decision["status"]
    safe["minuto"] = decision["minute"]
    return safe


def _parse_updated_at(raw):
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(str(raw))
    except ValueError:
        return None
    return parsed.replace(tzinfo=None) if parsed.tzinfo is not None else parsed


def _fixture_schedule_label(row, fecha_limpia):
    """Human-friendly fixture time, even when a provider score is unavailable."""
    hora_label = str(row.get("hora") or "").strip()
    if str(row.get("fecha") or "")[:10] == today_madrid():
        return f"{hora_label}h" if hora_label else "Horario por confirmar"
    if fecha_limpia and hora_label:
        return f"{fecha_limpia} {hora_label}h"
    return fecha_limpia or (f"{hora_label}h" if hora_label else "Horario por confirmar")


def build_jornada_matches(conn, jornada, team_logos):
    def logo_for(team_name):
        return team_logos.get(normalize_team_key(team_name), "")

    columns = {row[1] for row in conn.execute("PRAGMA table_info(resultados)").fetchall()}
    updated_at_select = "updated_at" if "updated_at" in columns else "NULL AS updated_at"
    rows = conn.execute(
        f"""
        SELECT partido_id as id, local, visitante, goles_local, goles_visitante,
               status, fecha, hora, minuto, {updated_at_select}
        FROM resultados
        WHERE jornada = ?
        ORDER BY partido_id ASC
    """,  # noqa: S608 - column name comes from a local allowlist, never user input
        (jornada,),
    ).fetchall()
    rows = [_display_safe_row(dict(row)) for row in rows]

    present_ids = set()
    for row in rows:
        try:
            present_ids.add(int(row.get("id")))
        except (TypeError, ValueError):
            continue
    missing_ids = [i for i in range(1, 16) if i not in present_ids]
    if missing_ids:
        rows.extend(_scrape_backfill_rows(jornada, set(present_ids)))
        rows.sort(key=lambda row: int(row.get("id") or 99))

    partidos = []
    for row in rows:
        r = dict(row)
        p_id = r["id"]
        gh, ga = r.get("goles_local"), r.get("goles_visitante")
        status = r.get("status") or "NS"
        minuto = (r.get("minuto") or "").replace("min. ", "").replace("min.", "").strip()

        signo = "-"
        if (
            status
            in (
                "FT",
                "LIVE",
                "FINISHED",
                "IN PLAY",
                "HT",
                "HALF TIME BREAK",
                "EN JUEGO",
                "TERMINADO",
                "STALE",
                "AET",
                "PEN",
                "AWARDED",
            )
            and gh is not None
            and ga is not None
        ):
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
                current_year = datetime.now().strftime("%Y")
                fecha_limpia = str(r["fecha"]).replace(f"{current_year}-", "").replace(f"/{current_year}", "")

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
            marcador = _fixture_schedule_label(r, fecha_limpia)
        else:
            minuto_num = ""
            marcador_base = f"{gh}-{ga}" if gh is not None and ga is not None else ""
            if gh is not None and ga is not None:
                marcador = f"{gh}-{ga}"
            else:
                # A stale/final provider state without a score is not a result.
                # Keep the useful, verifiable fixture time visible until an
                # actual score arrives instead of showing a vague placeholder.
                marcador = _fixture_schedule_label(r, fecha_limpia)

        partidos.append(
            {
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
                # Compatibility field for older clients. A fixture never gets a
                # vague pending-result label: it shows its schedule or a score.
                "resultado_pendiente": False,
            }
        )

    partidos_by_id = {}
    for partido in partidos:
        try:
            partidos_by_id[int(partido.get("id"))] = partido
        except (TypeError, ValueError):
            continue

    return [
        partidos_by_id.get(
            i,
            {
                "id": i,
                "local": "-",
                "visitante": "-",
                "logo_local": "",
                "logo_visitante": "",
                "marcador": "Horario por confirmar",
                "status": "NS",
                "marcador_base": "",
                "minuto_live": "",
                "fecha_raw": "",
                "hora": "-",
                "signo_actual": "-",
                "goles_local": None,
                "goles_visitante": None,
            },
        )
        for i in range(1, 16)
    ]
