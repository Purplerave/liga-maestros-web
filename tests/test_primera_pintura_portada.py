"""Primera pantalla de la portada: sin esperas eternas ni «Reintentando (n/4)».

Foto del 22/11/2026: cada visita a la portada mostraba «Cargando el directo…
Reintentando (1/4)». Tres causas, las tres cubiertas aqui (las de backend en
tests/test_cold_start_retry.py y tests/test_web_collector_startup.py):

1. `/api/liga/data` contestaba 503 mientras el collector hacia su primera
   pasada tras arrancar.
2. La primera peticion se quedaba hasta 6 s scrapeando Q15 dentro del ciclo de
   la peticion.
3. El navegador arrancaba de cero: esqueleto y a esperar, sin tope de espera ni
   reintento marcado.

Reglas que no se pueden perder:
- El HTML ya trae el esqueleto: nunca hay un hueco en blanco.
- Todas las peticiones del arranque tienen tope de espera.
- El reintento se identifica como automatico para que el backend no lo retenga.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "templates" / "liga_index.html"
EVENTS = ROOT / "static" / "js" / "events.js"
QUANTUM = ROOT / "static" / "js" / "quantum_final.js"
RUTA = ROOT / "liga_maestros" / "routes" / "liga_data.py"


def test_el_html_pinta_un_esqueleto_antes_de_cualquier_script():
    template = TEMPLATE.read_text(encoding="utf-8")
    cuerpo = template[template.index('id="matches-body"') :]
    cuerpo = cuerpo[: cuerpo.index("</section>")]
    assert "arena-skeleton" in cuerpo
    assert "Cargando la quiniela" in cuerpo
    # Accesible: el esqueleto es decorativo, el aviso va en una region status.
    assert 'role="status"' in cuerpo
    assert 'aria-hidden="true"' in cuerpo


def test_el_esqueleto_de_la_portada_tiene_estilos():
    css = (ROOT / "static" / "css" / "themes" / "newspaper" / "animations.css").read_text(encoding="utf-8")
    for clase in (".arena-skeleton", ".arena-skeleton-grid", ".arena-skeleton-card", ".arena-skeleton-status"):
        assert clase in css


def test_las_peticiones_del_arranque_tienen_tope_de_espera():
    quantum = QUANTUM.read_text(encoding="utf-8")

    assert "async function fetchWithTimeout" in quantum
    assert "AbortController" in quantum
    assert "FIRST_PAINT_TIMEOUT_MS" in quantum
    assert "FULL_PAINT_TIMEOUT_MS" in quantum
    assert "async function fetchLigaDataWithRetry(url, { timeoutMs = FULL_PAINT_TIMEOUT_MS" in quantum
    # El ultimo recurso tambien respeta el tope (antes era un fetch sin limite).
    assert 'return lastResponse || fetchWithTimeout(url, { timeoutMs, init: { cache: "no-store" } });' in quantum


def test_el_reintento_se_identifica_como_automatico():
    quantum = QUANTUM.read_text(encoding="utf-8")
    assert "function ligaDataRetryHeaders(attempt)" in quantum
    assert 'return attempt > 1 ? { "X-Liga-Retry": "1" } : {};' in quantum
    assert "headers: ligaDataRetryHeaders(attempt)" in quantum


def test_un_fallo_con_datos_ya_pintados_no_tapa_la_pagina():
    quantum = QUANTUM.read_text(encoding="utf-8")
    cuerpo = quantum[quantum.index("async function refreshData") :]
    # Con datos en memoria, el fallo del refresco no pinta el cartel de error:
    # mantiene lo que el usuario esta viendo.
    assert 'showToast("No se pudo actualizar en segundo plano. Mantengo la ultima version cargada.", "error")' in cuerpo
    assert "el directo&#8230; Reintentando" not in quantum


def test_el_aviso_de_reintento_es_un_esqueleto_y_no_un_error():
    quantum = QUANTUM.read_text(encoding="utf-8")
    cuerpo = quantum[quantum.index("async function refreshData") :]
    tramo = cuerpo[cuerpo.index("initialLoadAttempts += 1") :]
    assert "renderSkeletonLoading()" in tramo[: tramo.index("Reintentar ahora")]


def test_el_scrape_q15_de_primera_pintura_no_bloquea_la_respuesta():
    ruta = RUTA.read_text(encoding="utf-8")
    funcion = ruta[ruta.index("def _maybe_refresh_stale_window") : ruta.index("def _run_q15_cache")]
    assert "threading.Thread(" in funcion
    assert "_WINDOW_REFRESH_BUDGET" not in ruta
    assert "worker.join(" not in funcion


def test_el_backend_no_hace_esperar_al_poll_automatico():
    ruta = RUTA.read_text(encoding="utf-8")
    bloque = ruta[ruta.index("def _collector_warming_response") : ruta.index("def _wants_slim")]
    assert "collector_startup_stale" in bloque
    assert "wait_for_collector_startup" in bloque
    assert 'request.args.get("auto")' in bloque
