"""Regresión del incidente J21 2026/27 (17-19 noviembre 2026).

Síntoma reportado por el usuario:
"hay dos partidos de hoy que no sale el resultado" (Hungría - Irlanda N. y
Rep. Irlanda - Kosovo).

Causa raíz:
El boleto importa los nombres con abreviaturas ("Irlanda N." y "Rep. Irlanda"),
mientras que quiniela15.com y los proveedores externos publican "Irlanda del Norte" /
"Northern Ireland" y "Irlanda" / "República de Irlanda" / "Republic of Ireland".
Sin aliases en TEAM_LOGO_ALIASES, el cruce de nombres en LIVE_COLLECTOR
(apply_q15_results_to_db y Highlightly) descartaba en silencio ambos partidos
(q15_team_mismatch_skipped) y las filas se quedaban en "NS" sin marcador.
Igualmente, "Bosnia Herzegovina" requería alias con "Bosnia".
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

from liga_maestros.db import migrations  # noqa: E402
from liga_maestros.utils import (  # noqa: E402
    normalize_team_key,
    short_team_name,
    team_keys_compatible,
)
from tools.ops import LIVE_COLLECTOR as collector  # noqa: E402

MADRID = ZoneInfo("Europe/Madrid")
NOW = datetime(2026, 11, 17, 21, 35, tzinfo=MADRID)

# Nombres del boleto J21 en la base de datos
DB_J21 = {
    1: ("Bosnia Herzegovina", "Rumanía"),
    2: ("Ucrania", "Georgia"),
    3: ("Gales", "Portugal"),
    4: ("Hungría", "Irlanda N."),
    5: ("Polonia", "Suecia"),
    6: ("Rep. Irlanda", "Kosovo"),
    7: ("R. Madrid (F)", "Inter (F)"),
    8: ("BK Hacken (F)", "Man. City (F)"),
    9: ("Chelsea (F)", "PSG (F)"),
    10: ("Juventus (F)", "Leuven (F)"),
    11: ("Austria Wien (F)", "B. Munich (F)"),
    12: ("Arsenal (F)", "OL. Lyonnes (F)"),
    13: ("Barcelona (F)", "Servette (F)"),
    14: ("Benfica (F)", "Roma (F)"),
    15: ("Dinamarca", "Noruega"),
}

# Nombres tal como los publica quiniela15.com en directo
Q15_J21 = {
    1: ("Bosnia", "Rumania"),
    2: ("Ucrania", "Georgia"),
    3: ("Gales", "Portugal"),
    4: ("Hungria", "Irlanda del Norte"),
    5: ("Polonia", "Suecia"),
    6: ("Irlanda", "Kosovo"),
    7: ("Real Madrid (F)", "Inter Femenino"),
    8: ("Hacken (F)", "Manchester City (F)"),
    9: ("Chelsea (F)", "PSG (F)"),
    10: ("Juventus (F)", "OH Leuven (F)"),
    11: ("Austria Viena (F)", "Bayern Munich (F)"),
    12: ("Arsenal (F)", "Lyon (F)"),
    13: ("FC Barcelona (F)", "Servette Femenino"),
    14: ("Benfica (F)", "Roma (F)"),
    15: ("Dinamarca", "Noruega"),
}

# Variantes habituales de proveedores de feed (Highlightly / UEFA)
PROVIDER_VARIANTS_J21 = {
    1: [("Bosnia and Herzegovina", "Romania"), ("Bosnia & Herzegovina", "Romania")],
    4: [("Hungary", "Northern Ireland"), ("Hungría", "Irlanda del Norte")],
    6: [("Republic of Ireland", "Kosovo"), ("República de Irlanda", "Kosovo")],
    7: [("Real Madrid", "Inter Milan"), ("Real Madrid CF", "FC Internazionale")],
    8: [("BK Häcken", "Manchester City"), ("Häcken", "Man City")],
    10: [("Juventus", "Oud-Heverlee Leuven"), ("Juventus", "OH Leuven")],
    11: [("Austria Wien", "FC Bayern München"), ("Austria Viena", "Bayern")],
    12: [("Arsenal", "Olympique Lyonnais"), ("Arsenal WFC", "Olympique Lyon")],
    13: [("Barcelona", "Servette Chênois")],
    14: [("SL Benfica", "AS Roma")],
}


class TestCruceNombresJ21:
    """Verifica que todas las casillas de J21 cruzan entre BD y Q15."""

    @pytest.mark.parametrize("partido_id", sorted(Q15_J21))
    def test_nombres_q15_cruzan_con_bd(self, partido_id):
        local_q15, visit_q15 = Q15_J21[partido_id]
        local_db, visit_db = DB_J21[partido_id]
        assert team_keys_compatible(local_q15, local_db), f"Partido {partido_id} local: {local_q15} vs {local_db}"
        assert team_keys_compatible(visit_q15, visit_db), f"Partido {partido_id} visitante: {visit_q15} vs {visit_db}"

    @pytest.mark.parametrize("partido_id,variantes", sorted(PROVIDER_VARIANTS_J21.items()))
    def test_variantes_proveedores_cruzan_con_bd(self, partido_id, variantes):
        local_db, visit_db = DB_J21[partido_id]
        is_femenino = 7 <= partido_id <= 14
        for local_p, visit_p in variantes:
            if is_femenino:
                assert normalize_team_key(local_p, feminine=True) == normalize_team_key(local_db), (
                    f"P{partido_id} local: {local_p} vs {local_db}"
                )
                assert normalize_team_key(visit_p, feminine=True) == normalize_team_key(visit_db), (
                    f"P{partido_id} visitante: {visit_p} vs {visit_db}"
                )
            else:
                assert team_keys_compatible(local_p, local_db), f"P{partido_id} local: {local_p} vs {local_db}"
                assert team_keys_compatible(visit_p, visit_db), f"P{partido_id} visitante: {visit_p} vs {visit_db}"

    def test_irlanda_del_norte_y_irlanda_n_tienen_canonico_comun(self):
        assert normalize_team_key("Irlanda N.") == "IRLANDA DEL NORTE"
        assert normalize_team_key("Irlanda del Norte") == "IRLANDA DEL NORTE"
        assert normalize_team_key("Northern Ireland") == "IRLANDA DEL NORTE"

    def test_republica_de_irlanda_y_rep_irlanda_tienen_canonico_comun(self):
        assert normalize_team_key("Rep. Irlanda") == "REPUBLICA DE IRLANDA"
        assert normalize_team_key("República de Irlanda") == "REPUBLICA DE IRLANDA"
        assert normalize_team_key("Irlanda") == "REPUBLICA DE IRLANDA"
        assert normalize_team_key("Republic of Ireland") == "REPUBLICA DE IRLANDA"

    def test_bosnia_y_bosnia_herzegovina_tienen_canonico_comun(self):
        assert normalize_team_key("Bosnia") == "BOSNIA HERZEGOVINA"
        assert normalize_team_key("Bosnia Herzegovina") == "BOSNIA HERZEGOVINA"
        assert normalize_team_key("Bosnia & Herzegovina") == "BOSNIA HERZEGOVINA"

    def test_short_names_round_trip(self):
        assert short_team_name("REPUBLICA DE IRLANDA") == "REP. IRLANDA"
        assert short_team_name("IRLANDA DEL NORTE") == "IRLANDA N."


class TestApplyQ15ResultadosJ21:
    """Simula una pasada del colector sobre la J21 con resultados en directo."""

    def test_colector_actualiza_partidos_4_y_6_sin_descartarlos(self, monkeypatch):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        migrations.ensure_core_tables(conn)
        migrations.ensure_jornada_21(conn)

        monkeypatch.setattr(collector, "get_db", lambda: conn)
        monkeypatch.setattr(collector, "madrid_now", lambda: NOW)

        # Q15 reporta resultados en directo (Hungría 1-0 Irlanda del Norte, Irlanda 1-0 Kosovo)
        payload = {
            "jornada": 21,
            "matches": [
                {
                    "id": 1,
                    "local": "Bosnia",
                    "visitante": "Rumania",
                    "score_home": 1,
                    "score_away": 0,
                    "status": "LIVE",
                    "minute": "45'",
                },
                {
                    "id": 4,
                    "local": "Hungria",
                    "visitante": "Irlanda del Norte",
                    "score_home": 1,
                    "score_away": 0,
                    "status": "LIVE",
                    "minute": "35'",
                },
                {
                    "id": 6,
                    "local": "Irlanda",
                    "visitante": "Kosovo",
                    "score_home": 1,
                    "score_away": 0,
                    "status": "LIVE",
                    "minute": "28'",
                },
            ],
        }

        updates = collector.apply_q15_results_to_db(21, payload)
        assert updates == 3, f"Deben actualizarse los 3 partidos, pero se actualizaron {updates}"

        p4 = conn.execute(
            "SELECT goles_local, goles_visitante, status, signo_actual FROM resultados WHERE jornada=21 AND partido_id=4"
        ).fetchone()
        assert p4["goles_local"] == 1
        assert p4["goles_visitante"] == 0
        assert p4["status"] == "LIVE"
        assert p4["signo_actual"] == "1"

        p6 = conn.execute(
            "SELECT goles_local, goles_visitante, status, signo_actual FROM resultados WHERE jornada=21 AND partido_id=6"
        ).fetchone()
        assert p6["goles_local"] == 1
        assert p6["goles_visitante"] == 0
        assert p6["status"] == "LIVE"
        assert p6["signo_actual"] == "1"
