"""Aislamiento global del estado para toda la suite.

Sin este fichero, cualquier test que llama a `create_app()` dispara
`run_startup_migrations()` → `sync_runtime_standings_files()`, que escribe en
`config.SEED_DATA_DIR` (= `<repo>/data/`) cuando la cache está stale. Como
`data/MULTI_STANDINGS.json` está versionado, cada `pytest` dejaba el árbol de
trabajo con diffs fantasma que el developer acababa commiteando por error.

Aquí se copia el seed a un directorio temporal y se parchea la variable, de modo
que los tests leen los datos reales de la jornada pero escriben siempre en el
temporal. Los ficheros que un test individual ya parchea (los que usan
`monkeypatch.setattr(config, "DB_PATH", ...)`) siguen mandando, porque este
fixture sólo actúa cuando nadie lo ha pisado antes.
"""

import os
import shutil

import pytest

import config

# Ficheros de `data/` que la app reescribe en cada arranque y que están versionados.
SEED_FILES_TO_ISOLATE = (
    "MULTI_STANDINGS.json",
    "STANDINGS_LALIGA_BASE.json",
    "STANDINGS_SEGUNDA_BASE.json",
    "standings_oficial.json",
    "PREDICCIONES_ACTUALES.json",
    "MIMO_COMENTARISTA_EMITIDOS.json",
    "LIVE_COLLECTOR_HEALTH.json",
)


@pytest.fixture(autouse=True)
def _isolate_seed_data_dir(tmp_path_factory, request):
    """Redirige SEED_DATA_DIR a un temporal durante cada test.

    Se salta a propósito los tests que ya aíslan el seed por su cuenta para no
    pisar su `tmp_path` y romper sus aserciones.
    """
    if "seed_data_dir" in request.fixturenames:
        return

    seed_dir = getattr(config, "SEED_DATA_DIR", None)
    if not seed_dir or not os.path.isdir(seed_dir):
        return

    isolated = tmp_path_factory.mktemp("seed_data")

    # Copia de lectura: los tests necesitan ver los JSON reales de la jornada.
    for name in os.listdir(seed_dir):
        src = os.path.join(seed_dir, name)
        if os.path.isfile(src) and name.lower().endswith(".json"):
            try:
                shutil.copy2(src, os.path.join(isolated, name))
            except OSError:
                # Un seed ilegible no debe romper la suite entera.
                pass

    original = seed_dir
    config.SEED_DATA_DIR = str(isolated)
    try:
        yield
    finally:
        config.SEED_DATA_DIR = original


@pytest.fixture
def seed_data_dir(tmp_path, monkeypatch):
    """Variante explícita para tests que necesitan escribir en el seed.

    Uso: `def test_x(tmp_path, monkeypatch, seed_data_dir): ...`
    """
    isolated = tmp_path / "seed"
    isolated.mkdir(parents=True, exist_ok=True)

    seed_dir = getattr(config, "SEED_DATA_DIR", None)
    if seed_dir and os.path.isdir(seed_dir):
        for name in os.listdir(seed_dir):
            src = os.path.join(seed_dir, name)
            if os.path.isfile(src) and name.lower().endswith(".json"):
                try:
                    shutil.copy2(src, os.path.join(isolated, name))
                except OSError:
                    pass

    monkeypatch.setattr(config, "SEED_DATA_DIR", str(isolated))
    return isolated
