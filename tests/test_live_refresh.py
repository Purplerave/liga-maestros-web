"""Refresco del directo bajo demanda (``services/live_refresh.py``).

Incidente del 22/11/2026 (J22, boleto SELAE 23): tras el despliegue de las
16:04 el hilo del colector se quedo colgado. El unico scrape de quiniela15 que
entro despues (17:03) fue el de primera pintura, que solo saltaba con casillas
en ventana todavia en NS. A las 17:33 la lectura segura de la portada cerro
como STALE «Sin datos» los tres partidos que se estaban jugando:

* #5  Racing - Real Sociedad (16:15), 2-1 en el 45'
* #9  Sporting - Las Palmas (16:15), 0-1 en el 45'
* #14 Tenerife (F) - Madrid CFF (17:00), 0-0 en el 2'

Sin marcador en la quiniela y fuera del DIRECTO mientras se jugaban.

Cubren:
- La decision se toma por frescura del dato, no por estado: LIVE, HT, STALE y
  NS en ventana cuentan; los finales confirmados y lo que esta fuera de
  ventana, no.
- Con la cache de quiniela15 recien escrita (colector sano) no se duplica.
- Un solo refresco a la vez, como mucho uno por minuto, y un refresco colgado
  se abandona sin acumular hilos sin fin.
- La ruta lanza el refresco en todas las variantes y no lo espera.
- De punta a punta: la foto de produccion se cura sola con la portada abierta.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

import config
from liga_maestros import create_app
from liga_maestros.db.connection import get_db
from liga_maestros.routes import liga_data
from liga_maestros.services import live_refresh
from liga_maestros.services.ticket import madrid_now

MADRID = ZoneInfo("Europe/Madrid")
# Foto de produccion: 22/11/2026 a las 17:45 (hora de Madrid).
NOW = datetime(2026, 11, 22, 17, 45)
Q15_STAMP = "2026-11-22T17:03:12+01:00"


def _row(partido_id, hora, status, updated_at, fecha="2026-11-22"):
    return {"partido_id": partido_id, "fecha": fecha, "hora": hora, "status": status, "updated_at": updated_at}


J22_SNAPSHOT = [
    _row(4, "14:00", "FT", "2026-11-22T15:58:40+01:00"),
    _row(5, "16:15", "LIVE", Q15_STAMP),
    _row(6, "18:30", "NS", None),
    _row(7, "21:00", "NS", None),
    _row(9, "16:15", "LIVE", Q15_STAMP),
    _row(10, "18:30", "NS", None),
    _row(12, "12:00", "FT", "2026-11-22T13:55:00+01:00"),
    _row(13, "12:00", "FT", "2026-11-22T13:55:00+01:00"),
    _row(14, "17:00", "LIVE", Q15_STAMP),
    _row(15, "18:30", "FT", "2026-11-21T20:25:00+01:00", fecha="2026-11-21"),
]


class TestDecision:
    def test_la_foto_de_produccion_pide_refresco_de_los_tres_partidos_en_juego(self):
        assert live_refresh.stale_live_rows(J22_SNAPSHOT, NOW) == [5, 9, 14]
        assert live_refresh.needs_live_refresh(J22_SNAPSHOT, NOW, cache_age_seconds=42 * 60) is True

    def test_stale_tambien_cuenta_es_el_directo_degradado_que_hay_que_recuperar(self):
        rows = [_row(5, "16:15", "STALE", Q15_STAMP)]
        assert live_refresh.stale_live_rows(rows, NOW) == [5]

    def test_un_dato_reciente_no_pide_nada(self):
        fresh = (NOW - timedelta(seconds=40)).replace(tzinfo=MADRID).isoformat()
        rows = [_row(5, "16:15", "LIVE", fresh), _row(14, "17:00", "HT", fresh)]
        assert live_refresh.stale_live_rows(rows, NOW) == []

    def test_los_finales_confirmados_y_lo_que_esta_fuera_de_ventana_no_cuentan(self):
        rows = [
            _row(4, "14:00", "FT", None),  # final confirmado
            _row(1, "16:00", "FINISHED", None),  # final con otro nombre
            _row(6, "18:30", "NS", None),  # saque dentro de 45 minutos
            _row(3, "12:00", "LIVE", None),  # mas de 3 horas despues del saque
        ]
        assert live_refresh.stale_live_rows(rows, NOW) == []

    def test_una_casilla_en_ns_entra_diez_minutos_antes_del_saque(self):
        rows = [_row(6, "18:30", "NS", None)]
        assert live_refresh.stale_live_rows(rows, datetime(2026, 11, 22, 18, 19)) == []
        assert live_refresh.stale_live_rows(rows, datetime(2026, 11, 22, 18, 21)) == [6]
        # Ya empezado y quiniela15 todavia sin publicarlo: se sigue pidiendo.
        assert live_refresh.stale_live_rows(rows, datetime(2026, 11, 22, 18, 34)) == [6]

    def test_el_sello_con_zona_y_el_reloj_con_zona_se_comparan_bien(self):
        # El colector sella con madrid_now().isoformat(): con zona horaria.
        stamp = "2026-11-22T17:44:10+01:00"
        rows = [_row(5, "16:15", "LIVE", stamp)]
        assert live_refresh.stale_live_rows(rows, NOW.replace(tzinfo=MADRID)) == []
        # El mismo instante escrito en UTC tambien vale.
        rows = [_row(5, "16:15", "LIVE", "2026-11-22T16:44:10+00:00")]
        assert live_refresh.stale_live_rows(rows, NOW) == []

    def test_filas_raras_no_rompen_la_decision(self):
        rows = [
            _row(1, "", "LIVE", None),
            _row(2, "16:15", "LIVE", "no-es-una-fecha"),
            {"id": 3, "fecha": "2026-11-22", "hora": "17:00", "status": "LIVE", "updated_at": None},
            {"partido_id": 4},
        ]
        # Sello ilegible = sin sello = viejo; las filas sin horario se ignoran.
        assert live_refresh.stale_live_rows(rows, NOW) == [2, 3]

    def test_acepta_filas_de_sqlite(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("CREATE TABLE r (partido_id INT, fecha TEXT, hora TEXT, status TEXT, updated_at TEXT)")
        conn.executemany(
            "INSERT INTO r VALUES (?, ?, ?, ?, ?)",
            [(row["partido_id"], row["fecha"], row["hora"], row["status"], row["updated_at"]) for row in J22_SNAPSHOT],
        )
        rows = conn.execute("SELECT * FROM r").fetchall()
        assert live_refresh.stale_live_rows(rows, NOW) == [5, 9, 14]

    def test_con_la_cache_recien_escrita_no_se_duplica_el_trabajo_del_colector(self):
        assert live_refresh.needs_live_refresh(J22_SNAPSHOT, NOW, cache_age_seconds=20) is False
        assert live_refresh.needs_live_refresh(J22_SNAPSHOT, NOW, cache_age_seconds=None) is True
        assert (
            live_refresh.needs_live_refresh(J22_SNAPSHOT, NOW, cache_age_seconds=live_refresh.CACHE_FRESH_FOR + 1)
            is True
        )

    def test_el_colector_sano_no_dispara_el_refresco(self):
        """Pasada cada 60 s + lo que dure: ni la fila ni la cache llegan al umbral."""
        assert live_refresh.ROW_STALE_AFTER > 60 + 30
        assert live_refresh.CACHE_FRESH_FOR > 60 + 30
        # Muy por debajo de los 30 minutos que tardan en caer a STALE.
        assert live_refresh.ROW_STALE_AFTER + live_refresh.MIN_GAP_SECONDS < 30 * 60


class _DeferredThreads:
    """Fabrica de hilos que no arranca nada hasta que el test lo pide."""

    def __init__(self):
        self.created = []

    def __call__(self, target, name, daemon):
        factory = self

        class _Thread:
            def __init__(self):
                self.target = target
                self.name = name
                self.daemon = daemon
                self.started = False

            def start(self):
                self.started = True
                factory.created.append(self)

        return _Thread()


class TestTrigger:
    def test_lanza_un_hilo_daemon_y_no_ejecuta_nada_en_la_peticion(self):
        threads = _DeferredThreads()
        calls = []

        assert live_refresh.trigger_refresh(22, calls.append, reason="r", now_ts=1000.0, thread_factory=threads)
        assert calls == []  # la peticion no espera al scrape
        assert [(t.name, t.daemon, t.started) for t in threads.created] == [("liga-live-refresh", True, True)]
        state = live_refresh.refresh_state()
        assert state["running"] is True
        assert state["runs"] == 1
        assert state["last_reason"] == "r"

        threads.created[0].target()
        assert calls == [22]
        assert live_refresh.refresh_state()["running"] is False

    def test_un_solo_refresco_a_la_vez_y_como_mucho_uno_por_minuto(self):
        threads = _DeferredThreads()
        assert live_refresh.trigger_refresh(22, lambda j: None, now_ts=1000.0, thread_factory=threads)
        # Mientras corre, nadie mas lanza otro.
        assert not live_refresh.trigger_refresh(22, lambda j: None, now_ts=1010.0, thread_factory=threads)
        threads.created[0].target()
        # Ya termino, pero no ha pasado el minuto.
        assert not live_refresh.trigger_refresh(22, lambda j: None, now_ts=1030.0, thread_factory=threads)
        assert live_refresh.trigger_refresh(
            22, lambda j: None, now_ts=1000.0 + live_refresh.MIN_GAP_SECONDS, thread_factory=threads
        )
        assert len(threads.created) == 2

    def test_un_refresco_colgado_se_abandona_y_su_final_tardio_no_pisa_al_nuevo(self):
        threads = _DeferredThreads()
        stuck_at = 1000.0
        assert live_refresh.trigger_refresh(22, lambda j: None, now_ts=stuck_at, thread_factory=threads)
        assert not live_refresh.trigger_refresh(
            22, lambda j: None, now_ts=stuck_at + live_refresh.STUCK_AFTER_SECONDS - 1, thread_factory=threads
        )
        assert live_refresh.trigger_refresh(
            22, lambda j: None, now_ts=stuck_at + live_refresh.STUCK_AFTER_SECONDS + 1, thread_factory=threads
        )
        assert live_refresh.refresh_state()["abandoned"] == 1

        # El colgado despierta tarde: no marca como terminado al que sigue vivo.
        threads.created[0].target()
        assert live_refresh.refresh_state()["running"] is True
        threads.created[1].target()
        state = live_refresh.refresh_state()
        assert state["running"] is False
        assert state["abandoned"] == 0

    def test_con_la_red_rota_no_se_acumulan_hilos_sin_fin(self):
        threads = _DeferredThreads()
        ts = 1000.0
        assert live_refresh.trigger_refresh(22, lambda j: None, now_ts=ts, thread_factory=threads)
        for _ in range(live_refresh.MAX_ABANDONED + 3):
            ts += live_refresh.STUCK_AFTER_SECONDS + 1
            live_refresh.trigger_refresh(22, lambda j: None, now_ts=ts, thread_factory=threads)
        assert len(threads.created) == live_refresh.MAX_ABANDONED + 1
        assert live_refresh.refresh_state()["abandoned"] == live_refresh.MAX_ABANDONED

    def test_un_runner_que_falla_queda_registrado_y_libera_el_turno(self):
        threads = _DeferredThreads()

        def boom(jornada):
            raise RuntimeError("quiniela15 caido")

        assert live_refresh.trigger_refresh(22, boom, now_ts=1000.0, thread_factory=threads)
        threads.created[0].target()
        state = live_refresh.refresh_state()
        assert state["running"] is False
        assert "quiniela15 caido" in state["last_error"]

    def test_con_hilos_reales_la_llamada_vuelve_al_instante(self):
        gate = threading.Event()
        done = threading.Event()

        def slow_runner(jornada):
            gate.wait(5)
            done.set()

        started = time.perf_counter()
        assert live_refresh.trigger_refresh(22, slow_runner)
        assert time.perf_counter() - started < 0.5
        gate.set()
        assert done.wait(5)


# ---------------------------------------------------------------------------
# Ruta /api/liga/data
# ---------------------------------------------------------------------------

JORNADA = 1


def _test_app(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "live_refresh.db"))
    monkeypatch.setattr(config, "BOOTSTRAP_DB_PATH", str(tmp_path / "missing.db"))
    monkeypatch.setattr(config, "PRODUCTION_SEED_PATH", str(tmp_path / "missing-seed.json"))
    monkeypatch.setattr(config, "DB_BACKUP_DIR", str(tmp_path / "backups"))
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.setattr(config, "DATA_DIR", str(data_dir))
    monkeypatch.setenv("SECRET_KEY", "live-refresh-test-secret")
    monkeypatch.setenv("WEB_COLLECTOR_ENABLED", "0")
    monkeypatch.setenv("DB_BACKUP_ENABLED", "0")
    monkeypatch.setenv("ALLOW_LOCAL_ADMIN", "0")
    monkeypatch.setenv("TRUSTED_HOSTS", "localhost,127.0.0.1")
    monkeypatch.delenv("LIVE_ALL_MATCHES_EXTRA_PATH", raising=False)
    app = create_app()
    monkeypatch.setenv("LIVE_REFRESH_ON_DEMAND", "1")
    return app


def _seed(app, *, live_status="LIVE", live_age_minutes=40):
    """14 casillas de esta noche y la 15 en juego desde hace 40 minutos."""
    now = madrid_now()
    later = now + timedelta(hours=6)
    kickoff = now - timedelta(minutes=40)
    stamp = (now - timedelta(minutes=live_age_minutes)).isoformat(timespec="seconds")
    with app.app_context():
        conn = get_db()
        conn.execute("DELETE FROM resultados WHERE jornada = ?", (JORNADA,))
        for partido_id in range(1, 15):
            conn.execute(
                "INSERT INTO resultados (jornada, partido_id, local, visitante, status, fecha, hora)"
                " VALUES (?, ?, ?, ?, 'NS', ?, ?)",
                (
                    JORNADA,
                    partido_id,
                    f"Local {partido_id}",
                    f"Visitante {partido_id}",
                    later.strftime("%Y-%m-%d"),
                    later.strftime("%H:%M"),
                ),
            )
        conn.execute(
            "INSERT INTO resultados (jornada, partido_id, local, visitante, status, fecha, hora,"
            " goles_local, goles_visitante, minuto, updated_at)"
            " VALUES (?, 15, 'Racing Santander', 'Real Sociedad', ?, ?, ?, 2, 1, '45''', ?)",
            (JORNADA, live_status, kickoff.strftime("%Y-%m-%d"), kickoff.strftime("%H:%M"), stamp),
        )
        conn.commit()


@pytest.fixture
def triggers(monkeypatch):
    calls = []

    def fake_trigger(jornada, runner, reason="", **kwargs):
        calls.append({"jornada": jornada, "runner": runner, "reason": reason})
        return True

    monkeypatch.setattr(liga_data.live_refresh, "trigger_refresh", fake_trigger)
    return calls


@pytest.mark.parametrize("variant", ["", "?slim=1", "?first=1"])
def test_un_partido_en_juego_sin_noticias_lanza_el_refresco_en_todas_las_variantes(
    variant, tmp_path, monkeypatch, triggers
):
    app = _test_app(tmp_path, monkeypatch)
    _seed(app)

    response = app.test_client().get(f"/api/liga/data{variant}")

    assert response.status_code == 200
    assert len(triggers) == 1
    assert triggers[0]["jornada"] == JORNADA
    assert triggers[0]["runner"] is liga_data._run_q15_cache
    assert triggers[0]["reason"].endswith(": 15")


def test_sin_noticias_la_casilla_sale_stale_y_eso_tambien_pide_refresco(tmp_path, monkeypatch, triggers):
    app = _test_app(tmp_path, monkeypatch)
    _seed(app, live_status="STALE")

    assert app.test_client().get("/api/liga/data?slim=1").status_code == 200
    assert len(triggers) == 1


def test_con_el_dato_fresco_no_se_pide_nada(tmp_path, monkeypatch, triggers):
    app = _test_app(tmp_path, monkeypatch)
    _seed(app, live_age_minutes=0)

    assert app.test_client().get("/api/liga/data?slim=1").status_code == 200
    assert triggers == []


def test_con_la_cache_q15_recien_escrita_no_se_pide_nada(tmp_path, monkeypatch, triggers):
    app = _test_app(tmp_path, monkeypatch)
    _seed(app)
    (tmp_path / "data" / f"quiniela15_directo_J{JORNADA}.json").write_text("{}", encoding="utf-8")

    assert app.test_client().get("/api/liga/data?slim=1").status_code == 200
    assert triggers == []


def test_el_interruptor_de_emergencia_lo_apaga(tmp_path, monkeypatch, triggers):
    app = _test_app(tmp_path, monkeypatch)
    _seed(app)
    monkeypatch.setenv("LIVE_REFRESH_ON_DEMAND", "0")

    assert app.test_client().get("/api/liga/data?slim=1").status_code == 200
    assert triggers == []


def test_la_portada_se_cura_sola_con_el_colector_caido(tmp_path, monkeypatch):
    """De punta a punta: STALE «Sin datos» -> refresco en segundo plano -> directo."""
    app = _test_app(tmp_path, monkeypatch)
    _seed(app)
    db_path = config.DB_PATH
    cache_path = tmp_path / "data" / f"quiniela15_directo_J{JORNADA}.json"
    scrapes = []

    def fake_q15_cache(jornada):
        # Lo mismo que write_q15_directo_cache: cache + marcador sellado en BD.
        scrapes.append(jornada)
        stamp = madrid_now().isoformat(timespec="seconds")
        with sqlite3.connect(db_path) as conn:
            # Minuto coherente con el saque (hace 40 minutos): uno por delante
            # del reloj lo descarta, con razon, la lectura segura del directo.
            conn.execute(
                "UPDATE resultados SET status = 'LIVE', goles_local = 2, goles_visitante = 2, minuto = '38''',"
                " updated_at = ? WHERE jornada = ? AND partido_id = 15",
                (stamp, jornada),
            )
        cache_path.write_text(json.dumps({"jornada": jornada, "matches": []}), encoding="utf-8")
        return {"done": True}

    monkeypatch.setattr(liga_data, "_run_q15_cache", fake_q15_cache)
    client = app.test_client()

    started = time.perf_counter()
    before = client.get("/api/liga/data?slim=1").get_json()
    elapsed = time.perf_counter() - started
    row = next(p for p in before["partidos"] if p["id"] == 15)
    assert row["status"] == "STALE"  # la foto de produccion
    assert before["live_matches"] == []

    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        state = live_refresh.refresh_state()
        if state["runs"] == 1 and not state["running"]:
            break
        time.sleep(0.05)
    assert scrapes == [JORNADA]
    assert elapsed < 5

    after = client.get("/api/liga/data?slim=1").get_json()
    row = next(p for p in after["partidos"] if p["id"] == 15)
    assert row["status"] == "LIVE"
    assert row["goles_local"] == 2
    assert row["goles_visitante"] == 2
    assert [m.get("local") for m in after["live_matches"]] == ["Racing Santander"]

    # Recien refrescado: otra visita no vuelve a pedir el scrape.
    client.get("/api/liga/data?slim=1")
    time.sleep(0.2)
    assert scrapes == [JORNADA]
