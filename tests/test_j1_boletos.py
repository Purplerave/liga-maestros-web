"""Acceptance: J1 boletos publicados para la temporada 2026-2027.

Contrato (aportado por el usuario el 12/08):
- Copilot publica su boleto REAL: X,1,1,1,1,X,X,1,1,1,1,1,X,1,1-0.
- La Peña (12 peñistas: chipi, geli, pepe, profe, fortu, oraculo, fistro,
  sesudo, jimmy, luzia, luna, erniebot) entrega sus boletos; MrPurple es el
  usuario humano y rellena su quiniela en la web.
- /api/liga/data?j=1 devuelve copilot con esos signos y consenso_pena con
  total 12 votos por partido.
"""

import json
import sqlite3

import config
from liga_maestros import create_app
from liga_maestros.db.migrations import ensure_core_tables, ensure_jornada_1, ensure_predicciones_unique_index

COPILOT_SIGNOS = ["X", "1", "1", "1", "1", "X", "X", "1", "1", "1", "1", "1", "X", "1", "1-0"]

PENA_12 = {
    "chipi",
    "geli",
    "pepe",
    "profe",
    "fortu",
    "oraculo",
    "fistro",
    "sesudo",
    "jimmy",
    "luzia",
    "luna",
    "erniebot",
}
MAESTROS = {"gemini", "claude", "grok", "chatgpt", "copilot"}


def _test_app(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "j1.db"))
    monkeypatch.setattr(config, "BOOTSTRAP_DB_PATH", str(tmp_path / "missing.db"))
    monkeypatch.setattr(config, "PRODUCTION_SEED_PATH", str(config.PRODUCTION_SEED_PATH))
    monkeypatch.setattr(config, "DB_BACKUP_DIR", str(tmp_path / "backups"))
    monkeypatch.setenv("SECRET_KEY", "j1-test-secret")
    monkeypatch.setenv("WEB_COLLECTOR_ENABLED", "0")
    monkeypatch.setenv("DB_BACKUP_ENABLED", "0")
    monkeypatch.setenv("ALLOW_LOCAL_ADMIN", "0")
    monkeypatch.setenv("TRUSTED_HOSTS", "localhost,127.0.0.1")
    return create_app()


def test_arena_file_has_copilot_real_ticket_and_12_pena_members():
    with open("data/inbox/JORNADA_1_LM_ARENA.json", encoding="utf-8") as fh:
        arena = json.load(fh)
    assert arena["jornada"] == 1
    pronosticos = {p["participante_id"]: p for p in arena["pronosticos"]}

    assert pronosticos["copilot"]["signos"] == COPILOT_SIGNOS
    assert pronosticos["copilot"]["grupo"] == "maestro"

    pena = {uid for uid, p in pronosticos.items() if p["grupo"] == "pena"}
    maestros = {uid for uid, p in pronosticos.items() if p["grupo"] == "maestro"}
    assert pena == PENA_12
    assert maestros == MAESTROS
    assert "mrpurple" not in pronosticos  # el usuario rellena su quiniela en la web
    for p in pronosticos.values():
        assert len(p["signos"]) == 15
        assert len(p.get("razones", [])) == 15


def test_ensure_jornada_1_imports_boletos_from_arena_file():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_core_tables(conn)
    ensure_predicciones_unique_index(conn)

    ensure_jornada_1(conn)
    assert conn.execute("SELECT COUNT(*) FROM resultados WHERE jornada = 1").fetchone()[0] == 15

    rows = conn.execute(
        "SELECT user_id, signo FROM predicciones WHERE jornada = 1 ORDER BY user_id, partido_id"
    ).fetchall()
    by_user = {}
    for row in rows:
        by_user.setdefault(row["user_id"], []).append(row["signo"])
    assert by_user["copilot"] == COPILOT_SIGNOS
    assert set(by_user) == MAESTROS | PENA_12

    # Idempotente: re-ejecutar no duplica ni cambia los boletos
    ensure_jornada_1(conn)
    again = conn.execute("SELECT COUNT(*) FROM predicciones WHERE jornada = 1").fetchone()[0]
    assert again == len(rows)


def test_api_liga_data_j1_returns_copilot_and_pena_consensus_total_12(tmp_path, monkeypatch):
    app = _test_app(tmp_path, monkeypatch)
    response = app.test_client().get("/api/liga/data?j=1")
    assert response.status_code == 200
    payload = response.get_json()

    assert payload["jornada"] == "1"
    assert payload["partidos"][0]["local"] == "Real Oviedo"

    copilot = payload["predicciones_actuales"]["copilot"]["signos"]
    assert copilot == COPILOT_SIGNOS

    consenso = payload["consenso_pena"]
    assert len(consenso) == 14
    assert all(item["total"] == 12 for item in consenso)
    assert all(item["fuente"] == "pena" for item in consenso)

    # Los maestros son públicos antes del cierre; La Peña no se filtra (privacidad)
    predicciones = payload["predicciones_actuales"]
    assert {"copilot", "gemini", "claude", "grok", "chatgpt"} <= set(predicciones)
    assert PENA_12.isdisjoint(predicciones)
