"""Regresion del incidente J17 2026/27 (31 de octubre de 2026).

Sintoma reportado por el usuario: "No vemos los resultados de partidos que ya
se han jugado". Ese sabado a las 16:47 el Levante-Atletico y el Rayo-Celta ya
estaban en juego y la portada seguia enseñando el horario de todos los partidos
de la jornada.

Se juntaron tres fallos, y los tres hacian falta para dejar la jornada a cero:

1. **Numeracion.** El boleto J17 de la liga (Levante-Atletico, Rayo-Celta,
   Betis-Malaga, ...) no es la J17 de quiniela15.com: alli la J17 es la Copa
   del Rey del miercoles 28/10, un boleto extraordinario de SELAE que esta
   liga no juega. El colector pedia ``/resultados-quiniela/17``, recibia los 15
   partidos de la Copa y los cruzaba por ``partido_id`` contra el boleto: 0
   updates, toda la jornada en ``NS``.
2. **Grafias.** La quiniela15 escribe "At. Madrid" en unas jornadas y
   "Atletico" a secas en la J17; "Racing" en vez de "Racing Santander";
   "R. Madrid (F)" y "R. Sociedad (F)" en vez de "Real Madrid (F)" /
   "Real Sociedad (F)". Esos nombres no canonizaban igual que los del boleto
   (``q15_team_mismatch_skipped``) y se perdian ademas el escudo.
3. **Fallback del proveedor.** ``_core_team_key`` troceaba y ordenaba tokens:
   "Atletico" daba ("ATL", "TICO") y "Malaga" ("LAGA", "M"), claves que solo
   casaban con otro nombre partido igual. El fallback por forma juridica del
   feed de Highlightly era practicamente inalcanzable.
"""

import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from liga_maestros.services.highlightly import _core_team_key, _find_feed_item  # noqa: E402
from liga_maestros.utils import (  # noqa: E402
    load_team_logos,
    normalize_team_key,
    team_keys_compatible,
)
from tools.ops import LIVE_COLLECTOR as collector  # noqa: E402
from tools.scrapers.SCRAPE_QUINIELA15_DIRECTO import parse_match_title, parse_score, q15_row_date  # noqa: E402

MADRID = ZoneInfo("Europe/Madrid")
# Sabado 31 de octubre de 2026, 16:47 Madrid: Levante-Atletico y Eibar-Almeria
# acabados, Rayo-Celta (16:15) en juego, Betis-Malaga (18:30) por empezar.
NOW = datetime(2026, 10, 31, 16, 47, tzinfo=MADRID)

# Boleto J17 tal y como lo guarda la BD (fecha, hora y nombres del ticket).
BOLETO_J17 = {
    1: ("Levante", "Atlético", "2026-10-31", "14:00"),
    2: ("Rayo", "Celta", "2026-10-31", "16:15"),
    3: ("Betis", "Málaga", "2026-10-31", "18:30"),
    4: ("Barcelona", "Alavés", "2026-10-31", "21:00"),
    5: ("Getafe", "Sevilla", "2026-11-01", "14:00"),
    6: ("Racing", "Real Madrid", "2026-11-01", "16:15"),
    7: ("Elche", "Valencia", "2026-11-01", "18:30"),
    8: ("Eibar", "Almería", "2026-10-31", "16:15"),
    9: ("Eldense", "Granada", "2026-11-01", "14:00"),
    10: ("Burgos", "Castellón", "2026-11-01", "18:30"),
    11: ("Alavés (F)", "R. Sociedad (F)", "2026-11-01", "12:00"),
    12: ("Madrid CFF (F)", "Deportivo (F)", "2026-10-31", "18:00"),
    13: ("Sevilla (F)", "R. Madrid (F)", "2026-11-01", "19:00"),
    14: ("Tenerife (F)", "Athletic (F)", "", ""),
    15: ("Athletic", "R. Sociedad", "2026-11-01", "21:00"),
}

# Nombres tal y como los publica quiniela15.com en /resultados-quiniela/18
# (captura real del 31/10/2026), que es la quiniela que juega este boleto.
Q15_J18 = {
    1: ("Levante", "At. Madrid", "2026-10-31", 0, 2),
    2: ("Rayo", "Celta", "2026-10-31", 0, 0),
    3: ("Betis", "Málaga", "2026-10-31", None, None),
    4: ("Barcelona", "Alavés", "2026-10-31", None, None),
    5: ("Getafe", "Sevilla", "2026-11-01", None, None),
    6: ("R. Santander", "Real Madrid", "2026-11-01", None, None),
    7: ("Elche", "Valencia", "2026-11-01", None, None),
    8: ("Eibar", "Almería", "2026-10-31", None, None),
    9: ("Eldense", "Granada", "2026-11-01", None, None),
    10: ("Burgos", "Castellón", "2026-11-01", None, None),
    11: ("Alavés Femenino", "R. Sociedad (F)", "2026-11-01", None, None),
    12: ("Madrid CFF", "Deportivo (F)", "2026-10-31", None, None),
    13: ("Sevilla (F)", "Real Madrid (F)", "2026-11-01", None, None),
    14: ("Tenerife (F)", "Athletic Club (F)", "2026-11-02", None, None),
    15: ("Athletic", "R. Sociedad", "2026-11-01", None, None),
}

# La J17 de quiniela15.com es la Copa del Rey del 28/10: otra quiniela.
# Se reproduce su casilla 1 a proposito, porque tambien se llama
# "Levante - At. Madrid" y es donde el cruce por id metia un marcador ajeno.
Q15_COPA_J17 = {
    1: ("Levante", "At. Madrid", "2026-10-28", 1, 3),
    2: ("Rayo", "Celta", "2026-10-28", 0, 1),
}


def _conn_j17():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE resultados (
            jornada INTEGER, partido_id INTEGER, local TEXT, visitante TEXT,
            goles_local INTEGER, goles_visitante INTEGER, status TEXT,
            fecha TEXT, hora TEXT, minuto TEXT, signo_actual TEXT, updated_at TEXT
        )
        """
    )
    for num, (local, visitante, fecha, hora) in BOLETO_J17.items():
        conn.execute(
            "INSERT INTO resultados VALUES (17, ?, ?, ?, NULL, NULL, 'NS', ?, ?, '', '-', NULL)",
            (num, local, visitante, fecha, hora),
        )
    conn.commit()
    return conn


@pytest.fixture
def j17_db(monkeypatch):
    conn = _conn_j17()
    monkeypatch.setattr(collector, "get_db", lambda: conn)
    monkeypatch.setattr(collector, "log_line", lambda message: None)
    monkeypatch.setattr(collector, "madrid_now", lambda: NOW)
    return conn


def _q15_match(num, source, status="NS"):
    local, visitante, fecha, home, away = source[num]
    return {
        "id": num,
        "local": local,
        "visitante": visitante,
        "fecha": fecha,
        "status": status,
        "minute": "",
        "score_home": home,
        "score_away": away,
    }


def _payload_j18(ids=None):
    """Foto real de las 16:47 del 31/10: el de las 14:00 acabado y el de las
    16:15 en el minuto 32 (0-0). Un FT del partido de las 16:15 seria
    incoherente (suelo de 60' desde el saque) y el colector lo descarta."""
    ids = ids or [1, 2]
    matches = []
    for num in ids:
        if num == 2:
            match = _q15_match(num, Q15_J18, "LIVE")
            match["minute"] = "32'"
        else:
            match = _q15_match(num, Q15_J18, "FT")
        matches.append(match)
    return {"jornada": 18, "q15_jornada": 18, "boleto_jornada": 17, "matches": matches}


class TestGrafiasDeLaJ17:
    """Las grafias que publica quiniela15 tienen que cruzar con el boleto."""

    @pytest.mark.parametrize(
        "q15, boleto",
        [
            ("At. Madrid", "Atlético"),
            ("Atlético de Madrid", "Atlético"),
            ("R. Santander", "Racing"),
            ("Racing Santander", "Racing"),
            ("R. Sociedad (F)", "R. Sociedad (F)"),
            ("Real Sociedad (F)", "R. Sociedad (F)"),
            ("Real Sociedad Femenino", "R. Sociedad (F)"),
            ("R. Madrid (F)", "R. Madrid (F)"),
            ("Real Madrid (F)", "R. Madrid (F)"),
            ("Real Madrid Femenino", "R. Madrid (F)"),
            ("Athletic Bilbao Femenino", "Athletic (F)"),
            ("UD Tenerife", "Tenerife (F)"),
            ("Deportivo de La Coruña Femenino", "Deportivo (F)"),
        ],
    )
    def test_nombre_q15_cruza_con_boleto(self, q15, boleto):
        assert team_keys_compatible(q15, boleto), f"{q15} no cruza con {boleto}"

    @pytest.mark.parametrize(
        "masculino, femenino",
        [
            ("Atlético", "Atlético (F)"),
            ("Real Madrid", "R. Madrid (F)"),
            ("R. Sociedad", "R. Sociedad (F)"),
            ("Tenerife", "UD Tenerife"),
            ("Tenerife", "Tenerife (F)"),
            ("Athletic", "Athletic Bilbao Femenino"),
            ("Sevilla", "Sevilla (F)"),
        ],
    )
    def test_genero_sigue_blindado(self, masculino, femenino):
        assert not team_keys_compatible(masculino, femenino)

    def test_los_equipos_de_la_j17_tienen_escudo(self):
        """Mismo canónico que el cruce: antes "Atletico" y "Racing" salían sin
        escudo además de sin resultado."""
        logos = load_team_logos()
        for name in ("Atlético", "Racing", "R. Sociedad (F)", "R. Madrid (F)", "Tenerife (F)", "Athletic (F)"):
            assert logos.get(normalize_team_key(name)), f"{name} sin escudo"


class TestNumeracionDeLaQuiniela:
    """El boleto J17 se juega en la J18 de quiniela15."""

    def test_override_de_jornada(self):
        from config.quiniela15_jornadas import q15_jornada

        assert q15_jornada(17) == 18
        assert q15_jornada(18) == 18
        assert q15_jornada(16) == 16

    def test_los_equipos_del_boleto_estan_en_la_q15_correcta(self, j17_db):
        payload = {"matches": [_q15_match(num, Q15_J18) for num in Q15_J18]}
        trusted, reason = collector._q15_payload_matches_boleto(17, payload)

        assert trusted, reason

    def test_la_jornada_de_la_copa_se_rechaza(self, j17_db):
        """Si quiniela15 devuelve la J17 (Copa), los equipos no son los del
        boleto y no se escribe nada."""
        payload = {"matches": [_q15_match(num, Q15_COPA_J17) for num in Q15_COPA_J17]}
        trusted, _ = collector._q15_payload_matches_boleto(17, payload)

        assert not trusted

    def test_payload_no_confirmado_no_toca_la_bd(self, j17_db):
        payload = _payload_j18(ids=[1, 2])
        payload["boleto_comprobado"] = False

        assert collector.apply_q15_results_to_db(17, payload) == 0
        rows = j17_db.execute("SELECT status FROM resultados WHERE jornada = 17").fetchall()
        assert {row["status"] for row in rows} == {"NS"}

    def test_marcador_de_otra_fecha_no_se_aplica(self, j17_db):
        """Blindaje final: aunque el cruce por nombre pase, un partido de otro
        dia no puede ser el mismo."""
        assert (
            collector._q15_kickoff_order_plausible(_q15_match(1, Q15_COPA_J17, "FT"), {"fecha": "2026-10-31"}) is False
        )
        assert collector._q15_kickoff_order_plausible(_q15_match(1, Q15_J18, "FT"), {"fecha": "2026-10-31"}) is True
        # Sin fecha en la fuente se acepta: el cruce de nombres ya ha pasado.
        assert collector._q15_kickoff_order_plausible({"fecha": ""}, {"fecha": "2026-10-31"}) is True


class TestResultadosDeLaJ17:
    """El sintoma exacto del usuario: los jugados tienen que entrar."""

    def test_levante_atletico_y_rayo_celta_entran(self, j17_db):
        updates = collector.apply_q15_results_to_db(17, _payload_j18(ids=[1, 2]))

        assert updates == 2, "0 updates = la portada se queda con el horario"
        rows = {
            row["partido_id"]: row for row in j17_db.execute("SELECT * FROM resultados WHERE jornada = 17").fetchall()
        }
        assert (rows[1]["goles_local"], rows[1]["goles_visitante"], rows[1]["status"]) == (0, 2, "FT")
        assert rows[1]["signo_actual"] == "2"
        assert rows[1]["minuto"] == "Finalizado"
        # 0-0 al minuto 32: se pinta el marcador en directo, no el horario.
        assert (rows[2]["goles_local"], rows[2]["goles_visitante"], rows[2]["status"]) == (0, 0, "LIVE")
        assert rows[2]["minuto"] == "32'"
        assert rows[2]["signo_actual"] == "X"
        # Las casillas por jugar siguen pendientes, no se inventan.
        assert rows[3]["status"] == "NS"

    def test_los_seis_primeros_de_la_j17_entran_completos(self, j17_db, monkeypatch):
        """Foto del domingo por la noche: Levante, Rayo, Betis y Eibar hechos."""
        monkeypatch.setattr(collector, "madrid_now", lambda: datetime(2026, 11, 1, 23, 0, tzinfo=MADRID))
        matches = []
        for num, scores in ((1, (0, 2)), (2, (0, 0)), (3, (2, 1)), (8, (1, 1))):
            match = _q15_match(num, Q15_J18, "FT")
            match["score_home"], match["score_away"] = scores
            matches.append(match)
        matches.append(_q15_match(6, Q15_J18, "FT"))
        matches[-1]["score_home"], matches[-1]["score_away"] = 1, 4

        updates = collector.apply_q15_results_to_db(17, {"matches": matches})

        assert updates == 5
        rows = {
            row["partido_id"]: row for row in j17_db.execute("SELECT * FROM resultados WHERE jornada = 17").fetchall()
        }
        assert (rows[11]["status"], rows[11]["goles_local"]) == ("NS", None), "las femeninas siguen pendientes"
        assert rows[6]["signo_actual"] == "2"


class TestFallbackDelProveedor:
    """_core_team_key ya no destroza los nombres con tilde."""

    @pytest.mark.parametrize(
        "nombre",
        ["Atlético", "At. Madrid", "Málaga", "Almería", "Castellón"],
    )
    def test_clave_core_estable(self, nombre):
        key = _core_team_key(nombre)

        assert len(key) == 1
        assert len(key[0]) > 3
        assert key == _core_team_key(nombre)

    def test_forma_juridica_sigue_siendo_ruido(self):
        assert _core_team_key("AD Ceuta FC") == _core_team_key("Ceuta")

    def test_el_feed_cruza_por_core(self):
        """El proveedor escribe el nombre largo y la BD el corto."""
        match = {"id": 991, "state": {"score": {"current": "0-2"}}}
        feed = {}
        home = normalize_team_key("Atlético Madrid")
        away = normalize_team_key("Valencia")
        core_feed = {(_core_team_key("Atlético Madrid"), _core_team_key("Valencia")): [(match, False)]}
        # El cruce canónico no encuentra nada (la BD dice "Atlético"), el core sí.
        assert feed.get((home, away)) is None
        assert _find_feed_item(feed, "Atlético", "Valencia", core_feed) == (match, False)

    def test_el_feed_no_mezcla_generos(self):
        match = {"id": 992}
        core_feed = {
            (_core_team_key("Real Madrid Femenino"), _core_team_key("Barcelona")): [(match, False)],
        }
        # "Real Madrid" (masculino) no puede casar con el femenino por el core.
        assert _find_feed_item({}, "Real Madrid", "Barcelona", core_feed) is None


class TestParserQuiniela15:
    """La fecha de cada fila se expone para poder validar la numeracion."""

    def test_fecha_de_celda_de_marcador(self):
        from bs4 import BeautifulSoup

        html = """
        <table><tr>
          <td class="tnum">1</td>
          <td>Levante (1647.8) - At. Madrid (1831.9)</td>
          <td><span class="matchdate">sábado31 oct 18:30h</span></td>
          <td></td>
        </tr></table>
        """
        row = BeautifulSoup(html, "html.parser").find("tr")
        assert q15_row_date(row, reference=datetime(2026, 10, 31)) == "2026-10-31"

    def test_titulo_con_fuerza_y_femenino(self):
        index, home, away = parse_match_title("12 Madrid CFF (1516.0) - Deportivo (F) (1466.6)")
        assert (index, home, away) == (12, "Madrid CFF", "Deportivo (F)")

    def test_marcador_parcial(self):
        assert parse_score("0 - 0") == (0, 0)
        assert parse_score("sábado31 oct 18:30h") == (None, None)


class TestAutodeteccionDeJornada:
    """La equivalencia no puede depender de que alguien edite una tabla."""

    def test_autodetecta_la_jornada_vecina(self, j17_db, monkeypatch):
        payloads = {
            17: {"jornada": 17, "matches": [_q15_match(num, Q15_COPA_J17) for num in Q15_COPA_J17]},
            18: {"jornada": 18, "matches": [_q15_match(num, Q15_J18) for num in Q15_J18]},
        }
        pedidos = []

        def fake_scrape(numero):
            pedidos.append(numero)
            return payloads.get(numero, {"jornada": numero, "matches": []})

        monkeypatch.setattr(collector, "scrape_q15_directo", fake_scrape)
        # Sin tabla: se prueba el numero pelado y sus vecinos.
        monkeypatch.setattr(collector, "q15_jornada", lambda numero: numero)

        numero, origen = collector._q15_numero_para_boleto(17)

        assert numero == 18
        assert origen.startswith("autodetectada")
        assert pedidos[0] == 17, "primero se mira el numero del boleto"

    def test_no_confirma_entonces_no_escribe(self, j17_db, monkeypatch):
        """Si la sonda no encuentra equivalencia, el payload queda sin
        confirmar y apply no toca la BD."""
        monkeypatch.setattr(collector, "q15_jornada", lambda numero: numero)
        monkeypatch.setattr(
            collector,
            "scrape_q15_directo",
            lambda numero: {"jornada": numero, "matches": [_q15_match(n, Q15_COPA_J17) for n in Q15_COPA_J17]},
        )
        monkeypatch.setattr(collector, "DATA_DIR", collector.DATA_DIR)
        payload = collector.scrape_q15_boleto(17)

        assert payload["matches"] == []
        assert payload["boleto_comprobado"] is False
        assert collector.apply_q15_results_to_db(17, payload) == 0
