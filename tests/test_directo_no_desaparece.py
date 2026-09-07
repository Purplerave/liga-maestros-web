"""Regresion: el DIRECTO no puede vaciarse con un partido en juego.

Cada test de aqui reproduce una averia real por la que un partido que se
estaba jugando (p. ej. el Celta un domingo por la tarde) no aparecia en la
pagina de DIRECTO. Son las tres capas donde se perdia el partido:

1. Parseo del horario del proveedor: un formato de fecha distinto dejaba el
   saque en None y la ventana de refresco nunca se abria.
2. Traduccion del estado del proveedor: una descripcion no contemplada caia
   en "NS" y el partido se escribia como no empezado.
3. Filtro del payload: la lista de estados en juego estaba incompleta y un
   partido en segunda parte / prorroga se caia de la lista.
"""

from datetime import datetime, timedelta

from liga_maestros.services import daily_matches
from liga_maestros.services.payloads import league_matches
from liga_maestros.utils import highlightly_match_to_panel, highlightly_status, parse_provider_datetime

# --- 1. Horarios del proveedor en cualquier formato -------------------------


def test_kickoff_se_lee_en_todos_los_formatos_del_proveedor():
    esperado = datetime(2026, 9, 7, 18, 15)  # 16:15 UTC -> 18:15 Madrid (verano)
    for raw in (
        "2026-09-07T16:15:00.000Z",
        "2026-09-07T16:15:00Z",
        "2026-09-07T18:15:00+02:00",
        "2026-09-07 16:15:00",
    ):
        assert parse_provider_datetime(raw) == esperado, f"no se parseo {raw}"


def test_ventana_de_directo_se_abre_con_fecha_sin_milisegundos(monkeypatch):
    """La averia original: sin milisegundos el saque era None y no habia ventana."""
    agenda = {"date": "2026-09-07", "matches": [{"id": 1, "kickoff": "2026-09-07T16:15:00Z"}]}
    monkeypatch.setattr(daily_matches, "madrid_now", lambda: datetime(2026, 9, 7, 18, 30))
    assert daily_matches.any_live_window_open(agenda) is True


def test_ventana_abierta_antes_del_saque_para_no_llegar_tarde(monkeypatch):
    """El refresco debe estar activo YA cuando el arbitro pita el inicio."""
    agenda = {"date": "2026-09-07", "matches": [{"id": 1, "kickoff": "2026-09-07T16:15:00.000Z"}]}
    monkeypatch.setattr(daily_matches, "madrid_now", lambda: datetime(2026, 9, 7, 18, 5))
    assert daily_matches.any_live_window_open(agenda) is True


def test_ventana_sigue_abierta_en_el_descuento_de_un_partido_largo(monkeypatch):
    agenda = {"date": "2026-09-07", "matches": [{"id": 1, "kickoff": "2026-09-07T16:15:00.000Z"}]}
    monkeypatch.setattr(daily_matches, "madrid_now", lambda: datetime(2026, 9, 7, 21, 45))
    assert daily_matches.any_live_window_open(agenda) is True


# --- 2. Estados del proveedor ----------------------------------------------


def test_estados_en_juego_no_se_traducen_como_no_empezado():
    for desc in ("Second half", "2H", "In progress", "Extra time", "Penalties", "In play"):
        status, _ = highlightly_status({"description": desc, "clock": "63"})
        assert status == "LIVE", f"{desc} deberia ser LIVE"


def test_descripcion_desconocida_con_reloj_en_marcha_es_directo():
    """Blindaje: si el reloj corre, el partido se esta jugando."""
    status, minute = highlightly_status({"description": "Second Half - stoppage", "clock": "88"})
    assert status == "LIVE"
    assert minute == "88'"


def test_descanso_es_directo_y_no_no_empezado():
    assert highlightly_status({"description": "Half time", "clock": ""}) == ("LIVE", "HT")


def test_partido_sin_empezar_sigue_siendo_no_empezado():
    assert highlightly_status({"description": "Not started", "clock": ""})[0] == "NS"


# --- 3. El payload del DIRECTO conserva el partido --------------------------


def _celta_en_juego(status="2H"):
    return {
        "id": 777,
        "fixture_id": 777,
        "status": status,
        "score": "1 - 0",
        "time": "63",
        "added": "2026-09-07 18:15:00",
        "fecha_raw": "2026-09-07",
        "hora": "18:15",
        "competition_name": "LA LIGA",
        "competition": {"name": "LA LIGA"},
        "home": {"name": "Celta de Vigo"},
        "away": {"name": "Girona FC"},
        "local": "Celta de Vigo",
        "visitante": "Girona FC",
    }


def test_celta_en_segunda_parte_aparece_en_el_directo(monkeypatch):
    """La averia del usuario: estado 2H no estaba en la lista y se perdia."""
    monkeypatch.setattr(league_matches, "today_madrid", lambda: "2026-09-07")
    monkeypatch.setattr(league_matches, "madrid_now", lambda: datetime(2026, 9, 7, 19, 20))
    monkeypatch.setattr(league_matches, "_load_external_matches", lambda: [_celta_en_juego()])

    live = league_matches.build_live_matches([], {}, {})

    assert len(live) == 1
    assert live[0]["local"] == "Celta de Vigo"


def test_todos_los_estados_en_juego_sobreviven_al_payload(monkeypatch):
    monkeypatch.setattr(league_matches, "today_madrid", lambda: "2026-09-07")
    monkeypatch.setattr(league_matches, "madrid_now", lambda: datetime(2026, 9, 7, 19, 20))
    for status in ("LIVE", "IN PLAY", "IN_PLAY", "1H", "2H", "HT", "ET", "EN JUEGO"):
        monkeypatch.setattr(league_matches, "_load_external_matches", lambda s=status: [_celta_en_juego(s)])
        live = league_matches.build_live_matches([], {}, {})
        assert len(live) == 1, f"el estado {status} desaparecio del DIRECTO"


def test_panel_guarda_fecha_hora_y_sello_de_frescura():
    """Sin fecha/hora propias el cierre de directos tenia que adivinar el saque."""
    panel = highlightly_match_to_panel(
        {
            "id": 777,
            "date": "2026-09-07T16:15:00Z",
            "_competition_name": "LA LIGA",
            "homeTeam": {"name": "Celta de Vigo"},
            "awayTeam": {"name": "Girona FC"},
            "state": {"description": "Second half", "clock": "63", "score": {"current": "1 - 0"}},
        }
    )
    assert panel["status"] == "IN PLAY"
    assert panel["fecha_raw"] == "2026-09-07"
    assert panel["hora"] == "18:15"
    assert panel["updated_at"]


def test_directo_del_panel_mantiene_el_refresco_aunque_falte_en_la_agenda(tmp_path, monkeypatch):
    """Red de seguridad: un directo ya visible nunca se queda sin refrescos."""
    import config

    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(daily_matches, "today_madrid", lambda: "2026-09-07")
    (tmp_path / "LIVE_ALL_MATCHES_V3.json").write_text(
        '[{"id": 777, "status": "IN PLAY", "fecha_raw": "2026-09-07"}]', encoding="utf-8"
    )
    assert daily_matches._panel_has_live_match() is True


def test_agenda_vacia_se_reintenta_en_vez_de_bloquear_el_dia(tmp_path, monkeypatch):
    """Si la primera pasada del dia salio vacia, hay que volver a preguntar."""
    import config

    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(daily_matches, "today_madrid", lambda: "2026-09-07")
    monkeypatch.setattr(daily_matches, "madrid_now", lambda: datetime(2026, 9, 7, 12, 0))

    llamadas = []

    def fake_fetch(date_text=None):
        llamadas.append(date_text)
        # Primera pasada: el proveedor aun no publica nada. Segunda: ya si.
        if len(llamadas) == 1:
            return []
        return [
            {
                "id": 777,
                "date": "2026-09-07T16:15:00Z",
                "_competition_name": "LA LIGA",
                "homeTeam": {"name": "Celta de Vigo"},
                "awayTeam": {"name": "Girona FC"},
                "state": {"description": "Not started", "score": {"current": ""}},
            }
        ]

    monkeypatch.setattr(daily_matches, "fetch_today_agenda", fake_fetch)

    primera = daily_matches.refresh_daily_agenda()
    segunda = daily_matches.refresh_daily_agenda()

    assert primera["matches"] == []
    assert len(llamadas) == 2, "una agenda vacia debe reintentarse el mismo dia"
    assert segunda["matches"][0]["home"] == "Celta de Vigo"


def test_agenda_con_partidos_no_se_repregunta_sin_necesidad(tmp_path, monkeypatch):
    """El reintento no puede convertirse en gasto de cuota."""
    import config

    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(daily_matches, "today_madrid", lambda: "2026-09-07")
    monkeypatch.setattr(daily_matches, "madrid_now", lambda: datetime(2026, 9, 7, 12, 0))

    llamadas = []

    def fake_fetch(date_text=None):
        llamadas.append(date_text)
        return [
            {
                "id": 777,
                "date": "2026-09-07T16:15:00Z",
                "_competition_name": "LA LIGA",
                "homeTeam": {"name": "Celta de Vigo"},
                "awayTeam": {"name": "Girona FC"},
                "state": {"description": "Not started", "score": {"current": ""}},
            }
        ]

    monkeypatch.setattr(daily_matches, "fetch_today_agenda", fake_fetch)

    daily_matches.refresh_daily_agenda()
    daily_matches.refresh_daily_agenda()

    assert len(llamadas) == 1


def test_el_tracker_despierta_a_tiempo_para_el_siguiente_saque(tmp_path, monkeypatch):
    """No se puede dormir 15 min si el partido empieza en 3."""
    import config

    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(daily_matches, "today_madrid", lambda: "2026-09-07")
    monkeypatch.setattr(daily_matches, "madrid_now", lambda: datetime(2026, 9, 7, 17, 50))

    agenda = {"date": "2026-09-07", "matches": [{"id": 1, "kickoff": "2026-09-07T16:15:00.000Z"}]}
    espera = daily_matches._seconds_until_next_window(agenda)

    # Ventana abierta a las 17:55 (18:15 - 20 min): quedan 5 minutos.
    assert espera == timedelta(minutes=5).total_seconds()
