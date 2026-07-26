"""El parte de bajas debe degradar sin ruido y no gastar tokens de mas."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from liga_maestros.services.ai import bajas as bajas_mod

NOTICIAS = [
    {
        "title": "El Betis pierde a Isco por lesion muscular",
        "summary": "El centrocampista sufre una lesion en el biceps femoral y sera baja.",
        "score": 6,
    },
    {
        "title": "Bellingham, duda para el derbi",
        "summary": "El ingles arrastra molestias y se decide el sabado.",
        "score": 6,
    },
]

PARTIDOS = [
    {"id": 7, "local": "Alaves", "visitante": "Betis"},
    {"id": 8, "local": "Real Madrid", "visitante": "Getafe"},
]


def test_sin_api_key_devuelve_lista_vacia(monkeypatch):
    """Sin configurar nada, la funcion no falla ni llama a ningun proveedor."""
    monkeypatch.setenv("AI_NEWS_ENABLED", "0")
    assert bajas_mod.construir_parte_bajas(NOTICIAS) == []


def test_no_llama_a_la_ia_si_esta_desactivada(monkeypatch):
    """Con el flag apagado no debe salir ni una peticion de red."""
    monkeypatch.setenv("AI_NEWS_ENABLED", "0")

    def _explota(*args, **kwargs):
        raise AssertionError("No se debe llamar a la IA con el flag apagado")

    monkeypatch.setattr(bajas_mod, "chat", _explota)
    assert bajas_mod.construir_parte_bajas(NOTICIAS) == []


def test_valida_estados_y_descarta_basura():
    crudas = [
        {
            "jugador": "Isco",
            "equipo": "Betis",
            "estado": "baja",
            "nota": "lesion muscular",
        },
        {
            "jugador": "X",
            "equipo": "Betis",
            "estado": "inventado",
            "nota": "?",
        },  # estado invalido
        {
            "jugador": "",
            "equipo": "Betis",
            "estado": "baja",
            "nota": "sin nombre",
        },  # sin jugador
        {
            "jugador": "Isco",
            "equipo": "Betis",
            "estado": "baja",
            "nota": "duplicado",
        },  # repetido
    ]
    limpias = bajas_mod._validar_bajas(crudas)
    assert len(limpias) == 1
    assert limpias[0]["jugador"] == "Isco"
    assert limpias[0]["icono"]


def test_descarta_equipos_que_no_existen_en_la_jornada():
    """Antialucinacion: si la IA inventa un equipo, esa baja se cae."""
    crudas = [
        {"jugador": "Isco", "equipo": "Betis", "estado": "baja", "nota": "lesion"},
        {
            "jugador": "Fulano",
            "equipo": "Equipo Inventado FC",
            "estado": "baja",
            "nota": "x",
        },
    ]
    validos = bajas_mod.equipos_de_jornada(PARTIDOS)
    limpias = bajas_mod._validar_bajas(crudas, validos)
    assert [b["equipo"] for b in limpias] == ["Betis"]


def test_cruce_con_partidos_no_consume_ia():
    bajas = [
        {
            "jugador": "Isco",
            "equipo": "Betis",
            "estado": "baja",
            "nota": "lesion",
            "icono": "x",
        }
    ]
    cruce = bajas_mod.bajas_por_partido(bajas, PARTIDOS)
    assert 7 in cruce
    assert cruce[7][0]["jugador"] == "Isco"
    assert 8 not in cruce


def test_entrada_se_recorta_para_no_gastar_tokens():
    muchas = [{"title": f"Noticia {i}", "summary": "x" * 500, "score": 6} for i in range(30)]
    entrada = bajas_mod._preparar_entrada(muchas)
    assert len(entrada) <= bajas_mod.MAX_NOTICIAS
    assert all(len(item["s"]) <= 220 for item in entrada)
    assert all(len(item["t"]) <= 120 for item in entrada)
