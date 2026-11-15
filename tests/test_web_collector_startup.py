"""The first API read must be able to detect the collector's boot pass."""

import threading

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
    monkeypatch.setattr(web_collector, "_leader_lock_handle", None)
    monkeypatch.setattr(web_collector, "_try_acquire_leader_lock", lambda: True)
    monkeypatch.setattr(web_collector.threading, "Thread", DeferredThread)

    web_collector.start_web_collector(Flask("collector-startup-test"))

    assert len(threads) == 2  # live collector + scheduled standings refresh
    assert threads[0].name == "liga-web-collector"
    assert web_collector.collector_startup_pending() is True

    ready.set()
    assert web_collector.collector_startup_pending() is False
