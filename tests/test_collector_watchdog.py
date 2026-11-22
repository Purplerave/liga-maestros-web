"""Vigilante del colector web (``workers/web_collector.py``).

22/11/2026, J22: tras el despliegue de las 16:04 el hilo del colector hizo una
pasada y se quedo colgado. ``LIVE_COLLECTOR_HEALTH.json`` se quedo en «idle»
a las 16:04:20 y nadie volvio a arrancar el hilo: la jornada se quedo sin
resultados hasta el siguiente reinicio manual.

Un hilo de Python no se puede matar, pero si sustituir. Cubren:
- El diagnostico: hilo muerto, pasada colgada, arranque colgado y silencio.
- La sustitucion sube la generacion y tiene tope.
- El bucle viejo, si despierta, ve que ya no es el titular y se retira.
- ``/health`` expone el latido sin secretos y la cuota con claves reales.
"""

from __future__ import annotations

import sys
import threading
import types

import pytest

from liga_maestros.workers import web_collector as wc

NOW = 1_800_000_000.0


class FakeThread:
    def __init__(self, alive=True):
        self.alive = alive

    def is_alive(self):
        return self.alive


@pytest.fixture(autouse=True)
def _clean_heartbeat():
    wc._reset_heartbeat_for_tests()
    yield
    wc._reset_heartbeat_for_tests()


def _beat(**values):
    with wc._heartbeat_lock:
        wc._heartbeat.update(values)


class TestDiagnostico:
    def test_sin_colector_en_este_proceso_no_hay_nada_que_vigilar(self):
        assert wc.collector_stall_reason(NOW) == ""

    def test_un_colector_sano_entre_pasadas(self):
        _beat(thread=FakeThread(), loop_started_at=NOW - 3600, pass_started_at=NOW - 70, pass_finished_at=NOW - 62)
        assert wc.collector_stall_reason(NOW) == ""

    def test_una_pasada_normal_en_curso_no_es_un_cuelgue(self):
        _beat(thread=FakeThread(), loop_started_at=NOW - 3600, pass_started_at=NOW - 20, pass_finished_at=NOW - 90)
        assert wc.collector_stall_reason(NOW) == ""

    def test_hilo_muerto(self):
        _beat(thread=FakeThread(alive=False), loop_started_at=NOW - 100)
        assert wc.collector_stall_reason(NOW) == "hilo_muerto"

    def test_la_foto_del_22_11_es_una_pasada_colgada(self):
        """Pasada empezada a las 16:04:20 que a las 17:45 seguia sin acabar."""
        started = NOW - (101 * 60)
        _beat(thread=FakeThread(), loop_started_at=started - 5, pass_started_at=started, pass_finished_at=started - 1)
        assert wc.collector_stall_reason(NOW) == "pasada_colgada"

    def test_el_umbral_de_pasada_colgada(self):
        deadline = wc.COLLECTOR_PASS_DEADLINE_SECONDS
        _beat(thread=FakeThread(), loop_started_at=NOW - 50_000, pass_finished_at=NOW - 20_000)
        _beat(pass_started_at=NOW - deadline + 5)
        assert wc.collector_stall_reason(NOW) == ""
        _beat(pass_started_at=NOW - deadline - 5)
        assert wc.collector_stall_reason(NOW) == "pasada_colgada"

    def test_una_pasada_lenta_tras_el_sueno_largo_no_se_confunde_con_silencio(self):
        """Sueño de 900 s y pasada de 6 minutos: lento, pero aun no colgado."""
        _beat(thread=FakeThread(), loop_started_at=NOW - 50_000, pass_finished_at=NOW - 900 - 380)
        _beat(pass_started_at=NOW - 380)
        assert wc.collector_stall_reason(NOW) == ""

    def test_arranque_colgado_antes_de_la_primera_pasada(self):
        _beat(thread=FakeThread(), loop_started_at=NOW - wc.COLLECTOR_PASS_DEADLINE_SECONDS - 5)
        assert wc.collector_stall_reason(NOW) == "arranque_colgado"

    def test_silencio_demasiado_largo_entre_pasadas(self):
        silence = wc.COLLECTOR_SILENCE_SECONDS
        _beat(
            thread=FakeThread(),
            loop_started_at=NOW - 10 * silence,
            pass_started_at=NOW - silence - 30,
            pass_finished_at=NOW - silence - 20,
        )
        assert wc.collector_stall_reason(NOW) == "sin_pasadas"

    def test_el_sueno_mas_largo_del_colector_no_dispara_el_silencio(self):
        # next_sleep_seconds nunca pasa de 900 s.
        assert wc.COLLECTOR_SILENCE_SECONDS > 900 + wc.COLLECTOR_PASS_DEADLINE_SECONDS // 2
        _beat(thread=FakeThread(), loop_started_at=NOW - 7200, pass_started_at=NOW - 905, pass_finished_at=NOW - 900)
        assert wc.collector_stall_reason(NOW) == ""

    def test_el_latido_publico_no_expone_el_hilo(self):
        _beat(thread=FakeThread(), loop_started_at=NOW - 100, pass_started_at=NOW - 30, pass_finished_at=NOW - 40)
        beat = wc.collector_heartbeat(NOW)
        assert "thread" not in beat
        assert beat["thread_alive"] is True
        assert beat["pass_running_for_seconds"] == 30
        assert beat["last_pass_age_seconds"] == 40
        assert beat["stall_reason"] == ""


class TestSustitucion:
    def test_sube_la_generacion_y_arranca_otro_bucle(self):
        started = []
        assert wc._restart_collector("pasada_colgada", started.append) is True
        assert wc._restart_collector("hilo_muerto", started.append) is True
        assert started == [1, 2]
        beat = wc.collector_heartbeat()
        assert beat["generation"] == 2
        assert beat["restarts"] == 2
        assert beat["last_restart_reason"] == "hilo_muerto"

    def test_tiene_tope_de_sustituciones(self, monkeypatch):
        monkeypatch.setattr(wc, "COLLECTOR_MAX_RESTARTS", 2)
        started = []
        assert wc._restart_collector("x", started.append)
        assert wc._restart_collector("x", started.append)
        assert wc._restart_collector("x", started.append) is False
        assert started == [1, 2]

    def test_el_vigilante_sustituye_una_pasada_colgada_una_sola_vez(self):
        now = wc.time.time()  # el vigilante usa el reloj real
        _beat(thread=FakeThread(), loop_started_at=now - 9000, pass_started_at=now - 6000, pass_finished_at=now - 6060)
        started = []

        def start_thread(generation):
            # Lo mismo que hace _start_collector_thread al arrancar el sustituto.
            started.append(generation)
            _beat(thread=FakeThread(), loop_started_at=wc.time.time(), pass_started_at=0.0)

        sleeps = []
        wc._collector_watchdog_loop(start_thread, sleep=sleeps.append, max_iterations=4)

        assert started == [1]
        assert sleeps == [wc.COLLECTOR_WATCHDOG_INTERVAL_SECONDS] * 4

    def test_un_error_del_vigilante_no_lo_mata(self, monkeypatch):
        calls = []

        def broken():
            calls.append(1)
            raise RuntimeError("boom")

        monkeypatch.setattr(wc, "collector_stall_reason", broken)
        wc._collector_watchdog_loop(lambda generation: None, sleep=lambda seconds: None, max_iterations=3)
        assert len(calls) == 3


def _fake_collector_module(monkeypatch, run_once):
    module = types.ModuleType("LIVE_COLLECTOR")
    module.ECHO_STDOUT = True
    module.log_line = lambda message: None
    module.write_health = lambda *args, **kwargs: None
    module.next_sleep_seconds = lambda window, interval: 60
    module.run_once = run_once
    monkeypatch.setitem(sys.modules, "LIVE_COLLECTOR", module)
    return module


class TestGeneraciones:
    def test_un_bucle_sustituido_se_retira_sin_otra_pasada(self, monkeypatch):
        passes = []
        module = _fake_collector_module(monkeypatch, lambda **kwargs: passes.append(kwargs) or (0, {}))
        ready = threading.Event()
        monkeypatch.setattr(wc, "_collector_startup_complete", ready)

        def sleep(seconds):
            # Mientras dormia, el vigilante lo dio por colgado y arranco otro.
            wc._restart_collector("pasada_colgada", lambda generation: None)

        loop = wc._make_collector_loop(0, interval=60, highlightly_interval=60, q15_enabled=False, sleep=sleep)
        loop()  # vuelve: no se queda en el while True

        assert len(passes) == 1
        assert wc.collector_heartbeat()["passes"] == 1
        assert ready.is_set()  # la primera pasada libero la barrera
        # Dentro del proceso web el log del colector no va a stdout.
        assert module.ECHO_STDOUT is False

    def test_el_final_tardio_de_una_pasada_vieja_no_cuenta_como_latido(self, monkeypatch):
        def run_once(**kwargs):
            # La pasada vieja tarda tanto que la sustituyen mientras corre.
            wc._restart_collector("pasada_colgada", lambda generation: None)
            return 0, {}

        _fake_collector_module(monkeypatch, run_once)
        monkeypatch.setattr(wc, "_collector_startup_complete", threading.Event())

        loop = wc._make_collector_loop(0, interval=60, highlightly_interval=60, q15_enabled=False, sleep=lambda s: None)
        loop()

        beat = wc.collector_heartbeat()
        assert beat["generation"] == 1
        assert beat["passes"] == 0  # el latido es del titular, no del zombi

    def test_un_sustituto_no_vuelve_a_tocar_la_barrera_de_arranque(self, monkeypatch):
        _beat(generation=3)
        passes = []
        _fake_collector_module(monkeypatch, lambda **kwargs: passes.append(1) or (0, {}))
        monkeypatch.setattr(wc, "_collector_startup_complete", threading.Event())

        def sleep(seconds):
            _beat(generation=4)

        loop = wc._make_collector_loop(3, interval=60, highlightly_interval=60, q15_enabled=True, sleep=sleep)
        loop()
        assert passes == [1]


def test_health_expone_el_latido_y_la_cuota_con_claves_reales(tmp_path, monkeypatch):
    from test_liga_data_slim import _test_app

    from liga_maestros.services import highlightly

    app = _test_app(tmp_path, monkeypatch)
    monkeypatch.setattr(
        highlightly,
        "get_highlightly_usage",
        lambda: {"calls": 30, "limit": 100, "usable_remaining": 60, "api_key": "secreto"},
    )
    _beat(thread=FakeThread(), loop_started_at=wc.time.time() - 100, pass_finished_at=wc.time.time() - 10)

    payload = app.test_client().get("/health").get_json()

    assert payload["quota"] == {"remaining_pct": 60.0, "used": 30, "limit": 100}
    assert payload["collector"]["stall_reason"] == ""
    assert payload["collector"]["last_pass_age_seconds"] >= 10
    assert set(payload["live_refresh"]) == {"runs", "running", "last_reason"}
    assert "secreto" not in str(payload)


def test_el_log_del_colector_rota_y_puede_callar_stdout(tmp_path, monkeypatch, capsys):
    from tools.ops import LIVE_COLLECTOR as collector

    log_path = tmp_path / "LIVE_COLLECTOR.log"
    monkeypatch.setattr(collector, "LOG_PATH", log_path)
    monkeypatch.setattr(collector, "LOG_MAX_BYTES", 200)

    monkeypatch.setattr(collector, "ECHO_STDOUT", True)
    collector.log_line("visible en la CLI")
    assert "visible en la CLI" in capsys.readouterr().out

    # Dentro del proceso web: nada por stdout (una tuberia llena no bloquea).
    monkeypatch.setattr(collector, "ECHO_STDOUT", False)
    for i in range(20):
        collector.log_line(f"pasada {i} " + "x" * 20)
    assert capsys.readouterr().out == ""
    rotated = log_path.with_name(log_path.name + ".1")
    assert rotated.exists()
    assert log_path.stat().st_size <= 200 + 100
    assert "pasada 19" in log_path.read_text(encoding="utf-8")
