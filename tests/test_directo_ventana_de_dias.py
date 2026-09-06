"""La ventana de dias del directo: el sabado no desaparece el domingo.

El aviso era «hay partidos de ayer que no aparecen». El navegador tenia dos
filtros de calendario: `getTodayLeagueMatches`/`getAllTodayLeagueMatches` con
`fecha == hoy` y `getLeagueMatchesWindow` con `fecha >= hoy`. Al pasar la
medianoche el sabado entero se caia del DIRECTO y de la portada, y el lunes ya no
habia forma de revisar el finde.

La ventana correcta es rodada (ayer..manana), se extiende a la jornada en curso
mientras no haya quedado atras del todo, y cualquier partido en juego se ensene
sea del dia que sea. El «hoy» lo fija el servidor (`today_madrid`, hora de
Madrid), no el movil de cada uno: con el telefono en UTC o de viaje, la jornada
cambiaba de dia a otra hora.

Se ejecutan `static/js/utils.js` y `static/js/state.js` tal cual los carga el
navegador, con reloj y zona del navegador controlados.
"""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
UTILS = ROOT / "static" / "js" / "utils.js"
STATE = ROOT / "static" / "js" / "state.js"

requires_node = pytest.mark.skipif(
    shutil.which("node") is None, reason="Node is required to exercise browser utilities"
)


def _match(match_id, date_text, status="FINISHED", hour="21:30", competition="LA LIGA", score="2-1", minute=""):
    """Fila del panel tal y como la deja el proveedor, con su minuto real.

    El minuto tiene que cuadrar con el saque: un 63' en un partido que empezo hacia
    35 minutos es la sena de un directo congelado y la web lo cierra, asi que las
    filas en juego de las pruebas se construyen con `minute` coherente.
    """
    return {
        "id": match_id,
        "fixture_id": match_id,
        "status": status,
        "score": score,
        "time": minute if status != "FINISHED" else "",
        "added": f"{date_text} {hour}:00",
        "fecha_raw": date_text,
        "hora": hour,
        "scheduled": hour,
        "competition_name": competition,
        "competition": {"name": competition},
        "home": {"name": f"Local {match_id}"},
        "away": {"name": f"Visitante {match_id}"},
    }


# Finde de la jornada 4: sabado 05/09 (dos partidos) y domingo 06/09 (uno).
SATURDAY = [_match(11, "2026-09-05"), _match(12, "2026-09-05", hour="19:30")]
SUNDAY = [_match(13, "2026-09-06")]
ANCIENT = [_match(14, "2026-08-20")]


def _payload(today_madrid, panel, **extra):
    payload = {
        "jornada": "4",
        "today_madrid": today_madrid,
        "all_league_matches": panel,
        "partidos": [],
        "live_matches": [],
    }
    payload.update(extra)
    return payload


HARNESS = """
    const fs = require("fs");
    const vm = require("vm");
    const context = { console, Map, Set, String, Number, Date, JSON, Array, Object, Boolean, RegExp, Math,
                      parseInt, isNaN, Intl, URLSearchParams, encodeURIComponent, setTimeout };
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
    vm.runInContext("state.data = DATA;", context);
    // Reloj del navegador: se fija al instante pedido para poder simular la
    // madrugada del domingo y el huso local.
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


def _run(expression, payload, now, timezone="UTC"):
    script = (
        HARNESS.replace("__UTILS__", json.dumps(str(UTILS)))
        .replace("__STATE__", json.dumps(str(STATE)))
        .replace("__DATA__", json.dumps(payload))
        .replace("__NOW__", json.dumps(now))
        + "\n    vm.runInContext("
        + json.dumps(f"console.log(JSON.stringify({expression}));")
        + ", context);"
    )
    result = subprocess.run(
        ["node", "-e", script],
        cwd=ROOT,
        check=True,
        capture_output=True,
        encoding="utf-8",
        env=dict(os.environ, TZ=timezone),
    )
    return json.loads(result.stdout)


@requires_node
def test_el_domingo_a_la_madrugada_se_siguen_vi_endo_los_del_sabado():
    """00:20 del domingo: lo jugado la víspera sigue en la ventana del directo."""
    payload = _payload("2026-09-06", SATURDAY + SUNDAY + ANCIENT)

    ids = _run("getLeagueMatchesWindow().map(m => m.id)", payload, "2026-09-05T22:20:00Z")

    assert set(ids) == {11, 12, 13}, "el sabado no puede evaporarse al cambiar de dia"
    assert 14 not in ids, "y una jornada de agosto no puede inundar el directo"


@requires_node
def test_sin_partidos_hoy_el_directo_saca_los_de_ayer():
    """Domingo sin futbol programado: el estado vacio muestra lo del sabado."""
    payload = _payload("2026-09-06", SATURDAY)

    today = _run("getAllTodayLeagueMatches().map(m => m.id)", payload, "2026-09-06T07:00:00Z")
    portada = _run("getTodayLeagueMatches().map(m => m.id)", payload, "2026-09-06T07:00:00Z")

    assert today == [12, 11], "el listado del dia cae a la vispera cuando hoy esta vacio"
    assert portada == [12, 11], "igual que la portada"


@requires_node
def test_orden_cronologico_real_no_por_texto_de_fecha():
    """El orden es por saque: las 19:30 del sabado van antes que las 21:30 del sabado."""
    payload = _payload("2026-09-06", SATURDAY + SUNDAY)

    ids = _run("getLeagueMatchesWindow().map(m => m.id)", payload, "2026-09-05T22:20:00Z")

    assert ids == [12, 11, 13]


@requires_node
def test_la_jornada_de_finde_se_sigue_vi_el_lunes():
    """Lunes por la mañana: la ventana se estira a toda la jornada en curso."""
    quiniela = [
        {
            "id": 1,
            "local": "Rayo",
            "visitante": "Girona",
            "status": "FT",
            "marcador": "2-1",
            "fecha_raw": "2026-09-05",
            "hora": "21:30",
            "minuto": "Finalizado",
        },
        {
            "id": 2,
            "local": "Valencia",
            "visitante": "Barcelona",
            "status": "FT",
            "marcador": "1-3",
            "fecha_raw": "2026-09-06",
            "hora": "21:30",
            "minuto": "Finalizado",
        },
    ]
    payload = _payload("2026-09-07", SATURDAY + SUNDAY, partidos=quiniela)

    ids = _run("getLeagueMatchesWindow().map(m => m.id)", payload, "2026-09-07T07:00:00Z")

    assert {11, 12, 13} <= set(ids), "el finde tiene que poder revisarse el lunes"


@requires_node
def test_un_partido_en_juego_se_ensena_siempre():
    """Directo del sabado que se alarga hasta la madrugada del domingo."""
    live = _match(15, "2026-09-05", status="IN PLAY", hour="23:45", score="0-1", minute="68")
    payload = _payload("2026-09-06", [live], live_matches=[live])

    relevant = _run(
        "getLeagueMatchesWindow().map(m => m.id)",
        payload,
        "2026-09-05T22:55:00Z",
    )
    stale = _run(
        "isRelevantDirectoMatch({id: 16, status: 'IN PLAY', fecha_raw: '2026-09-01', added: '2026-09-01 21:30:00'})",
        payload,
        "2026-09-06T07:00:00Z",
    )

    assert 15 in relevant
    assert stale is False, "un directo congelado de hace cinco dias no resucita"


@pytest.mark.parametrize("timezone", ["Europe/Madrid", "Atlantic/Canary", "UTC", "Etc/GMT+11", "Asia/Tokyo"])
@requires_node
def test_la_ventana_no_depende_del_huso_del_navegador(timezone):
    """El «hoy» lo manda el servidor: un movil en UTC-11 ve el mismo finde.

    Con el reloj local, en `Etc/GMT+11` aun era viernes y el sabado se filtraba
    como «futuro»; en Asia/Tokyo ya era lunes y el domingo desaparecia.
    """
    payload = _payload("2026-09-06", SATURDAY + SUNDAY)

    ids = _run("getLeagueMatchesWindow().map(m => m.id)", payload, "2026-09-05T22:20:00Z", timezone=timezone)

    assert set(ids) == {11, 12, 13}, f"la ventana cambia con el huso (TZ={timezone})"


@requires_node
def test_etiqueta_de_horario_ayer_hoy_y_manana():
    """La etiqueta del boleto dice cuando el partido no es de hoy.

    `17:00h` a secas dejaba un resultado del sabado colgado el domingo sin decir de
    que dia era, que es justo la sensacion de «las horas estan mal».
    """
    yesterday = _match(11, "2026-09-05")
    today = _match(13, "2026-09-06")
    tomorrow = _match(16, "2026-09-07")

    texto_ayer = _run(
        "fixtureScheduleDisplay(state.data.all_league_matches[0])",
        _payload("2026-09-06", [yesterday]),
        "2026-09-05T22:20:00Z",
    )
    texto_hoy = _run(
        "fixtureScheduleDisplay(state.data.all_league_matches[0])",
        _payload("2026-09-06", [today]),
        "2026-09-05T22:20:00Z",
    )
    texto_manana = _run(
        "fixtureScheduleDisplay(state.data.all_league_matches[0])",
        _payload("2026-09-05", [tomorrow]),
        "2026-09-04T22:20:00Z",
    )

    assert texto_ayer.startswith("Ayer") and "21:30h" in texto_ayer, texto_ayer
    assert "05/09" in texto_ayer, texto_ayer
    assert texto_hoy == "21:30h", texto_hoy
    assert "07/09" in texto_manana and "21:30h" in texto_manana, texto_manana


@requires_node
def test_match_kickoff_date_text_para_todas_las_formas():
    """El dia del saque se deduce igual del boleto, del panel y del texto UTC."""
    cases = [
        {"fecha_raw": "2026-09-05", "hora": "21:30"},
        {"fecha": "2026-09-05", "hora": "21:30"},
        {"added": "2026-09-05 21:30:00", "hora": "21:30"},
        {"date": "2026-09-05T19:30:00.000Z"},  # UTC crudo del proveedor -> dia Madrid
        {"fecha_raw": "2026-09-05"},  # sin hora: al menos el dia
    ]

    days = _run(
        "state.data.all_league_matches.map(c => matchKickoffDateText(c))",
        {"today_madrid": "2026-09-06", "partidos": [], "live_matches": [], "all_league_matches": cases},
        "2026-09-05T22:20:00Z",
    )

    assert days == ["2026-09-05"] * 5, "ninguna forma de la fecha puede perder el partido"


@requires_node
def test_de_la_api_al_navegador_sin_perder_el_sabado(tmp_path, monkeypatch):
    """Recorrido completo del finde: lo que arma el servidor es lo que pinta el DOM.

    Se construye el payload con los mismos helpers de /api/liga/data (panel del
    proveedor + `validate_liga_data`, que es donde se perdian los campos) y se
    mete tal cual en `utils.js`/`state.js`. Si alguna de las dos mitis volviera a
    filtrar por "fecha == hoy", el partido del sabado desaparece de la lista y
    este test lo pilla.
    """
    import json as _json

    from liga_maestros.schemas import validate_liga_data
    from liga_maestros.utils import MADRID_TZ

    panel = [
        # Sabado 05/09 con resultado confirmado: es el que "no aparecia".
        _match(101, "2026-09-05"),
        # Sabado 23:45, visto el domingo a las 00:20: sigue en juego.
        _match(
            102, "2026-09-05", status="IN PLAY", hour="23:45", score="0-0", competition="SEGUNDA DIVISION", minute="41"
        ),
        # jornada vieja: no debe colarse.
        _match(103, "2026-08-20", hour="19:00"),
    ]
    panel_file = tmp_path / "LIVE_ALL_MATCHES_V3.json"
    panel_file.write_text(_json.dumps(panel), encoding="utf-8")

    from liga_maestros.services.payloads import league_matches

    monkeypatch.setattr(league_matches.config, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(league_matches.config, "BASE_DIR", str(tmp_path))
    monkeypatch.setattr(league_matches, "today_madrid", lambda: "2026-09-06")
    monkeypatch.setattr(
        league_matches, "madrid_now", lambda: __import__("datetime").datetime(2026, 9, 6, 0, 20, tzinfo=MADRID_TZ)
    )

    all_matches = league_matches.build_all_league_matches("", [], {}, {})
    payload = {
        "jornada": "4",
        "partidos": [],
        "all_league_matches": all_matches,
        "live_matches": league_matches.build_live_matches([], {}),
        "today_madrid": "2026-09-06",
    }
    payload, error = validate_liga_data(payload)
    assert error is None, error
    assert {match["id"] for match in payload["all_league_matches"]} == {101, 102}

    ids = _run("getLeagueMatchesWindow().map(m => m.id)", payload, "2026-09-05T22:20:00Z")
    live_ids = _run("getLiveLeagueMatches().map(m => m.id)", payload, "2026-09-05T22:20:00Z")

    assert set(ids) == {101, 102}, "el navegador tiene que ver lo mismo que sirvio el servidor"
    assert live_ids == [102], "y el unico en juego, el que aun no ha terminado"


@requires_node
def test_sin_reloj_del_servidor_no_se_descarta_nada():
    """Payload sin `today_madrid`: mejor ensenar de mas que perder el finde."""
    payload = {"jornada": "4", "partidos": [], "all_league_matches": SATURDAY + SUNDAY + ANCIENT}

    ids = _run("getLeagueMatchesWindow().map(m => m.id)", payload, "2026-09-05T22:20:00Z")

    assert 11 in ids and 12 in ids and 13 in ids
