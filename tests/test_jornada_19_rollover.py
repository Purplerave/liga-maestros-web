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


def test_jornada_19_importa_selae_20_y_mantiene_j17_completa():
    conn = _conn()
    migrations.ensure_jornada_17(conn)
    migrations.ensure_jornada_19(conn)

    assert conn.execute("SELECT COUNT(*) FROM resultados WHERE jornada = 17").fetchone()[0] == 15
    assert conn.execute("SELECT COUNT(*) FROM predicciones WHERE jornada = 17").fetchone()[0] == 75
    assert conn.execute("SELECT COUNT(*) FROM resultados WHERE jornada = 19").fetchone()[0] == 15
    assert conn.execute("SELECT COUNT(*) FROM predicciones WHERE jornada = 19").fetchone()[0] == 75
    assert resolve_active_jornada(conn) == 19

    first = conn.execute(
        "SELECT local, visitante, fecha, hora FROM resultados WHERE jornada = 19 AND partido_id = 1"
    ).fetchone()
    assert tuple(first) == ("Málaga", "Racing Santander", "2026-11-07", "14:00")


def test_vista_activa_muestra_selae_20_sin_mezclar_jugadores_historicos():
    conn = _conn()
    migrations.ensure_jornada_17(conn)
    migrations.ensure_jornada_19(conn)
    # Los boletos de la J19 ya vienen en el seed (data/predicciones_J19.json):
    # los 5 de la liga tienen línea, incluido el Programa.
    partidos = build_jornada_matches(conn, "19", {})
    payload = build_simple_view_payload(
        conn,
        19,
        partidos,
        build_participant_contract(),
        max_jornada=19,
    )

    assert load_ticket_metadata(19)["nombre"] == "SELAE 20"
    assert [column["id"] for column in payload["columns"]] == [
        "mrpurple",
        "sonia",
        "programa",
        "tecnotron",
        "grok",
    ]
    assert payload["columns"][0]["sin_linea"] is False
    assert payload["columns"][1]["sin_linea"] is False
    assert payload["columns"][2]["sin_linea"] is False
    assert payload["columns"][3]["sin_linea"] is False
    assert payload["columns"][4]["sin_linea"] is False
    assert len(payload["rows"]) == 15
    assert payload["rows"][0]["local"] == "Málaga"
    assert payload["rows"][0]["cuando"].endswith("14:00")
    assert payload["rows"][0]["picks"]["mrpurple"]["signo"] == "2"
    assert payload["rows"][0]["picks"]["sonia"]["signo"] == "2"
    assert payload["rows"][0]["picks"]["programa"]["signo"] == "1"
    assert payload["rows"][0]["picks"]["tecnotron"]["signo"] == "X"
    assert payload["rows"][0]["picks"]["grok"]["signo"] == "X"


def test_fixture_j19_y_resultados_j17_estan_versionados_y_completos():
    horarios = json.loads((ROOT / "data" / "horarios_J19.json").read_text(encoding="utf-8"))
    scrape = json.loads((ROOT / "data" / "quiniela15_J19_scrape.json").read_text(encoding="utf-8"))
    resultados_j17 = json.loads((ROOT / "data" / "quiniela15_J17_resultados.json").read_text(encoding="utf-8"))

    assert set(horarios) == {str(i) for i in range(1, 16)}
    assert scrape["jornada"] == 19
    assert scrape["boleto"]["selae"] == 20
    assert len(scrape["partidos"]) == 15
    assert len(resultados_j17["resultados"]) == 15

    source = (ROOT / "liga_maestros" / "db" / "migrations.py").read_text(encoding="utf-8")
    startup = source[source.index("def run_startup_migrations") :]
    assert "ensure_jornada_19(conn)" in startup
