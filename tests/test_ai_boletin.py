"""El boletin resume noticias generales y conserva su fuente verificable."""

import json

from liga_maestros.services.ai import boletin

NOTICIAS = [
    {
        "source": "Marca",
        "title": "El Real Madrid trabaja el fichaje de Yan Diomande",
        "summary": "La operacion depende de las pretensiones del RB Leipzig.",
        "published_at": "2026-07-25 10:00",
        "link": "https://example.com/real-madrid",
    },
    {
        "source": "AS",
        "title": "Josan renueva con el Elche",
        "summary": "El extremo cumplira su decima temporada.",
        "published_at": "2026-07-25 11:00",
        "link": "https://example.com/elche",
    },
]


def test_valida_novedades_contra_la_noticia_original():
    crudas = [
        {"id": 1, "texto": "El Madrid negocia por Diomande con el Leipzig", "categoria": "fichaje"},
        {"id": 99, "texto": "Esta noticia no existe en las fuentes", "categoria": "club"},
    ]

    resultado = boletin._validar_novedades(crudas, NOTICIAS)

    assert len(resultado) == 1
    assert resultado[0]["source"] == "Marca"
    assert resultado[0]["link"] == NOTICIAS[0]["link"]


def test_una_llamada_devuelve_noticias_y_bajas(monkeypatch):
    monkeypatch.setattr(boletin, "ai_enabled", lambda: True)
    monkeypatch.setattr(boletin, "cache_get", lambda *args: None)
    monkeypatch.setattr(boletin, "cache_get_latest", lambda *args: None)
    monkeypatch.setattr(boletin, "reserve_call", lambda: True)
    monkeypatch.setattr(boletin, "cache_set", lambda *args: None)
    monkeypatch.setattr(
        boletin,
        "chat",
        lambda *args, **kwargs: json.dumps(
            {
                "novedades": [
                    {
                        "id": 2,
                        "texto": "Josan seguira una temporada mas en el Elche",
                        "categoria": "club",
                    }
                ],
                "bajas": [
                    {
                        "id": 2,
                        "jugador": "Josan",
                        "equipo": "Elche",
                        "estado": "duda",
                        "nota": "molestias",
                    }
                ],
            }
        ),
    )

    resultado = boletin.construir_boletin(NOTICIAS)

    assert resultado["novedades"][0]["source"] == "AS"
    assert resultado["bajas"][0]["estado"] == "duda"


def test_descarta_baja_que_mezcla_dos_noticias():
    crudas = [
        {
            "id": 1,
            "jugador": "Josan",
            "equipo": "Real Madrid",
            "estado": "baja",
            "nota": "mezcla fuentes",
        }
    ]

    assert boletin._validar_bajas_con_fuente(crudas, NOTICIAS) == []


def test_reutiliza_boletin_reciente_sin_gastar(monkeypatch):
    esperado = {"novedades": [{"texto": "Boletin anterior"}], "bajas": []}
    monkeypatch.setattr(boletin, "ai_enabled", lambda: True)
    monkeypatch.setattr(boletin, "cache_get", lambda *args: None)
    monkeypatch.setattr(boletin, "cache_get_latest", lambda *args: esperado)
    monkeypatch.setattr(
        boletin,
        "reserve_call",
        lambda: (_ for _ in ()).throw(AssertionError("No debe reservar llamada")),
    )

    assert boletin.construir_boletin(NOTICIAS) == esperado


def test_reutiliza_firma_exacta_sin_perder_novedades(monkeypatch):
    esperado = {
        "novedades": [
            {
                "texto": "El Madrid negocia el fichaje de Diomande",
                "categoria": "fichaje",
                "source": "Marca",
                "link": "https://example.com/real-madrid",
            }
        ],
        "bajas": [],
    }
    monkeypatch.setattr(boletin, "ai_enabled", lambda: True)
    monkeypatch.setattr(boletin, "cache_get", lambda *args: esperado)
    monkeypatch.setattr(
        boletin,
        "reserve_call",
        lambda: (_ for _ in ()).throw(AssertionError("No debe reservar llamada")),
    )

    assert boletin.construir_boletin(NOTICIAS) == esperado
