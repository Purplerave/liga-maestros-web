"""Partidos atascados: cierre de directos imposibles, congelados y pendientes.

Reproduce las averias vistas en produccion el 16/08/2026:

* Andorra-Ceuta marcado LIVE en el minuto 90 cuando su inicio (17:00) todavia
  estaba en el futuro.
* Cadiz-Celta Fortuna marcado LIVE en el minuto 45 con inicio a las 19:00.
* Eibar-Tenerife y Sporting-Sabadell pendientes desde el dia anterior.

Ninguno de los dos primeros se cerraba con la regla antigua, que solo miraba
`kickoff + 120 minutos`: como el inicio aun no habia llegado, la ventana nunca
expiraba y el partido se quedaba en directo indefinidamente.
"""

import sqlite3
from datetime import datetime, timedelta

import pytest

from liga_maestros.services.live_state import (
    CLOSE_FINAL,
    CLOSE_NO_DATA,
    KEEP,
    PENDING_OVERDUE,
    RESET_TO_SCHEDULED,
    evaluate_match_state,
    minute_number,
)
from liga_maestros.services.payloads import matches as matches_payload

NOW = datetime(2026, 8, 16, 15, 30)


class TestEvaluateMatchState:
    def test_live_before_kickoff_is_impossible_and_resets(self):
        """Andorra-Ceuta: LIVE minuto 90 con inicio a las 17:00."""
        decision = evaluate_match_state("LIVE", datetime(2026, 8, 16, 17, 0), NOW, minute="90")

        assert decision["action"] == RESET_TO_SCHEDULED
        assert decision["reason"] == "live_antes_del_inicio"
        assert decision["status"] == "NS"

    def test_live_before_kickoff_closes_even_at_minute_45(self):
        """Cadiz-Celta Fortuna: LIVE minuto 45 con inicio a las 19:00."""
        decision = evaluate_match_state("LIVE", datetime(2026, 8, 16, 19, 0), NOW, minute="45")

        assert decision["action"] == RESET_TO_SCHEDULED

    def test_minute_ahead_of_real_clock_is_closed_without_inventing_result(self):
        """Empezo hace 10 minutos pero el proveedor emite el minuto 90."""
        decision = evaluate_match_state("LIVE", NOW - timedelta(minutes=10), NOW, minute="90")

        assert decision["action"] == CLOSE_NO_DATA
        assert decision["status"] == "STALE"

    def test_no_provider_update_for_thirty_minutes_closes_the_match(self):
        decision = evaluate_match_state(
            "LIVE",
            NOW - timedelta(minutes=60),
            NOW,
            last_update_at=NOW - timedelta(minutes=31),
            minute="55",
        )

        assert decision["action"] == CLOSE_NO_DATA
        assert decision["reason"] == "sin_actualizacion_30min"

    def test_recent_update_keeps_a_genuine_live_match_open(self):
        decision = evaluate_match_state(
            "LIVE",
            NOW - timedelta(minutes=60),
            NOW,
            last_update_at=NOW - timedelta(minutes=2),
            minute="55",
        )

        assert decision["action"] == KEEP

    def test_full_window_elapsed_finalises_the_match(self):
        decision = evaluate_match_state(
            "LIVE",
            NOW - timedelta(minutes=125),
            NOW,
            last_update_at=NOW - timedelta(minutes=1),
            minute="90",
        )

        assert decision["action"] == CLOSE_FINAL
        assert decision["status"] == "FT"

    def test_half_time_without_updates_is_also_closed(self):
        decision = evaluate_match_state(
            "HT",
            NOW - timedelta(minutes=60),
            NOW,
            last_update_at=NOW - timedelta(minutes=45),
            minute="HT",
        )

        assert decision["action"] == CLOSE_NO_DATA

    def test_missing_freshness_stamp_does_not_close_a_plausible_live_match(self):
        """Legacy rows have no updated_at: they must not be closed blindly."""
        decision = evaluate_match_state("LIVE", NOW - timedelta(minutes=30), NOW, minute="30")

        assert decision["action"] == KEEP

    def test_scheduled_match_from_yesterday_is_flagged_overdue(self):
        """Eibar-Tenerife y Sporting-Sabadell: pendientes del dia anterior."""
        decision = evaluate_match_state("NS", NOW - timedelta(hours=20), NOW)

        assert decision["action"] == PENDING_OVERDUE

    def test_upcoming_scheduled_match_is_left_alone(self):
        decision = evaluate_match_state("NS", NOW + timedelta(hours=2), NOW)

        assert decision["action"] == KEEP

    def test_finished_match_is_never_touched(self):
        assert evaluate_match_state("FT", NOW - timedelta(days=3), NOW)["action"] == KEEP

    def test_match_without_kickoff_relies_only_on_freshness(self):
        stale = evaluate_match_state("LIVE", None, NOW, last_update_at=NOW - timedelta(minutes=40))
        fresh = evaluate_match_state("LIVE", None, NOW, last_update_at=NOW - timedelta(minutes=3))

        assert stale["action"] == CLOSE_NO_DATA
        assert fresh["action"] == KEEP

    def test_timezone_aware_and_naive_datetimes_can_be_mixed(self):
        from zoneinfo import ZoneInfo

        aware_kickoff = datetime(2026, 8, 16, 17, 0, tzinfo=ZoneInfo("Europe/Madrid"))

        decision = evaluate_match_state("LIVE", aware_kickoff, NOW, minute="90")

        assert decision["action"] == RESET_TO_SCHEDULED

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [("90", 90), ("45+2", 45), ("90'", 90), ("HT", None), ("", None), (None, None), ("min. 67", 67)],
    )
    def test_minute_number_parses_provider_labels(self, raw, expected):
        assert minute_number(raw) == expected


class TestJornadaPayloadSelfHeals:
    """The page must not depend on the collector having run successfully."""

    def _conn(self, rows):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute(
            """
            CREATE TABLE resultados (
                jornada INTEGER, partido_id INTEGER, local TEXT, visitante TEXT,
                goles_local INTEGER, goles_visitante INTEGER, status TEXT,
                fecha TEXT, hora TEXT, minuto TEXT, updated_at TEXT
            )
            """
        )
        conn.executemany(
            "INSERT INTO resultados VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        conn.commit()
        return conn

    def _freeze(self, monkeypatch, now=NOW):
        monkeypatch.setattr(matches_payload, "madrid_now", lambda: now)
        monkeypatch.setattr(matches_payload, "today_madrid", lambda: now.strftime("%Y-%m-%d"))

    def test_live_match_with_future_kickoff_is_not_served_as_live(self, monkeypatch):
        self._freeze(monkeypatch)
        conn = self._conn(
            [(6, "Andorra", "Ceuta", 1, 0, "LIVE", "2026-08-16", "17:00", "90", None)],
        )

        partidos = matches_payload.build_jornada_matches(conn, 1, {})
        andorra = partidos[5]

        assert andorra["status"] == "NS"
        assert andorra["minuto_live"] == ""
        assert andorra["goles_local"] is None
        assert andorra["marcador"] == "17:00h"

    def test_frozen_live_match_is_marked_stale_keeping_its_score(self, monkeypatch):
        self._freeze(monkeypatch)
        conn = self._conn(
            [(7, "Cádiz", "Celta Fortuna", 2, 1, "LIVE", "2026-08-16", "14:30", "45", "2026-08-16T14:35:00")],
        )

        partidos = matches_payload.build_jornada_matches(conn, 1, {})
        cadiz = partidos[6]

        assert cadiz["status"] == "STALE"
        assert (cadiz["goles_local"], cadiz["goles_visitante"]) == (2, 1)
        assert cadiz["marcador"] == "2-1"
        assert cadiz["signo_actual"] == "1"

    def test_genuine_live_match_is_untouched(self, monkeypatch):
        self._freeze(monkeypatch)
        conn = self._conn(
            [(1, "Alavés", "Getafe", 1, 1, "LIVE", "2026-08-16", "14:45", "40", "2026-08-16T15:29:00")],
        )

        partidos = matches_payload.build_jornada_matches(conn, 1, {})

        assert partidos[0]["status"] == "LIVE"
        assert partidos[0]["minuto_live"] == "40"

    def test_yesterdays_unscored_match_keeps_its_fixture_date(self, monkeypatch):
        """Eibar-Tenerife del 15/08 muestra su fecha, nunca un placeholder opaco."""
        self._freeze(monkeypatch)
        conn = self._conn(
            [(10, "Eibar", "Tenerife", None, None, "NS", "2026-08-15", "21:30", "", None)],
        )

        partidos = matches_payload.build_jornada_matches(conn, 1, {})
        eibar = partidos[9]

        assert eibar["resultado_pendiente"] is False
        assert eibar["marcador"] == "sabado 15/08 21:30h"

    def test_todays_upcoming_match_still_shows_its_kickoff_time(self, monkeypatch):
        self._freeze(monkeypatch)
        conn = self._conn(
            [(5, "Celta", "Osasuna", None, None, "NS", "2026-08-16", "21:30", "", None)],
        )

        partidos = matches_payload.build_jornada_matches(conn, 1, {})

        assert partidos[4]["resultado_pendiente"] is False
        assert partidos[4]["marcador"] == "21:30h"

    def test_closed_provider_row_without_score_keeps_its_fixture_date(self, monkeypatch):
        """STALE/FT without goals must not leak a fake result label to the UI."""
        self._freeze(monkeypatch)
        conn = self._conn(
            [(10, "Eibar", "Tenerife", None, None, "STALE", "2026-08-15", "21:30", "Sin datos", None)],
        )

        partidos = matches_payload.build_jornada_matches(conn, 1, {})

        assert partidos[9]["marcador"] == "sabado 15/08 21:30h"
        assert "pendiente" not in partidos[9]["marcador"].lower()

    def test_legacy_database_without_updated_at_column_still_works(self, monkeypatch):
        self._freeze(monkeypatch)
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute(
            """
            CREATE TABLE resultados (
                jornada INTEGER, partido_id INTEGER, local TEXT, visitante TEXT,
                goles_local INTEGER, goles_visitante INTEGER, status TEXT,
                fecha TEXT, hora TEXT, minuto TEXT
            )
            """
        )
        conn.execute(
            "INSERT INTO resultados VALUES (1, 6, 'Andorra', 'Ceuta', 1, 0, 'LIVE', '2026-08-16', '17:00', '90')"
        )
        conn.commit()

        partidos = matches_payload.build_jornada_matches(conn, 1, {})

        assert partidos[5]["status"] == "NS"
