import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

os.environ.setdefault("SECRET_KEY", "test-secret-key")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from liga_maestros.db.connection import ClosingConnection
from liga_maestros.db.migrations import ensure_quiz_tables
from liga_maestros.routes.snake import _expected_arcade_score, _validate_arcade_score
from liga_maestros.services import quiz as quiz_service


def test_snake_rejects_big_score_without_arcade_telemetry():
    assert _validate_arcade_score(99999, {}) is False


def test_snake_rejects_score_that_does_not_match_eaten_count():
    assert _validate_arcade_score(999, {"eaten": 3, "duration_ms": 5000}) is False


def test_snake_rejects_impossible_short_duration():
    score = _expected_arcade_score(10)
    assert _validate_arcade_score(score, {"eaten": 10, "duration_ms": 1000}) is False


def test_snake_accepts_plausible_arcade_run():
    score = _expected_arcade_score(10)
    assert _validate_arcade_score(score, {"eaten": 10, "duration_ms": 12000}) is True


def _quiz_conn():
    conn = sqlite3.connect(":memory:", factory=ClosingConnection)
    conn.row_factory = sqlite3.Row
    ensure_quiz_tables(conn)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rows = [
        (72, "multiple", f"Pregunta {idx}", "A", "B", "C", "A", "", 1, "test", 1, now)
        for idx in range(1, 4)
    ]
    conn.executemany("""
        INSERT INTO quiz_preguntas
        (jornada, tipo, enunciado, opcion_a, opcion_b, opcion_c, respuesta_correcta, explicacion, dificultad, tema, activa, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, rows)
    conn.commit()
    return conn


def _submit_with_conn(monkeypatch, respuestas):
    conn = _quiz_conn()
    monkeypatch.setattr(quiz_service, "get_db", lambda: conn)
    return quiz_service.submit_quiz_respuestas(
        jornada=72,
        user_id="u1",
        nombre="Pablo",
        respuestas=respuestas,
        tiempo_total_ms=45000,
        expected_question_ids=[1, 2, 3],
    )


def test_quiz_rejects_incomplete_answers(monkeypatch):
    result = _submit_with_conn(monkeypatch, [{"pregunta_id": 1, "respuesta": "A"}])
    assert "exactamente" in result["error"]


def test_quiz_rejects_duplicate_answers(monkeypatch):
    result = _submit_with_conn(monkeypatch, [
        {"pregunta_id": 1, "respuesta": "A"},
        {"pregunta_id": 1, "respuesta": "A"},
        {"pregunta_id": 2, "respuesta": "A"},
    ])
    assert "duplicadas" in result["error"]


def test_quiz_rejects_invalid_option(monkeypatch):
    result = _submit_with_conn(monkeypatch, [
        {"pregunta_id": 1, "respuesta": "A"},
        {"pregunta_id": 2, "respuesta": "D"},
        {"pregunta_id": 3, "respuesta": "A"},
    ])
    assert "invalida" in result["error"]


def test_quiz_rejects_other_question_ids(monkeypatch):
    result = _submit_with_conn(monkeypatch, [
        {"pregunta_id": 1, "respuesta": "A"},
        {"pregunta_id": 2, "respuesta": "A"},
        {"pregunta_id": 99, "respuesta": "A"},
    ])
    assert "corresponden" in result["error"]
