"""Las horas son de Madrid y el finde no se pierde.

Tres averias que se repetian TODOS los findes de semana, cada una con su test:

1. **La hora mal.** El proveedor habla en UTC y el contrato de la web es que todas
   las horas que se sirven son reloj de Madrid sin zona. El parser solo admitia
   `2026-09-05T21:00:00.000Z`; cualquier variante (`...T21:00:00Z`, sin
   milisegundos, con offset) caia al `except` y devolvia el texto CRUDO en UTC: el
   saque de las 21:30 se pintaba a las 19:30 y, en los partidos que empiezan
   despues de las 00:00 UTC, hasta cambiaba de dia. Lo mismo en el propio servidor:
   `datetime.now()` y `datetime.fromtimestamp(ts)` sin zona en un Alwaysdata que
   corre en UTC retrasaban dos horas el «ultima sincronizacion».

2. **Los partidos de ayer desaparecian.** `build_all_league_matches` filtraba por
   `fecha == hoy` y el navegador, ademas, por `fecha >= hoy`. Con el cambio de dia
   el sabado entero se evaporaba del directo.

3. **No se actualizaban.** La ventana del collector se cerraba 24 horas despues del
   saque y las filas sin horario (scrape que no lo leyo) no la abrian nunca: lo que
   no se capturo el sabado por la noche no se capturaba jams.
"""

import ast
import json
import pathlib
import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

import config
from liga_maestros.services.payloads import league_matches
from liga_maestros.services.payloads.matches import build_jornada_matches
from liga_maestros.utils import (
    highlightly_match_to_panel,
    kickoff_date_text,
    parse_any_match_datetime,
    parse_provider_datetime,
)

MADRID = ZoneInfo("Europe/Madrid")
ROOT = pathlib.Path(__file__).resolve().parents[1]


def _load_tool(relative_path, module_name):
    """Carga un script de tools/ como modulo (son ficheros sueltos, no paquetes)."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(module_name, (ROOT / relative_path).resolve())
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------- hora Madrid


def test_parse_provider_datetime_a_madrid_en_todas_las_variantes():
    """UTC con/sin milisegundos y con offset acaban en el mismo reloj de Madrid."""
    expected = datetime(2026, 9, 5, 21, 30)
    for raw in (
        "2026-09-05T19:30:00.000Z",
        "2026-09-05T19:30:00Z",
        "2026-09-05T19:30:00+00:00",
        "2026-09-05T21:30:00+02:00",
        "2026-09-05 21:30:00",  # texto de Madrid, como lo sirve la propia web
        "2026-09-05 21:30",
    ):
        assert parse_provider_datetime(raw) == expected, raw
    assert parse_provider_datetime("") is None
    assert parse_provider_datetime("no es una fecha") is None


def test_parse_provider_datetime_acepta_epoch():
    stamp = datetime(2026, 9, 5, 19, 30, tzinfo=ZoneInfo("UTC")).timestamp()
    assert parse_provider_datetime(str(int(stamp))) == datetime(2026, 9, 5, 21, 30)
    assert parse_provider_datetime(str(int(stamp * 1000))) == datetime(2026, 9, 5, 21, 30)


def test_panel_de_highlightly_pinta_la_hora_de_madrid_y_su_dia():
    """El partido de las 21:30 (19:30 UTC) sale a las 21:30 y en el dia correcto."""
    for payload_date in ("2026-09-05T19:30:00.000Z", "2026-09-05T19:30:00Z"):
        panel = highlightly_match_to_panel(
            {
                "id": 4242,
                "date": payload_date,
                "state": {"description": "Not started", "score": {"current": ""}},
                "homeTeam": {"name": "Rayo Vallecano"},
                "awayTeam": {"name": "Girona"},
            }
        )
        assert panel["added"] == "2026-09-05 21:30:00", payload_date
        assert panel["scheduled"] == "21:30", payload_date
        assert panel["fecha_raw"] == "2026-09-05", payload_date
        assert panel["hora"] == "21:30", payload_date


def test_panel_de_un_partido_de_madrugada_no_cambia_de_dia():
    """23:55 UTC del sabado son 01:55 del domingo en Madrid: el dia es el domingo."""
    panel = highlightly_match_to_panel(
        {
            "id": 9,
            "date": "2026-09-05T23:55:00Z",
            "state": {"description": "First half"},
            "homeTeam": {"name": "A"},
            "awayTeam": {"name": "B"},
        }
    )
    assert panel["fecha_raw"] == "2026-09-06"
    assert panel["added"].startswith("2026-09-06 01:55")


def test_fila_panel_legada_en_texto_utc_crudo_se_reconvierte():
    """Las filas escritas por el parser viejo siguen en el JSON: se releen bien."""
    legacy = {"id": 1, "date": "2026-09-05T19:30:00.000Z", "added": "2026-09-05T19:30:00.000Z"}
    assert parse_any_match_datetime(legacy) == datetime(2026, 9, 5, 21, 30)
    assert kickoff_date_text(legacy) == "2026-09-05"


def test_sello_de_frescura_del_panel():
    panel = highlightly_match_to_panel(
        {"id": 3, "date": "2026-09-06T19:00:00Z", "homeTeam": {"name": "A"}, "awayTeam": {"name": "B"}},
        updated_at="2026-09-06T21:00:03+02:00",
    )
    assert panel["updated_at"] == "2026-09-06T21:00:03+02:00"


def test_en_la_web_no_quedan_relojes_naive():
    """`datetime.now()` en un servidor UTC son las 19:00 cuando en Madrid son las 21:00.

    Comprobacion estructural sobre el arbol: toda la hora que se pinta o se compara
    en la web tiene que salir de `madrid_now()` / `to_madrid_naive()`. Se analiza el
    AST para que no cuenten comentarios ni cadenas de texto.
    """
    offenders = []
    for path in sorted(pathlib.Path("liga_maestros").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
            if name in {"now", "utcnow", "today"} and not node.args and not node.keywords:
                if ast.unparse(node).startswith(("datetime.", "date.")):
                    offenders.append(f"{path}:{node.lineno}: {ast.unparse(node)}")
            if name == "fromtimestamp" and len(node.args) < 2 and not node.keywords:
                offenders.append(f"{path}:{node.lineno}: fromtimestamp sin zona")

    assert offenders == [], "horas naive que el huso de Madrid puede mover un dia entero"


# ------------------------------------------------- partidos de ayer / de hoy


def _panel_match(match_id, date_text, status="FINISHED", score="2-1", competition="LA LIGA"):
    return {
        "id": match_id,
        "fixture_id": match_id,
        "status": status,
        "score": score,
        "added": f"{date_text} 21:30:00",
        "fecha_raw": date_text,
        "hora": "21:30",
        "scheduled": "21:30",
        "competition_name": competition,
        "competition": {"name": competition},
        "home": {"name": f"Local {match_id}"},
        "away": {"name": f"Visitante {match_id}"},
    }


@pytest.fixture()
def domingo_de_jornada(monkeypatch):
    """Hoy = domingo 6 de septiembre de 2026, 21:45, justo al cerrar el finde."""
    monkeypatch.setattr(league_matches, "today_madrid", lambda: "2026-09-06")
    monkeypatch.setattr(league_matches, "madrid_now", lambda: datetime(2026, 9, 6, 21, 45, tzinfo=MADRID))
    monkeypatch.setattr(league_matches, "PANEL_HISTORY_DAYS", 7)


def test_los_partidos_del_sabado_siguen_en_el_directo_el_domingo(domingo_de_jornada, monkeypatch):
    monkeypatch.setattr(
        league_matches,
        "_load_external_matches",
        lambda: [_panel_match(1, "2026-09-05"), _panel_match(2, "2026-09-06")],
    )

    matches = league_matches.build_all_league_matches("", [], {}, {})

    assert {match["id"] for match in matches} == {1, 2}, "el sabado no puede desaparecer el domingo"


def test_una_jornada_de_finde_se_ve_al_completo_el_lunes(domingo_de_jornada, monkeypatch):
    """Lunes: la jornada del sabado-domingo sigue visible mientras este en curso."""
    monkeypatch.setattr(league_matches, "today_madrid", lambda: "2026-09-07")
    monkeypatch.setattr(league_matches, "madrid_now", lambda: datetime(2026, 9, 7, 9, 0, tzinfo=MADRID))
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
    monkeypatch.setattr(
        league_matches,
        "_load_external_matches",
        lambda: [_panel_match(51, "2026-09-05"), _panel_match(52, "2026-09-06"), _panel_match(53, "2026-08-20")],
    )

    matches = league_matches.build_all_league_matches("4", quiniela, {}, {})
    ids = {match["id"] for match in matches}

    assert 51 in ids and 52 in ids, "el finde tiene que poder revisarse el lunes"
    assert 53 not in ids, "y una jornada de hace tres semanas no puede inundar el directo"


def test_un_directo_del_sabado_sigue_vivo_pasada_la_medianoche(domingo_de_jornada, monkeypatch):
    """Saque del sabado 23:45 visto el domingo a las 00:15: sigue en juego."""
    monkeypatch.setattr(league_matches, "madrid_now", lambda: datetime(2026, 9, 6, 0, 15, tzinfo=MADRID))
    live = _panel_match(77, "2026-09-05", status="IN PLAY", score="0-0")
    live["added"] = "2026-09-05 23:45:00"
    live["hora"] = "23:45"
    live["scheduled"] = "23:45"
    monkeypatch.setattr(league_matches, "_load_external_matches", lambda: [live])

    matches = league_matches.build_live_matches([], {})

    assert [match["id"] for match in matches] == [77]


def test_un_directo_congelado_de_hace_dias_no_resucita(domingo_de_jornada, monkeypatch):
    stale = _panel_match(78, "2026-09-01", status="IN PLAY", score="0-0")
    monkeypatch.setattr(league_matches, "_load_external_matches", lambda: [stale])

    assert league_matches.build_live_matches([], {}) == []


def test_el_panel_se_rellena_though_la_fecha_venga_solo_en_utc_del_proveedor(domingo_de_jornada, monkeypatch):
    raw = {
        "id": 79,
        "date": "2026-09-06T19:30:00.000Z",
        "status": "IN PLAY",
        "score": "1-0",
        "competition_name": "LA LIGA",
        "home": {"name": "Sevilla"},
        "away": {"name": "Betis"},
    }
    monkeypatch.setattr(league_matches, "_load_external_matches", lambda: [raw])

    matches = league_matches.build_all_league_matches("", [], {}, {})

    assert [match["id"] for match in matches] == [79]


def test_la_retencion_del_panel_no_recorta_el_finde(monkeypatch):
    """El recorte de historial conserva los dias jugados, que es lo que se consulta."""
    monkeypatch.setattr(league_matches, "today_madrid", lambda: "2026-09-07")
    matches = [_panel_match(i, f"2026-09-{day:02d}") for i, day in enumerate([4, 5, 6, 7], start=1)]
    matches.append(_panel_match(99, "2026-08-01"))

    kept = league_matches._prune_panel_history(matches)

    assert {match["id"] for match in kept} == {1, 2, 3, 4}


# --------------------------------------------------------- ventana del collector


@pytest.fixture()
def conn_with_jornada():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE resultados (
            jornada INTEGER, partido_id INTEGER, local TEXT, visitante TEXT,
            status TEXT, fecha TEXT, hora TEXT, goles_local INTEGER, goles_visitante INTEGER
        )
        """
    )
    return conn


def _insert(conn, jornada, partido_id, fecha, hora, status, gl=None, gv=None):
    conn.execute(
        "INSERT INTO resultados (jornada, partido_id, local, visitante, status, fecha, hora,"
        " goles_local, goles_visitante) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (jornada, partido_id, f"L{partido_id}", f"V{partido_id}", status, fecha, hora, gl, gv),
    )


def test_la_ventana_sigue_abierta_30_horas_despues_del_saque(monkeypatch, conn_with_jornada):
    """El agujero del finde: con el collector caido, al dia siguiente hay que cerrar.

    Antes `needs_result_catchup` moria a las 24 horas del saque y la ventana se
    cerraba para siempre: el resultado del sabado ya no se pedia nunca.
    """
    from liga_maestros.services import highlightly

    monkeypatch.setattr(highlightly, "today_madrid", lambda: "2026-09-06")
    monkeypatch.setattr(highlightly, "madrid_now", lambda: datetime(2026, 9, 6, 3, 0, tzinfo=MADRID))
    _insert(conn_with_jornada, 4, 1, "2026-09-05", "21:30", "NS")

    window = highlightly.compute_refresh_window(conn_with_jornada, 4)

    assert window["enabled"] is True
    assert window["needs_result_catchup"] is True
    assert window["result_catchup_urgent"] is True


def test_un_stale_con_marcador_se_sigue_persiguiendo(monkeypatch, conn_with_jornada):
    """Marcador guardado + status STALE no es un cierre: hay que confirmar el FT."""
    from liga_maestros.services import highlightly

    monkeypatch.setattr(highlightly, "today_madrid", lambda: "2026-09-06")
    monkeypatch.setattr(highlightly, "madrid_now", lambda: datetime(2026, 9, 6, 12, 0, tzinfo=MADRID))
    _insert(conn_with_jornada, 4, 1, "2026-09-05", "21:30", "STALE", 2, 1)

    window = highlightly.compute_refresh_window(conn_with_jornada, 4)

    assert window["enabled"] is True
    assert window["needs_result_catchup"] is True


def test_jornada_sin_horarios_tambien_se_refresca(monkeypatch, conn_with_jornada):
    """Boleto importado sin fecha ni hora: antes la ventana nunca se abria.

    `data/horarios_J4.json` si que traia los horarios y el boleto no: de ahi el
    «no se actualiza» del sabado.
    """
    from liga_maestros.services import highlightly

    monkeypatch.setattr(highlightly, "today_madrid", lambda: "2026-09-06")
    monkeypatch.setattr(highlightly, "madrid_now", lambda: datetime(2026, 9, 6, 22, 0, tzinfo=MADRID))
    _insert(conn_with_jornada, 4, 1, "", "", "NS")

    window = highlightly.compute_refresh_window(conn_with_jornada, 4)

    assert window["enabled"] is True
    assert window["reason"] == "sin_horarios"


def test_jornada_cerrada_no_gasta_cuota(monkeypatch, conn_with_jornada):
    from liga_maestros.services import highlightly

    monkeypatch.setattr(highlightly, "today_madrid", lambda: "2026-09-06")
    monkeypatch.setattr(highlightly, "madrid_now", lambda: datetime(2026, 9, 6, 23, 30, tzinfo=MADRID))
    _insert(conn_with_jornada, 4, 1, "2026-09-05", "21:30", "FT", 2, 1)
    _insert(conn_with_jornada, 4, 2, "2026-09-06", "19:30", "FT", 0, 0)

    window = highlightly.compute_refresh_window(conn_with_jornada, 4)

    assert window["enabled"] is False
    assert window["needs_result_catchup"] is False


def test_aplazado_antiguo_baja_el_ritmo_sin_cerrarse(monkeypatch, conn_with_jornada):
    """Mas de 48 h: se sigue persiguiendo, pero 3 veces al dia en vez de cada 15 min."""
    from liga_maestros.services import highlightly

    monkeypatch.setattr(highlightly, "today_madrid", lambda: "2026-09-10")
    monkeypatch.setattr(highlightly, "madrid_now", lambda: datetime(2026, 9, 10, 12, 0, tzinfo=MADRID))
    _insert(conn_with_jornada, 4, 1, "2026-09-05", "21:30", "NS")

    window = highlightly.compute_refresh_window(conn_with_jornada, 4)

    assert window["enabled"] is True
    assert window["needs_result_catchup"] is True
    assert window["result_catchup_urgent"] is False


def test_refresh_dates_incluye_la_fecha_de_un_stale_con_marcador(monkeypatch, conn_with_jornada):
    from liga_maestros.services import highlightly

    monkeypatch.setattr(highlightly, "today_madrid", lambda: "2026-09-06")
    _insert(conn_with_jornada, 4, 1, "2026-09-05", "21:30", "STALE", 2, 1)
    _insert(conn_with_jornada, 4, 2, "2026-09-06", "19:30", "FT", 1, 1)

    assert highlightly.refresh_dates_for_jornada(conn_with_jornada, 4) == ["2026-09-05", "2026-09-06"]


def test_las_ligas_del_boleto_se_consultan_primero():
    """Con una sola llamada por pasada, la ultima liga del dict nunca se refrescaba.

    Las competiciones del boleto van delante; ninguna liga desaparece de la lista.
    """
    from liga_maestros.services import highlightly

    names = [name for name, _ in highlightly._ordered_leagues()]

    assert names[:2] == ["LA LIGA", "SEGUNDA DIVISION"]
    assert sorted(names) == sorted(config.HIGHLIGHTLY_LEAGUES.keys()), "no se puede dejar ninguna liga fuera"


def test_sueno_del_collector_segun_la_urgencia():
    module = _load_tool("tools/ops/LIVE_COLLECTOR.py", "LIVE_COLLECTOR_TEST")
    module.get_highlightly_circuit = lambda: {}  # sin circuito abierto: determinista

    # finde con el resultado pendiente: no se duerme 6 horas, cada 15 minutos
    assert (
        module.next_sleep_seconds({"enabled": True, "needs_result_catchup": True, "result_catchup_urgent": True}, 60)
        == 900
    )
    # aplazado de hace una semana: 3 pasadas al dia, pero la ventana sigue viva
    assert (
        module.next_sleep_seconds({"enabled": True, "needs_result_catchup": True, "result_catchup_urgent": False}, 60)
        == 6 * 3600
    )
    # jornada cerrada: el ritmo base, sin colarse un sueno infinito
    assert 60 <= module.next_sleep_seconds({"enabled": False, "reason": "ventana_jornada"}, 600) <= 300


# ----------------------------------------------------- horario del boleto (scrape)


@pytest.mark.parametrize(
    "detalle,expected",
    [
        # Tal y como lo escribe quiniela15.com: mes abreviado pegado a la hora.
        ("sábado 22 ago17:00h Estado de Forma (Últimos 6)", ("2026-08-22", "17:00")),
        ("sábado 5 sep21:30h", ("2026-09-05", "21:30")),
        ("domingo 6 de septiembre, 21:30 h", ("2026-09-06", "21:30")),
        ("viernes 4 septiembre 19:30h", ("2026-09-04", "19:30")),
        ("miércoles 23 dic 24:00h", ("2026-12-24", "00:00")),
        ("2026-08-23 19:00h", ("2026-08-23", "19:00")),
        ("Hoy 21:30h", ("2026-09-03", "21:30")),
        ("mañana a las 19:00", ("2026-09-04", "19:00")),
        # Sin horario no se inventa: mejor "por confirmar" que una hora falsa.
        ("Estado de Forma (Últimos 6) Athletic Clasificación: #15", ("", "")),
    ],
)
def test_scrape_boleto_extrae_dia_y_hora(detalle, expected):
    module = _load_tool("tools/scrapers/SCRAPE_QUINIELA15_PROXIMA.py", "SCRAPE_Q15_TEST")

    assert module.parse_detail_datetime(detalle, now=datetime(2026, 9, 3, 12, 0)) == expected


# ------------------------------------------------------ contrato del payload API


def test_validate_liga_data_conserva_lo_que_el_navegador_lee():
    """El payload se reconstruye desde el schema: lo no declarado se pierde.

    Perder `fecha_raw` bastaba para que un partido del sabado desapareciera el
    domingo: el navegador filtra por dia y sin fecha no hay nada que comparar.
    """
    from liga_maestros.schemas import MatchPayload, validate_liga_data

    partido = {
        "id": 3,
        "local": "Villarreal",
        "visitante": "Deportivo",
        "goles_local": None,
        "goles_visitante": None,
        "status": "NS",
        "fecha": "2026-09-05",
        "fecha_raw": "2026-09-05",
        "hora": "21:30",
        "minuto": "",
        "minuto_live": "",
        "marcador": "21:30h",
        "marcador_base": "",
        "logo_local": "/static/img/a.png",
        "logo_visitante": "/static/img/b.png",
        "signo_actual": "-",
        "resultado_pendiente": False,
        "updated_at": "2026-09-05T21:00:00+02:00",
    }
    payload = {"jornada": "4", "partidos": [partido], "today_madrid": "2026-09-06"}

    validated, error = validate_liga_data(payload)

    assert error is None
    served = validated["partidos"][0]
    for field in ("fecha_raw", "fecha", "minuto_live", "marcador_base", "logo_local", "updated_at"):
        assert field in served, f"el contrato de /api/liga/data perdi{field}"
    assert served["fecha_raw"] == "2026-09-05"
    assert {field for field in MatchPayload.model_fields} >= set(partido)


@pytest.fixture()
def conn_con_resultados():
    from liga_maestros.db.migrations import ensure_core_tables

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_core_tables(conn)
    conn.execute(
        "INSERT INTO resultados (jornada, partido_id, local, visitante, status, fecha, hora)"
        " VALUES (99, 1, 'Athletic Club', 'At. Madrid', 'NS', '2026-09-05', '17:00')"
    )
    conn.commit()
    yield conn
    conn.close()


def test_build_jornada_matches_devuelve_fecha_raw_y_hora(conn_con_resultados, monkeypatch):
    """Sin `fecha_raw` el navegador no puede filtrar por dia: el sabado se pierde.

    Ademas, el texto que ve el usuario lleva el dia cuando el partido no es de hoy:
    un resultado del sabado tiene que decir «sabado 05/09», no una hora suelta.
    """
    from liga_maestros.services.payloads import matches as matches_module

    partidos = build_jornada_matches(conn_con_resultados, "99", {})
    row = next(match for match in partidos if match["id"] == 1)

    assert len(partidos) == 15, "el boleto se sirve siempre con sus quince filas"
    assert row["fecha_raw"] == "2026-09-05"
    assert row["fecha"] == "2026-09-05"
    assert row["hora"] == "17:00"

    monkeypatch.setattr(matches_module, "today_madrid", lambda: "2026-09-05")
    on_its_own_day = next(match for match in build_jornada_matches(conn_con_resultados, "99", {}) if match["id"] == 1)
    assert on_its_own_day["marcador"] == "17:00h"

    monkeypatch.setattr(matches_module, "today_madrid", lambda: "2026-09-06")
    day_after = next(match for match in build_jornada_matches(conn_con_resultados, "99", {}) if match["id"] == 1)
    assert day_after["marcador"].endswith("17:00h") and "05/09" in day_after["marcador"]


def test_todos_los_campos_del_builder_estan_declarados_en_el_schema(conn_con_resultados):
    """Guardia del contrato: ningun campo que se pinta puede quedarse fuera.

    Si alguien anade una clave al builder y olvida `MatchPayload`, este test lo para
    antes de que llegue al navegador y desaparezca en silencio.
    """
    from liga_maestros.schemas import MatchPayload

    partidos = build_jornada_matches(conn_con_resultados, "99", {})
    undeclared = set(partidos[0]) - set(MatchPayload.model_fields)

    assert not undeclared, f"fuera del contrato: {sorted(undeclared)}"


def test_la_frescura_se_mide_sobre_el_fichero_que_se_esta_sirviendo(tmp_path, monkeypatch):
    """El aviso de datos viejos tiene que hablar del panel que se pinta.

    Con `LIVE_ALL_MATCHES_EXTRA_PATH` (o el `LIVE_ALL_MATCHES.json` legado) el
    navegador se quedaba sin edad del panel porque la frescura miraba solo el V3 de
    DATA_DIR: y sin frescura, un collector caido pasa por "no hay partido".
    """
    from liga_maestros.services.payloads import league_matches as panel_module

    extra = tmp_path / "PANEL_EXTRA.json"
    extra.write_text(json.dumps([_panel_match(1, "2026-09-06")]), encoding="utf-8")
    monkeypatch.setattr(panel_module.config, "DATA_DIR", str(tmp_path / "vacio"))
    monkeypatch.setattr(panel_module.config, "BASE_DIR", str(tmp_path / "vacio"))
    monkeypatch.setenv("LIVE_ALL_MATCHES_EXTRA_PATH", str(extra))

    matches = panel_module._load_external_matches()

    assert [match["id"] for match in matches] == [1]
    assert panel_module.panel_source_path() == str(extra)
    assert panel_module.panel_freshness_stamp() == pytest.approx(extra.stat().st_mtime)


def test_la_frescura_del_panel_sale_con_ofset_de_madrid(tmp_path, monkeypatch):
    """`panel_age_seconds` nace del mtime del panel, en hora de Madrid.

    El navegador ya no la adivina con `new Date(texto)`: un texto sin zona se leia
    en la hora local y el desfase dejaba el aviso de datos viejos sin saltar.
    """
    import os

    from liga_maestros.routes import liga_data as route_module

    panel = tmp_path / "LIVE_ALL_MATCHES_V3.json"
    panel.write_text("[]", encoding="utf-8")
    os.utime(panel, (0, 0))
    monkeypatch.setattr(route_module.config, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(route_module.config, "BASE_DIR", str(tmp_path / "sin-panel"))
    monkeypatch.delenv("LIVE_ALL_MATCHES_EXTRA_PATH", raising=False)
    from liga_maestros.services.payloads import league_matches as panel_module

    monkeypatch.setattr(panel_module, "_panel_source_path", None)

    stamp, age = route_module._panel_freshness()

    assert stamp and datetime.fromisoformat(stamp).tzinfo is not None, "debe salir con offset de Madrid"
    assert age and age > 0


# --------------------------------------------------------------- cierre en la web


def test_la_hora_de_ultima_sync_es_de_madrid():
    from liga_maestros.routes.live import _madrid_from_timestamp, _madrid_hm

    stamp = datetime(2026, 9, 5, 19, 4, tzinfo=ZoneInfo("UTC")).timestamp()
    assert _madrid_from_timestamp(stamp).strftime("%H:%M") == "21:04"
    assert _madrid_hm(stamp) == "21:04"
    assert _madrid_hm(None) == "--:--"


def test_fixture_schedule_label_saca_el_dia_cuando_no_es_hoy(monkeypatch):
    from liga_maestros.services.payloads import matches as matches_module

    monkeypatch.setattr(matches_module, "today_madrid", lambda: "2026-09-06")
    label = matches_module._fixture_schedule_label({"fecha": "2026-09-05", "hora": "17:00"}, "sábado 05/09")

    assert "17:00h" in label and "05/09" in label


def test_la_comentario_de_jornada_se_sella_en_madrid():
    """`created_at` de los comentarios lleva offset: el orden del hilo es el real."""
    source = pathlib.Path("liga_maestros/routes/comments.py").read_text(encoding="utf-8")

    assert "madrid_now().isoformat" in source


# -------------------------------------------------------------------- tracker


def test_backfill_no_da_por_cerrada_una_fecha_que_no_se_pudo_leer(monkeypatch, tmp_path):
    """Cuota agotada o circuito abierto el domingo por la noche: hay que reintentar.

    Antes la fecha se marcaba como procesada con cero partidos y nunca mas se volvia
    a pedir: asi es como un finde se quedaba sin resultados definitivamente.
    """
    from liga_maestros.services import daily_matches as tracker

    monkeypatch.setattr(tracker.config, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(tracker, "today_madrid", lambda: "2026-09-07")
    monkeypatch.setattr(tracker, "open_panel_dates", lambda limit=None: [])
    monkeypatch.setattr(tracker, "fetch_day_matches", lambda date_text: ([], True))

    assert tracker.backfill_recent_spanish_matches(days=2) == 0

    state_file = tmp_path / tracker.STATE_PATH
    state = json.loads(state_file.read_text(encoding="utf-8")) if state_file.exists() else {}
    assert state.get("backfilled_dates") in (None, []), "ninguna fecha puede quedar cerrada sin leerla"


def test_el_panel_con_partidos_abiertos_pide_el_dia_anterior(monkeypatch, tmp_path):
    from liga_maestros.services import daily_matches as tracker

    monkeypatch.setattr(tracker.config, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(tracker, "today_madrid", lambda: "2026-09-07")
    monkeypatch.setattr(tracker, "madrid_now", lambda: datetime(2026, 9, 7, 3, 0, tzinfo=MADRID))
    (tmp_path / "LIVE_ALL_MATCHES_V3.json").write_text(
        json.dumps(
            [
                {"id": 1, "status": "IN PLAY", "fecha_raw": "2026-09-06", "added": "2026-09-06 21:30:00"},
                {"id": 2, "status": "FINISHED", "fecha_raw": "2026-09-05", "added": "2026-09-05 19:30:00"},
            ]
        ),
        encoding="utf-8",
    )

    # la fila en juego de ayer sigue abierta: hay que refrescar su dia
    assert tracker.open_panel_dates() == ["2026-09-06"]
    assert tracker.panel_has_recent_live() is True
    # ... y deja de estarlo cuando ya hace mas de seis horas del saque
    monkeypatch.setattr(tracker, "madrid_now", lambda: datetime(2026, 9, 7, 9, 0, tzinfo=MADRID))
    assert tracker.panel_has_recent_live() is False


def test_saque_de_varias_formas_abre_la_ventana_de_directo(monkeypatch):
    from liga_maestros.services import daily_matches as tracker

    for raw in ("2026-09-06T19:30:00.000Z", "2026-09-06T19:30:00Z", "2026-09-06 21:30:00"):
        assert tracker._parse_kickoff(raw) == datetime(2026, 9, 6, 21, 30), raw

    monkeypatch.setattr(tracker, "today_madrid", lambda: "2026-09-06")
    monkeypatch.setattr(tracker, "madrid_now", lambda: datetime(2026, 9, 6, 21, 35, tzinfo=MADRID))
    agenda = {"date": "2026-09-06", "matches": [{"id": 1, "kickoff": "2026-09-06T19:30:00Z"}]}

    assert tracker.any_live_window_open(agenda) is True


# --------------------------------------------------------- servicios en hora Madrid


def test_el_radar_de_noticias_mide_con_el_reloj_de_madrid(monkeypatch):
    """Las RSS se publican en hora de Madrid; la ventana de frescura usa ese reloj.

    Con un `datetime.now()` de servidor UTC las dos fronteras se movian dos horas:
    se caia el ultimo titular del dia y se colaba el del dia siguiente.
    """
    from liga_maestros.services import news_radar

    monkeypatch.setattr(news_radar, "madrid_now", lambda: datetime(2026, 9, 6, 21, 0, tzinfo=MADRID))

    # dos horas por delante del reloj de referencia: entra con Madrid, caia con UTC
    assert news_radar._is_recent({"published_at": "2026-09-07 03:00"}) is True
    # justo en el borde de los siete dias: entra con Madrid, se caia con UTC
    assert news_radar._is_recent({"published_at": "2026-08-30 22:00"}) is True
    assert news_radar._is_recent({"published_at": "2026-08-30 19:00"}) is False


# ------------------------------------------------- un collector por despliegue


def test_un_solo_coleccionador_por_disco(tmp_path, monkeypatch):
    """Dos procesos del mismo despliegue no pueden ir a la vez a la API.

    Alwaysdata reinicia el proceso web sin esperar a que el hilo anterior muera, y
    un cron manual suma otro: cada uno gastaba cuota y escribia el panel por su
    cuenta. A mitad de la jornada del finde la cuota se agotaba y los resultados
    dejaban de llegar.
    """
    from liga_maestros.workers import web_collector as wc

    monkeypatch.setattr("config.DATA_DIR", str(tmp_path))

    first = wc._acquire_owner_lock()
    assert first is not None, "el primero es el dueno del collector"
    try:
        assert wc._acquire_owner_lock() is None, "el segundo no debe coleccionar ni duplicar llamadas"
    finally:
        first.close()  # cerrar el descriptor suelta el flock

    assert wc._acquire_owner_lock() is not None, "y cuando el dueno muere, el relevo se toma solo"
