"""Coherencia de estados de partido: cierre de directos imposibles o parados.

Un partido no puede estar EN DIRECTO por horario ni por minuto: solo lo esta
mientras un proveedor sigue confirmandolo. En produccion se han visto dos
averias distintas que dejaban partidos "atascados" en la portada:

1. Directo imposible: la fila queda en LIVE (incluso con minuto 90) mientras el
   inicio del partido todavia esta en el futuro. Pasa cuando el partido se
   reprograma, cuando el proveedor devuelve el encuentro de otra jornada con el
   mismo emparejamiento, o cuando una importacion antigua deja el estado sucio.
   El horario por si solo nunca cierra esta fila porque `kickoff + margen`
   todavia no ha llegado.

2. Directo congelado: el proveedor deja de emitir (cuota agotada, corte de red,
   reinicio del colector) y la ultima foto se queda en LIVE para siempre.

Por eso la decision NO depende solo del horario: se cruzan tres senales
independientes (estado, hora de inicio y frescura del ultimo dato) y basta con
que una sea imposible para cerrar. Las reglas viven aqui, sin SQL ni IO, para
que el colector (escritura) y los payloads de la web (lectura) apliquen
exactamente el mismo criterio y se puedan testear sin base de datos.
"""

from datetime import timedelta

LIVE_STATUSES = frozenset(
    {
        "LIVE",
        "IN PLAY",
        "IN_PLAY",
        "HT",
        "HALF TIME",
        "HALF TIME BREAK",
        "EN JUEGO",
        "1H",
        "2H",
        "ET",
        "P",
        "PEN LIVE",
    }
)
FINAL_STATUSES = frozenset({"FT", "FINISHED", "TERMINADO", "AET", "PEN", "AWARDED", "STALE"})
PENDING_STATUSES = frozenset({"", "NS", "SCHEDULED", "NOT STARTED", "TBD", "POSTPONED"})

# Sin noticias del proveedor durante este tiempo, el directo se cierra.
NO_UPDATE_TIMEOUT = timedelta(minutes=30)
# 90 minutos + descanso + prolongacion razonable: pasado esto el partido acabo.
FULL_MATCH_WINDOW = timedelta(minutes=120)
# Margen antes del inicio en el que un LIVE aun es creible (retrasos de reloj).
PREKICKOFF_TOLERANCE = timedelta(minutes=5)
# Un partido programado que ya deberia haber acabado y sigue "pendiente".
PENDING_OVERDUE_AFTER = timedelta(hours=3)

# Acciones devueltas por `evaluate_match_state`.
KEEP = "keep"
RESET_TO_SCHEDULED = "reset_to_scheduled"
CLOSE_FINAL = "close_final"
CLOSE_NO_DATA = "close_no_data"
PENDING_OVERDUE = "pending_overdue"

# Estado con el que se marca un directo cerrado sin datos suficientes para dar
# el partido por finalizado oficialmente. La web ya lo trata como terminado.
NO_DATA_STATUS = "STALE"
NO_DATA_MINUTE = "Sin datos"
FINAL_STATUS = "FT"
FINAL_MINUTE = "Finalizado"
SCHEDULED_STATUS = "NS"


def normalize_status(status):
    return str(status or "").strip().upper()


def is_live_status(status):
    return normalize_status(status) in LIVE_STATUSES


def is_final_status(status):
    return normalize_status(status) in FINAL_STATUSES


def is_pending_status(status):
    return normalize_status(status) in PENDING_STATUSES


def minute_number(minute):
    """Return the numeric minute of a provider label ('45+2', "90'", 'HT')."""
    digits = ""
    for char in str(minute or ""):
        if char.isdigit():
            digits += char
        elif digits:
            break
    if not digits:
        return None
    try:
        return int(digits)
    except ValueError:
        return None


def _as_naive(value):
    """Compare datetimes safely whether or not they carry a timezone."""
    if value is None:
        return None
    return value.replace(tzinfo=None) if value.tzinfo is not None else value


def evaluate_match_state(
    status,
    kickoff_at,
    now,
    last_update_at=None,
    minute=None,
    no_update_timeout=NO_UPDATE_TIMEOUT,
    full_match_window=FULL_MATCH_WINDOW,
):
    """Decide what to do with a match row. Pure function, no IO.

    Returns a dict ``{"action", "reason", "status", "minute"}`` where ``status``
    and ``minute`` are the values to persist (``None`` when nothing changes).

    ``last_update_at`` is when a provider last confirmed this row. When it is
    unknown (legacy rows written before the column existed) the freshness rule
    is skipped and only the impossible-state and schedule rules apply.
    """
    now = _as_naive(now)
    kickoff_at = _as_naive(kickoff_at)
    last_update_at = _as_naive(last_update_at)
    normalized = normalize_status(status)

    if normalized not in LIVE_STATUSES:
        if normalized in PENDING_STATUSES and kickoff_at and now >= kickoff_at + PENDING_OVERDUE_AFTER:
            return _decision(
                PENDING_OVERDUE,
                "programado_sin_resultado",
                status=None,
                minute=None,
            )
        return _decision(KEEP, "estado_no_live")

    # 1. Imposible por definicion: en juego antes de empezar. No se inventa
    #    resultado: la fila vuelve a "pendiente" y el proveedor la repoblara.
    if kickoff_at and now < kickoff_at - PREKICKOFF_TOLERANCE:
        return _decision(
            RESET_TO_SCHEDULED,
            "live_antes_del_inicio",
            status=SCHEDULED_STATUS,
            minute="",
        )

    # 2. Imposible por reloj: el minuto emitido va por delante del tiempo real
    #    transcurrido desde el inicio (p. ej. minuto 90 a los 10 minutos).
    if kickoff_at and _minute_ahead_of_clock(minute, kickoff_at, now):
        if now >= kickoff_at + full_match_window:
            return _decision(CLOSE_FINAL, "minuto_imposible_ventana_agotada", status=FINAL_STATUS, minute=FINAL_MINUTE)
        return _decision(CLOSE_NO_DATA, "minuto_imposible", status=NO_DATA_STATUS, minute=NO_DATA_MINUTE)

    # 3. Ventana maxima de partido agotada: cierre definitivo.
    if kickoff_at and now >= kickoff_at + full_match_window:
        return _decision(CLOSE_FINAL, "ventana_de_partido_agotada", status=FINAL_STATUS, minute=FINAL_MINUTE)

    # 4. Sin actualizaciones del proveedor: el directo deja de ser creible.
    if last_update_at is not None and now - last_update_at >= no_update_timeout:
        return _decision(CLOSE_NO_DATA, "sin_actualizacion_30min", status=NO_DATA_STATUS, minute=NO_DATA_MINUTE)

    return _decision(KEEP, "live_coherente")


def _minute_ahead_of_clock(minute, kickoff_at, now, tolerance_minutes=15):
    """True when the broadcast minute cannot fit the elapsed real time.

    The clock can only run slower than real time (half-time break, stoppages),
    never faster, so a minute well above the elapsed time is a frozen or
    mismatched snapshot rather than a live match.
    """
    value = minute_number(minute)
    if value is None:
        return False
    elapsed_minutes = (now - kickoff_at).total_seconds() / 60.0
    if elapsed_minutes < 0:
        return True
    return value > elapsed_minutes + tolerance_minutes


def _decision(action, reason, status=None, minute=None):
    return {"action": action, "reason": reason, "status": status, "minute": minute}


def closes_live(action):
    """True when the action stops a row from being shown as live."""
    return action in (RESET_TO_SCHEDULED, CLOSE_FINAL, CLOSE_NO_DATA)
