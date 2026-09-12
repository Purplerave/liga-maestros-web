"""Cold start — retry y 503 (Tarea #1, MESA VIVA 2026-09-12).

Verifica que el fix de cold start no se pierda:
- utils.js expone fetchWithRetry global
- quantum_final.js lo usa y mantiene skeleton + botón Reintentar
- /api/liga/data devuelve 503 con Retry-After cuando no hay jornada (cache miss)
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UTILS = ROOT / "static" / "js" / "utils.js"
QUANTUM = ROOT / "static" / "js" / "quantum_final.js"
LIGA_DATA = ROOT / "liga_maestros" / "routes" / "liga_data.py"
EVENTS = ROOT / "static" / "js" / "events.js"


def test_utils_exposes_fetch_with_retry():
    text = UTILS.read_text(encoding="utf-8")
    assert "async function fetchWithRetry" in text, "utils.js debe definir fetchWithRetry"
    assert "window.fetchWithRetry" in text
    assert "503" in text and "404" in text
    assert "Retry-After" in text
    assert "500 * Math.pow(2" in text or "baseDelay" in text


def test_quantum_uses_retry_and_keeps_skeleton():
    text = QUANTUM.read_text(encoding="utf-8")
    assert "fetchWithRetry" in text, "quantum_final.js debe usar fetchWithRetry"
    assert "renderSkeletonLoading" in text
    assert "skeleton" in text.lower()
    assert "Reintentar ahora" in text
    assert "Retry-After" in text
    assert "cold_start" in text


def test_events_uses_retry_for_live_snapshot():
    text = EVENTS.read_text(encoding="utf-8")
    assert "fetchWithRetry" in text or "fetcher" in text
    assert "refreshLiveSnapshot" in text


def test_liga_data_returns_503_on_cold_start():
    text = LIGA_DATA.read_text(encoding="utf-8")
    assert "status_code = 503" in text
    assert "Retry-After" in text
    assert '"cold_start": True' in text or "'cold_start': True" in text
    assert "Cold start" in text


def test_frontend_retry_handles_network_errors():
    text = UTILS.read_text(encoding="utf-8")
    assert "Failed to fetch" in text
    assert "TypeError" in text
