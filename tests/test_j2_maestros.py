import json
import sqlite3
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from liga_maestros.db.migrations import (
    _import_compact_prediction_tickets,
    ensure_core_tables,
    ensure_jornada_2,
    ensure_predicciones_unique_index,
)
from liga_maestros.scoring import normalize_prediction_sign
from liga_maestros.services.payloads.predictions import _load_prediction_reasons

MAESTROS = {"gemini", "claude", "grok", "chatgpt", "copilot", "programa"}
PENA_12 = {
    "chipi",
    "geli",
    "pepe",
    "profe",
    "fortu",
    "oraculo",
    "sesudo",
    "luzia",
    "erniebot",
    "jimmy",
    "sonia",
    "sonia2",
}
PENA_WITH_REASONS = PENA_12 - {"sonia", "sonia2"}
PENA_PENDING = {"luna", "fistro"}
CHIPI_SIGNOS = ["1", "X", "2", "1", "2", "1", "X", "1", "2", "X", "1", "1", "1", "2", "2-1"]
JIMMY_SIGNOS = ["2", "X", "1", "2", "2", "2", "1", "X", "1", "1", "X", "1", "X", "2", "M-0"]
SONIA_SIGNOS = ["1", "2", "1", "1", "2", "X", "2", "X", "2", "X", "1", "X", "1", "1", "2-1"]
SONIA2_SIGNOS = ["1", "2", "1", "1", "2", "1", "2", "2", "2", "X", "1", "1", "1", "1", "2-1"]
FORTU_PLENO = "2-0"
PROGRAMA_SIGNOS = ["1", "1", "2", "1X", "2", "1", "12", "1", "2", "1", "1", "1", "12", "2", "1-1"]


def _ticket(sign="1", pleno="2-1"):
    return {"signos": [sign] * 14 + [pleno], "razones": [f"Razón {idx}" for idx in range(1, 16)]}


def _load_j2():
    with open("data/predicciones_J2.json", encoding="utf-8") as fh:
        return json.load(fh)


def _test_app(tmp_path, monkeypatch):
    import config
    from liga_maestros import create_app
    from liga_maestros.routes import liga_data

    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "j2.db"))
    monkeypatch.setattr(config, "BOOTSTRAP_DB_PATH", str(tmp_path / "missing.db"))
    monkeypatch.setattr(config, "PRODUCTION_SEED_PATH", str(config.PRODUCTION_SEED_PATH))
    monkeypatch.setattr(config, "DB_BACKUP_DIR", str(tmp_path / "backups"))
    monkeypatch.setenv("SECRET_KEY", "j2-test-secret")
    monkeypatch.setenv("WEB_COLLECTOR_ENABLED", "0")
    monkeypatch.setenv("DB_BACKUP_ENABLED", "0")
    monkeypatch.setenv("ALLOW_LOCAL_ADMIN", "0")
    monkeypatch.setenv("TRUSTED_HOSTS", "localhost,127.0.0.1")
    monkeypatch.setattr(
        liga_data,
        "madrid_now",
        lambda: datetime(2026, 8, 19, 18, 0, tzinfo=ZoneInfo("Europe/Madrid")),
    )
    return create_app()


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


def test_j2_file_has_six_masters_and_twelve_pena_tickets():
    payload = _load_j2()
    assert payload["jornada"] == 2
    tickets = {uid: entry for uid, entry in payload.items() if isinstance(entry, dict) and entry.get("signos")}
    assert MAESTROS <= set(tickets)
    assert PENA_12 <= set(tickets)
    assert PENA_PENDING.isdisjoint(tickets)
    assert tickets["chipi"]["signos"] == CHIPI_SIGNOS
    assert tickets["jimmy"]["signos"] == JIMMY_SIGNOS
    assert tickets["sonia"]["signos"] == SONIA_SIGNOS
    assert tickets["sonia2"]["signos"] == SONIA2_SIGNOS
    assert tickets["fortu"]["signos"][14] == FORTU_PLENO
    assert tickets["programa"]["signos"] == PROGRAMA_SIGNOS
    for uid, entry in tickets.items():
        signos = entry["signos"]
        razones = entry.get("razones") or []
        assert len(signos) == 15, uid
        if uid in PENA_WITH_REASONS:
            assert len(razones) == 15, uid
        normalized = [normalize_prediction_sign(pid, value) for pid, value in enumerate(signos, start=1)]
        assert all(sign and sign != "-" for sign in normalized), (uid, normalized)


def test_ensure_jornada_2_imports_masters_and_pena():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_core_tables(conn)
    ensure_predicciones_unique_index(conn)

    imported = ensure_jornada_2(conn)
    assert imported >= 270
    rows = conn.execute(
        "SELECT user_id, signo FROM predicciones WHERE jornada = 2 ORDER BY user_id, partido_id"
    ).fetchall()
    by_user = {}
    for row in rows:
        by_user.setdefault(row["user_id"], []).append(row["signo"])
    assert MAESTROS | PENA_12 <= set(by_user)
    assert by_user["chipi"] == CHIPI_SIGNOS
    assert by_user["jimmy"] == JIMMY_SIGNOS
    assert by_user["sonia"] == SONIA_SIGNOS
    assert by_user["sonia2"] == SONIA2_SIGNOS
    assert by_user["chatgpt"][14] == "M-1"
    assert by_user["fortu"][14] == FORTU_PLENO
    assert by_user["programa"] == PROGRAMA_SIGNOS
    assert PENA_PENDING.isdisjoint(by_user)

    ensure_jornada_2(conn)
    again = conn.execute("SELECT COUNT(*) FROM predicciones WHERE jornada = 2").fetchone()[0]
    assert again == len(rows)


def test_j2_prediction_reasons_include_pena_explanations():
    reasons = _load_prediction_reasons(2)
    assert MAESTROS | PENA_WITH_REASONS <= set(reasons)
    assert len(reasons["programa"]) == 15
    assert "Motor v4" in reasons["programa"][0]
    assert len(reasons["oraculo"]) == 15
    assert "San Mamés" in reasons["luzia"][0] or "Athletic" in reasons["luzia"][0]
    assert reasons["erniebot"][14]


def test_api_liga_data_j2_hides_pena_tickets_and_exposes_consensus(tmp_path, monkeypatch):
    app = _test_app(tmp_path, monkeypatch)
    response = app.test_client().get("/api/liga/data?j=2")
    assert response.status_code == 200
    payload = response.get_json()

    assert payload["jornada"] == "2"
    assert payload["partidos"][0]["local"] == "Athletic"
    assert payload["partidos"][14]["visitante"] == "Villarreal"
    assert payload["is_locked"] is False

    predicciones = payload["predicciones_actuales"]
    assert MAESTROS <= set(predicciones)
    assert PENA_12.isdisjoint(predicciones)
    assert predicciones["programa"]["signos"] == PROGRAMA_SIGNOS
    assert len(predicciones["programa"]["motivos"]) == 15

    consenso = payload["consenso_pena"]
    assert len(consenso) == 14
    assert all(item["total"] == 12 for item in consenso)
    assert all(item["fuente"] == "pena" for item in consenso)
    assert consenso[0]["ganador"] == "1"
    assert consenso[4]["ganador"] == "2"
    assert consenso[8]["ganador"] == "2"

    pleno = payload["consenso_pleno_pena"]
    assert pleno["valid"] == 12
    assert pleno["exactCounts"]["2-1"] == 9
    assert pleno["exactCounts"]["M-0"] == 1
    assert pleno["topScore"] == ["2-1", 9]


def test_pena_revision_file_matches_compact_tickets():
    compact = _load_j2()
    revision = json.loads(Path("data/predicciones_J2_pena_revision.json").read_text(encoding="utf-8"))
    assert revision["jornada"] == 2
    assert set(revision["entregados"]) == PENA_12
    assert set(revision["pendientes"]) == PENA_PENDING
    assert revision["entregados"]["sonia"]["signos"] == SONIA_SIGNOS
    assert revision["entregados"]["sonia2"]["signos"] == SONIA2_SIGNOS
    for uid, entry in revision["entregados"].items():
        assert compact[uid]["signos"] == entry["signos"]
