"""Escudos de equipo: del payload a la insignia.

El fallo era de los dos extremos a la vez, asi que se testean los dos:

1. `MatchPayload` no declaraba `logo_local` / `logo_visitante`, y como hereda de
   `_StrictBase` (`extra="ignore"`), cualquier escudo que trajera la fuente se
   descartaba en silencio al serializar.
2. `logoBadge()` no tenia el fallback por nombre que si tiene `teamLogo()`. Con el
   escudo vacio devolvia directamente el token de texto, de modo que todos los
   fixtures del TICKET se pintaban como iniciales en vez de con su escudo.

O sea: el payload no traia escudos y, aunque los trajera, el render los habria
descartado igualmente.
"""

import json
import re
from pathlib import Path

import pytest
from pydantic import BaseModel

from liga_maestros.schemas import MatchPayload

ROOT = Path(__file__).resolve().parents[1]
LOGOS_JS = ROOT / "static" / "js" / "logos.js"
TICKET_JS = ROOT / "static" / "js" / "pages" / "ticket_page.js"


def test_match_payload_conserva_los_escudos():
    partido = MatchPayload(
        id=1,
        local="FC Barcelona",
        visitante="Real Madrid",
        logo_local="/static/img/equipos/barcelona.png",
        logo_visitante="/static/img/equipos/real_madrid.png",
    )
    datos = json.loads(partido.model_dump_json())
    assert datos["logo_local"] == "/static/img/equipos/barcelona.png"
    assert datos["logo_visitante"] == "/static/img/equipos/real_madrid.png"


def test_match_payload_no_exige_escudos():
    """Que sean opcionales: la fuente no siempre los trae y no debe reventar."""
    partido = MatchPayload(id=1, local="A", visitante="B")
    assert partido.logo_local == ""
    assert partido.logo_visitante == ""


def test_los_escudos_siguen_siendo_opcionales_para_lo_existente():
    """No se rompen los partidos que ya se serializaban bien."""
    assert issubclass(MatchPayload, BaseModel)
    partido = MatchPayload(id=9, local="L", visitante="V", status="FT", signo_actual="1")
    assert partido.model_dump()["signo_actual"] == "1"


def _cuerpo(nombre: str, texto: str) -> str:
    patron = rf"(?:async\s+)?function\s+{nombre}\s*\(.*?\n\}}"
    match = re.search(patron, texto, re.S)
    assert match, f"no encuentro la funcion {nombre}"
    return match.group(0)


def test_logo_badge_resuelve_el_escudo_por_nombre():
    """El punto del arreglo: sin logo explicito, se busca por nombre."""
    logos = LOGOS_JS.read_text(encoding="utf-8")
    cuerpo = _cuerpo("logoBadge", logos)
    assert re.search(r"logo\s*\|\|\s*findTeamLogo\(", cuerpo), (
        "logoBadge tiene que caer a findTeamLogo(name) cuando no recibe escudo; "
        "sin esto los fixtures del TICKET salen como token de texto"
    )


def test_logo_badge_sigue_aceptando_un_escudo_explicito():
    logos = LOGOS_JS.read_text(encoding="utf-8")
    cuerpo = _cuerpo("logoBadge", logos)
    assert "logoBadge(name, logo)" in logos, "logoBadge debe seguir aceptando el escudo que le pasen"
    assert re.search(r"const\s+src\s*=\s*logo\s*\|\|", cuerpo), "el escudo explicito tiene que ganar al mapa por nombre"
    # Y si de verdad no hay ninguna fuente, el token de texto es el ultimo recurso.
    assert "teamToken(name)" in cuerpo, "sin ninguna fuente debe quedar el token de texto"


def test_team_logo_usa_el_mismo_fallback_que_logo_badge():
    """Los dos resolutores de escudo no pueden discrepar."""
    cuerpo = _cuerpo("teamLogo", LOGOS_JS.read_text(encoding="utf-8"))
    assert re.search(r"direct\s*\|\|\s*findTeamLogo\(", cuerpo), (
        "teamLogo y logoBadge deberian seguir agreeing en la precedencia: "
        "escudo explicito, luego mapa por nombre, luego token"
    )


def test_fixture_inline_y_el_ticket_pasan_el_escudo():
    """El TICKET debe seguir entregando al render los campos del payload."""
    ticket = TICKET_JS.read_text(encoding="utf-8")
    assert "m.logo_local" in ticket and "m.logo_visitante" in ticket, (
        "el fixture del TICKET debe pasar los escudos que ahora llegan en el payload"
    )
    fixture = _cuerpo("fixtureInline", LOGOS_JS.read_text(encoding="utf-8"))
    assert "logoBadge(" in fixture, "fixtureInline debe seguir delegando en logoBadge"


@pytest.mark.parametrize(
    "campo",
    ["logo_local", "logo_visitante"],
)
def test_los_escudos_leidos_por_el_js_existen_en_el_schema(campo):
    """Tope el contrato: si el JS lee un campo, el schema tiene que declararlo.

    `_StrictBase` ignora lo que no conoce, asi que un campo que el JS lee y el
    schema no declara desaparece sin error ni aviso.
    """
    assert campo in MatchPayload.model_fields, f"el JS lee {campo} pero MatchPayload no lo declara"
    js = "\n".join(
        path.read_text(encoding="utf-8")
        for path in [
            LOGOS_JS,
            TICKET_JS,
            ROOT / "static" / "js" / "events.js",
            ROOT / "static" / "js" / "arena.js",
        ]
    )
    assert campo in js, f"{campo} esta declarado en el schema pero nadie lo lee"
