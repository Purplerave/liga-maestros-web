import json
import sqlite3
from pathlib import Path

from liga_maestros.db import migrations
from liga_maestros.services.jornada import resolve_active_jornada
from liga_maestros.services.payloads.matches import build_jornada_matches
from liga_maestros.services.payloads.simple_view import (
    add_competition_roster_columns,
    build_simple_view_payload,
    build_two_round_competition_ranking,
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


def test_jornada_24_importa_selae_25_y_promociona_la_activa():
    conn = _conn()
    migrations.ensure_jornada_22(conn)
    migrations.ensure_jornada_24(conn)

    assert conn.execute("SELECT COUNT(*) FROM resultados WHERE jornada = 24").fetchone()[0] == 15
    assert conn.execute("SELECT COUNT(*) FROM predicciones WHERE jornada = 24").fetchone()[0] == 75
    # J22 (21-22/11) ya no tiene NS abiertos; la J24 (28-30/11) toma el relevo.
    assert resolve_active_jornada(conn) == 24

    first = conn.execute(
        "SELECT local, visitante, fecha, hora FROM resultados WHERE jornada = 24 AND partido_id = 1"
    ).fetchone()
    assert tuple(first) == ("Betis", "Rayo Vallecano", "2026-11-28", "14:00")

    last = conn.execute("SELECT local, visitante FROM resultados WHERE jornada = 24 AND partido_id = 15").fetchone()
    assert tuple(last) == ("Espanyol", "Getafe")


def test_vista_j24_muestra_cinco_lineas_y_sonia_pendiente():
    conn = _conn()
    migrations.ensure_jornada_22(conn)
    migrations.ensure_jornada_24(conn)
    partidos = build_jornada_matches(conn, "24", {})
    payload = build_simple_view_payload(
        conn,
        24,
        partidos,
        build_participant_contract(),
        max_jornada=24,
    )

    assert load_ticket_metadata(24)["nombre"] == "SELAE 25"
    # Sin linea, Sonia no entra en las columnas de la jornada (>= J19 solo
    # aparecen los maestros con linea, salvo Programa). La ruta la repone
    # como pendiente a traves del roster de la competicion (viene de la J22).
    assert [column["id"] for column in payload["columns"]] == [
        "mrpurple",
        "programa",
        "tecnotron",
        "grok",
        "gemini",
    ]
    assert all(column["sin_linea"] is False for column in payload["columns"])
    ranking = build_two_round_competition_ranking(
        conn, 24, partidos, payload, build_participant_contract(), 24, [24, 22]
    )
    payload = add_competition_roster_columns(payload, ranking)
    assert [column["id"] for column in payload["columns"]] == COLUMNS
    assert [column for column in payload["columns"] if column["id"] == "sonia"][0]["sin_linea"] is True
    assert len(payload["rows"]) == 15
    assert payload["rows"][0]["local"] == "Betis"
    # Casilla 1: las cinco lineas abren con 1.
    assert payload["rows"][0]["picks"]["mrpurple"]["signo"] == "1"
    assert payload["rows"][0]["picks"]["programa"]["signo"] == "1"
    assert payload["rows"][0]["picks"]["tecnotron"]["signo"] == "1"
    assert payload["rows"][0]["picks"]["grok"]["signo"] == "1"
    assert payload["rows"][0]["picks"]["gemini"]["signo"] == "1"
    # Casilla 7: Programa va solo al 2; el resto, X.
    assert payload["rows"][6]["picks"]["mrpurple"]["signo"] == "X"
    assert payload["rows"][6]["picks"]["programa"]["signo"] == "2"
    assert payload["rows"][6]["picks"]["tecnotron"]["signo"] == "X"
    assert payload["rows"][6]["picks"]["grok"]["signo"] == "X"
    assert payload["rows"][6]["picks"]["gemini"]["signo"] == "X"
    # Casilla 8: MrPurple va solo al 2; el resto, 1.
    assert payload["rows"][7]["picks"]["mrpurple"]["signo"] == "2"
    assert payload["rows"][7]["picks"]["programa"]["signo"] == "1"
    assert payload["rows"][7]["picks"]["tecnotron"]["signo"] == "1"
    assert payload["rows"][7]["picks"]["grok"]["signo"] == "1"
    assert payload["rows"][7]["picks"]["gemini"]["signo"] == "1"
    # Casilla 13: MrPurple va solo al 2; Programa al 1; el resto, X.
    assert payload["rows"][12]["picks"]["mrpurple"]["signo"] == "2"
    assert payload["rows"][12]["picks"]["programa"]["signo"] == "1"
    assert payload["rows"][12]["picks"]["tecnotron"]["signo"] == "X"
    assert payload["rows"][12]["picks"]["grok"]["signo"] == "X"
    assert payload["rows"][12]["picks"]["gemini"]["signo"] == "X"


def test_fixture_j24_esta_versionado_y_completo():
    horarios = json.loads((ROOT / "data" / "horarios_J24.json").read_text(encoding="utf-8"))
    scrape = json.loads((ROOT / "data" / "quiniela15_J24_scrape.json").read_text(encoding="utf-8"))
    predicciones = json.loads((ROOT / "data" / "predicciones_J24.json").read_text(encoding="utf-8"))

    assert set(horarios) == {str(i) for i in range(1, 16)}
    assert scrape["jornada"] == 24
    assert scrape["boleto"]["selae"] == 25
    assert scrape["temporada"] == "2026-2027"
    assert len(scrape["partidos"]) == 15
    assert [p["division"] for p in scrape["partidos"]][0] == "primera"
    assert [p["division"] for p in scrape["partidos"]][7] == "primera"
    assert [p["division"] for p in scrape["partidos"]][8] == "segunda"
    assert [p["division"] for p in scrape["partidos"]][13] == "segunda"
    assert [p["division"] for p in scrape["partidos"]][14] == "primera"
    assert scrape["partidos"][14].get("pleno_al_15") is True

    assert predicciones["jornada"] == 24
    lineas = [k for k, v in predicciones.items() if isinstance(v, dict) and "signos" in v]
    assert sorted(lineas) == sorted(["gemini", "grok", "mrpurple", "programa", "tecnotron"])
    for linea in lineas:
        assert len(predicciones[linea]["signos"]) == 15
    assert predicciones["mrpurple"]["signos"][0] == "1"
    assert predicciones["mrpurple"]["signos"][14] == "1-0"
    assert predicciones["grok"]["signos"][14] == "1-0"
    assert predicciones["gemini"]["signos"][14] == "1-0"
    assert predicciones["programa"]["signos"][14] == "1-1"

    source = (ROOT / "liga_maestros" / "db" / "migrations.py").read_text(encoding="utf-8")
    startup = source[source.index("def run_startup_migrations") :]
    assert "ensure_jornada_24(conn)" in startup
