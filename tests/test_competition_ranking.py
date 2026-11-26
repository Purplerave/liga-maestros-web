"""La clasificación de la competición acumula desde la J17.

Antes solo sumaba las dos jornadas más recientes (``[:2]``) y la portada
mostraba únicamente la última jornada cerrada. Los totales de este test
están verificados contra los cierres conocidos (J17, J20, J21, J22) y
contra el API en vivo: nadie llegó a 14 aciertos en J17-J22, así que el
punto del pleno no suma en ninguna de esas jornadas.
"""

import sqlite3

from liga_maestros.db import migrations
from liga_maestros.services.payloads.matches import build_jornada_matches
from liga_maestros.services.payloads.simple_view import (
    build_competition_ranking,
    build_simple_view_payload,
)
from liga_maestros.services.teams import build_participant_contract

# (total, puntos por jornada). Sonia no tiene línea en la J24 (en juego) y
# Gemini no jugó ni la J17 ni la J19: en esos casos no hay entrada en
# por_jornada, no un cero.
ESPERADO = {
    "grok": (45, {"17": 9, "19": 8, "20": 8, "21": 11, "22": 9, "24": 0}),
    "programa": (43, {"17": 9, "19": 7, "20": 9, "21": 10, "22": 8, "24": 0}),
    "tecnotron": (42, {"17": 9, "19": 7, "20": 6, "21": 11, "22": 9, "24": 0}),
    "mrpurple": (37, {"17": 9, "19": 6, "20": 7, "21": 7, "22": 8, "24": 0}),
    "sonia": (34, {"17": 5, "19": 5, "20": 7, "21": 9, "22": 8}),
    "gemini": (28, {"20": 9, "21": 11, "22": 8, "24": 0}),
}


def _conn_con_jornadas():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    migrations.ensure_core_tables(conn)
    migrations.ensure_predicciones_unique_index(conn)
    for ensure in (
        migrations.ensure_jornada_17,
        migrations.ensure_jornada_19,
        migrations.ensure_jornada_20,
        migrations.ensure_jornada_21,
        migrations.ensure_jornada_22,
        migrations.ensure_jornada_24,
    ):
        ensure(conn)
    return conn


def test_resultados_j19_j22_importados_desde_los_ficheros():
    conn = _conn_con_jornadas()
    for jornada in (17, 19, 20, 21, 22):
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM resultados WHERE jornada = ? AND goles_local IS NOT NULL",
                (jornada,),
            ).fetchone()[0]
            == 15
        )
    # J17 y J19 traen 5 líneas (sin Gemini); J20-J22 traen 6.
    assert conn.execute("SELECT COUNT(*) FROM predicciones WHERE jornada = 17").fetchone()[0] == 75
    assert conn.execute("SELECT COUNT(*) FROM predicciones WHERE jornada = 19").fetchone()[0] == 75
    assert conn.execute("SELECT COUNT(*) FROM predicciones WHERE jornada = 20").fetchone()[0] == 90
    assert conn.execute("SELECT COUNT(*) FROM predicciones WHERE jornada = 21").fetchone()[0] == 90
    assert conn.execute("SELECT COUNT(*) FROM predicciones WHERE jornada = 22").fetchone()[0] == 90
    # La J24 sigue en juego: fixture completo pero sin resultados.
    assert (
        conn.execute("SELECT COUNT(*) FROM resultados WHERE jornada = 24 AND goles_local IS NOT NULL").fetchone()[0]
        == 0
    )


def test_clasificacion_acumula_desde_j17_hasta_la_jornada_en_juego():
    conn = _conn_con_jornadas()
    partidos = build_jornada_matches(conn, "24", {})
    payload = build_simple_view_payload(
        conn,
        24,
        partidos,
        build_participant_contract(),
        max_jornada=24,
    )
    ranking = build_competition_ranking(
        conn,
        24,
        partidos,
        payload,
        build_participant_contract(),
        24,
        [17, 19, 20, 21, 22, 24],
    )

    assert ranking["jornadas"] == [24, 22, 21, 20, 19, 17]
    rows = {row["id"]: row for row in ranking["rows"]}
    assert [row["id"] for row in ranking["rows"]] == [
        "grok",
        "programa",
        "tecnotron",
        "mrpurple",
        "sonia",
        "gemini",
    ]
    for uid, (total, por_jornada) in ESPERADO.items():
        assert rows[uid]["total"] == total
        assert rows[uid]["por_jornada"] == por_jornada


def test_clasificacion_en_j22_no_incluye_la_j24():
    conn = _conn_con_jornadas()
    partidos = build_jornada_matches(conn, "22", {})
    payload = build_simple_view_payload(
        conn,
        22,
        partidos,
        build_participant_contract(),
        max_jornada=22,
    )
    ranking = build_competition_ranking(
        conn,
        22,
        partidos,
        payload,
        build_participant_contract(),
        22,
        [17, 19, 20, 21, 22],
    )

    assert ranking["jornadas"] == [22, 21, 20, 19, 17]
    rows = {row["id"]: row for row in ranking["rows"]}
    assert rows["grok"]["total"] == 45
    assert rows["programa"]["total"] == 43
    assert rows["tecnotron"]["total"] == 42
    assert rows["gemini"]["total"] == 28
    assert rows["gemini"]["por_jornada"] == {"20": 9, "21": 11, "22": 8}
