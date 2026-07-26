"""Cliente minimo para APIs de IA con tier gratuito.

Groq y Gemini exponen endpoints compatibles con OpenAI, asi que un unico cliente
sirve para ambos y no hace falta ninguna dependencia nueva: basta `requests`,
que ya esta en requirements.txt.

Orden de preferencia:
  1. Groq (Llama 3.3 70B) - rapido y no entrena con los datos enviados.
  2. Gemini 2.5 Flash - reserva con cuota diaria mas amplia.
"""

import logging
import os

import requests

logger = logging.getLogger(__name__)

AI_TIMEOUT_SECONDS = int(os.getenv("AI_TIMEOUT_SECONDS", "10"))

PROVIDERS = (
    {
        "name": "groq",
        "url": "https://api.groq.com/openai/v1/chat/completions",
        "key_env": "GROQ_API_KEY",
        "model": os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
    },
    {
        "name": "gemini",
        "url": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
        "key_env": "GEMINI_API_KEY",
        "model": os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
    },
)


def ai_enabled():
    """La IA solo actua si esta activada por flag y hay al menos una key."""
    if os.getenv("AI_NEWS_ENABLED", "0").strip().lower() not in (
        "1",
        "true",
        "yes",
        "on",
    ):
        return False
    return any(os.getenv(provider["key_env"], "").strip() for provider in PROVIDERS)


def chat(messages, *, json_mode=True, max_tokens=600, temperature=0.2):
    """Pide una respuesta al primer proveedor disponible.

    Devuelve el texto de la respuesta, o None si ninguno responde.
    Nunca lanza: quien llama decide como degradar.
    """
    for provider in PROVIDERS:
        api_key = os.getenv(provider["key_env"], "").strip()
        if not api_key:
            continue

        body = {
            "model": provider["model"],
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}

        try:
            response = requests.post(
                provider["url"],
                json=body,
                timeout=AI_TIMEOUT_SECONDS,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            if content and content.strip():
                logger.info("IA: respuesta obtenida de %s", provider["name"])
                return content.strip()
        except Exception as exc:
            logger.warning("IA: fallo en %s (%s)", provider["name"], exc)
            continue

    return None
