"""Config corrupta no puede tumbar la app.

`int(os.getenv("X", "1"))` es una bomba de relojería: con `X=""` o `X="abc"` en el
`.env`, el error salta en tiempo de import o al construir la app, y el sitio no
arranca. Y no es hipotético: `HIGHLIGHTLY_LIGA_F_ID` se rellena a mano desde un
panel externo.

Un identificador de liga mal puesto no es motivo para que caiga la web: el
collector ya cae a las consultas por nombre de liga. Estos tests fijan que se
avisa por log y se usa el valor por defecto.
"""

import importlib
import logging

import pytest

from config.env import env_bool, env_float, env_int, env_min_int, env_str


@pytest.mark.parametrize("bruto", ["", "   ", "abc", "12,5", "1e3", "None", "0x10"])
def test_env_int_tolera_una_variable_corrupta(monkeypatch, bruto, caplog):
    monkeypatch.setenv("PRUEBA_LIMITE", bruto)
    with caplog.at_level(logging.WARNING):
        assert env_int("PRUEBA_LIMITE", 7) == 7, f"un valor corrupto no debe ganar al default: {bruto!r}"


def test_env_int_avisa_cuando_toca_el_default(monkeypatch, caplog):
    """El fallo tiene que verse en el log; si no, es silencioso."""
    monkeypatch.setenv("PRUEBA_LIMITE", "abc")
    with caplog.at_level(logging.WARNING):
        env_int("PRUEBA_LIMITE", 7)
    assert "PRUEBA_LIMITE" in caplog.text


def test_env_int_acepta_un_entero_valido(monkeypatch):
    monkeypatch.setenv("PRUEBA_LIMITE", "250")
    assert env_int("PRUEBA_LIMITE", 7) == 250


def test_env_int_acepta_espacios_alrededor(monkeypatch):
    monkeypatch.setenv("PRUEBA_LIMITE", "  42  ")
    assert env_int("PRUEBA_LIMITE", 7) == 42


def test_una_variable_ausente_devuelve_el_default():
    assert env_int("PRUEBA_NO_EXISTE_JAJA", 99) == 99


@pytest.mark.parametrize(
    ("bruto", "esperado"),
    [
        ("1", True),
        ("true", True),
        ("YES", True),
        ("on", True),
        ("si", True),
        ("0", False),
        ("false", False),
        ("no", False),
    ],
)
def test_env_bool(monkeypatch, bruto, esperado):
    monkeypatch.setenv("PRUEBA_FLAG", bruto)
    assert env_bool("PRUEBA_FLAG", not esperado) is esperado


def test_env_bool_corrupto_usa_el_default(monkeypatch):
    monkeypatch.setenv("PRUEBA_FLAG", "quiza")
    assert env_bool("PRUEBA_FLAG", False) is False


def test_env_str_trata_vacio_como_ausente(monkeypatch):
    """En un `.env` escrito a mano, CLAVE= significa "sin valor"."""
    monkeypatch.setenv("PRUEBA_TEXTO", "  ")
    assert env_str("PRUEBA_TEXTO", "Lax") == "Lax"


def test_env_float_tolera_corrupto(monkeypatch):
    monkeypatch.setenv("PRUEBA_FLOAT", "no")
    assert env_float("PRUEBA_FLOAT", 1.5) == 1.5


def test_env_min_int_respeta_el_suelo(monkeypatch):
    monkeypatch.setenv("PRUEBA_MIN", "-5")
    assert env_min_int("PRUEBA_MIN", 4, 0) == 0, "un limite de llamadas nunca debe ser negativo"


# ── La app entera, con el entorno deliberadamente roto ──────────────────────


@pytest.fixture
def entorno_roto(monkeypatch):
    """Simula un `.env` mal escrito en todas las variables numericas clave."""
    for nombre in [
        "HIGHLIGHTLY_LIGA_F_ID",
        "HIGHLIGHTLY_LIGA_F_MOEVE_ID",
        "HIGHLIGHTLY_LIGA_F_ALT_ID",
        "HIGHLIGHTLY_DAILY_CALL_LIMIT",
        "HIGHLIGHTLY_DAILY_CALL_RESERVE",
        "HIGHLIGHTLY_CIRCUIT_FAILURE_LIMIT",
        "HIGHLIGHTLY_CIRCUIT_COOLDOWN_SECONDS",
        "HIGHLIGHTLY_CIRCUIT_MAX_COOLDOWN_SECONDS",
        "HIGHLIGHTLY_MAX_CALLS_PER_REFRESH",
        "MAX_DOBLES_PER_TICKET",
        "MAX_TRIPLES_PER_TICKET",
        "MAX_CONTENT_LENGTH",
        "MAX_FORM_MEMORY_SIZE",
        "MAX_FORM_PARTS",
        "API_FOOTBALL_DAILY_LIMIT",
        "API_FOOTBALL_DAILY_RESERVE",
        "NEWS_REFRESH_SECONDS",
        "AI_DAILY_CALL_LIMIT",
        "AI_TIMEOUT_SECONDS",
        "AI_NEWS_MIN_INTERVAL_SECONDS",
        "MIMO_COMENTARISTA_MIN_INTERVAL_SECONDS",
        "PREDICTION_CLOSE_MINUTES_BEFORE_KICKOFF",
        "SESSION_LIFETIME_HOURS",
    ]:
        monkeypatch.setenv(nombre, "abc")
    return monkeypatch


@pytest.mark.parametrize(
    "modulo",
    [
        "config.api",
        "config.feeds",
        "config.game",
        "config.settings",
        "liga_maestros.services.highlightly_limits",
        "liga_maestros.services.ticket",
        "liga_maestros.services.ai.budget",
        "liga_maestros.services.ai.client",
        "liga_maestros.services.ai.boletin",
        "liga_maestros.services.ai.comentarista",
        "liga_maestros.services.highlightly",
    ],
)
def test_los_modulos_de_config_arrancan_con_el_entero_roto(entorno_roto, modulo):
    """El fallo original: estos modulos son de nivel de import, asi que un
    ValueError al leer el entorno tumbaba la app antes de servir nada."""
    importlib.import_module(modulo)
    importlib.reload(importlib.import_module(modulo))


def test_los_limites_de_highlighter_no_quedan_corruptos(entorno_roto):
    limits = importlib.reload(importlib.import_module("liga_maestros.services.highlightly_limits"))
    assert limits.HIGHLIGHTLY_DAILY_CALL_LIMIT == 7500
    assert limits.HIGHLIGHTLY_DAILY_CALL_RESERVE == 250


def test_el_limite_de_llamadas_por_refresh_no_puede_ser_negativo(entorno_roto):
    highlightly = importlib.reload(importlib.import_module("liga_maestros.services.highlightly"))
    assert highlightly.HIGHLIGHTLY_MAX_CALLS_PER_REFRESH >= 0


def test_create_app_arranca_con_el_entero_roto(entorno_roto, tmp_path):
    """La prueba de fuego: la app se construye."""
    import config
    from liga_maestros import create_app

    entorno_roto.setattr(config, "DB_PATH", str(tmp_path / "roto.db"))
    entorno_roto.setattr(config, "BOOTSTRAP_DB_PATH", str(tmp_path / "missing.db"))
    entorno_roto.setattr(config, "PRODUCTION_SEED_PATH", str(tmp_path / "missing-seed.json"))
    entorno_roto.setenv("SECRET_KEY", "test-secret")
    entorno_roto.setenv("WEB_COLLECTOR_ENABLED", "0")
    entorno_roto.setenv("DB_BACKUP_ENABLED", "0")
    app = create_app()
    assert app is not None
    assert app.config["MAX_FORM_PARTS"] == 50
    assert app.config["PERMANENT_SESSION_LIFETIME"].total_seconds() == 12 * 3600
