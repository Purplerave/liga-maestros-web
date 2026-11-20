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
COLUMNS = ["mrpurple", "sonia", "programa", "tecnotron", "grok", "gemini"]


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    migrations.ensure_core_tables(conn)
    migrations.ensure_predicciones_unique_index(conn)
    return conn


def test_jornada_22_importa_selae_23_y_promociona_la_activa():
    conn = _conn()
    migrations.ensure_jornada_21(conn)
    migrations.ensure_jornada_22(conn)

    assert conn.execute("SELECT COUNT(*) FROM resultados WHERE jornada = 22").fetchone()[0] == 15
    assert conn.execute("SELECT COUNT(*) FROM predicciones WHERE jornada = 22").fetchone()[0] == 90
    # J21 (17-19/11) ya no tiene NS abiertos; la J22 (21-22/11) toma el relevo.
    assert resolve_active_jornada(conn) == 22

    first = conn.execute(
        "SELECT local, visitante, fecha, hora FROM resultados WHERE jornada = 22 AND partido_id = 1"
    ).fetchone()
    assert tuple(first) == ("Alavés", "Deportivo", "2026-11-21", "14:00")

    last = conn.execute("SELECT local, visitante FROM resultados WHERE jornada = 22 AND partido_id = 15").fetchone()
    assert tuple(last) == ("Sevilla", "Betis")


def test_vista_j22_muestra_las_seis_lineas_de_la_liga():
    conn = _conn()
    migrations.ensure_jornada_21(conn)
    migrations.ensure_jornada_22(conn)
    partidos = build_jornada_matches(conn, "22", {})
    payload = build_simple_view_payload(
        conn,
        22,
        partidos,
        build_participant_contract(),
        max_jornada=22,
    )

    assert load_ticket_metadata(22)["nombre"] == "SELAE 23"
    assert [column["id"] for column in payload["columns"]] == COLUMNS
    assert all(column["sin_linea"] is False for column in payload["columns"])
    assert len(payload["rows"]) == 15
    assert payload["rows"][0]["local"] == "Alavés"
    # Casilla 1: la linea de Pablo (MrPurple) abre con 2.
    assert payload["rows"][0]["picks"]["mrpurple"]["signo"] == "2"
    assert payload["rows"][0]["picks"]["sonia"]["signo"] == "2"
    assert payload["rows"][0]["picks"]["programa"]["signo"] == "1"
    assert payload["rows"][0]["picks"]["tecnotron"]["signo"] == "X"
    assert payload["rows"][0]["picks"]["grok"]["signo"] == "X"
    assert payload["rows"][0]["picks"]["gemini"]["signo"] == "1"
    # Casilla 12: unico partido donde Sonia va sola a la X.
    assert payload["rows"][11]["picks"]["mrpurple"]["signo"] == "2"
    assert payload["rows"][11]["picks"]["sonia"]["signo"] == "X"
    assert payload["rows"][11]["picks"]["programa"]["signo"] == "2"
    assert payload["rows"][11]["picks"]["tecnotron"]["signo"] == "2"
    assert payload["rows"][11]["picks"]["grok"]["signo"] == "2"
    assert payload["rows"][11]["picks"]["gemini"]["signo"] == "2"


def test_fixture_j22_esta_versionado_y_completo():
    horarios = json.loads((ROOT / "data" / "horarios_J22.json").read_text(encoding="utf-8"))
    scrape = json.loads((ROOT / "data" / "quiniela15_J22_scrape.json").read_text(encoding="utf-8"))
    predicciones = json.loads((ROOT / "data" / "predicciones_J22.json").read_text(encoding="utf-8"))

    assert set(horarios) == {str(i) for i in range(1, 16)}
    assert scrape["jornada"] == 22
    assert scrape["boleto"]["selae"] == 23
    assert scrape["temporada"] == "2026-2027"
    assert len(scrape["partidos"]) == 15
    assert [p["division"] for p in scrape["partidos"]][0] == "primera"
    assert [p["division"] for p in scrape["partidos"]][7] == "segunda"
    assert [p["division"] for p in scrape["partidos"]][10] == "liga_f"
    assert [p["division"] for p in scrape["partidos"]][14] == "primera"
    assert scrape["partidos"][14].get("pleno_al_15") is True

    assert predicciones["jornada"] == 22
    lineas = [k for k, v in predicciones.items() if isinstance(v, dict) and "signos" in v]
    assert sorted(lineas) == sorted(COLUMNS)
    for linea in lineas:
        assert len(predicciones[linea]["signos"]) == 15
    assert predicciones["mrpurple"]["signos"][0] == "2"
    assert predicciones["mrpurple"]["signos"][14] == "1-1"
    assert predicciones["grok"]["signos"][14] == "1-1"
    assert predicciones["gemini"]["signos"][14] == "1-1"
    assert predicciones["sonia"]["signos"][14] == "1-2"

    source = (ROOT / "liga_maestros" / "db" / "migrations.py").read_text(encoding="utf-8")
    startup = source[source.index("def run_startup_migrations") :]
    assert "ensure_jornada_22(conn)" in startup
