"""La linea publica de MrPurple se escribe con el guardado del admin.

El brief de la J17 exige que la columna MrPurple se vea sin login y que, si
Pablo edita su boleto «Tu», la copia publica se actualice con el mismo guardado.
Este modulo cubre las cuatro reglas que protegen ese espejo:

1. Un guardado del admin crea/actualiza la fila ``mrpurple`` en la misma
   transaccion.
2. Un guardado de un usuario no admin no crea ni toca filas ``mrpurple``.
3. La importacion editorial del arranque no pisa un espejo ya guardado.
4. Un guardado directo con ``user_id = "mrpurple"`` de un no admin se rechaza.
"""

import json
import sqlite3
from datetime import timedelta

import pytest

import config
from liga_maestros import create_app
from liga_maestros.db import migrations
from liga_maestros.db.connection import get_db
from liga_maestros.routes import predictions as predictions_route
from liga_maestros.services.payloads.matches import build_jornada_matches
from liga_maestros.services.payloads.simple_view import build_simple_view_payload
from liga_maestros.services.teams import build_participant_contract
from liga_maestros.services.ticket import madrid_now

JORNADA = 1
VALID_SIGNS = ["1", "X", "2", "1", "X", "2", "1", "X", "2", "1", "X", "2", "1", "X", "1-0"]
OTRA_LINEA = ["2", "2", "1", "X", "1", "1", "2", "2", "1", "1", "2", "2", "1", "1", "2-1"]
ADMIN_ID = "admin-account-1"


def _app(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "mrpurple.db"))
    monkeypatch.setattr(config, "BOOTSTRAP_DB_PATH", str(tmp_path / "missing.db"))
    monkeypatch.setattr(config, "PRODUCTION_SEED_PATH", str(tmp_path / "missing-seed.json"))
    monkeypatch.setattr(config, "DB_BACKUP_DIR", str(tmp_path / "backups"))
    monkeypatch.setenv("SECRET_KEY", "mrpurple-publico-test-secret")
    monkeypatch.setenv("WEB_COLLECTOR_ENABLED", "0")
    monkeypatch.setenv("DB_BACKUP_ENABLED", "0")
    monkeypatch.setenv("ALLOW_LOCAL_ADMIN", "0")
    monkeypatch.setenv("TRUSTED_HOSTS", "localhost,127.0.0.1")
    # Los tests guardan varias veces seguidas; el cooldown anti-flood no es lo
    # que se esta verificando aqui.
    monkeypatch.setattr(predictions_route, "is_rate_limited", lambda *args, **kwargs: False)
    return create_app()


def _seed(app, jornada=JORNADA, kickoff_hours=8):
    """15 partidos NS con el saque en el futuro: la jornada sigue abierta."""
    kickoff = madrid_now() + timedelta(hours=kickoff_hours)
    with app.app_context():
        conn = get_db()
        conn.execute("DELETE FROM resultados WHERE jornada = ?", (jornada,))
        for partido_id in range(1, 16):
            conn.execute(
                """
                INSERT INTO resultados
                    (jornada, partido_id, local, visitante, goles_local, goles_visitante,
                     status, fecha, hora, minuto, signo_actual)
                VALUES (?, ?, ?, ?, NULL, NULL, 'NS', ?, ?, '', '-')
                """,
                (
                    jornada,
                    partido_id,
                    f"Local {partido_id}",
                    f"Visitante {partido_id}",
                    kickoff.strftime("%Y-%m-%d"),
                    kickoff.strftime("%H:%M"),
                ),
            )
        conn.commit()


def _client(app, user_id, *, is_admin=False):
    client = app.test_client()
    with client.session_transaction() as sesion:
        sesion["user"] = {"id": user_id, "name": f"User {user_id}", "is_admin": is_admin}
        sesion["csrf_token"] = f"csrf-{user_id}"
    return client


def _guardar(client, user_id, signos, jornada=JORNADA):
    return client.post(
        "/api/predicciones/save",
        json={"user_id": user_id, "jornada": jornada, "signos": signos},
        headers={"X-CSRF-Token": f"csrf-{user_id}"},
    )


def _filas_mrpurple(conn, jornada=JORNADA):
    filas = conn.execute(
        "SELECT partido_id, signo FROM predicciones WHERE user_id = 'mrpurple' AND jornada = ? ORDER BY partido_id",
        (jornada,),
    ).fetchall()
    return [fila["signo"] for fila in filas]


def test_el_guardado_del_admin_crea_y_actualiza_el_espejo(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch)
    _seed(app)
    client = _client(app, ADMIN_ID, is_admin=True)

    respuesta = _guardar(client, ADMIN_ID, VALID_SIGNS)
    assert respuesta.status_code == 200

    with app.app_context():
        conn = get_db()
        assert _filas_mrpurple(conn) == VALID_SIGNS
        # La linea del admin sigue guardada bajo su id privado: el espejo es una
        # copia publica, no sustituye su boleto.
        propias = conn.execute(
            "SELECT signo FROM predicciones WHERE user_id = ? AND jornada = ? ORDER BY partido_id",
            (ADMIN_ID, JORNADA),
        ).fetchall()
        assert [fila["signo"] for fila in propias] == VALID_SIGNS

        # Y la vista anonima ya publica la linea nueva, sin sesion.
        payload = build_simple_view_payload(
            conn,
            JORNADA,
            build_jornada_matches(conn, str(JORNADA), {}),
            build_participant_contract(),
            max_jornada=JORNADA,
        )
        assert payload["columns"][0]["id"] == "mrpurple"
        assert payload["columns"][0]["sin_linea"] is False
        assert payload["columns"][0]["es_mia"] is False
        assert [row["picks"]["mrpurple"]["signo"] for row in payload["rows"]] == VALID_SIGNS

        # Con su sesion, Pablo sigue viendo la columna como suya, pero su id de
        # cuenta no viaja en el payload.
        payload_con_sesion = build_simple_view_payload(
            conn,
            JORNADA,
            build_jornada_matches(conn, str(JORNADA), {}),
            build_participant_contract(),
            max_jornada=JORNADA,
            current_user_id=ADMIN_ID,
        )
        assert payload_con_sesion["columns"][0]["es_mia"] is True
        assert [row["picks"]["mrpurple"]["signo"] for row in payload_con_sesion["rows"]] == VALID_SIGNS
        assert ADMIN_ID not in json.dumps(payload_con_sesion)

    # Un segundo guardado reemplaza la linea: no quedan filas de la anterior.
    respuesta = _guardar(client, ADMIN_ID, OTRA_LINEA)
    assert respuesta.status_code == 200
    with app.app_context():
        conn = get_db()
        assert _filas_mrpurple(conn) == OTRA_LINEA
        total = conn.execute(
            "SELECT COUNT(*) FROM predicciones WHERE user_id = 'mrpurple' AND jornada = ?",
            (JORNADA,),
        ).fetchone()[0]
        assert total == 15


def test_el_guardado_de_un_no_admin_no_toca_el_espejo(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch)
    _seed(app)
    with app.app_context():
        conn = get_db()
        conn.executemany(
            "INSERT OR REPLACE INTO predicciones (user_id, jornada, partido_id, signo) VALUES ('mrpurple', ?, ?, ?)",
            [(JORNADA, partido_id, signo) for partido_id, signo in enumerate(OTRA_LINEA, start=1)],
        )
        conn.commit()

    client = _client(app, "usuario-normal")
    respuesta = _guardar(client, "usuario-normal", VALID_SIGNS)
    assert respuesta.status_code == 200

    with app.app_context():
        conn = get_db()
        assert _filas_mrpurple(conn) == OTRA_LINEA


def test_la_importacion_editorial_no_pisa_un_espejo_existente():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    migrations.ensure_core_tables(conn)
    migrations.ensure_predicciones_unique_index(conn)

    conn.executemany(
        "INSERT OR REPLACE INTO predicciones (user_id, jornada, partido_id, signo) VALUES ('mrpurple', 17, ?, ?)",
        [(partido_id, signo) for partido_id, signo in enumerate(OTRA_LINEA, start=1)],
    )
    conn.commit()

    migrations._import_inline_prediction_tickets(conn, 17, migrations.J17_EDITORIAL_TICKETS)

    assert _filas_mrpurple(conn, 17) == OTRA_LINEA
    # Los demas boletos editoriales se importan igual que siempre.
    for uid in ("programa", "tecnotron", "grok", "sonia"):
        assert (
            conn.execute("SELECT COUNT(*) FROM predicciones WHERE user_id = ? AND jornada = 17", (uid,)).fetchone()[0]
            == 15
        )


def test_un_no_admin_no_puede_guardar_el_id_reservado(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch)
    _seed(app)
    client = _client(app, "mrpurple", is_admin=False)

    respuesta = _guardar(client, "mrpurple", VALID_SIGNS)
    assert respuesta.status_code == 403

    with app.app_context():
        conn = get_db()
        assert _filas_mrpurple(conn) == []


@pytest.mark.parametrize("signos", [VALID_SIGNS, OTRA_LINEA])
def test_el_espejo_solo_lo_escribe_el_admin(tmp_path, monkeypatch, signos):
    """El mismo POST cambia de resultado segun la sesion, no segun el payload."""
    app = _app(tmp_path, monkeypatch)
    _seed(app)

    no_admin = _client(app, "no-admin")
    assert _guardar(no_admin, "no-admin", signos).status_code == 200
    with app.app_context():
        assert _filas_mrpurple(get_db()) == []

    admin = _client(app, ADMIN_ID, is_admin=True)
    assert _guardar(admin, ADMIN_ID, signos).status_code == 200
    with app.app_context():
        assert _filas_mrpurple(get_db()) == signos
