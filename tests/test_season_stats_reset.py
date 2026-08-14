"""Regresión: las estadísticas arrancan de cero con la temporada 2026/27.

El periodo de pruebas (jornadas 51-76) se conserva en la BD como archivo,
pero no debe alimentar rankings, perfiles, rachas ni rankings de quiz. Solo
cuentan las jornadas de la temporada publicada (J1 en adelante).
"""

import sqlite3

import config
from liga_maestros import create_app
from liga_maestros.db.migrations import ensure_core_tables, ensure_porra_table, ensure_quiz_tables
from liga_maestros.services import contest as contest_service
from liga_maestros.services.engagement import build_post_jornada_summary, compute_quiniela_streak
from liga_maestros.services.jornada import current_season_sql, is_current_season_jornada
from liga_maestros.services.payloads.predictions import _build_ranking
from liga_maestros.services.quiz import get_quiz_ranking_temporada

LEGACY_JORNADA = 75  # periodo de pruebas
CURRENT_JORNADA = 1  # temporada publicada 2026/27


def _make_db(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "season.db"))
    monkeypatch.setattr(config, "BOOTSTRAP_DB_PATH", str(tmp_path / "missing.db"))
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    ensure_core_tables(conn)
    ensure_quiz_tables(conn)
    ensure_porra_table(conn)
    conn.execute("INSERT INTO usuarios (id, nombre, puntos_acumulados) VALUES ('mrpurple', 'MrPurple', 14)")
    for partido_id in range(1, 16):
        # Jornada de pruebas: todos los partidos puntuados y acertados.
        conn.execute(
            """
            INSERT INTO resultados
                (jornada, partido_id, local, visitante, goles_local, goles_visitante,
                 status, fecha, hora, minuto, signo_actual)
            VALUES (?, ?, 'Local', 'Visitante', 1, 0, 'FT', '2026-07-25', '18:00', 'FT', '1')
            """,
            (LEGACY_JORNADA, partido_id),
        )
        conn.execute(
            "INSERT INTO predicciones (user_id, jornada, partido_id, signo) VALUES ('mrpurple', ?, ?, '1')",
            (LEGACY_JORNADA, partido_id),
        )
        # Jornada 1 de la temporada: solo dos partidos puntuados.
        status = "FT" if partido_id <= 2 else "NS"
        signo_actual = "1" if partido_id <= 2 else "-"
        goles = (1, 0) if partido_id <= 2 else (None, None)
        conn.execute(
            """
            INSERT INTO resultados
                (jornada, partido_id, local, visitante, goles_local, goles_visitante,
                 status, fecha, hora, minuto, signo_actual)
            VALUES (?, ?, 'Local', 'Visitante', ?, ?, ?, '2026-08-16', '18:00', '', ?)
            """,
            (CURRENT_JORNADA, partido_id, goles[0], goles[1], status, signo_actual),
        )
        conn.execute(
            "INSERT INTO predicciones (user_id, jornada, partido_id, signo) VALUES ('mrpurple', ?, ?, '1')",
            (CURRENT_JORNADA, partido_id),
        )
    # Bonus de porra: 2 puntos en pruebas y 2 en la temporada actual.
    conn.execute(
        "INSERT INTO porra_puntos (jornada, partido_id, user_id, puntos) VALUES (?, 1, 'mrpurple', 5)",
        (LEGACY_JORNADA,),
    )
    conn.execute(
        "INSERT INTO porra_puntos (jornada, partido_id, user_id, puntos) VALUES (?, 3, 'mrpurple', 2)",
        (CURRENT_JORNADA,),
    )
    conn.commit()
    conn.close()
    contest_service._contest_payload_cache.clear()
    return config.DB_PATH


def test_season_window_helper():
    assert is_current_season_jornada(1)
    assert is_current_season_jornada("38")
    assert not is_current_season_jornada(75)
    assert not is_current_season_jornada("abc")
    assert current_season_sql("p.jornada") == "p.jornada BETWEEN 1 AND 42"


def test_contest_payload_ignores_test_jornadas(tmp_path, monkeypatch):
    _make_db(tmp_path, monkeypatch)

    payload = contest_service.build_contest_payload(None, "mrpurple")

    general = {row["id"]: row for row in payload["general"]}
    # 2 aciertos de la J1 + 2 puntos de porra de temporada; ni los 15 aciertos
    # de pruebas ni el bonus de pruebas cuentan.
    assert general["mrpurple"]["points"] == 4
    assert general["mrpurple"]["played"] == 1

    profile = payload["profile"]
    assert profile["hits"] == 2
    assert profile["predictions"] == 2
    assert profile["bonus"] == 2
    assert [row["jornada"] for row in profile["results"]] == [CURRENT_JORNADA]
    assert all(j == CURRENT_JORNADA for j in payload["jornada"]["jornadas"])
    contest_service._contest_payload_cache.clear()


def test_streak_ignores_test_jornadas(tmp_path, monkeypatch):
    _make_db(tmp_path, monkeypatch)
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row

    streak = compute_quiniela_streak(conn, "mrpurple")

    assert streak["jornadas_jugadas"] == 1
    assert streak["ultima_jornada"] == CURRENT_JORNADA
    conn.close()


def test_post_jornada_summary_uses_current_season(tmp_path, monkeypatch):
    _make_db(tmp_path, monkeypatch)
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row

    summary = build_post_jornada_summary(conn, "mrpurple")

    assert summary is not None
    assert summary["jornada"] == CURRENT_JORNADA
    assert summary["human_hits"] == 2
    conn.close()


def test_predictions_ranking_ignores_test_jornadas(tmp_path, monkeypatch):
    _make_db(tmp_path, monkeypatch)
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row

    ranking = _build_ranking(conn, CURRENT_JORNADA)

    assert ranking["mrpurple"]["total"] == 4  # 2 aciertos J1 + 2 de porra actual
    assert ranking["mrpurple"]["bonus"] == 2
    assert ranking["mrpurple"]["jornada_final"] == 2
    conn.close()


def test_quiz_ranking_temporada_ignores_test_jornadas(tmp_path, monkeypatch):
    _make_db(tmp_path, monkeypatch)
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        INSERT INTO quiz_participaciones
            (jornada, user_id, nombre, respuestas, aciertos, total_preguntas, puntos, created_at)
        VALUES (72, 'mrpurple', 'MrPurple', '[]', 9, 10, 10, '2026-07-20 10:00:00')
        """
    )
    conn.execute(
        """
        INSERT INTO quiz_participaciones
            (jornada, user_id, nombre, respuestas, aciertos, total_preguntas, puntos, created_at)
        VALUES (1, 'mrpurple', 'MrPurple', '[]', 5, 10, 6, '2026-08-14 10:00:00')
        """
    )
    conn.commit()
    conn.close()

    ranking = get_quiz_ranking_temporada()

    assert len(ranking) == 1
    assert ranking[0]["puntos_totales"] == 6
    assert ranking[0]["jornadas_participadas"] == 1


def _test_app(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PRODUCTION_SEED_PATH", str(tmp_path / "missing-seed.json"))
    monkeypatch.setattr(config, "FIXTURE_CORRECTIONS_PATH", str(tmp_path / "missing-fixtures.json"))
    monkeypatch.setattr(config, "DB_BACKUP_DIR", str(tmp_path / "backups"))
    monkeypatch.setenv("SECRET_KEY", "season-test-secret")
    monkeypatch.setenv("WEB_COLLECTOR_ENABLED", "0")
    monkeypatch.setenv("DB_BACKUP_ENABLED", "0")
    monkeypatch.setenv("ALLOW_LOCAL_ADMIN", "0")
    return create_app()


def test_user_stats_endpoint_counts_only_current_season(tmp_path, monkeypatch):
    _make_db(tmp_path, monkeypatch)
    app = _test_app(tmp_path, monkeypatch)
    contest_service._contest_payload_cache.clear()

    with app.test_client() as client:
        with client.session_transaction() as flask_session:
            flask_session["user"] = {"id": "mrpurple", "name": "MrPurple"}
        response = client.get("/api/user/stats?uid=mrpurple")

    assert response.status_code == 200
    data = response.get_json()
    assert data["total_aciertos"] == 2
    assert data["mejor_jornada"] == 2
    assert data["jornadas_jugadas"] == 1
    assert data["ultima_jornada"] == CURRENT_JORNADA
    contest_service._contest_payload_cache.clear()
