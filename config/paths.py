"""Centralized path calculations for config package."""

import os

from dotenv import load_dotenv

# Cargar variables de entorno una sola vez.
load_dotenv()

# Directorio base del proyecto (raíz de web2.0, un nivel arriba de config/).
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Datos runtime: Render usa /var/data, si no, data/ junto al proyecto.
RENDER_DATA_DIR = "/var/data"
DEFAULT_DATA_DIR = (
    RENDER_DATA_DIR if os.getenv("RENDER") and os.path.isdir(RENDER_DATA_DIR) else os.path.join(BASE_DIR, "data")
)
DATA_DIR = os.getenv("DATA_DIR", "").strip() or DEFAULT_DATA_DIR
SEED_DATA_DIR = os.path.join(BASE_DIR, "data")


def data_path(*parts: str) -> str:
    """Build a path inside the runtime DATA_DIR."""
    return os.path.join(DATA_DIR, *parts)


def ensure_runtime_data_dir() -> None:
    """Create DATA_DIR and copy seed JSONs when runtime != seed."""
    import shutil

    os.makedirs(DATA_DIR, exist_ok=True)
    if os.path.abspath(DATA_DIR) == os.path.abspath(SEED_DATA_DIR):
        return
    if not os.path.isdir(SEED_DATA_DIR):
        return
    for name in os.listdir(SEED_DATA_DIR):
        src = os.path.join(SEED_DATA_DIR, name)
        dst = os.path.join(DATA_DIR, name)
        if os.path.isfile(src) and name.lower().endswith(".json") and not os.path.exists(dst):
            shutil.copy2(src, dst)
