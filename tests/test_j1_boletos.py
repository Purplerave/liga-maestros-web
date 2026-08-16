"""Acceptance: J1 boletos publicados para la temporada 2026-2027.

Contrato (aportado por el usuario el 12/08):
- Copilot publica su boleto REAL en el orden oficial del boleto de la J1:
  1,1,X,1,X,1,1,X,1,X,1,1,1,1,1-0.
- La Peña (12 peñistas: chipi, geli, pepe, profe, fortu, oraculo, fistro,
  sesudo, jimmy, luzia, luna, erniebot) entrega sus boletos; MrPurple es el
  usuario humano y rellena su quiniela en la web.
- /api/liga/data?j=1 devuelve copilot con esos signos y consenso_pena con
  total 12 votos por partido.
"""

import json
import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo

import config
from liga_maestros import create_app
from liga_maestros.db.migrations import (
    _rekey_j1_partido_ids,
    ensure_core_tables,
    ensure_jornada_1,
    ensure_predicciones_unique_index,
)
from liga_maestros.routes import liga_data

COPILOT_SIGNOS = ["1", "1", "X", "1", "X", "1", "1", "X", "1", "X", "1", "1", "1", "1", "1-0"]
PROGRAMA_SIGNOS = ["1X", "1", "2", "1X", "1", "1", "1", "1X", "1", "1", "1", "1", "1", "1", "2-1"]

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
MAESTROS = {"gemini", "claude", "grok", "chatgpt", "copilot", "programa"}


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
    with open("data/predicciones_J1.json", encoding="utf-8") as fh:
        programa_source = json.load(fh)
    assert arena["jornada"] == 1
    pronosticos = {p["participante_id"]: p for p in arena["pronosticos"]}

    assert pronosticos["copilot"]["signos"] == COPILOT_SIGNOS
    assert pronosticos["copilot"]["grupo"] == "maestro"
    assert pronosticos["programa"]["signos"] == PROGRAMA_SIGNOS
    assert programa_source["programa"]["signos"] == PROGRAMA_SIGNOS

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
    assert by_user["programa"] == PROGRAMA_SIGNOS
    assert set(by_user) == MAESTROS | PENA_12

    # Idempotente: re-ejecutar no duplica ni cambia los boletos
    ensure_jornada_1(conn)
    again = conn.execute("SELECT COUNT(*) FROM predicciones WHERE jornada = 1").fetchone()[0]
    assert again == len(rows)


def test_rekey_j1_keeps_results_attached_to_their_match():
    """Al reordenar la J1, cada partido conserva SUS goles/estado/signo.

    El reorder no puede pegar el resultado de un partido a otro: mueve la fila
    entera de `resultados` (incluidos goles y estado) junto con su partido.
    """
    # Orden antiguo (por horario) con resultados en algunos partidos.
    old_order = [
        (1, "Real Oviedo", "Granada", 2, 1, "FT", "1"),
        (2, "Alavés", "Getafe", 1, 0, "FT", "1"),
        (3, "Mallorca", "Valladolid", None, None, "NS", "-"),
        (4, "Sporting Gijón", "Sabadell", None, None, "NS", "-"),
        (5, "Sevilla", "Rayo Vallecano", None, None, "NS", "-"),
        (6, "Eibar", "Tenerife", None, None, "NS", "-"),
        (7, "R. Santander", "Villarreal", None, None, "NS", "-"),
        (8, "Andorra", "Ceuta", None, None, "NS", "-"),
        (9, "Burgos", "Córdoba", None, None, "NS", "-"),
        (10, "Espanyol", "Levante", None, None, "NS", "-"),
        (11, "Cádiz", "Celta Fortuna", None, None, "NS", "-"),
        (12, "Girona", "Leganés", None, None, "NS", "-"),
        (13, "Celta", "Osasuna", None, None, "NS", "-"),
        (14, "Las Palmas", "Albacete", None, None, "NS", "-"),
        (15, "Deportivo", "Elche", 1, 1, "FT", "1-1"),
    ]
    # Copilot en orden antiguo (mismo boleto real, sin reordenar).
    old_copilot = ["X", "1", "1", "1", "1", "X", "X", "1", "1", "1", "1", "1", "X", "1", "1-0"]

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_core_tables(conn)
    ensure_predicciones_unique_index(conn)

    for pid, local, visitante, gh, ga, status, signo in old_order:
        conn.execute(
            """
            INSERT INTO resultados (jornada, partido_id, local, visitante,
                goles_local, goles_visitante, status, signo_actual)
            VALUES (1, ?, ?, ?, ?, ?, ?, ?)
            """,
            (pid, local, visitante, gh, ga, status, signo),
        )
    for pid, signo in enumerate(old_copilot, start=1):
        conn.execute(
            "INSERT INTO predicciones (user_id, jornada, partido_id, signo) VALUES ('copilot', 1, ?, ?)",
            (pid, signo),
        )
    conn.commit()

    _rekey_j1_partido_ids(conn)

    def match(pid):
        return conn.execute(
            "SELECT local, visitante, goles_local, goles_visitante, status, signo_actual "
            "FROM resultados WHERE jornada = 1 AND partido_id = ?",
            (pid,),
        ).fetchone()

    # El resultado de Alavés-Getafe (1-0) se mueve a la posición 1, no se queda en la 2.
    assert tuple(match(1)) == ("Alavés", "Getafe", 1, 0, "FT", "1")
    # El de Real Oviedo-Granada (2-1) viaja a la posición 8.
    assert tuple(match(8)) == ("Real Oviedo", "Granada", 2, 1, "FT", "1")
    # El pleno (Deportivo-Elche 1-1) sigue en la 15.
    assert tuple(match(15)) == ("Deportivo", "Elche", 1, 1, "FT", "1-1")

    # Los boletos también se reordenan con sus partidos.
    signs = conn.execute(
        "SELECT signo FROM predicciones WHERE jornada = 1 AND user_id = 'copilot' ORDER BY partido_id"
    ).fetchall()
    assert [row["signo"] for row in signs] == COPILOT_SIGNOS

    # Idempotente.
    assert _rekey_j1_partido_ids(conn) == 0


def test_api_liga_data_j1_returns_copilot_and_pena_consensus_total_12(tmp_path, monkeypatch):
    # Keep this privacy-before-kickoff contract deterministic after the real J1 date.
    monkeypatch.setattr(
        liga_data,
        "madrid_now",
        lambda: datetime(2026, 8, 14, 12, 0, tzinfo=ZoneInfo("Europe/Madrid")),
    )
    app = _test_app(tmp_path, monkeypatch)
    response = app.test_client().get("/api/liga/data?j=1")
    assert response.status_code == 200
    payload = response.get_json()

    assert payload["jornada"] == "1"
    assert payload["partidos"][0]["local"] == "Alavés"
    assert payload["partidos"][0]["visitante"] == "Getafe"
    assert payload["partidos"][7]["local"] == "Real Oviedo"
    assert payload["partidos"][14]["local"] == "Deportivo"

    copilot = payload["predicciones_actuales"]["copilot"]["signos"]
    programa = payload["predicciones_actuales"]["programa"]["signos"]
    assert copilot == COPILOT_SIGNOS
    assert programa == PROGRAMA_SIGNOS

    consenso = payload["consenso_pena"]
    assert len(consenso) == 14
    assert all(item["total"] == 12 for item in consenso)
    assert all(item["fuente"] == "pena" for item in consenso)

    # Los maestros son públicos antes del cierre; La Peña solo se revela una vez cerrada.
    predicciones = payload["predicciones_actuales"]
    assert {"copilot", "gemini", "claude", "grok", "chatgpt"} <= set(predicciones)
    if payload["is_locked"]:
        assert PENA_12 <= set(predicciones)
    else:
        assert PENA_12.isdisjoint(predicciones)
