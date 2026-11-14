import json
import sqlite3
from pathlib import Path

from liga_maestros.db import migrations
from liga_maestros.services.jornada import resolve_active_jornada
from liga_maestros.services.payloads.matches import build_jornada_matches
from liga_maestros.services.payloads.simple_view import (
    build_simple_view_payload,
    load_ticket_metadata,
)
from liga_maestros.services.teams import build_participant_contract

ROOT = Path(__file__).resolve().parents[1]


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    migrations.ensure_core_tables(conn)
    migrations.ensure_predicciones_unique_index(conn)
    return conn


def test_jornada_20_importa_selae_21_y_mantiene_j17_completa():
    conn = _conn()
    migrations.ensure_jornada_17(conn)
    migrations.ensure_jornada_20(conn)

    assert conn.execute("SELECT COUNT(*) FROM resultados WHERE jornada = 17").fetchone()[0] == 15
    assert conn.execute("SELECT COUNT(*) FROM predicciones WHERE jornada = 17").fetchone()[0] == 75
    assert conn.execute("SELECT COUNT(*) FROM resultados WHERE jornada = 20").fetchone()[0] == 15
    assert conn.execute("SELECT COUNT(*) FROM predicciones WHERE jornada = 20").fetchone()[0] == 90
    assert resolve_active_jornada(conn) == 20

    first = conn.execute(
        "SELECT local, visitante, fecha, hora FROM resultados WHERE jornada = 20 AND partido_id = 1"
    ).fetchone()
    assert tuple(first) == ("Valladolid", "Castellón", "2026-11-14", "14:00")


def test_vista_activa_muestra_selae_21_sin_mezclar_jugadores_historicos():
    conn = _conn()
    migrations.ensure_jornada_17(conn)
    migrations.ensure_jornada_20(conn)
    # Los boletos de la J20 ya vienen en el seed (data/predicciones_J20.json):
    # los 5 de la liga tienen línea, incluido el Programa, y Gemini como
    # invitado en una sexta columna (CURRENT_MASTER_COLUMNS ya lo incluye).
    partidos = build_jornada_matches(conn, "20", {})
    payload = build_simple_view_payload(
        conn,
        20,
        partidos,
        build_participant_contract(),
        max_jornada=20,
    )

    assert load_ticket_metadata(20)["nombre"] == "SELAE 21"
    assert [column["id"] for column in payload["columns"]] == [
        "mrpurple",
        "sonia",
        "programa",
        "tecnotron",
        "grok",
        "gemini",
    ]
    assert payload["columns"][0]["sin_linea"] is False
    assert payload["columns"][1]["sin_linea"] is False
    assert payload["columns"][2]["sin_linea"] is False
    assert payload["columns"][3]["sin_linea"] is False
    assert payload["columns"][4]["sin_linea"] is False
    assert payload["columns"][5]["sin_linea"] is False
    assert len(payload["rows"]) == 15
    assert payload["rows"][0]["local"] == "Valladolid"
    assert payload["rows"][0]["cuando"].endswith("14:00")
    assert payload["rows"][0]["picks"]["mrpurple"]["signo"] == "2"
    assert payload["rows"][0]["picks"]["sonia"]["signo"] == "2"
    assert payload["rows"][0]["picks"]["programa"]["signo"] == "2"
    assert payload["rows"][0]["picks"]["tecnotron"]["signo"] == "2"
    assert payload["rows"][0]["picks"]["grok"]["signo"] == "2"
    assert payload["rows"][0]["picks"]["gemini"]["signo"] == "2"
    # Casilla 5: la que más separa a los 6 (X / 2 / 2 / 1 / 1 / 1).
    assert payload["rows"][4]["picks"]["mrpurple"]["signo"] == "X"
    assert payload["rows"][4]["picks"]["sonia"]["signo"] == "2"
    assert payload["rows"][4]["picks"]["programa"]["signo"] == "2"
    assert payload["rows"][4]["picks"]["tecnotron"]["signo"] == "1"
    assert payload["rows"][4]["picks"]["grok"]["signo"] == "1"
    assert payload["rows"][4]["picks"]["gemini"]["signo"] == "1"


def test_fixture_j20_esta_versionado_y_completo():
    horarios = json.loads((ROOT / "data" / "horarios_J20.json").read_text(encoding="utf-8"))
    scrape = json.loads((ROOT / "data" / "quiniela15_J20_scrape.json").read_text(encoding="utf-8"))
    predicciones = json.loads((ROOT / "data" / "predicciones_J20.json").read_text(encoding="utf-8"))

    assert set(horarios) == {str(i) for i in range(1, 16)}
    assert scrape["jornada"] == 20
    assert scrape["boleto"]["selae"] == 21
    assert len(scrape["partidos"]) == 15
    assert [p["division"] for p in scrape["partidos"]][9] == "internacional"
    assert [p["division"] for p in scrape["partidos"]][14] == "internacional"
    assert scrape["partidos"][14].get("pleno_al_15") is True
    assert predicciones["jornada"] == 20
    assert len(predicciones["mrpurple"]["signos"]) == 15
    # El pleno de MrPurple es 3-1, su predicción real (el 2-1 del boleto
    # apostado fue solo el pleno único que admite La Barca de Oro).
    assert predicciones["mrpurple"]["signos"][14] == "3-1"
    # Gemini juega como invitado en una sexta columna, con su línea tal cual.
    assert len(predicciones["gemini"]["signos"]) == 15
    assert predicciones["gemini"]["signos"][14] == "2-1"

    source = (ROOT / "liga_maestros" / "db" / "migrations.py").read_text(encoding="utf-8")
    startup = source[source.index("def run_startup_migrations") :]
    assert "ensure_jornada_20(conn)" in startup
