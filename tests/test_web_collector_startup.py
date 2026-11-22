"""The first API read must be able to detect the collector's boot pass.

El 22/11/2026 la portada se quedaba en «Cargando el directo… Reintentando
(n/4)» en cada visita. No era la red: `/api/liga/data` contestaba 503
`cold_start` mientras el collector hacia su primera pasada, y en produccion esa
pasada dura bastante mas que los 4 reintentos del navegador. Estos tests fijan
que la barrera exista (para servir el snapshot con contexto, no a ciegas) pero
que **nunca** pueda dejar la portada sin datos.
"""

import threading
import time

from flask import Flask

from liga_maestros.workers import web_collector


def test_collector_marks_startup_pending_before_background_thread_runs(monkeypatch):
    ready = threading.Event()
    ready.set()
    threads = []

    class DeferredThread:
        def __init__(self, *, target, name, daemon):
            self.target = target
            self.name = name
            self.daemon = daemon

        def start(self):
            # Leave the target paused, modelling a collector that has not yet
            # completed its first pass when Gunicorn begins serving requests.
            threads.append(self)

    monkeypatch.setenv("WEB_COLLECTOR_ENABLED", "1")
    monkeypatch.setenv("WEB_COLLECTOR_INTERVAL_SECONDS", "60")
    monkeypatch.setenv("WEB_COLLECTOR_HIGHLIGHTLY_INTERVAL_SECONDS", "60")
    monkeypatch.setenv("WEB_COLLECTOR_DISABLE_Q15", "0")
    monkeypatch.setenv("DAILY_TRACKER_ENABLED", "0")
    monkeypatch.setattr(web_collector, "_collector_started", False)
    monkeypatch.setattr(web_collector, "_collector_startup_complete", ready)
    monkeypatch.setattr(web_collector, "_collector_startup_released_at", 0.0)
    monkeypatch.setattr(web_collector, "_leader_lock_handle", None)
    monkeypatch.setattr(web_collector, "_try_acquire_leader_lock", lambda: True)
    monkeypatch.setattr(web_collector.threading, "Thread", DeferredThread)

    web_collector.start_web_collector(Flask("collector-startup-test"))

    # live collector + scheduled standings refresh + vigilante del colector
    assert [thread.name for thread in threads] == [
        "liga-web-collector",
        "liga-standings-refresh",
        "liga-collector-watchdog",
    ]
    assert all(thread.daemon for thread in threads)
    assert web_collector.collector_startup_pending() is True
    # La marca temporal del cierre queda puesta: sin ella no hay forma de
    # distinguir "acaba de arrancar" de "se quedo atascado".
    assert web_collector._collector_startup_released_at > 0

    ready.set()
    assert web_collector.collector_startup_pending() is False


def test_la_barrera_se_da_por_superada_si_la_primera_pasada_no_llega(monkeypatch):
    """Un hilo que nunca termina no puede dejar la portada en 503 eternamente."""
    evento = threading.Event()
    evento.clear()
    monkeypatch.setattr(web_collector, "_collector_startup_complete", evento)
    monkeypatch.setattr(web_collector, "_collector_startup_released_at", time.time() - 60)

    assert web_collector.collector_startup_pending() is True
    assert web_collector.collector_startup_stale() is True


def test_la_barrera_reciente_no_se_da_por_superada(monkeypatch):
    evento = threading.Event()
    evento.clear()
    monkeypatch.setattr(web_collector, "_collector_startup_complete", evento)
    monkeypatch.setattr(web_collector, "_collector_startup_released_at", time.time())

    assert web_collector.collector_startup_pending() is True
    assert web_collector.collector_startup_stale() is False


def test_wait_for_collector_startup_devuelve_el_estado(monkeypatch):
    evento = threading.Event()
    evento.clear()
    monkeypatch.setattr(web_collector, "_collector_startup_complete", evento)

    started = time.monotonic()
    assert web_collector.wait_for_collector_startup(timeout=0.05) is False
    assert time.monotonic() - started >= 0.04

    evento.set()
    assert web_collector.wait_for_collector_startup(timeout=1) is True


def test_handles_del_collector_abren_la_barrera(monkeypatch):
    """La barrera se abre con exito, con fallo y al saltarse el liderazgo."""
    evento = threading.Event()
    evento.clear()
    monkeypatch.setattr(web_collector, "_collector_startup_complete", evento)
    monkeypatch.setattr(web_collector, "_collector_startup_released_at", 0.0)

    web_collector.mark_collector_startup_complete()

    assert evento.is_set()
    assert web_collector.collector_startup_pending() is False
