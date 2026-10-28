"""Regresion: el selector de pleno debe ser visible tambien en portada."""

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(shutil.which("node") is None, reason="Node is required")
def test_pleno_picker_assets_and_confirmation():
    subprocess.run(["node", "tests/js/check_pleno_picker.js"], cwd=ROOT, check=True)
