"""Jornada 9 fixtures must reach both the cover and ticket payload on time."""

import sqlite3

from liga_maestros.db.migrations import ensure_core_tables, ensure_jornada_9
from liga_maestros.schemas import MatchPayload
from liga_maestros.services.payloads.matches import build_jornada_matches

EXPECTED = [
    (1, "2026-09-26", "14:00"),
    (2, "2026-09-26", "16:15"),
    (3, "2026-09-26", "18:30"),
    (4, "2026-09-26", "18:30"),
    (5, "2026-09-27", "14:00"),
    (6, "2026-09-27", "16:15"),
    (7, "2026-09-27", "18:30"),
    (8, "2026-09-27", "18:30"),
    (9, "2026-09-27", "21:00"),
    (10, "2026-09-28", "20:30"),
    (11, "2026-09-27", "12:00"),
    (12, "2026-09-27", "12:00"),
    (13, "2026-09-27", "16:00"),
    (14, "2026-09-27", "18:00"),
    (15, "2026-09-26", "20:45"),
]

# Campos que el builder emite y que el frontend lee. Si uno no coincide con
# el nombre declarado en MatchPayload, `extra="ignore"` lo borra en silencio.
_MATCH_KEYS = ("logo_local", "logo_visitante")


def _as_api(match):
    """Serializa como lo hace GET /api/liga/data (schemas.MatchPayload)."""
    return MatchPayload(**{k: v for k, v in match.items() if k not in _MATCH_KEYS}).model_dump()


def _js_display(match, today):
    """Replica de fixtureScheduleDisplay() de static/js/utils.js."""
    fecha = str(match.get("fecha_raw") or match.get("fecha") or "")[:10]
    hora = str(match.get("hora") or "").replace("h", "").strip()
    if fecha and fecha == today:
        return hora or "Horario por confirmar"
    if not fecha:
        return f"{hora}h" if hora else "Horario pendiente"
    year, month, day = fecha.split("-")
    label = f"{int(day)}/{int(month)}"
    return f"{label} {hora}" if hora else label


def test_j9_schedule_is_persisted_and_served_to_the_cover_and_ticket():
    with sqlite3.connect(":memory:") as conn:
        conn.row_factory = sqlite3.Row
        ensure_core_tables(conn)
        ensure_jornada_9(conn)

        payload = build_jornada_matches(conn, 9, {})

    assert len(payload) == 15
    assert [(match["id"], match["fecha_raw"], match["hora"]) for match in payload] == EXPECTED


def test_j9_schedule_survives_the_api_schema():
    """La fecha debe seguir presente DESPUES de pasar por MatchPayload.

    Regresion: el builder emitia solo `fecha_raw`, que MatchPayload no
    declara, asi que `extra="ignore"` lo eliminaba y la API devolvia
    `fecha: ""`. El frontend se quedaba sin dia y pintaba "16:15h".
    """
    with sqlite3.connect(":memory:") as conn:
        conn.row_factory = sqlite3.Row
        ensure_core_tables(conn)
        ensure_jornada_9(conn)

        api = [_as_api(match) for match in build_jornada_matches(conn, 9, {})]

    assert [(match["id"], match["fecha"], match["hora"]) for match in api] == EXPECTED
    assert all(match["fecha_limpia"] for match in api)


def test_j9_display_shows_only_the_time_today_and_date_time_later():
    with sqlite3.connect(":memory:") as conn:
        conn.row_factory = sqlite3.Row
        ensure_core_tables(conn)
        ensure_jornada_9(conn)

        api = {match["id"]: _as_api(match) for match in build_jornada_matches(conn, 9, {})}

    assert _js_display(api[2], "2026-09-26") == "16:15"
    assert _js_display(api[8], "2026-09-26") == "27/9 18:30"
    assert _js_display(api[10], "2026-09-26") == "28/9 20:30"
    # Un partido de hoy no debe llevar fecha por delante.
    assert "/" not in _js_display(api[1], "2026-09-26")


def test_j9_live_minute_reaches_the_api():
    """`minuto_live` lo lee el frontend el primero; no debe perderse."""
    with sqlite3.connect(":memory:") as conn:
        conn.row_factory = sqlite3.Row
        ensure_core_tables(conn)
        ensure_jornada_9(conn)
        conn.execute(
            "UPDATE resultados SET status='LIVE', minuto='67', goles_local=1, "
            "goles_visitante=0 WHERE jornada=9 AND partido_id=1"
        )
        conn.commit()

        match = _as_api(build_jornada_matches(conn, 9, {})[0])

    assert match["status"] == "LIVE"
    assert match["minuto_live"] == "67"
    assert match["minuto"] == "67"
    assert match["marcador_base"] == "1-0"
