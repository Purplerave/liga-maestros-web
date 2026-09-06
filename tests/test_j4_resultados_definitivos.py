"""Regresion del incidente J4 2026/27 (5-7 septiembre 2026).

Sintomas reportados por el usuario:
1. El Valencia - Barcelona ("el del barsa") dejo de actualizarse antes de
   acabar y mostro un marcador como resultado final.
2. Partidos jugados el sabado (Sporting - Girona, Edf Logrono - Athletic (F))
   no mostraban resultado.
3. Los horarios publicados no coincidian con los reales (Espanyol - Sevilla
   figuraba el lunes cuando se jugaba el domingo 21:00).

Causas: nombres sin alias comun ("Sporting" vs "Sporting Gijon",
"Logrono (F)" vs "Edf Logrono", "Barcelona (F)" sin canonico femenino),
horarios del boleto desfasados que hacian descartar los directos como
"imposibles", y reglas de cierre (105'/120') que congelaban marcadores
parciales como finales.
"""

import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from liga_maestros.utils import normalize_team_key, team_keys_compatible  # noqa: E402
from tools.ops import LIVE_COLLECTOR as collector  # noqa: E402

MADRID = ZoneInfo("Europe/Madrid")
# Domingo 6 de septiembre de 2026, 18:40 Madrid: partidos 5, 6 y 12 en juego.
NOW = datetime(2026, 9, 6, 18, 40, tzinfo=MADRID)

# Nombres tal y como los publica quiniela15.com en /resultados-quiniela/4.
Q15_J4 = {
    1: ("Athletic", "At. Madrid"),
    2: ("Rayo", "R. Santander"),
    3: ("Villarreal", "Deportivo"),
    4: ("Valencia", "Barcelona"),
    5: ("Alavés", "Osasuna"),
    6: ("Málaga", "Levante"),
    7: ("Espanyol", "Sevilla"),
    8: ("R. Sociedad B", "Tenerife"),
    9: ("Sporting Gijón", "Girona"),
    10: ("Almería", "Cádiz"),
    11: ("Sevilla (F)", "Barcelona (F)"),
    12: ("Edf Logroño", "Athletic Club (F)"),
    13: ("At. Madrid (F)", "Alavés Femenino"),
    14: ("Real Madrid (F)", "Eibar (F)"),
    15: ("Getafe", "Celta"),
}

# Nombres tal y como los guarda la BD de la quiniela (boleto).
DB_J4 = {
    1: ("Athletic Club", "At. Madrid"),
    2: ("Rayo Vallecano", "Racing Santander"),
    3: ("Villarreal", "Deportivo"),
    4: ("Valencia", "Barcelona"),
    5: ("Alavés", "Osasuna"),
    6: ("Málaga", "Levante"),
    7: ("Espanyol", "Sevilla"),
    8: ("Real Sociedad B", "Tenerife"),
    9: ("Sporting", "Girona"),
    10: ("Almería", "Cádiz"),
    11: ("Sevilla (F)", "Barcelona (F)"),
    12: ("Logroño (F)", "Athletic Club (F)"),
    13: ("At. Madrid (F)", "Alavés (F)"),
    14: ("Real Madrid (F)", "Eibar (F)"),
    15: ("Getafe", "Celta"),
}

# Horarios reales verificados (hora de Madrid) el 06/09/2026.
HORARIOS_REALES_J4 = {
    1: ("2026-09-05", "16:15"),
    2: ("2026-09-05", "18:30"),
    3: ("2026-09-05", "21:00"),
    4: ("2026-09-06", "16:15"),
    5: ("2026-09-06", "18:30"),
    6: ("2026-09-06", "18:30"),
    7: ("2026-09-06", "21:00"),
    8: ("2026-09-05", "19:00"),
    9: ("2026-09-06", "16:30"),
    10: ("2026-09-06", "21:00"),
    11: ("2026-09-06", "12:00"),
    12: ("2026-09-06", "18:30"),
    13: ("2026-09-06", "17:00"),
    14: ("2026-09-06", "20:30"),
    15: ("2026-09-07", "19:00"),
}


class TestNombresJ4:
    """Cada partido de la J4 debe cruzar con el nombre de quiniela15."""

    @pytest.mark.parametrize("partido", sorted(Q15_J4))
    def test_nombre_q15_cruza_con_bd(self, partido):
        local_q15, visita_q15 = Q15_J4[partido]
        local_db, visita_db = DB_J4[partido]
        assert team_keys_compatible(local_q15, local_db), f"local {partido}: {local_q15} vs {local_db}"
        assert team_keys_compatible(visita_q15, visita_db), f"visitante {partido}: {visita_q15} vs {visita_db}"

    def test_sporting_gijon_tiene_canonico_comun(self):
        assert normalize_team_key("Sporting") == normalize_team_key("Sporting Gijón") == "SPORTING GIJON"

    def test_edf_logrono_cruza_con_logrono_f(self):
        assert team_keys_compatible("Edf Logroño", "Logroño (F)")
        assert normalize_team_key("Edf Logroño") == normalize_team_key("Logroño (F)")

    def test_barcelona_f_tiene_canonico_femenino(self):
        assert normalize_team_key("Barcelona (F)") == normalize_team_key("Barcelona Femenino") == "BARCELONA FEMENINO"

    def test_masculino_y_femenino_nunca_cruzan(self):
        """Un "(F)" no puede casar con el equipo masculino del mismo nombre."""
        assert not team_keys_compatible("Sevilla", "Sevilla (F)")
        assert not team_keys_compatible("Barcelona", "Barcelona (F)")
        assert not team_keys_compatible("Valencia Femenino", "Valencia")


def _conn_j4(horarios=None):
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
    horarios = horarios or HORARIOS_REALES_J4
    for num, (local, visitante) in DB_J4.items():
        fecha, hora = horarios[num]
        conn.execute(
            "INSERT INTO resultados VALUES (4, ?, ?, ?, NULL, NULL, 'NS', ?, ?, '', '-', NULL)",
            (num, local, visitante, fecha, hora),
        )
    conn.commit()
    return conn


@pytest.fixture
def j4_db(monkeypatch):
    conn = _conn_j4()
    monkeypatch.setattr(collector, "get_db", lambda: conn)
    monkeypatch.setattr(collector, "log_line", lambda message: None)
    monkeypatch.setattr(collector, "madrid_now", lambda: NOW)
    return conn


def _q15_match(num, local, visitante, status, minute, home, away):
    return {
        "id": num,
        "local": local,
        "visitante": visitante,
        "status": status,
        "minute": minute,
        "score_home": home,
        "score_away": away,
    }


def _q15_payload_j4_domingo_1840():
    """Foto real de quiniela15.com a las 18:40 del domingo 06/09/2026."""
    return {
        "matches": [
            _q15_match(1, *Q15_J4[1], "FT", "", 3, 0),
            _q15_match(2, *Q15_J4[2], "FT", "", 3, 2),
            _q15_match(3, *Q15_J4[3], "FT", "", 2, 3),
            _q15_match(4, *Q15_J4[4], "FT", "", 0, 5),
            _q15_match(5, *Q15_J4[5], "LIVE", "2'", 0, 0),
            _q15_match(6, *Q15_J4[6], "LIVE", "4'", 0, 0),
            # 7, 10, 14 y 15 aun sin jugar: sin marcador, no aplican.
            _q15_match(8, *Q15_J4[8], "FT", "", 1, 1),
            _q15_match(9, *Q15_J4[9], "FT", "", 0, 2),
            _q15_match(11, *Q15_J4[11], "FT", "", 0, 4),
            _q15_match(12, *Q15_J4[12], "LIVE", "5'", 0, 0),
            _q15_match(13, *Q15_J4[13], "FT", "", 1, 0),
        ]
    }


class TestAplicarResultadosQ15:
    def test_resultados_reales_de_la_j4_se_aplican_completos(self, j4_db):
        """Los 11 partidos con datos (8 FT + 3 LIVE) entran, incluidos los
        que antes fallaban por nombre: Sporting Gijon, Edf Logrono y
        Alaves Femenino."""
        updates = collector.apply_q15_results_to_db(4, _q15_payload_j4_domingo_1840())

        assert updates == 11
        rows = {
            row["partido_id"]: row
            for row in j4_db.execute("SELECT * FROM resultados WHERE jornada = 4").fetchall()
        }
        # Terminados del sabado y domingo (el "0-5 del barsa" incluido).
        assert (rows[4]["goles_local"], rows[4]["goles_visitante"], rows[4]["status"]) == (0, 5, "FT")
        assert (rows[4]["signo_actual"]) == "2"
        # Sporting - Girona: antes descartado por "Sporting Gijon" != "Sporting".
        assert (rows[9]["goles_local"], rows[9]["goles_visitante"], rows[9]["status"]) == (0, 2, "FT")
        # Edf Logrono - Athletic (F): antes descartado por nombre.
        assert (rows[12]["status"], rows[12]["minuto"]) == ("LIVE", "5'")
        # At. Madrid (F) - Alaves Femenino.
        assert (rows[13]["goles_local"], rows[13]["goles_visitante"]) == (1, 0)
        # Partidos en juego ahora mismo quedan LIVE con sello de frescura.
        assert rows[5]["status"] == "LIVE"
        assert rows[5]["updated_at"]

    def test_stale_no_se_fabrica_como_ft_antes_de_la_ventana_completa(self, j4_db, monkeypatch):
        """El caso "se paro antes de terminar y mostro resultado final".

        A las 18:40 un partido de las 16:15 lleva 145': con el umbral viejo
        (105') un STALE se escribia como FT y congelaba el marcador parcial.
        Ahora necesita la ventana completa (150').
        """
        payload = {"matches": [_q15_match(4, *Q15_J4[4], "STALE", "", 1, 2)]}
        updates = collector.apply_q15_results_to_db(4, payload)
        row = j4_db.execute("SELECT * FROM resultados WHERE partido_id = 4").fetchone()
        assert updates == 0
        assert row["status"] == "NS"

        later = NOW + timedelta(minutes=15)  # 18:55 -> 160' desde las 16:15
        monkeypatch.setattr(collector, "madrid_now", lambda: later)
        assert collector.apply_q15_results_to_db(4, payload) == 1
        row = j4_db.execute("SELECT status, goles_local FROM resultados WHERE partido_id = 4").fetchone()
        assert row["status"] == "FT"
        assert row["goles_local"] == 1

    def test_payload_parcial_no_tira_la_jornada_entera(self, monkeypatch, tmp_path):
        """write_q15_directo_cache aplica 12 filas si la web solo parsea 12."""
        conn = _conn_j4()
        monkeypatch.setattr(collector, "get_db", lambda: conn)
        monkeypatch.setattr(collector, "log_line", lambda message: None)
        monkeypatch.setattr(collector, "madrid_now", lambda: NOW)

        partial = _q15_payload_j4_domingo_1840()
        partial["matches"] = partial["matches"][:10]  # la web "pierde" la ultima fila
        partial["jornada"] = 4
        partial["source"] = "fixture"
        partial["fetched_at"] = "2026-09-06T18:40:00"

        monkeypatch.setattr(collector, "DATA_DIR", Path(tmp_path))
        monkeypatch.setattr(collector, "scrape_q15_directo", lambda jornada: partial)

        detail = collector.write_q15_directo_cache(4)

        assert detail["matches"] == 10
        row = conn.execute("SELECT status FROM resultados WHERE partido_id = 9").fetchone()
        assert row["status"] == "FT"


class TestHorariosReparados:
    def test_migracion_corrige_horarios_de_filas_pendientes(self, monkeypatch):
        """La BD en produccion arrastra los horarios malos del boleto; la
        migracion debe alinear las filas NS con el horario corregido."""
        from liga_maestros.db import migrations

        horarios_malos = {
            num: ("2026-09-05", "17:00") if num % 2 else ("2026-09-06", "21:30") for num in DB_J4
        }
        conn = _conn_j4(horarios=horarios_malos)
        # Un partido ya finalizado con marcador: no se toca.
        conn.execute(
            "UPDATE resultados SET status='FT', goles_local=3, goles_visitante=0, minuto='Finalizado',"
            " signo_actual='1' WHERE partido_id = 1"
        )
        conn.commit()

        corrected = [
            (num, DB_J4[num][0], DB_J4[num][1], HORARIOS_REALES_J4[num][0], HORARIOS_REALES_J4[num][1])
            for num in sorted(DB_J4)
        ]
        monkeypatch.setattr(migrations, "load_scrape_matches", lambda jornada: corrected)

        migrations.ensure_jornada_completa(conn, 4)

        rows = {
            row["partido_id"]: row
            for row in conn.execute("SELECT * FROM resultados WHERE jornada = 4").fetchall()
        }
        # Espanyol - Sevilla: el boleto decia lunes 19:30, es domingo 21:00.
        assert (rows[7]["fecha"], rows[7]["hora"]) == ("2026-09-06", "21:00")
        # Valencia - Barcelona: el boleto decia 17:00, real 16:15.
        assert (rows[4]["fecha"], rows[4]["hora"]) == ("2026-09-06", "16:15")
        # El FT con marcador conserva su horario original (protegido).
        assert (rows[1]["fecha"], rows[1]["hora"]) == ("2026-09-05", "17:00")


class TestRefrescoHighlightly:
    def test_todas_las_fechas_de_la_jornada_reciben_llamada(self, monkeypatch, tmp_path):
        """Con presupuesto 4 y fechas pasadas primero, el sabado (con
        resultados pendientes) se refresca aunque hoy sea domingo."""
        from liga_maestros.services import highlightly

        conn = _conn_j4()
        # Sabado terminado sin recoger (status NS sin goles) + domingo en juego.
        for num in (1, 2, 3, 8):
            conn.execute(
                "UPDATE resultados SET fecha='2026-09-05' WHERE partido_id = ?", (num,)
            )
        conn.commit()

        fetched_dates = []

        def _fake_fetch(date_text, conn=None, jornada=None, max_calls=None):
            fetched_dates.append(date_text)
            return []

        usage = {"calls": 0}

        def _fake_usage():
            return dict(usage)

        class _ConnProxy:
            """get_db() con contexto: devuelve la conexion compartida."""

            def __enter__(self):
                return conn

            def __exit__(self, *exc):
                return False

        monkeypatch.setattr(highlightly, "get_db", lambda: _ConnProxy())
        monkeypatch.setattr(highlightly, "fetch_highlightly_matches", _fake_fetch)
        monkeypatch.setattr(highlightly, "get_highlightly_usage", _fake_usage)
        monkeypatch.setattr(highlightly, "get_highlightly_circuit", lambda: {"open": False})
        monkeypatch.setattr(highlightly, "today_madrid", lambda: "2026-09-06")
        monkeypatch.setattr(highlightly, "HIGHLIGHTLY_REFRESH_ENABLED", True)
        monkeypatch.setattr(highlightly, "HIGHLIGHTLY_MAX_CALLS_PER_REFRESH", 4)
        monkeypatch.setenv("HIGHLIGHTLY_API_KEY", "test-key")
        # Uso creciente: cada llamada al API consume 1 del presupuesto.
        original_fetch = highlightly.fetch_highlightly_matches

        def _fetch_counting(date_text, conn=None, jornada=None, max_calls=None):
            result = original_fetch(date_text, conn=conn, jornada=jornada, max_calls=max_calls)
            usage["calls"] += 1
            return result

        monkeypatch.setattr(highlightly, "fetch_highlightly_matches", _fetch_counting)

        updates = highlightly.refresh_current_matches_from_highlightly(force=True, jornada=4)

        assert updates == 0  # el feed simulado no trae partidos
        assert fetched_dates == ["2026-09-05", "2026-09-06"]
