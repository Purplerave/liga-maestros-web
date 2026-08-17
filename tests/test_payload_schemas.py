"""Tests de los schemas Pydantic (3.1).

Cubren:
- Validación de un payload mínimo real
- Drift de tipos: el validador detecta y reporta, sin lanzar
- Schema drift en participant_contract (campo faltante)
- Trash-talk con estado inválido cae a 'primera'
- Match con signo inválido cae a '-'
- helper validate_liga_data devuelve el payload original si hay error
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _schemas():
    mod = importlib.import_module("liga_maestros.schemas")
    importlib.reload(mod)
    return mod


def _min_partido():
    return {
        "id": 1,
        "local": "Alavés",
        "visitante": "Getafe",
        "goles_local": None,
        "goles_visitante": None,
        "status": "NS",
        "signo": "-",
        "signo_actual": "-",
    }


def test_participant_contract_minimal():
    s = _schemas()
    pc = s.ParticipantContract.model_validate(
        {"visible_ai_columns": [{"id": "programa", "label": "PROG", "name": "Programa"}]}
    )
    assert pc.version == 1
    assert pc.visible_ai_columns[0].id == "programa"
    assert pc.hidden_ids == []


def test_match_signo_normalized_to_dash():
    s = _schemas()
    m = s.MatchPayload.model_validate({**_min_partido(), "signo": "Z", "signo_actual": "Q"})
    assert m.signo == "-" and m.signo_actual == "-"


def test_match_signo_accepts_valid():
    s = _schemas()
    for sign in ("1", "X", "2", "-"):
        m = s.MatchPayload.model_validate({**_min_partido(), "signo": sign})
        assert m.signo == sign


def test_trash_talk_state_normalized():
    s = _schemas()
    tt = s.TrashTalkPayload.model_validate({"bando_state": "inventado", "masters": {}, "pena_replica": ""})
    assert tt.bando_state == "primera"


def test_trash_talk_valid_states():
    s = _schemas()
    for st in ("va_ganando", "va_perdiendo", "empate", "primera"):
        tt = s.TrashTalkPayload.model_validate({"bando_state": st})
        assert tt.bando_state == st


def test_liga_data_minimal_passes():
    s = _schemas()
    payload = {
        "jornada": "1",
        "partidos": [_min_partido()],
        "participant_contract": {"visible_ai_columns": [{"id": "programa", "label": "PROG", "name": "Programa"}]},
    }
    validated, err = s.validate_liga_data(payload)
    assert err is None
    assert validated["jornada"] == "1"
    assert len(validated["partidos"]) == 1


def test_liga_data_drift_is_reported_but_not_fatal():
    s = _schemas()
    # Simulamos un payload que rompe el schema: jornada falta
    bad = {"partidos": [_min_partido()]}
    validated, err = s.validate_liga_data(bad)
    assert err is not None
    # Aun así devolvemos el payload (o fallback) para no romper la respuesta
    assert isinstance(validated, dict)


def test_liga_data_drift_participant_contract_missing():
    s = _schemas()
    bad = {"jornada": "1", "partidos": []}
    validated, err = s.validate_liga_data(bad)
    assert err is None  # participant_contract tiene default
    assert "participant_contract" in validated


def test_liga_data_extra_fields_are_ignored():
    s = _schemas()
    payload = {"jornada": "1", "partidos": [], "campo_inventado_en_el_futuro": [1, 2, 3]}
    validated, err = s.validate_liga_data(payload)
    assert err is None
    # El schema lo ignora silenciosamente (extra=ignore)
    assert "campo_inventado_en_el_futuro" not in validated


def test_match_status_defaults_to_ns():
    s = _schemas()
    m = s.MatchPayload.model_validate({"id": 1, "local": "A", "visitante": "B"})
    assert m.status == "NS"
    assert m.signo == "-"
