"""El DIRECTO no puede caerse porque el servidor tarde o porque la IA piense.

Foto de producción del 13/09/2026 (14:47, jornada 6, Celta - Málaga en juego):

* ``/metrics`` -> ``/api/liga/data`` 3 peticiones, 3,94 s acumulados (~1,3 s de
  media) y ``/api/noticias/radar`` 4,28 s en UNA petición.
* El service worker cortaba cualquier ``/api/`` GET a los **4 s** y devolvía un
  ``503 {"status":"error"}`` inventado: la portada pintaba «No se pudo cargar la
  Arena» y los refrescos del directo se descartaban en silencio.
* El frontend solo reintentaba el ``503`` con ``status: cold_start``, así que ese
  503 sintético no se reintentaba nunca.
* El comentarista (MiMo) llamaba a la IA DENTRO de la petición, hasta 10 s por
  proveedor y reintento, exactamente cuando hay partidos en juego.

Estos tests fijan los tres arreglos: sin guillotina de 4 s, reintento de
cualquier 503/504 reintentable, IA fuera del ciclo de petición y un payload del
directo que no se deja la mitad de la CPU en canonicalizar nombres y reparsear
los escudos.
"""

from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SW = ROOT / "static" / "sw.js"
EVENTS_JS = ROOT / "static" / "js" / "events.js"
QUANTUM_JS = ROOT / "static" / "js" / "quantum_final.js"

PARTIDO_EN_JUEGO = {
    "local": "Celta",
    "visitante": "Málaga",
    "minuto": "45",
    "marcador": "1-0",
    "status": "IN PLAY",
}


# --- Service worker ---------------------------------------------------------


def test_sw_no_guillotina_las_respuestas_de_api():
    sw = SW.read_text(encoding="utf-8")
    assert "networkWithTimeout(request, 4000)" not in sw, "vuelve la guillotina de 4 s sobre la API"
    assert "API_TIMEOUT_MS = 30000" in sw
    assert "networkWithTimeout(request, API_TIMEOUT_MS)" in sw


def test_sw_marca_su_respuesta_sintetica_como_reintentable():
    sw = SW.read_text(encoding="utf-8")
    assert "status: 'network_error'" in sw
    assert "retryable: true" in sw
    # No puede disfrazarse del cold_start del backend (503 + status cold_start).
    assert "status: 504" in sw
    assert "message: 'Offline'" not in sw


def test_sw_cache_versions_bumped():
    sw = SW.read_text(encoding="utf-8")
    assert "liga-maestros-v12" not in sw, "los clientes no descargarían el SW nuevo"


# --- Frontend: reintento y recuperación ------------------------------------


def test_frontend_reintenta_cualquier_fallo_reintentable():
    source = QUANTUM_JS.read_text(encoding="utf-8")
    assert "response.status !== 504" in source
    assert 'payload?.status === "network_error"' in source
    assert "isRetryableLigaDataFailure" in source
    # Un corte de red (fetch lanza) también reintenta en vez de reventar.
    assert "catch (networkError)" in source


def test_carga_inicial_no_es_un_callejon_sin_salida():
    source = QUANTUM_JS.read_text(encoding="utf-8")
    assert "INITIAL_LOAD_MAX_RETRIES" in source
    assert "initialLoadAttempts" in source
    assert "data-reload-arena" in source
    # CSP `script-src 'self'`: un onclick inline no se ejecutaría jamás.
    assert "onclick=" not in source


def test_un_refresco_fallido_del_directo_se_reintenta_antes_de_30s():
    events = EVENTS_JS.read_text(encoding="utf-8")
    assert "LIVE_FAILURE_RETRY_MS" in events
    assert "scheduleLivePoll(refreshed ? undefined : LIVE_FAILURE_RETRY_MS)" in events
    assert "async function refreshLiveSnapshot" in events
    assert "return false" in events


# --- Backend: la IA nunca bloquea una petición ------------------------------


def _comentarista():
    from liga_maestros.services.ai import comentarista

    return comentarista


def test_comentarios_para_web_no_llama_a_la_ia_en_la_peticion(monkeypatch):
    comentarista = _comentarista()
    comentarista._reset_estado_refresco()
    llamadas = []

    def chat_lento(*args, **kwargs):
        llamadas.append(time.monotonic())
        time.sleep(1.5)
        return json.dumps({"comentarios": [{"partido": 1, "texto": "gol del Celta en el 45"}]})

    monkeypatch.setattr(comentarista, "ai_enabled", lambda: True)
    monkeypatch.setattr(comentarista, "cache_get", lambda *args: None)
    monkeypatch.setattr(comentarista, "cache_get_latest", lambda *args: None)
    monkeypatch.setattr(comentarista, "reserve_call", lambda: True)
    monkeypatch.setattr(comentarista, "cache_set", lambda *args: None)
    monkeypatch.setattr(comentarista, "_cargar_emitidos", lambda: [])
    monkeypatch.setattr(comentarista, "_guardar_emitidos", lambda emitidos: None)
    monkeypatch.setattr(comentarista, "chat", chat_lento)

    empezado = time.monotonic()
    resultado = comentarista.comentarios_para_web([PARTIDO_EN_JUEGO])
    transcurrido = time.monotonic() - empezado

    assert resultado == {"comentarios": [], "generated": False}
    assert transcurrido < 0.5, f"la petición esperó a la IA {transcurrido:.2f} s"
    # La generación queda encargada a un hilo, no perdida.
    deadline = time.monotonic() + 5
    while not llamadas and time.monotonic() < deadline:
        time.sleep(0.02)
    assert llamadas, "el refresco en segundo plano no llegó a lanzarse"


def test_refresco_en_segundo_plano_es_single_flight(monkeypatch):
    comentarista = _comentarista()
    comentarista._reset_estado_refresco()
    barrera = threading.Event()
    entradas = []

    def chat_bloqueante(*args, **kwargs):
        entradas.append(args)
        barrera.wait(5)
        return json.dumps({"comentarios": [{"partido": 1, "texto": "empata el Málaga"}]})

    monkeypatch.setattr(comentarista, "ai_enabled", lambda: True)
    monkeypatch.setattr(comentarista, "cache_get", lambda *args: None)
    monkeypatch.setattr(comentarista, "cache_get_latest", lambda *args: None)
    monkeypatch.setattr(comentarista, "reserve_call", lambda: True)
    monkeypatch.setattr(comentarista, "cache_set", lambda *args: None)
    monkeypatch.setattr(comentarista, "_cargar_emitidos", lambda: [])
    monkeypatch.setattr(comentarista, "_guardar_emitidos", lambda emitidos: None)
    monkeypatch.setattr(comentarista, "chat", chat_bloqueante)

    comentarista.comentarios_para_web([PARTIDO_EN_JUEGO])
    comentarista.comentarios_para_web([PARTIDO_EN_JUEGO])
    comentarista.comentarios_para_web([PARTIDO_EN_JUEGO])
    barrera.set()
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and comentarista._refresco_en_curso:
        time.sleep(0.02)

    assert len(entradas) == 1, f"se lanzaron {len(entradas)} llamadas a la IA a la vez"
    assert comentarista._refresco_en_curso is False


def test_la_ruta_del_directo_usa_la_variante_no_bloqueante():
    source = (ROOT / "liga_maestros" / "routes" / "liga_data.py").read_text(encoding="utf-8")
    assert "comentarios_para_web" in source
    bloque = source.split("def _build_comentarista_payload", 1)[1].split("\ndef ", 1)[0]
    assert "construir_comentarios" not in bloque


# --- Backend: el payload del directo ya no repite trabajo -------------------


def test_clean_team_key_memoizado_devuelve_lo_mismo():
    from liga_maestros.utils import clean_team_key

    assert clean_team_key("Sevilla (M)") == "SEVILLA"
    assert clean_team_key("Sevilla (F)") == "SEVILLA F"
    assert clean_team_key("  RCD  Espanyol ") == "ESPANYOL"
    assert clean_team_key(None) == ""
    # Distintas llamadas con el mismo texto pasan por la memoización.
    assert clean_team_key("Sevilla (M)") == clean_team_key("SEVILLA (M)")


def test_load_team_logos_cachea_y_se_invalida_con_el_fichero(tmp_path, monkeypatch):
    import config
    from liga_maestros import utils

    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(utils, "DATA_DIR", str(tmp_path))
    logos_path = tmp_path / "TEAM_LOGOS.json"
    # Nombre fuera del manifiesto de escudos del repo, para medir solo el JSON.
    logos_path.write_text(json.dumps({"Zarzalejo Deportivo": "https://example.test/v1.png"}), encoding="utf-8")

    primero = utils.load_team_logos()
    assert primero["ZARZALEJO DEPORTIVO"] == "https://example.test/v1.png"

    # Sin cambios en disco, la segunda lectura sale de la caché.
    assert utils.load_team_logos() == primero

    # Un scrape nuevo entra sin reiniciar la app.
    time.sleep(0.01)
    logos_path.write_text(json.dumps({"Zarzalejo Deportivo": "https://example.test/v2.png"}), encoding="utf-8")
    assert utils.load_team_logos()["ZARZALEJO DEPORTIVO"] == "https://example.test/v2.png"
