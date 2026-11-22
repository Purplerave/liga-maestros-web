"""Tope de tiempo TOTAL para las llamadas de red de los hilos de fondo.

``requests`` limita cada operacion de socket por separado: un servidor que
contesta a goteo puede retener una llamada con ``timeout=25`` mucho mas de 25
segundos. En el hilo del colector eso es una jornada sin resultados (22/11/2026,
J22). ``get_with_deadline`` lee el cuerpo por trozos y corta en el tope total.
"""

from __future__ import annotations

import importlib.util
import io
import types
from pathlib import Path

import pytest
import requests

from liga_maestros.services import http_deadline
from liga_maestros.services.http_deadline import DeadlineExceeded, get_with_deadline

ROOT = Path(__file__).resolve().parents[1]


def _response(body=b"", status=200, raw=None):
    response = requests.models.Response()
    response.status_code = status
    response.raw = raw if raw is not None else io.BytesIO(body)
    response.encoding = "utf-8"
    response.url = "https://example.test/x"
    return response


class _DripRaw:
    """Cuerpo que llega a trozos, sin fin (servidor a goteo)."""

    def __init__(self):
        self.closed = False
        self.reads = 0

    def read(self, size=-1):
        self.reads += 1
        return b"x" * 10

    def close(self):
        self.closed = True


def test_respuesta_normal_cuerpo_completo_y_parametros_de_requests(monkeypatch):
    seen = {}

    def fake_get(url, **kwargs):
        seen.update(kwargs, url=url)
        return _response(b'{"data": [1, 2, 3]}')

    monkeypatch.setattr(http_deadline.requests, "get", fake_get)

    response = get_with_deadline(
        "https://example.test/x", params={"a": 1}, headers={"h": "v"}, connect_timeout=3, read_timeout=7
    )

    assert response.status_code == 200
    assert response.json() == {"data": [1, 2, 3]}
    assert seen["stream"] is True
    assert seen["timeout"] == (3, 7)
    assert seen["params"] == {"a": 1}
    assert seen["headers"] == {"h": "v"}


def test_un_servidor_a_goteo_se_corta_en_el_tope_total(monkeypatch):
    raw = _DripRaw()
    monkeypatch.setattr(http_deadline.requests, "get", lambda url, **kwargs: _response(raw=raw))
    clock = iter(range(0, 10_000, 4))  # cada lectura "tarda" 4 s
    monkeypatch.setattr(http_deadline, "_monotonic", lambda: next(clock))

    with pytest.raises(DeadlineExceeded) as excinfo:
        get_with_deadline("https://example.test/x", total_timeout=20)

    # Los llamadores existentes ya capturan RequestException / Timeout.
    assert isinstance(excinfo.value, requests.Timeout)
    assert isinstance(excinfo.value, requests.RequestException)
    assert raw.reads <= 6
    assert raw.closed is True


def test_un_cuerpo_desmesurado_se_corta(monkeypatch):
    monkeypatch.setattr(http_deadline.requests, "get", lambda url, **kwargs: _response(b"x" * 5000))

    with pytest.raises(requests.RequestException) as excinfo:
        get_with_deadline("https://example.test/x", max_bytes=1000)
    assert not isinstance(excinfo.value, requests.Timeout)


def test_los_dobles_de_test_sin_cuerpo_crudo_pasan_tal_cual(monkeypatch):
    double = types.SimpleNamespace(status_code=200, json=lambda: {"ok": True})
    monkeypatch.setattr(http_deadline.requests, "get", lambda url, **kwargs: double)

    assert get_with_deadline("https://example.test/x") is double


def _scraper():
    path = ROOT / "tools" / "scrapers" / "SCRAPE_QUINIELA15_DIRECTO.py"
    spec = importlib.util.spec_from_file_location("scrape_q15_directo_deadline", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_el_scrape_de_quiniela15_tiene_tope_total_y_reintenta(monkeypatch):
    scraper = _scraper()
    calls = []
    sleeps = []

    def stuck(url, **kwargs):
        calls.append(kwargs)
        raise DeadlineExceeded("goteo")

    monkeypatch.setattr(scraper, "get_with_deadline", stuck)
    monkeypatch.setattr(scraper, "time", types.SimpleNamespace(sleep=sleeps.append))

    with pytest.raises(DeadlineExceeded):
        scraper.fetch_page("https://www.quiniela15.com/resultados-quiniela/23")

    assert len(calls) == 2
    assert all(call["total_timeout"] == scraper.FETCH_TOTAL_TIMEOUT for call in calls)
    # Peor caso de la funcion entera: dos intentos con tope y una espera.
    assert len(calls) * scraper.FETCH_TOTAL_TIMEOUT + sum(sleeps) <= 60


def test_el_scrape_de_quiniela15_devuelve_la_pagina_decodificada(monkeypatch):
    scraper = _scraper()
    monkeypatch.setattr(
        scraper, "get_with_deadline", lambda url, **kwargs: _response("Alavés 3 - 1 Deportivo".encode())
    )

    response = scraper.fetch_page("https://www.quiniela15.com/resultados-quiniela/23")
    assert "Alavés" in response.text


def test_highlightly_con_la_red_colgada_registra_el_fallo_y_sigue(monkeypatch):
    from liga_maestros.services import highlightly

    failures = []
    monkeypatch.setattr(highlightly, "reserve_highlightly_calls", lambda n: True)
    monkeypatch.setattr(highlightly, "record_highlightly_failure", failures.append)

    def stuck(url, **kwargs):
        assert kwargs["total_timeout"] == highlightly.HIGHLIGHTLY_TOTAL_TIMEOUT
        raise DeadlineExceeded("goteo")

    monkeypatch.setattr(highlightly, "get_with_deadline", stuck)

    assert highlightly._highlightly_get_matches({"date": "2026-11-22"}, {"x-rapidapi-key": "k"}) == []
    assert len(failures) == 1
    assert isinstance(failures[0], DeadlineExceeded)


def test_el_panel_diario_usa_el_tope_total(monkeypatch):
    from liga_maestros.services import daily_matches

    seen = []
    failures = []
    monkeypatch.setenv("HIGHLIGHTLY_API_KEY", "k")
    monkeypatch.setattr(daily_matches, "get_highlightly_circuit", lambda: {"open": False})
    monkeypatch.setattr(daily_matches, "reserve_highlightly_calls", lambda n: True)
    monkeypatch.setattr(daily_matches, "record_highlightly_success", lambda: None)
    monkeypatch.setattr(daily_matches, "record_highlightly_failure", failures.append)

    def fake(url, **kwargs):
        seen.append(kwargs)
        return _response(b'{"data": []}')

    monkeypatch.setattr(daily_matches, "get_with_deadline", fake)
    assert daily_matches._api_get("/matches", {"date": "2026-11-22"}) == {"data": []}
    assert seen[0]["total_timeout"] == 20

    def stuck(url, **kwargs):
        raise DeadlineExceeded("goteo")

    monkeypatch.setattr(daily_matches, "get_with_deadline", stuck)
    assert daily_matches._api_get("/matches", {"date": "2026-11-22"}) is None
    assert len(failures) == 1
