"""Schemas Pydantic para los payloads runtime que cruzan la frontera servidor → frontend.

Filosofía: estos schemas validan la **forma** del payload serializado (lo que el
frontend consume) y no el modelo de dominio. Sirven para:

1. Detectar derivas silenciosas en la serialización (un campo que deja de venir,
   un tipo que cambia) antes de que el frontend muestre `undefined` o se rompa.
2. Documentar de forma ejecutable el contrato de cada payload crítico.
3. Fallar de forma controlada: si un payload no encaja, devolvemos un fallback
   con `status="schema_error"` y los campos que sí pudimos extraer, en vez de
   un 500 silencioso.

NO validamos el origen de los datos (eso es trabajo de los servicios), solo la
forma del JSON que sale del backend.
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

logger = logging.getLogger(__name__)


# ---- Base -----------------------------------------------------------------


class _StrictBase(BaseModel):
    """Base: ignora campos extra pero reporta los nombres para diagnóstico."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)


# ---- Atómicos -------------------------------------------------------------


class ParticipantColumn(_StrictBase):
    id: str
    fallback: str | None = None
    label: str
    name: str


class ParticipantContract(_StrictBase):
    version: int = 1
    names: dict[str, str] = Field(default_factory=dict)
    hidden_ids: list[str] = Field(default_factory=list)
    pena_ids: list[str] = Field(default_factory=list)
    visible_ai_columns: list[ParticipantColumn] = Field(default_factory=list)
    roles: dict[str, Any] = Field(default_factory=dict)


class MatchPayload(_StrictBase):
    id: int
    local: str
    visitante: str
    goles_local: int | None = None
    goles_visitante: int | None = None
    status: str = "NS"
    fecha: str = ""
    hora: str = ""
    minuto: str = ""
    signo: str = "-"
    signo_actual: str = "-"
    marcador: str = ""
    fecha_limpia: str = ""

    @field_validator("signo", "signo_actual")
    @classmethod
    def _signo_in_set(cls, v: str) -> str:
        if v not in {"1", "X", "2", "-"}:
            return "-"
        return v


class LigaDataPayload(_StrictBase):
    """Schema del payload principal que sirve ``GET /api/liga/data``.

    Solo valida los campos críticos para que el render de portada funcione.
    Si en el futuro se añade un campo, basta con extender este modelo.
    """

    jornada: str
    jornada_liga: str = ""
    max_jornada: int | str = ""
    jornadas_disponibles: list[int] = Field(default_factory=list)
    today_madrid: str = ""
    is_locked: bool = False
    edit_deadline: str = ""
    kickoff_at: str = ""
    partidos: list[MatchPayload] = Field(default_factory=list)
    all_league_matches: list[Any] = Field(default_factory=list)
    live_matches: list[Any] = Field(default_factory=list)
    standings: dict[str, Any] = Field(default_factory=dict)
    multi_league_standings: dict[str, Any] = Field(default_factory=dict)
    participant_contract: ParticipantContract = Field(default_factory=ParticipantContract)
    match_info: dict[str, Any] = Field(default_factory=dict)
    predicciones_actuales: dict[str, Any] = Field(default_factory=dict)
    consenso_pena: list[Any] = Field(default_factory=list)
    consenso_pleno_pena: list[Any] = Field(default_factory=list)
    ranking_maestros: dict[str, Any] = Field(default_factory=dict)
    auth_enabled: bool = False
    live_stream_enabled: bool = False
    is_admin: bool = False
    ticket_policy: dict[str, Any] = Field(default_factory=dict)


# ---- Helper de validación -------------------------------------------------


def validate_liga_data(payload: Any) -> tuple[dict[str, Any], str | None]:
    """Valida el payload de ``/api/liga/data``. Devuelve (payload, error_msg).

    Si hay error, loguea y devuelve el payload original (no se rompe la
    respuesta) para que el frontend pueda seguir funcionando con un fallback.
    El error_msg es None si todo va bien.
    """
    try:
        validated = LigaDataPayload.model_validate(payload)
        return validated.model_dump(exclude_none=False), None
    except ValidationError as exc:
        # Truncamos el detalle para no spammear logs
        problems = exc.errors()[:5]
        summary = "; ".join(f"{'.'.join(str(p) for p in err['loc'])}: {err['type']}" for err in problems)
        logger.warning("liga_data payload no encaja con schema: %s", summary)
        if isinstance(payload, dict):
            return payload, summary
        return {}, summary
