"""Database paths and seed/bootstrap locations."""

import os

from . import BASE_DIR, DATA_DIR

# Primary database path (runtime). Can be overridden with DB_PATH.
DEFAULT_DB_PATH = (
    os.path.join(DATA_DIR, "LIGA_MAESTROS_PRO.db")
    if os.getenv("RENDER")
    else os.path.join(BASE_DIR, "DATOS", "LIGA_MAESTROS_PRO.db")
)
DB_PATH = os.getenv("DB_PATH", "").strip() or DEFAULT_DB_PATH

# Bootstrap / seed files.
BOOTSTRAP_DB_PATH = os.path.join(BASE_DIR, "DATOS", "LIGA_MAESTROS_PRO.db")
PRODUCTION_SEED_PATH = os.getenv("PRODUCTION_SEED_PATH", "").strip() or os.path.join(
    BASE_DIR, "data", "bootstrap", "production_seed.json"
)
FIXTURE_CORRECTIONS_PATH = os.getenv("FIXTURE_CORRECTIONS_PATH", "").strip() or os.path.join(
    BASE_DIR, "data", "bootstrap", "fixture_corrections.json"
)

# Backups directory.
DB_BACKUP_DIR = os.getenv("DB_BACKUP_DIR", os.path.join(DATA_DIR, "backups"))
