import json
import sqlite3

from liga_maestros.db.migrations import _import_compact_prediction_tickets, ensure_core_tables
from liga_maestros.services.payloads.predictions import _load_prediction_reasons


def _ticket(sign="1", pleno="2-1"):
    return {"signos": [sign] * 14 + [pleno], "razones": [f"Razón {idx}" for idx in range(1, 16)]}


def test_import_compact_prediction_tickets_imports_complete_valid_masters(tmp_path, monkeypatch):
    payload = {
        "jornada": 2,
        "gemini": _ticket(),
        "chatgpt": _ticket("X", "M-1"),
        "metadata": {"signos": ["1"]},
    }
    (tmp_path / "predicciones_J2.json").write_text(json.dumps(payload), encoding="utf-8")

    import config

    monkeypatch.setattr(config, "SEED_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path / "runtime"))

    conn = sqlite3.connect(":memory:")
    ensure_core_tables(conn)

    assert _import_compact_prediction_tickets(conn, 2) == 30
    rows = conn.execute(
        "SELECT user_id, partido_id, signo FROM predicciones WHERE jornada=2 ORDER BY user_id, partido_id"
    ).fetchall()
    assert len(rows) == 30
    assert rows[14] == ("chatgpt", 15, "M-1")
    assert rows[29] == ("gemini", 15, "2-1")


def test_load_prediction_reasons_falls_back_to_compact_jornada_file(tmp_path, monkeypatch):
    payload = {"jornada": 2, "gemini": _ticket()}
    (tmp_path / "predicciones_J2.json").write_text(json.dumps(payload), encoding="utf-8")

    import config

    monkeypatch.setattr(config, "SEED_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path / "runtime"))

    reasons = _load_prediction_reasons(2)

    assert list(reasons) == ["gemini"]
    assert len(reasons["gemini"]) == 15
    assert reasons["gemini"][0] == "Razón 1"
    assert reasons["gemini"][14] == "Razón 15"
