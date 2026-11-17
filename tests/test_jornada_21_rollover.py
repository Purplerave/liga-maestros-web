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


def test_jornada_21_importa_selae_22_y_promociona_la_activa():
    conn = _conn()
    migrations.ensure_jornada_20(conn)
    migrations.ensure_jornada_21(conn)

    assert conn.execute("SELECT COUNT(*) FROM resultados WHERE jornada = 21").fetchone()[0] == 15
    assert conn.execute("SELECT COUNT(*) FROM predicciones WHERE jornada = 21").fetchone()[0] == 90
    # J20 (14-15/11) ya no tiene NS abiertos; la J21 (17-19/11) toma el relevo.
    assert resolve_active_jornada(conn) == 21

    first = conn.execute(
        "SELECT local, visitante, fecha, hora FROM resultados WHERE jornada = 21 AND partido_id = 1"
    ).fetchone()
    assert tuple(first) == ("Bosnia Herzegovina", "Ruman\u00eda", "2026-11-17", "20:45")

    last = conn.execute("SELECT local, visitante FROM resultados WHERE jornada = 21 AND partido_id = 15").fetchone()
    assert tuple(last) == ("Dinamarca", "Noruega")


def test_vista_j21_muestra_las_seis_lineas_de_la_liga():
    conn = _conn()
    migrations.ensure_jornada_20(conn)
    migrations.ensure_jornada_21(conn)
    partidos = build_jornada_matches(conn, "21", {})
    payload = build_simple_view_payload(
        conn,
        21,
        partidos,
        build_participant_contract(),
        max_jornada=21,
    )

    assert load_ticket_metadata(21)["nombre"] == "SELAE 22"
    assert [column["id"] for column in payload["columns"]] == COLUMNS
    assert all(column["sin_linea"] is False for column in payload["columns"])
    assert len(payload["rows"]) == 15
    assert payload["rows"][0]["local"] == "Bosnia Herzegovina"
    # Casilla 1: la linea de Pablo (MrPurple) abre con X.
    assert payload["rows"][0]["picks"]["mrpurple"]["signo"] == "X"
    assert payload["rows"][0]["picks"]["sonia"]["signo"] == "X"
    assert payload["rows"][0]["picks"]["programa"]["signo"] == "1"
    assert payload["rows"][0]["picks"]["tecnotron"]["signo"] == "1"
    assert payload["rows"][0]["picks"]["grok"]["signo"] == "1"
    assert payload["rows"][0]["picks"]["gemini"]["signo"] == "X"
    # Casilla 12: unico partido donde MrPurple va solo al 1.
    assert payload["rows"][11]["picks"]["mrpurple"]["signo"] == "1"
    assert payload["rows"][11]["picks"]["sonia"]["signo"] == "2"
    assert payload["rows"][11]["picks"]["programa"]["signo"] == "2"
    assert payload["rows"][11]["picks"]["tecnotron"]["signo"] == "2"
    assert payload["rows"][11]["picks"]["grok"]["signo"] == "2"
    assert payload["rows"][11]["picks"]["gemini"]["signo"] == "2"


def test_fixture_j21_esta_versionado_y_completo():
    horarios = json.loads((ROOT / "data" / "horarios_J21.json").read_text(encoding="utf-8"))
    scrape = json.loads((ROOT / "data" / "quiniela15_J21_scrape.json").read_text(encoding="utf-8"))
    predicciones = json.loads((ROOT / "data" / "predicciones_J21.json").read_text(encoding="utf-8"))

    assert set(horarios) == {str(i) for i in range(1, 16)}
    assert scrape["jornada"] == 21
    assert scrape["boleto"]["selae"] == 22
    assert scrape["temporada"] == "2026-2027"
    assert len(scrape["partidos"]) == 15
    assert [p["division"] for p in scrape["partidos"]][0] == "internacional"
    assert [p["division"] for p in scrape["partidos"]][6] == "liga_f"
    assert [p["division"] for p in scrape["partidos"]][14] == "internacional"
    assert scrape["partidos"][14].get("pleno_al_15") is True

    assert predicciones["jornada"] == 21
    lineas = [k for k, v in predicciones.items() if isinstance(v, dict) and "signos" in v]
    assert sorted(lineas) == sorted(COLUMNS)
    for linea in lineas:
        assert len(predicciones[linea]["signos"]) == 15
    assert predicciones["mrpurple"]["signos"][0] == "X"
    assert predicciones["mrpurple"]["signos"][14] == "1-1"
    assert predicciones["grok"]["signos"][14] == "1-1"
    assert predicciones["gemini"]["signos"][14] == "2-1"
    assert predicciones["codigos"]["gemini"] == "WE3DWN"

    source = (ROOT / "liga_maestros" / "db" / "migrations.py").read_text(encoding="utf-8")
    startup = source[source.index("def run_startup_migrations") :]
    assert "ensure_jornada_21(conn)" in startup
