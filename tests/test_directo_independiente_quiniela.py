"""El DIRECTO de las 5 ligas funciona sin quiniela y en cualquier huso.

Dos averias reales detras del aviso «ahora mismo no hay partidos en juego»
mientras la Real Sociedad - Celta estaba en juego (03/09/2026, minuto 21):

1. **El reloj del navegador mandaba.** El servidor entrega todas las horas
   como texto sin zona ya en hora de Madrid (``added``, ``scheduled``,
   ``fecha_raw``/``hora``). El cliente las metia en ``new Date()``, que las
   lee en la zona local: en Canarias, con el movil en UTC o de viaje, el saque
   de las 21:00 caia despues y el filtro de caducidad daba el partido por
   muerto justo cuando empezaba. El DIRECTO se quedaba vacio aunque el
   servidor estuviera sirviendo el partido en ``live_matches``.

2. **La quiniela no puede ser la condicion.** Un jueves con futbol de Liga no
   tiene por que coincidir con el boleto: el directo se construye con los
   partidos del panel de las 5 ligas (LaLiga, Segunda, Premier, Bundesliga y
   Ligue 1) y con los de la quiniela, sin duplicar el mismo partido.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
UTILS = ROOT / "static" / "js" / "utils.js"
STATE = ROOT / "static" / "js" / "state.js"

requires_node = pytest.mark.skipif(
    shutil.which("node") is None, reason="Node is required to exercise browser utility functions"
)

# Tal cual lo sirvio /api/liga/data el dia del aviso: la Real Sociedad - Celta
# en juego (minuto 21) y el Toulouse - Lille de la Ligue 1 (minuto 38). Hora
# de Madrid, que es como la manda el servidor.
PANEL_LIVE = [
    {
        "id": 1336404376,
        "fixture_id": 1336404376,
        "status": "IN PLAY",
        "time": "21",
        "score": "0 - 0",
        "added": "2026-09-03 21:00:00",
        "scheduled": "21:00",
        "competition_name": "LA LIGA",
        "competition": {"name": "LA LIGA"},
        "home": {"name": "Real Sociedad"},
        "away": {"name": "Celta de Vigo"},
    },
    {
        "id": 1321394438,
        "fixture_id": 1321394438,
        "status": "IN PLAY",
        "time": "38",
        "score": "0 - 0",
        "added": "2026-09-03 20:45:00",
        "scheduled": "20:45",
        "competition_name": "LIGUE 1",
        "competition": {"name": "LIGUE 1"},
        "home": {"name": "Toulouse"},
        "away": {"name": "Lille"},
    },
]

# El reloj de la prueba: 21:30 en Madrid, con el Celta en el minuto 21.
NOW_MADRID = "2026-09-03T21:30:00+02:00"


def _run_node(script, now=NOW_MADRID, env=None):
    import os

    environment = dict(os.environ, TZ=env or "UTC")
    result = subprocess.run(
        ["node", "-e", script],
        cwd=ROOT,
        check=True,
        capture_output=True,
        encoding="utf-8",
        env=environment,
    )
    return json.loads(result.stdout)


HARNESS = """
    const fs = require("fs");
    const vm = require("vm");
    const context = { console, Map, Set, String, Number, Date, JSON, Array, Object, Boolean, RegExp, Math,
                      parseInt, isNaN, URLSearchParams, encodeURIComponent, Intl, setTimeout };
    context.window = context;
    context.document = { body: { classList: { toggle() {}, add() {}, remove() {} } },
                         getElementById: () => null, querySelectorAll: () => [] };
    context.location = { search: "?view=LIVE", href: "https://example.test/?view=LIVE" };
    context.localStorage = { getItem: () => null, setItem() {}, removeItem() {} };
    vm.createContext(context);
    for (const path of [__UTILS__, __STATE__]) {
        vm.runInContext(fs.readFileSync(path, "utf8"), context, { filename: path });
    }
    context.DATA = __DATA__;
    vm.runInContext("state.data = DATA; state.currentFilter = 'LIVE';", context);
    // Reloj fijo: 21:30 en Madrid (el Celta va por el minuto 21).
    const RealDate = Date;
    const FIXED = RealDate.parse(__NOW__);
    class FakeDate extends RealDate {
        constructor(...args) { if (args.length === 0) { super(FIXED); } else { super(...args); } }
        static now() { return FIXED; }
        static parse(value) { return RealDate.parse(value); }
        static UTC(...args) { return RealDate.UTC(...args); }
    }
    context.__Date = FakeDate;
    vm.runInContext("Date = globalThis.__Date;", context);
"""


def _script(payload, extra=""):
    """Carga utils.js + state.js en una VM con reloj fijo y ejecuta `extra` dentro.

    `extra` corre dentro del contexto (no como script suelto) para ver las
    funciones globales que definen los dos ficheros.
    """
    base = (
        HARNESS.replace("__UTILS__", json.dumps(str(UTILS)))
        .replace("__STATE__", json.dumps(str(STATE)))
        .replace("__DATA__", json.dumps(payload))
        .replace("__NOW__", json.dumps(NOW_MADRID))
    )
    if not extra:
        return base
    return base + "\n    vm.runInContext(" + json.dumps(extra) + ", context);"


def _live_pairs(payload, tz="UTC"):
    return _run_node(
        _script(
            payload,
            """
        console.log(JSON.stringify(getLiveLeagueMatches().map(m => ({
            id: m.id,
            local: m.local || (m.home && m.home.name) || "",
            visitante: m.visitante || (m.away && m.away.name) || ""
        }))));
    """,
        ),
        env=tz,
    )


@pytest.mark.parametrize(
    "timezone",
    ["Europe/Madrid", "Atlantic/Canary", "Europe/London", "UTC", "America/New_York", "Asia/Tokyo"],
)
@requires_node
def test_directo_shows_the_live_match_in_every_timezone(timezone):
    """Con el Celta en juego, el DIRECTO lo ve desde cualquier huso.

    Antes este mismo payload dejaba el DIRECTO en «no hay partidos en juego»
    en todo el mundo salvo en la peninsula: el saque de las 21:00 de Madrid se
    leia en la zona del navegador y el partido parecia empezar mas tarde.
    """
    live = _live_pairs({"today_madrid": "2026-09-03", "live_matches": PANEL_LIVE}, tz=timezone)

    pairs = {f"{m['local']}|{m['visitante']}" for m in live}
    assert "Real Sociedad|Celta de Vigo" in pairs, f"el Celta no sale en DIRECTO con TZ={timezone}"
    assert "Toulouse|Lille" in pairs, f"la Ligue 1 tampoco depende de la quiniela (TZ={timezone})"


@requires_node
def test_directo_works_without_any_quiniela_match():
    """Un jueves de Liga: cero partidos de quiniela y directo en las 5 ligas."""
    live = _live_pairs(
        {"today_madrid": "2026-09-03", "partidos": [], "live_matches": PANEL_LIVE},
        tz="UTC",
    )

    assert len(live) == 2


@requires_node
def test_directo_falls_back_to_all_league_matches_without_server_list():
    """Sin `live_matches` (payload viejo) se deriva igual, en hora de Madrid."""
    live = _live_pairs(
        {
            "today_madrid": "2026-09-03",
            "partidos": [],
            "live_matches": [],
            "all_league_matches": PANEL_LIVE,
        },
        tz="UTC",
    )

    assert {m["id"] for m in live} == {1336404376, 1321394438}


@requires_node
def test_kickoff_is_read_in_madrid_time_not_in_the_browser_zone():
    """21:00 de Madrid es 19:00 UTC, se mire desde donde se mire."""
    result = _run_node(
        _script(
            {"today_madrid": "2026-09-03", "live_matches": PANEL_LIVE},
            """
        console.log(JSON.stringify({
            celta: parseMatchTimestamp(state.data.live_matches[0]),
            lille: parseMatchTimestamp(state.data.live_matches[1]),
            // `time` es el minuto ("21"), no la hora de saque.
            minutoNoSeUsaComoHora: parseMatchTimestamp({ added: "2026-09-03 21:00:00", time: "21" }),
            // Una quiniela sin horario confirmado manda hora "-".
            sinHorario: parseMatchTimestamp({ fecha_raw: "2026-09-03", hora: "-" }),
            horario: fixtureScheduleDisplay(state.data.live_matches[0])
        }));
    """,
        ),
        env="UTC",
    )

    assert result["celta"] == 1788462000000  # 2026-09-03T19:00:00Z == 21:00 en Madrid
    assert result["lille"] == 1788461100000  # 2026-09-03T18:45:00Z == 20:45 en Madrid
    # Sin hora de saque fiable no se inventa una: inventarla daba el partido
    # por caducado (y por tanto fuera del DIRECTO) mientras estaba en juego.
    assert result["minutoNoSeUsaComoHora"] is None
    assert result["sinHorario"] is None
    assert result["horario"] == "21:00h"


@requires_node
def test_a_match_that_has_not_kicked_off_is_not_shown_as_live():
    """El reloj de Madrid no puede inventar un directo antes del saque."""
    future = [dict(PANEL_LIVE[0], added="2026-09-03 23:30:00", scheduled="23:30")]

    live = _live_pairs(
        {"today_madrid": "2026-09-03", "partidos": [], "live_matches": [], "all_league_matches": future},
        tz="UTC",
    )

    assert live == [], "un partido que no ha empezado no puede salir como en juego"


@requires_node
def test_the_same_match_is_never_listed_twice():
    """El Celta llega por la quiniela y por el panel: una sola tarjeta."""
    quiniela = [
        {
            "id": 3,
            "local": "Real Sociedad",
            "visitante": "Celta de Vigo",
            "status": "LIVE",
            "marcador": "0-0 (21')",
            "minuto": "21",
            "fecha_raw": "2026-09-03",
            "hora": "21:00",
        }
    ]

    live = _live_pairs(
        {
            "today_madrid": "2026-09-03",
            "partidos": quiniela,
            "live_matches": [],
            "all_league_matches": PANEL_LIVE,
        },
        tz="UTC",
    )

    celtas = [m for m in live if "Celta" in (m["local"] + m["visitante"])]
    assert len(celtas) == 1


def test_directo_deep_link_is_not_a_404(tmp_path, monkeypatch):
    """«VER DIRECTO COMPLETO» apunta a /directo: no puede acabar en 404.

    La vista vive dentro de la SPA (``?view=LIVE``), asi que la ruta publica
    solo tiene que llevar hasta ahi sin perder la jornada de la URL.
    """
    import config
    from liga_maestros import create_app

    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "directo.db"))
    monkeypatch.setattr(config, "BOOTSTRAP_DB_PATH", str(tmp_path / "missing.db"))
    monkeypatch.setattr(config, "PRODUCTION_SEED_PATH", str(tmp_path / "missing-seed.json"))
    monkeypatch.setenv("SECRET_KEY", "directo-test-secret")
    monkeypatch.setenv("WEB_COLLECTOR_ENABLED", "0")
    monkeypatch.setenv("TRUSTED_HOSTS", "localhost,127.0.0.1,ligademaestros.alwaysdata.net")

    client = create_app().test_client()

    response = client.get("/directo")
    assert response.status_code == 302
    assert "view=LIVE" in response.headers["Location"]

    with_jornada = client.get("/directo?j=4")
    assert "j=4" in with_jornada.headers["Location"]
    assert "view=LIVE" in with_jornada.headers["Location"]
