"""Regresion del incidente J6 2026/27 (11-14 septiembre 2026).

Sintoma reportado por el usuario (repetido todas las semanas): "no aparece el
resultado de los partidos de la quiniela"; el viernes 11/09 el directo veia el
Sevilla - Valencia de las 21:00 (1-0, min. 84) y el boleto seguia mostrando
"NS" sin marcador.

Causa raiz: el boleto J6 mezcla LaLiga y Liga F, asi que la importacion marco
los equipos masculinos con "(M)" ("Sevilla (M)", "Valencia (M)"...). Ese
marcador no existia para las funciones de cruce: la clave canonica de
"Sevilla (M)" pasaba a ser "SEVILLA M", una clave que no publica ni
quiniela15 ("Sevilla") ni el proveedor ("Sevilla FC"). Resultado: el cruce de
nombres descartaba EL RESULTADO DE TODOS los equipos masculinos de la jornada
(``q15_team_mismatch_skipped`` en el colector y feed sin casar en Highlightly),
mientras el Directo seguia viendose porque el panel externo no cruza con la BD.

Arreglo: ``clean_team_key`` elimina el marcador "(M)" (y la palabra
"MASCULINO/MASCULINA") igual que preserva el "(F)"; aliases nuevos para
"R. Valladolid" y "Badalona W.". El genero sigue protegido: "Sevilla (M)"
nunca casa con "Sevilla (F)".
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

from liga_maestros.services.highlightly import _find_feed_item  # noqa: E402
from liga_maestros.utils import (  # noqa: E402
    clean_team_key,
    load_team_logos,
    normalize_team_key,
    team_keys_compatible,
)
from tools.ops import LIVE_COLLECTOR as collector  # noqa: E402

MADRID = ZoneInfo("Europe/Madrid")
# Viernes 11 de septiembre de 2026, 22:55 en Madrid: el Sevilla - Valencia
# (partido 6, el "de las 9") esta en el minuto 84.
NOW = datetime(2026, 9, 11, 22, 55, tzinfo=MADRID)

# Nombres tal y como los publica quiniela15.com en /resultados-quiniela/6
# (captura real del cache en produccion, 22:51 del 11/09/2026).
Q15_J6 = {
    1: ("Athletic", "Elche"),
    2: ("Levante", "Barcelona"),
    3: ("Osasuna", "Espanyol"),
    4: ("R. Santander", "Alavés"),
    5: ("Real Madrid", "Rayo"),
    6: ("Sevilla", "Valencia"),
    7: ("Villarreal", "Betis"),
    8: ("Cádiz", "Las Palmas"),
    9: ("Tenerife", "Leganés"),
    10: ("Valladolid", "Real Oviedo"),
    11: ("Alavés Femenino", "Granada (F)"),
    12: ("Edf Logroño", "Valencia (F)"),
    13: ("Eibar (F)", "Las Planas (F)"),
    14: ("Madrid CFF", "Sevilla (F)"),
    15: ("R. Sociedad", "At. Madrid"),
}

# Nombres tal y como los guarda la BD (boleto J6 importado con marcador "(M)").
DB_J6 = {
    1: ("Athletic Club (M)", "Elche (M)"),
    2: ("Levante (M)", "Barcelona (M)"),
    3: ("Osasuna (M)", "Espanyol (M)"),
    4: ("Racing de Santander (M)", "Alavés (M)"),
    5: ("Real Madrid (M)", "Rayo Vallecano (M)"),
    6: ("Sevilla (M)", "Valencia (M)"),
    7: ("Villarreal (M)", "Betis (M)"),
    8: ("Cádiz (M)", "Las Palmas (M)"),
    9: ("Tenerife (M)", "Leganés (M)"),
    10: ("R. Valladolid (M)", "R. Oviedo (M)"),
    11: ("Alavés (F)", "Granada (F)"),
    12: ("Logroño (F)", "Valencia (F)"),
    13: ("Eibar (F)", "Badalona W. (F)"),
    14: ("Madrid CFF (F)", "Sevilla (F)"),
    15: ("Real Sociedad (M)", "At. Madrid (M)"),
}

# Nombres del proveedor (Highlightly) para el partido del viernes.
HIGHLIGHTLY_J6_VIERNES = {6: ("Sevilla FC", "Valencia")}


class TestMarcadorMasculino:
    """El marcador "(M)" del boleto no debe cambiar la clave canonica."""

    def test_m_marker_se_elimina_de_la_clave(self):
        assert clean_team_key("Sevilla (M)") == "SEVILLA"

    def test_canonico_igual_al_nombre_oficial(self):
        assert normalize_team_key("Sevilla (M)") == normalize_team_key("Sevilla") == "SEVILLA FC"
        assert normalize_team_key("Valencia (M)") == normalize_team_key("Valencia") == "VALENCIA"
        assert normalize_team_key("Athletic Club (M)") == normalize_team_key("Athletic") == "ATHLETIC CLUB"

    def test_palabra_masculino_tambien_se_elimina(self):
        assert normalize_team_key("Sevilla Masculino") == normalize_team_key("Sevilla")

    def test_femenino_conserva_su_canonico(self):
        assert normalize_team_key("Sevilla (F)") == "SEVILLA FEMENINO"

    def test_sevilla_m_tiene_escudo(self):
        """El boleto J6 mostraba los equipos (M) sin escudo por la misma causa."""
        logos = load_team_logos()
        assert logos.get(normalize_team_key("Sevilla (M)"))
        assert logos.get(normalize_team_key("R. Valladolid (M)"))


class TestGeneroSeguro:
    """Quitar el "(M)" no puede abrir el cruce masculino <-> femenino."""

    @pytest.mark.parametrize(
        "masculino",
        ["Sevilla (M)", "Sevilla Masculino", "Barcelona (M)", "Valencia (M)"],
    )
    def test_masculino_nunca_cruza_con_femenino(self, masculino):
        femenino = masculino.split(" (M)")[0].replace(" Masculino", "") + " (F)"
        assert not team_keys_compatible(masculino, femenino)
        assert not team_keys_compatible(masculino, masculino.split(" (M)")[0].replace(" Masculino", "") + " Femenino")


class TestNombresJ6:
    """Cada partido de la J6 debe cruzar con el nombre de quiniela15."""

    @pytest.mark.parametrize("partido", sorted(Q15_J6))
    def test_nombre_q15_cruza_con_bd(self, partido):
        local_q15, visita_q15 = Q15_J6[partido]
        local_db, visita_db = DB_J6[partido]
        assert team_keys_compatible(local_q15, local_db), f"local {partido}: {local_q15} vs {local_db}"
        assert team_keys_compatible(visita_q15, visita_db), f"visitante {partido}: {visita_q15} vs {visita_db}"

    @pytest.mark.parametrize("partido", sorted(HIGHLIGHTLY_J6_VIERNES))
    def test_nombre_proveedor_cruza_con_bd(self, partido):
        local_hl, visita_hl = HIGHLIGHTLY_J6_VIERNES[partido]
        local_db, visita_db = DB_J6[partido]
        feed = {
            (normalize_team_key(local_hl), normalize_team_key(visita_hl)): "encontrado",
        }
        assert _find_feed_item(feed, local_db, visita_db) == "encontrado", (
            f"El feed del proveedor no encuentra la fila {partido} de la BD: {local_db} - {visita_db}"
        )


def _conn_j6():
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
    horarios = {
        1: ("2026-09-12", "18:30"),
        2: ("2026-09-13", "16:15"),
        3: ("2026-09-12", "16:15"),
        4: ("2026-09-12", "14:00"),
        5: ("2026-09-12", "21:00"),
        6: ("2026-09-11", "21:00"),
        7: ("2026-09-14", "21:00"),
        8: ("2026-09-12", "16:15"),
        9: ("2026-09-13", "21:00"),
        10: ("2026-09-13", "16:15"),
        11: ("2026-09-13", "12:00"),
        12: ("2026-09-13", "17:00"),
        13: ("2026-09-13", "19:30"),
        14: ("2026-09-12", "16:30"),
        15: ("2026-09-13", "21:00"),
    }
    for num, (local, visitante) in DB_J6.items():
        fecha, hora = horarios[num]
        conn.execute(
            "INSERT INTO resultados VALUES (6, ?, ?, ?, NULL, NULL, 'NS', ?, ?, '', '-', NULL)",
            (num, local, visitante, fecha, hora),
        )
    conn.commit()
    return conn


@pytest.fixture
def j6_db(monkeypatch):
    conn = _conn_j6()
    monkeypatch.setattr(collector, "get_db", lambda: conn)
    monkeypatch.setattr(collector, "log_line", lambda message: None)
    monkeypatch.setattr(collector, "madrid_now", lambda: NOW)
    return conn


def _q15_match(num, status, minute, home, away):
    local, visitante = Q15_J6[num]
    return {
        "id": num,
        "local": local,
        "visitante": visitante,
        "status": status,
        "minute": minute,
        "score_home": home,
        "score_away": away,
    }


class TestAplicarResultadosQ15:
    def test_sevilla_valencia_de_las_9_entra_en_la_bd(self, j6_db):
        """La foto real del viernes 22:51: solo el partido 6 en juego, 1-0 al 84'.

        Antes del arreglo esta pasada aplicaba 0 updates (todos los cruces
        masculinos se descartaban por "q15_team_mismatch_skipped") y el boleto
        se quedaba sin resultado toda la semana.
        """
        payload = {"matches": [_q15_match(6, "LIVE", "84'", 1, 0)]}

        updates = collector.apply_q15_results_to_db(6, payload)

        assert updates == 1
        row = j6_db.execute("SELECT * FROM resultados WHERE jornada = 6 AND partido_id = 6").fetchone()
        assert (row["goles_local"], row["goles_visitante"]) == (1, 0)
        assert row["status"] == "LIVE"
        assert row["signo_actual"] == "1"

    def test_resultado_final_se_aplica_y_se_sella(self, j6_db):
        collector.apply_q15_results_to_db(6, {"matches": [_q15_match(6, "LIVE", "84'", 1, 0)]})
        collector.madrid_now = lambda: datetime(2026, 9, 11, 23, 5, tzinfo=MADRID)

        updates = collector.apply_q15_results_to_db(6, {"matches": [_q15_match(6, "FT", "", 2, 1)]})

        assert updates == 1
        row = j6_db.execute("SELECT * FROM resultados WHERE jornada = 6 AND partido_id = 6").fetchone()
        assert (row["goles_local"], row["goles_visitante"], row["status"]) == (2, 1, "FT")
        assert row["minuto"] == "Finalizado"

    def test_femeninas_siguen_cruzando(self, j6_db, monkeypatch):
        """El arreglo del "(M)" no puede romper el cruce de Liga F."""
        # La J6 se juega del 11 al 14; el reloj se pone al final de la jornada
        # para que un FT reciente no choque con el suelo de seguridad de 60 min.
        monkeypatch.setattr(collector, "madrid_now", lambda: datetime(2026, 9, 14, 23, 0, tzinfo=MADRID))
        payload = {
            "matches": [
                _q15_match(11, "FT", "", 2, 0),
                _q15_match(13, "FT", "", 1, 3),
                _q15_match(14, "FT", "", 0, 2),
            ]
        }

        updates = collector.apply_q15_results_to_db(6, payload)

        assert updates == 3

    def test_ft_antes_del_saque_se_ignora(self, j6_db):
        """Un FT de un partido que aun no ha saqueado no se escribe nunca.

        La quiniela15 marca FT cuando el marcador deja de parpadear; si el
        partido no ha empezado, ese marcador es una foto vieja o un partido
        suspendido. Cerrar aqui congelaria un marcador parcial como final.
        """
        # NOW = 11/09 22:55 y el partido 13 kicks off el 13/09 19:30.
        payload = {"matches": [_q15_match(13, "FT", "", 1, 3)]}

        updates = collector.apply_q15_results_to_db(6, payload)

        assert updates == 0
        row = j6_db.execute("SELECT * FROM resultados WHERE jornada = 6 AND partido_id = 13").fetchone()
        assert row["goles_local"] is None
        assert row["status"] != "FT"
