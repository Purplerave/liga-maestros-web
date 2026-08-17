"""El cliente de IA prioriza MiMo (Token Plan) y degrada a Groq/Gemini.

Fija el contrato del orden de proveedores y de la seleccion por key:
- MiMo va primero (plan de tokens ya pagado, coste marginal cero).
- Sin MIMO_API_KEY, se salta a Groq/Gemini sin fallar.
- ai_enabled() reconoce cualquiera de las tres keys.
"""

import importlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _client():
    mod = importlib.import_module("liga_maestros.services.ai.client")
    return importlib.reload(mod)


def test_provider_order_mimo_first():
    client = _client()
    names = [provider["name"] for provider in client.PROVIDERS]
    assert names == ["mimo", "groq", "gemini"]


def test_mimo_uses_token_plan_endpoint_and_omni_by_default(monkeypatch):
    monkeypatch.delenv("MIMO_BASE_URL", raising=False)
    monkeypatch.delenv("MIMO_MODEL", raising=False)
    client = _client()
    mimo = client.PROVIDERS[0]
    assert mimo["url"] == "https://token-plan-ams.xiaomimimo.com/v1/chat/completions"
    # Omni consume 1 credito/token frente a los 2 de Pro: es el default sensato.
    assert mimo["model"] == "mimo-v2-omni"
    assert mimo["key_env"] == "MIMO_API_KEY"


def test_mimo_base_url_and_model_overridable(monkeypatch):
    monkeypatch.setenv("MIMO_BASE_URL", "https://token-plan-sgp.xiaomimimo.com/v1/")
    monkeypatch.setenv("MIMO_MODEL", "mimo-v2-pro")
    client = _client()
    mimo = client.PROVIDERS[0]
    assert mimo["url"] == "https://token-plan-sgp.xiaomimimo.com/v1/chat/completions"
    assert mimo["model"] == "mimo-v2-pro"


def test_ai_enabled_with_only_mimo_key(monkeypatch):
    client = _client()
    monkeypatch.setenv("AI_NEWS_ENABLED", "1")
    monkeypatch.setenv("MIMO_API_KEY", "tp-test")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert client.ai_enabled() is True


def test_chat_skips_mimo_without_key_and_uses_groq(monkeypatch):
    client = _client()
    monkeypatch.delenv("MIMO_API_KEY", raising=False)
    monkeypatch.setenv("GROQ_API_KEY", "gsk-test")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    called = []

    class _Resp:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": '{"ok": true}'}}]}

    def _fake_post(url, **kwargs):
        called.append(url)
        return _Resp()

    monkeypatch.setattr(client.requests, "post", _fake_post)
    out = client.chat([{"role": "user", "content": "hola"}])
    assert out == '{"ok": true}'
    assert called == ["https://api.groq.com/openai/v1/chat/completions"]


def test_chat_prefers_mimo_when_key_present(monkeypatch):
    client = _client()
    monkeypatch.setenv("MIMO_API_KEY", "tp-test")
    monkeypatch.setenv("GROQ_API_KEY", "gsk-test")

    called = []

    class _Resp:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": "respuesta"}}]}

    def _fake_post(url, **kwargs):
        called.append(url)
        return _Resp()

    monkeypatch.setattr(client.requests, "post", _fake_post)
    out = client.chat([{"role": "user", "content": "hola"}], json_mode=False)
    assert out == "respuesta"
    assert len(called) == 1
    assert "xiaomimimo.com" in called[0]
