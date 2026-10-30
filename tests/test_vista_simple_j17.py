"""Vista simple J17: cinco columnas, líneas simples y resultados honestos.

(a) el orden fijo es MrPurple, Programa, Tecnotron, Grok y Sonia;
(b) la línea del usuario autenticado se integra bajo MrPurple;
(c) el pleno solo acierta con el marcador exacto (buckets de scoring.py);
(d) sin resultado o con directo degradado la fila queda pendiente;
(e) la casilla 14 no muestra hora;
(f) ensure_jornada_17 importa fixtures y líneas desde la tabla predicciones.

Los casos de pintado se ejecutan de verdad contra cover_page.js en una maquina
virtual (mismo arnes que test_cover_directo_panel), y los de puntuacion contra
el payload que construye liga_maestros.services.payloads.simple_view: la regla
esta una sola vez, en scoring.py, y el frontend solo la pinta.
"""

import json
import re
import shutil
import sqlite3
import subprocess
from pathlib import Path

import pytest

from liga_maestros.db import migrations
from liga_maestros.scoring import normalize_prediction_sign
from liga_maestros.services.payloads.matches import build_jornada_matches
from liga_maestros.services.payloads.simple_view import build_simple_view_payload, build_simple_view_ranking
from liga_maestros.services.teams import build_participant_contract

ROOT = Path(__file__).resolve().parents[1]
COVER = ROOT / "static" / "js" / "pages" / "cover_page.js"
UTILS = ROOT / "static" / "js" / "utils.js"
STATE = ROOT / "static" / "js" / "state.js"

LINEA_TECNOTRON = ["2", "1", "1", "1", "2", "2", "1", "1", "2", "2", "X", "2", "2", "1", "2-1"]
LINEA_PROGRAMA = ["2", "1", "1", "1", "1", "2", "1", "1", "2", "1", "1", "1", "2", "2", "1-0"]
LINEA_GROK = ["2", "1", "1", "1", "X", "2", "1", "X", "2", "2", "2", "1", "2", "2", "1-1"]
LINEA_SONIA = ["2", "X", "1", "1", "X", "X", "1", "X", "2", "2", "2", "X", "X", "2", "2-1"]
LINEA_MRPURPLE = ["2", "1", "X", "1", "X", "2", "2", "1", "2", "2", "X", "X", "2", "1", "2-1"]
COLUMN_IDS = ["mrpurple", "programa", "tecnotron", "grok", "sonia"]


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    migrations.ensure_core_tables(conn)
    migrations.ensure_predicciones_unique_index(conn)
    migrations.ensure_jornada_17(conn)
    return conn


def _payload(conn, jornada=17, max_jornada=17):
    partidos = build_jornada_matches(conn, str(jornada), {})
    return build_simple_view_payload(conn, jornada, partidos, build_participant_contract(), max_jornada=max_jornada)


def _marca_resultado(conn, partido_id, goles_local, goles_visitante, status="FT"):
    conn.execute(
        "UPDATE resultados SET goles_local = ?, goles_visitante = ?, status = ?, signo_actual = ? "
        "WHERE jornada = 17 AND partido_id = ?",
        (
            goles_local,
            goles_visitante,
            status,
            "1" if goles_local > goles_visitante else ("2" if goles_local < goles_visitante else "X"),
            partido_id,
        ),
    )
    conn.commit()


def _fila(payload, partido_id):
    for row in payload["rows"]:
        if row["id"] == partido_id:
            return row
    raise AssertionError(f"la casilla {partido_id} no esta en el payload")


# ---------------------------------------------------------------------------
# (f) la migracion
# ---------------------------------------------------------------------------


def test_ensure_jornada_17_importa_los_quince_partidos():
    conn = _conn()
    filas = conn.execute(
        "SELECT partido_id, local, visitante, fecha, hora FROM resultados WHERE jornada = 17 ORDER BY partido_id"
    ).fetchall()
    assert len(filas) == 15
    assert {int(f["partido_id"]) for f in filas} == set(range(1, 16))
    assert (filas[0]["local"], filas[0]["visitante"]) == ("Levante", "Atlético")
    assert (filas[2]["local"], filas[2]["visitante"]) == ("Betis", "Málaga")
    assert filas[13]["local"] == "Tenerife (F)" and filas[13]["visitante"] == "Athletic (F)"
    assert (filas[14]["local"], filas[14]["visitante"]) == ("Athletic", "R. Sociedad")
    # Boleto SELAE 18: sáb 31/10 y dom 01/11, sin mezclar la Copa del 28/10.
    assert filas[0]["fecha"] == "2026-10-31" and filas[0]["hora"] == "14:00"
    assert filas[14]["fecha"] == "2026-11-01" and filas[14]["hora"] == "21:00"
    # La casilla 14 no tiene hora (ni fecha) verificada: no se inventa.
    assert filas[13]["hora"] in ("", None)
    assert filas[13]["fecha"] in ("", None)


def test_ensure_jornada_17_las_lineas_salen_de_la_tabla_predicciones():
    """Lección J16: la pagina lee de la tabla predicciones, no de data/."""
    conn = _conn()
    filas = conn.execute("SELECT user_id, partido_id, signo FROM predicciones WHERE jornada = 17").fetchall()
    por_uid = {}
    for fila in filas:
        por_uid.setdefault(fila["user_id"], {})[int(fila["partido_id"])] = fila["signo"]

    assert set(por_uid) == {"mrpurple", "tecnotron", "programa", "grok", "sonia"}
    assert [por_uid["tecnotron"][i] for i in range(1, 16)] == LINEA_TECNOTRON
    assert [por_uid["programa"][i] for i in range(1, 16)] == LINEA_PROGRAMA
    assert [por_uid["grok"][i] for i in range(1, 16)] == LINEA_GROK
    assert [por_uid["sonia"][i] for i in range(1, 16)] == LINEA_SONIA
    assert all(
        len(signo) == 1
        for uid in ("tecnotron", "programa", "grok", "sonia")
        for pid, signo in por_uid[uid].items()
        if pid < 15
    )
    # Sin linea validada no hay fila (los signos pasan por scoring.py).
    for uid, signos in por_uid.items():
        for partido_id, signo in signos.items():
            assert normalize_prediction_sign(partido_id, signo) == signo, (uid, partido_id, signo)
    # MrPurple ya tiene línea pública
    assert [por_uid["mrpurple"][i] for i in range(1, 16)] == LINEA_MRPURPLE


def test_ensure_jornada_17_es_idempotente_y_esta_registrada_en_el_arranque():
    conn = _conn()
    primera = migrations.ensure_jornada_17(conn)
    assert primera > 0
    assert conn.execute("SELECT COUNT(*) FROM resultados WHERE jornada = 17").fetchone()[0] == 15
    assert conn.execute("SELECT COUNT(*) FROM predicciones WHERE jornada = 17").fetchone()[0] == 75

    fuente = (ROOT / "liga_maestros" / "db" / "migrations.py").read_text(encoding="utf-8")
    arranque = fuente[fuente.index("def run_startup_migrations") :]
    assert "ensure_jornada_17(conn)" in arranque, "la migracion no esta registrada en el arranque"


def test_los_datos_de_la_jornada_17_estan_versionados():
    """El fixture sale de data/ con la estructura de las jornadas anteriores."""
    horarios = json.loads((ROOT / "data" / "horarios_J17.json").read_text(encoding="utf-8"))
    assert set(horarios) == {str(i) for i in range(1, 16)}
    assert horarios["14"]["hora"] == "" and horarios["14"]["fecha"] == ""
    assert horarios["1"] == {"fecha": "2026-10-31", "hora": "14:00"}

    scrape = json.loads((ROOT / "data" / "quiniela15_J17_scrape.json").read_text(encoding="utf-8"))
    assert scrape["jornada"] == 17
    assert len(scrape["partidos"]) == 15
    assert scrape["partidos"][13]["hora"] == ""
    assert scrape["boleto"]["nombre"] == "SELAE 18"
    assert scrape["boleto"]["concurso"] == "2026/63"
    assert scrape["boleto"]["cierre_estimado"] is True
    # Sin importe de bote: no existe ni la clave.
    assert "bote" not in scrape["boleto"]


# ---------------------------------------------------------------------------
# (a) cinco columnas fijas
# ---------------------------------------------------------------------------


def test_vista_por_defecto_solo_muestra_las_cinco_columnas_en_orden():
    conn = _conn()
    payload = _payload(conn)
    assert [col["id"] for col in payload["columns"]] == COLUMN_IDS
    assert [col["name"] for col in payload["columns"]] == ["MrPurple", "Programa", "Tecnotron", "Grok", "Sonia"]
    assert [col["sin_linea"] for col in payload["columns"]] == [False, False, False, False, False]


def test_el_payload_anonimo_publica_la_linea_de_mrpurple_sin_ids_privados():
    """Sin sesion, la columna MrPurple trae sus 15 signos y ningun id de cuenta.

    Se siembra ademas el boleto privado de otro usuario (id decimal largo) para
    comprobar que ni se cuela en la tabla ni aparece serializado en el payload.
    """
    conn = _conn()
    private_id = "102938475610293847"
    conn.executemany(
        "INSERT OR REPLACE INTO predicciones (user_id, jornada, partido_id, signo) VALUES (?, 17, ?, ?)",
        [(private_id, partido_id, signo) for partido_id, signo in enumerate(LINEA_TECNOTRON, start=1)],
    )
    conn.commit()

    payload = _payload(conn)  # sin current_user_id: la peticion es anonima

    mrpurple = payload["columns"][0]
    assert mrpurple["id"] == "mrpurple"
    assert mrpurple["name"] == "MrPurple"
    assert mrpurple["sin_linea"] is False
    assert mrpurple["es_mia"] is False
    assert [row["picks"]["mrpurple"]["signo"] for row in payload["rows"]] == LINEA_MRPURPLE
    assert private_id not in json.dumps(payload)
    assert all(private_id not in row["picks"] for row in payload["rows"])


def test_el_historico_no_deja_colarse_otras_columnas():
    """Los ids fuera de los cinco no aparecen aunque tengan predicciones."""
    conn = _conn()
    conn.executemany(
        "INSERT OR REPLACE INTO predicciones (user_id, jornada, partido_id, signo) VALUES (?, 12, ?, ?)",
        [
            (uid, pid, signo)
            for uid in ("chipi", "claude", "gemini", "baidu", "gstudio")
            for pid, signo in enumerate(LINEA_TECNOTRON, start=1)
        ],
    )
    conn.commit()
    payload = _payload(conn, jornada=12, max_jornada=17)
    assert [col["id"] for col in payload["columns"]] == COLUMN_IDS
    assert all(col["sin_linea"] for col in payload["columns"])


def test_una_linea_ajena_no_anade_una_sexta_columna():
    conn = _conn()
    conn.executemany(
        "INSERT OR REPLACE INTO predicciones (user_id, jornada, partido_id, signo) VALUES ('chipi', 17, ?, ?)",
        list(enumerate(LINEA_PROGRAMA, start=1)),
    )
    conn.commit()
    payload = _payload(conn)
    assert [col["id"] for col in payload["columns"]] == COLUMN_IDS
    assert all(col["id"] != "chipi" for col in payload["columns"])


def test_la_linea_guardada_en_tu_se_mapea_a_mrpurple():
    conn = _conn()
    user_id = "pablo-account-1"
    conn.executemany(
        "INSERT OR REPLACE INTO predicciones (user_id, jornada, partido_id, signo) VALUES (?, 17, ?, ?)",
        [(user_id, partido_id, signo) for partido_id, signo in enumerate(LINEA_TECNOTRON, start=1)],
    )
    conn.commit()
    payload = build_simple_view_payload(
        conn,
        17,
        build_jornada_matches(conn, "17", {}),
        build_participant_contract(),
        max_jornada=17,
        current_user_id=user_id,
    )
    assert [col["id"] for col in payload["columns"]] == COLUMN_IDS
    assert payload["columns"][0]["es_mia"] is True
    assert payload["columns"][0]["sin_linea"] is False
    assert _fila(payload, 1)["picks"]["mrpurple"]["signo"] == "2"
    assert all(user_id not in row["picks"] for row in payload["rows"])


def test_los_ids_ocultos_del_contrato_no_pueden_colarse():
    conn = _conn()
    conn.executemany(
        "INSERT OR REPLACE INTO predicciones (user_id, jornada, partido_id, signo) VALUES (?, 17, ?, ?)",
        [
            (uid, pid, signo)
            for uid in ("consenso", "consejo_ias", "hermes")
            for pid, signo in enumerate(LINEA_TECNOTRON, start=1)
        ],
    )
    conn.commit()
    payload = _payload(conn)
    assert [col["id"] for col in payload["columns"]] == COLUMN_IDS


# ---------------------------------------------------------------------------
# (b) signos simples, (c) pleno, (d) pendiente
# ---------------------------------------------------------------------------


def test_las_tres_lineas_recibidas_son_simples_y_se_puntuan():
    conn = _conn()
    _marca_resultado(conn, 9, 1, 0)
    _marca_resultado(conn, 12, 1, 0)
    payload = _payload(conn)

    for uid in ("programa", "tecnotron", "grok"):
        assert all(not pick["dobles"] for row in payload["rows"] for pick in [row["picks"][uid]])
    assert _fila(payload, 9)["picks"]["tecnotron"] == {"signo": "2", "dobles": False, "hit": False}
    assert _fila(payload, 9)["picks"]["programa"]["hit"] is False
    assert _fila(payload, 9)["picks"]["grok"]["hit"] is False
    assert _fila(payload, 12)["picks"]["tecnotron"]["hit"] is False
    assert _fila(payload, 12)["picks"]["programa"]["hit"] is True


def test_el_total_del_pie_solo_cuenta_casillas_con_linea_y_resultado():
    conn = _conn()
    for partido_id in range(1, 8):
        _marca_resultado(conn, partido_id, 1, 0)
    payload = _payload(conn)
    # Programa: 5 unos acertados de 7 jugados (puso 2 en la 1 y en la 6).
    assert payload["totals"]["programa"] == {"aciertos": 5, "jugados": 7}
    # Tecnotron: 4 de 7 (2 en las casillas 1, 5 y 6).
    assert payload["totals"]["tecnotron"] == {"aciertos": 4, "jugados": 7}
    # MrPurple acierta casilla 2 y 4 con '1'
    assert payload["totals"]["mrpurple"] == {"aciertos": 2, "jugados": 7}


def test_el_pleno_solo_acierta_con_el_marcador_exacto():
    conn = _conn()
    _marca_resultado(conn, 15, 2, 1)
    payload = _payload(conn)
    pleno = _fila(payload, 15)
    assert pleno["is_pleno"] is True
    assert pleno["signo_real"] == "2-1"
    assert pleno["picks"]["tecnotron"] == {"signo": "2-1", "dobles": False, "hit": True}
    assert pleno["picks"]["programa"] == {"signo": "1-0", "dobles": False, "hit": False}
    # El pleno no entra en el total de 14.
    assert all(col["jugados"] == 0 for col in payload["totals"].values())

    _marca_resultado(conn, 15, 2, 2)
    payload = _payload(conn)
    assert _fila(payload, 15)["picks"]["tecnotron"]["hit"] is False


def test_clasificacion_j17_solo_incluye_los_cinco_y_reutiliza_hits():
    conn = _conn()
    for partido_id in range(1, 4):
        _marca_resultado(conn, partido_id, 1, 0)
    payload = _payload(conn)
    ranking = build_simple_view_ranking(payload)
    assert list(ranking) == COLUMN_IDS
    assert ranking["programa"]["total"] == payload["totals"]["programa"]["aciertos"]
    assert ranking["programa"]["jornada"] == ranking["programa"]["total"]
    assert ranking["sonia"]["total"] == payload["totals"]["sonia"]["aciertos"]
    assert ranking["mrpurple"]["total"] == 1


def test_el_pleno_cuenta_por_buckets_como_score_prediction():
    """M-M acierta a M-M: mismo criterio que el ranking, ni mas ni menos."""
    conn = _conn()
    conn.execute(
        "INSERT OR REPLACE INTO predicciones (user_id, jornada, partido_id, signo) VALUES ('grok', 17, 15, 'M-M')"
    )
    conn.commit()
    _marca_resultado(conn, 15, 5, 5)
    payload = _payload(conn)
    assert _fila(payload, 15)["picks"]["grok"] == {"signo": "M-M", "dobles": False, "hit": True}
    assert _fila(payload, 15)["picks"]["tecnotron"]["hit"] is False  # 2-1 contra M-M


def test_sin_resultado_la_fila_queda_pendiente():
    conn = _conn()
    payload = _payload(conn)
    for row in payload["rows"]:
        assert row["has_result"] is False
        assert row["resultado"] == ""
        assert row["signo_real"] == ""
        # Todas menos la 14 muestran horario: esa casilla no lo tiene verificado.
        if row["id"] != 14:
            assert row["cuando"], f"la casilla {row['id']} deberia mostrar su horario"
        for pick in row["picks"].values():
            assert pick["hit"] is None, f"casilla {row['id']}: sin resultado no hay acierto ni fallo"
    assert all(total == {"aciertos": 0, "jugados": 0} for total in payload["totals"].values())


def test_directo_degradado_deja_el_resultado_pendiente():
    conn = _conn()
    _marca_resultado(conn, 1, 1, 0, status="STALE")
    payload = _payload(conn)
    fila = _fila(payload, 1)
    assert fila["has_result"] is False
    assert fila["resultado"] == "" and fila["signo_real"] == ""
    assert all(pick["hit"] is None for pick in fila["picks"].values())


def test_el_resultado_se_pinta_cuando_existe():
    conn = _conn()
    _marca_resultado(conn, 1, 1, 0)
    payload = _payload(conn)
    fila = _fila(payload, 1)
    assert fila["has_result"] and fila["resultado"] == "1-0" and fila["signo_real"] == "1"
    # MrPurple puso '2' en casilla 1
    assert fila["picks"]["mrpurple"] == {"signo": "2", "dobles": False, "hit": False}
    # La resta de casillas sigue pendiente.
    assert _fila(payload, 2)["has_result"] is False


# ---------------------------------------------------------------------------
# (e) casilla 14 sin hora
# ---------------------------------------------------------------------------


def test_la_casilla_14_no_muestra_hora():
    conn = _conn()
    payload = _payload(conn)
    fila = _fila(payload, 14)
    assert fila["hora"] == ""
    assert fila["cuando"] == ""
    assert fila["has_result"] is False and fila["resultado"] == ""
    # El resto de casillas si conservan su horario verificado.
    assert _fila(payload, 13)["cuando"].endswith("19:00")


def test_las_estadisticas_del_boleto_no_inventan_bote():
    conn = _conn()
    payload = _payload(conn)
    assert payload["boleto"]["nombre"] == "SELAE 18"
    assert payload["boleto"]["concurso"] == "2026/63"
    assert payload["boleto"]["cierre_estimado"] is True
    assert not any("bote" == key or "importe" == key for key in payload["boleto"])


# ---------------------------------------------------------------------------
# Pintado real de la portada (node)
# ---------------------------------------------------------------------------

_HARNESS = r"""
const fs = require("fs");
const vm = require("vm");
const sandbox = {
    console,
    Map, Set, String, Number, Date, JSON, Array, Object, Boolean, RegExp, Math, parseInt, isNaN,
    URLSearchParams,
    setTimeout: () => 0,
    setInterval: () => 0,
    clearTimeout: () => {},
    document: {
        body: { dataset: { assetsV: "test" }, classList: { toggle() {}, add() {}, remove() {}, contains() { return false; } } },
        createElement: () => ({ classList: { add() {}, remove() {} }, style: {}, setAttribute() {}, appendChild() {} }),
        getElementById: () => null,
        querySelector: () => null,
        querySelectorAll: () => [],
        addEventListener() {},
        head: { appendChild() {} },
    },
    window: { location: { search: "" } },
    localStorage: { getItem: () => null, setItem() {}, removeItem() {} },
    CSS: { escape: (s) => String(s) },
};
vm.createContext(sandbox);
for (const path of [UTILS_PATH, STATE_PATH, COVER_PATH]) {
    vm.runInContext(fs.readFileSync(path, "utf8"), sandbox, { filename: path });
}
const payload = JSON.parse(PAYLOAD_JSON);
vm.runInContext(`
    globalThis.__pintar = function (data) {
        Object.assign(state, {
            data,
            user: null,
            my_signs: Array(15).fill("-"),
            server_signs: Array(15).fill("-"),
            currentFilter: "ALL",
            contestView: "MATCHES",
        });
        return renderNewspaperCoverPageV3();
    };
`, sandbox);
process.stdout.write(sandbox.__pintar(payload));
"""


def _render_cover(state_data):
    if shutil.which("node") is None:
        pytest.skip("node no esta disponible para ejecutar la portada")
    script = (
        _HARNESS.replace("UTILS_PATH", json.dumps(str(UTILS)))
        .replace("STATE_PATH", json.dumps(str(STATE)))
        .replace("COVER_PATH", json.dumps(str(COVER)))
        .replace("PAYLOAD_JSON", json.dumps(json.dumps(state_data)))
    )
    result = subprocess.run(
        ["node", "-e", script],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )
    return result.stdout


@pytest.fixture
def portada_j17():
    conn = _conn()
    _marca_resultado(conn, 9, 1, 0)
    _marca_resultado(conn, 12, 1, 0)
    simple_view = _payload(conn)
    partidos = build_jornada_matches(conn, "17", {})
    state_data = {
        "jornada": "17",
        "max_jornada": 17,
        "is_locked": False,
        "partidos": partidos,
        "participant_contract": build_participant_contract(),
        "predicciones_actuales": {},
        "consenso_pena": [],
        "consenso_pleno_pena": {},
        "ranking_maestros": {},
        "simple_view": simple_view,
    }
    return state_data, partidos, _render_cover(state_data)


def test_a_la_vista_por_defecto_se_le_ven_exactamente_las_cinco_columnas(portada_j17):
    _, _, html = portada_j17
    cabeceras = re.findall(r'class="cx-sv-col" data-col="([^"]+)"', html)
    assert cabeceras == COLUMN_IDS
    assert html.count('class="cx-sv-col"') == 5
    assert "MrPurple" in html and "Programa" in html and "Tecnotron" in html and "Grok" in html and "Sonia" in html
    # 14 casillas + el pleno, con su total al pie.
    assert html.count('class="cx-sv-row"') == 14
    assert html.count('class="cx-sv-row is-pleno"') == 1
    assert "TOTAL · 14 CASILLAS SIN PLENO" in html
    # El pleno va en su propio cuerpo de tabla, separado del total.
    assert '<tbody class="cx-sv-pleno">' in html
    # Y el boleto, con el cierre marcado como estimado y sin bote.
    assert "SELAE 18" in html and "2026/63" in html and "(estimado)" in html
    assert "€" not in html and "importe" not in html.lower()


def test_b_las_casillas_pintan_aciertos_y_fallos_sin_dobles(portada_j17):
    _, _, html = portada_j17
    fila = re.search(r'<tr class="cx-sv-row" data-id="9">.*?</tr>', html, re.S)
    assert fila, "la casilla 9 no se pinta"
    celda = re.search(r'<td class="[^"]*" title="Tecnotron: 2, fallo">.*?</td>', fila.group(0), re.S)
    assert celda, "la celda simple de Tecnotron en la 9 no aparece"
    assert "is-double" not in celda.group(0) and "is-miss" in celda.group(0)
    assert "✗" in celda.group(0)

    fila12 = re.search(r'<tr class="cx-sv-row" data-id="12">.*?</tr>', html, re.S)
    celda12 = re.search(r'<td class="[^"]*" title="Tecnotron: 2, fallo">.*?</td>', fila12.group(0), re.S)
    assert celda12 and "is-double" not in celda12.group(0)
    assert "✗" in celda12.group(0)
    assert not re.search(r"cx-sv-cell[^>]*is-double", html)


def test_c_el_pleno_se_pinta_con_goles_y_su_acierto(portada_j17):
    _, _, html = portada_j17
    assert '<tbody class="cx-sv-pleno">' in html
    assert "PLENO AL 15 · GOLES EXACTOS" in html
    assert "Athletic" in html and "R. Sociedad" in html
    assert 'title="Tecnotron: 2-1, pendiente"' in html
    assert 'title="Programa: 1-0, pendiente"' in html


def test_d_sin_resultado_la_casilla_se_pinta_con_raya(portada_j17):
    _, _, html = portada_j17
    fila1 = re.search(r'<tr class="cx-sv-row" data-id="1">.*?</tr>', html, re.S).group(0)
    assert '<span class="cx-sv-result-val">—</span>' in fila1
    assert "cx-sv-result is-pending" in fila1
    # La casilla 9 si tiene resultado y lo pinta tal cual.
    fila9 = re.search(r'<tr class="cx-sv-row" data-id="9">.*?</tr>', html, re.S).group(0)
    assert '<span class="cx-sv-result-val">1-0</span>' in fila9
    assert "cx-sv-result is-ft" in fila9
    assert "nunca se inventa un marcador" in html


def test_el_fallback_frontend_no_pinta_marcador_stale():
    conn = _conn()
    _marca_resultado(conn, 1, 1, 0, status="STALE")
    partidos = build_jornada_matches(conn, "17", {})
    simple_view = _payload(conn)
    simple_view["rows"] = []
    state_data = {
        "jornada": "17",
        "max_jornada": 17,
        "is_locked": False,
        "partidos": partidos,
        "participant_contract": build_participant_contract(),
        "ranking_maestros": {},
        "simple_view": simple_view,
    }
    html = _render_cover(state_data)
    fila1 = re.search(r'<tr class="cx-sv-row" data-id="1">.*?</tr>', html, re.S).group(0)
    assert '<span class="cx-sv-result-val">—</span>' in fila1
    assert "cx-sv-result is-pending" in fila1


def test_e_la_casilla_14_se_pinta_sin_hora(portada_j17):
    _, _, html = portada_j17
    fila14 = re.search(r'<tr class="cx-sv-row" data-id="14">.*?</tr>', html, re.S).group(0)
    assert '<span class="cx-sv-when">—</span>' in fila14
    assert "Casilla 14 sin hora verificada" in html
    # Las demas casillas si muestran dia y hora.
    fila13 = re.search(r'<tr class="cx-sv-row" data-id="13">.*?</tr>', html, re.S).group(0)
    assert re.search(r'<span class="cx-sv-when">[^—]+19:00</span>', fila13)
