"""Tests del sistema de trash-talk (P1 2.2).

Cubre:
- Carga del banco desde seed.
- Determinismo de la frase por (jornada, maestro).
- Rotación por jornada (no es constante).
- Réplica de La Peña.
- Estado del duelo calculado server-side.
- Render HTML del cover con `cp-voz`.
- Helpers JS no inventan marcadores.
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _load_trash():
    mod = importlib.import_module("liga_maestros.services.trash_talk")
    importlib.reload(mod)
    return mod


def test_bank_loads_from_seed():
    mod = _load_trash()
    assert mod.maestro_phrase("grok", "va_ganando", "1")
    assert mod.pena_replica("primera", "1")


def test_phrase_is_stable_for_same_seed():
    mod = _load_trash()
    a = mod.maestro_phrase("grok", "va_ganando", "5")
    b = mod.maestro_phrase("grok", "va_ganando", "5")
    assert a == b and a


def test_phrase_rotates_between_jornadas():
    mod = _load_trash()
    seen = {mod.maestro_phrase("grok", "va_ganando", str(j)) for j in range(1, 20)}
    # 19 jornadas deben dar al menos 2 frases distintas en estado va_ganando
    assert len([s for s in seen if s]) >= 2


def test_phrase_never_invents_score():
    """El banco no debe contener dígitos sueltos tipo '3-1' o marcadores."""
    seed_path = ROOT / "data" / "MAESTROS_TRASH_TALK.json"
    raw = json.loads(seed_path.read_text(encoding="utf-8"))
    forbidden = ["1-0", "2-1", "3-0", "0-1", "1-1", "0-0", "2-0", "0-2"]
    for maestro, states in raw["frases"].items():
        for state, lines in states.items():
            for line in lines:
                for bad in forbidden:
                    assert bad not in line, f"{maestro}/{state} contiene marcador {bad!r}: {line!r}"


def test_phrase_empty_for_unknown_maestro():
    mod = _load_trash()
    assert mod.maestro_phrase("inexistente", "va_ganando", "1") == ""


def test_phrase_falls_back_to_primera_when_state_unknown():
    mod = _load_trash()
    fallback = mod.maestro_phrase("claude", "primera", "1")
    weird = mod.maestro_phrase("claude", "estado_inventado", "1")
    assert fallback and weird == fallback


def test_pena_replica_changes_with_state():
    mod = _load_trash()
    gana = mod.pena_replica("va_ganando", "5")
    pierde = mod.pena_replica("va_perdiendo", "5")
    assert gana and pierde and gana != pierde


def test_build_trash_talk_payload_shape():
    mod = _load_trash()
    out = mod.build_trash_talk("5", "empate")
    assert out["jornada"] == "5"
    assert out["bando_state"] == "empate"
    assert set(out["masters"].keys()) == {"programa", "claude", "grok", "chatgpt", "copilot", "gemini"}
    assert out["pena_replica"]


# ---- Server-side bando_state ----


def test_bando_state_primera_when_empty():
    from liga_maestros.routes.liga_data import _bando_state_for

    contract = {"visible_ai_columns": [{"id": "programa"}], "pena_ids": ["mrpurple"]}
    assert _bando_state_for({}, contract) == "primera"


def test_bando_state_primera_when_only_one_side():
    from liga_maestros.routes.liga_data import _bando_state_for

    contract = {"visible_ai_columns": [{"id": "programa"}], "pena_ids": ["mrpurple"]}
    # Solo IA
    assert _bando_state_for({"programa": {"jornada_live": 10}}, contract) == "primera"
    # Solo Peña
    assert _bando_state_for({"mrpurple": {"jornada_live": 10}}, contract) == "primera"


def test_bando_state_va_perdiendo_when_ia_ahead():
    from liga_maestros.routes.liga_data import _bando_state_for

    contract = {"visible_ai_columns": [{"id": "programa"}, {"id": "grok"}], "pena_ids": ["mrpurple"]}
    ranking = {"programa": {"jornada_live": 10}, "grok": {"jornada_live": 8}, "mrpurple": {"jornada_live": 3}}
    assert _bando_state_for(ranking, contract) == "va_perdiendo"


def test_bando_state_va_ganando_when_pena_ahead():
    from liga_maestros.routes.liga_data import _bando_state_for

    contract = {"visible_ai_columns": [{"id": "programa"}], "pena_ids": ["mrpurple"]}
    ranking = {"programa": {"jornada_live": 3}, "mrpurple": {"jornada_live": 10}}
    assert _bando_state_for(ranking, contract) == "va_ganando"


def test_bando_state_empate_when_close():
    from liga_maestros.routes.liga_data import _bando_state_for

    contract = {"visible_ai_columns": [{"id": "programa"}], "pena_ids": ["mrpurple"]}
    ranking = {"programa": {"jornada_live": 5}, "mrpurple": {"jornada_live": 5}}
    assert _bando_state_for(ranking, contract) == "empate"


# ---- Frontend: el cover expone cp-voz ----


def test_cover_contains_cp_voz_block():
    cover = (ROOT / "static" / "js" / "pages" / "cover_page.js").read_text(encoding="utf-8")
    assert "cp-voz" in cover
    assert "coverTrashTalkHtml" in cover
    assert "trash_talk" in cover  # consume payload
    # No inventa marcadores
    assert "3-1" not in cover and "2-0" not in cover
    # Click delegation + pausa por visibilidad
    assert "data-voz-idx" in cover
    assert "visibilitychange" in cover
    # 6 avatares en el carrusel
    for mid in ["programa", "claude", "grok", "chatgpt", "copilot", "gemini"]:
        assert mid in cover, f"avatar para {mid} no presente"


def test_cover_css_has_cp_voz_styles():
    css = (
        ROOT / "static" / "cover_hero.css"
        if (ROOT / "static" / "cover_hero.css").exists()
        else ROOT / "static" / "css" / "cover_hero.css"
    ).read_text(encoding="utf-8")
    for selector in [".cp-voz", ".cp-voz-quote", ".cp-voz-dots", ".cp-voz-replica", ".cp-voz-avatar", ".cp-voz-dot"]:
        assert selector in css, f"Falta selector {selector} en cover_hero.css"
    assert "prefers-reduced-motion" in css
    assert "@keyframes cpVozFade" in css


def test_liga_data_route_includes_trash_talk_in_payload():
    route = (ROOT / "liga_maestros" / "routes" / "liga_data.py").read_text(encoding="utf-8")
    assert "trash_talk" in route
    assert "build_trash_talk" in route
    assert "_bando_state_for" in route
