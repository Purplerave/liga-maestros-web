"""El comentarista MiMo genera frases breves del directo sin inventar ni gastar de más."""

import json

from liga_maestros.services.ai import comentarista

PARTIDOS = [
    {"local": "Barcelona", "visitante": "Atlético de Madrid", "status": "LIVE", "minuto": "63", "marcador": "2-1"},
    {"local": "Real Betis", "visitante": "Sevilla", "status": "HT", "minuto": "45", "marcador": "0-0"},
]


def _sin_cache(monkeypatch):
    monkeypatch.setattr(comentarista, "ai_enabled", lambda: True)
    monkeypatch.setattr(comentarista, "cache_get", lambda *args: None)
    monkeypatch.setattr(comentarista, "cache_get_latest", lambda *args: None)
    monkeypatch.setattr(comentarista, "reserve_call", lambda: True)
    monkeypatch.setattr(comentarista, "cache_set", lambda *args: None)
    monkeypatch.setattr(comentarista, "_cargar_emitidos", lambda: [])
    monkeypatch.setattr(comentarista, "_guardar_emitidos", lambda emitidos: None)


def test_valida_comentarios_contra_el_partido_original():
    entrada = comentarista._preparar_entrada(comentarista._live_matches(PARTIDOS))

    crudas = [
        {"partido": 1, "texto": "Gol de Lewandowski para el Barcelona"},
        {"partido": 99, "texto": "Este partido no existe en la foto"},
        {"partido": 2, "texto": "U" * 40},  # demasiado largo
        {"partido": 2, "texto": "gol"},  # demasiado corto
    ]

    resultado = comentarista._validar_comentarios(crudas, entrada)

    assert len(resultado) == 1
    assert resultado[0]["texto"] == "Gol de Lewandowski para el Barcelona"
    assert resultado[0]["local"] == "Barcelona"
    assert resultado[0]["visitante"] == "Atlético de Madrid"
    assert resultado[0]["marcador"] == "2-1"


def test_sin_partidos_en_juego_no_llama(monkeypatch):
    llamadas = []
    monkeypatch.setattr(comentarista, "ai_enabled", lambda: True)
    monkeypatch.setattr(comentarista, "chat", lambda *a, **k: llamadas.append(1))

    resultado = comentarista.construir_comentarios(
        [{"local": "Barcelona", "visitante": "Madrid", "status": "FT", "minuto": "Finalizado", "marcador": "1-0"}]
    )

    assert resultado == {"comentarios": [], "generated": False}
    assert llamadas == []


def test_una_llamada_genera_comentarios(monkeypatch):
    _sin_cache(monkeypatch)
    capturado = {}

    def fake_chat(*args, **kwargs):
        capturado["kwargs"] = kwargs
        return json.dumps({"comentarios": [{"partido": 1, "texto": "Gol de Lewandowski para el Barcelona"}]})

    monkeypatch.setattr(comentarista, "chat", fake_chat)

    resultado = comentarista.construir_comentarios(PARTIDOS)

    assert resultado["generated"] is True
    assert resultado["comentarios"][0]["texto"] == "Gol de Lewandowski para el Barcelona"
    assert resultado["comentarios"][0]["local"] == "Barcelona"
    # El comentarista prefiere MiMo y no manda mas de lo necesario.
    assert capturado["kwargs"]["prefer"] == "mimo"
    assert capturado["kwargs"]["max_tokens"] <= 200


def test_cache_por_firma_evita_llamada(monkeypatch):
    cached = [
        {"texto": "Gol de Lewandowski para el Barcelona", "local": "Barcelona", "visitante": "Atlético de Madrid"}
    ]
    monkeypatch.setattr(comentarista, "ai_enabled", lambda: True)
    monkeypatch.setattr(comentarista, "cache_get", lambda *args: {"comentarios": cached})
    monkeypatch.setattr(comentarista, "chat", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no debe llamar")))

    resultado = comentarista.construir_comentarios(PARTIDOS)

    assert resultado == {"comentarios": cached, "generated": False}


def test_cadencia_minima_sirve_cache_reciente(monkeypatch):
    reciente = [{"texto": "Le toca remontar al Betis", "local": "Real Betis", "visitante": "Sevilla"}]
    monkeypatch.setattr(comentarista, "ai_enabled", lambda: True)
    monkeypatch.setattr(comentarista, "cache_get", lambda *args: None)
    monkeypatch.setattr(comentarista, "cache_get_latest", lambda *args: {"comentarios": reciente})
    monkeypatch.setattr(comentarista, "chat", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no debe llamar")))

    resultado = comentarista.construir_comentarios(PARTIDOS)

    assert resultado == {"comentarios": reciente, "generated": False}


def test_cuota_agotada_no_llama_y_degradar(monkeypatch):
    monkeypatch.setattr(comentarista, "ai_enabled", lambda: True)
    monkeypatch.setattr(comentarista, "cache_get", lambda *args: None)
    monkeypatch.setattr(comentarista, "cache_get_latest", lambda *args: None)
    monkeypatch.setattr(comentarista, "reserve_call", lambda: False)
    monkeypatch.setattr(comentarista, "chat", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no debe llamar")))

    resultado = comentarista.construir_comentarios(PARTIDOS)

    assert resultado == {"comentarios": [], "generated": False}


def test_respuesta_en_prosa_se_parsea_igual():
    cruda = 'Aquí va tu JSON: {"comentarios":[{"partido":1,"texto":"Gol de Lewandowski para el Barcelona"}]} listo.'

    parsed = comentarista._parsear_json(cruda)

    assert parsed["comentarios"][0]["partido"] == 1


def test_respuesta_invalida_degradar_sin_lanzar(monkeypatch):
    _sin_cache(monkeypatch)
    monkeypatch.setattr(comentarista, "chat", lambda *a, **k: "esto no es json")

    resultado = comentarista.construir_comentarios(PARTIDOS)

    assert resultado == {"comentarios": [], "generated": False}
