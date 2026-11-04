"""La Peña vota de verdad: del POST a ``votos_pena`` al consenso de la portada.

Cubre el recorrido que el rediseño de La Peña dejó a medias:

1. El blueprint ``pena`` está registrado (sin ``register_blueprint`` las rutas
   devolvían 404 y el voto se perdía en silencio).
2. El voto de una cuenta normal entra en la tabla nueva y baja de ahí al
   consenso que sirve ``/api/liga/data``.
3. Los boletos del seed siguen contando como votos de los peñistas históricos.
4. Un partido sin votos no hereda los porcentajes de otro ni el total global.
5. Los maestros y las columnas ocultas no son La Peña aunque su cuenta vote.
"""

import sqlite3
from datetime import timedelta

import pytest

import config
from liga_maestros import create_app
from liga_maestros.db import migrations
from liga_maestros.db.connection import get_db
from liga_maestros.routes import pena as pena_route
from liga_maestros.services.payloads.predictions import (
    _build_pena_consensus_from_preds,
    load_pena_votes,
)
from liga_maestros.services.ticket import madrid_now

JORNADA = 1
SIGNO = ["1"] * 14 + ["2-1"]


def _app(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "pena.db"))
    monkeypatch.setattr(config, "BOOTSTRAP_DB_PATH", str(tmp_path / "missing.db"))
    monkeypatch.setattr(config, "PRODUCTION_SEED_PATH", str(tmp_path / "missing-seed.json"))
    monkeypatch.setattr(config, "DB_BACKUP_DIR", str(tmp_path / "backups"))
    monkeypatch.setenv("SECRET_KEY", "pena-votos-test-secret")
    monkeypatch.setenv("WEB_COLLECTOR_ENABLED", "0")
    monkeypatch.setenv("DB_BACKUP_ENABLED", "0")
    monkeypatch.setenv("ALLOW_LOCAL_ADMIN", "0")
    monkeypatch.setenv("TRUSTED_HOSTS", "localhost,127.0.0.1")
    # Los tests votan varias veces seguidas; el cooldown anti-flood no es lo
    # que se comprueba aqui (tiene su propio test).
    monkeypatch.setattr(pena_route, "is_rate_limited", lambda *args, **kwargs: False)
    return create_app()


def _seed_jornada(app, jornada=JORNADA, kickoff_hours=8):
    """15 casillas NS con el saque en el futuro: la jornada sigue abierta."""
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


def _votar(client, user_id, signos=SIGNO, jornada=JORNADA):
    return client.post(
        "/api/pena/votar",
        json={"jornada": jornada, "signos": signos},
        headers={"X-CSRF-Token": f"csrf-{user_id}"},
    )


def _consenso_del_partido(payload, partido_id=1):
    if partido_id == 15:
        return {"total": 0}
    return next(item for item in payload["consenso_pena"] if item["id"] == partido_id)


def test_las_rutas_de_la_pena_estan_registradas(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch)
    client = app.test_client()
    # Sin sesion no hay voto, pero la ruta existe: nunca un 404.
    assert client.post("/api/pena/votar", json={}).status_code == 401
    assert client.get("/api/pena/mis-votos").status_code == 200
    assert client.get("/api/pena/consenso").status_code == 400
    assert client.get("/api/pena/consenso?j=1").status_code == 200


def test_el_voto_de_una_cuenta_llega_al_consenso_de_la_portada(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch)
    _seed_jornada(app)
    client = _client(app, "cuenta-real-1")

    # Foto del consenso del seed antes de votar.
    antes = app.test_client().get(f"/api/liga/data?j={JORNADA}").get_json()
    base = _consenso_del_partido(antes, 1)

    assert _votar(client, "cuenta-real-1").status_code == 200

    with app.app_context():
        conn = get_db()
        filas = conn.execute(
            "SELECT partido_id, signo FROM votos_pena WHERE user_id = ? AND jornada = ? ORDER BY partido_id",
            ("cuenta-real-1", JORNADA),
        ).fetchall()
    assert [(fila["partido_id"], fila["signo"]) for fila in filas] == [(i, "1") for i in range(1, 15)] + [(15, "2-1")]

    despues = app.test_client().get(f"/api/liga/data?j={JORNADA}").get_json()
    ahora = _consenso_del_partido(despues, 1)
    # El seed de la J1 trae a los peñistas historicos: el voto nuevo se SUMA
    # (antes del arreglo el consenso se leia solo de la tabla vacia).
    assert ahora["total"] == base["total"] + 1
    assert ahora["votes"]["1"] == base["votes"]["1"] + 1
    # El pleno no se cuela como voto de las 14 previas.
    assert _consenso_del_partido(despues, 15)["total"] == 0


def test_mis_votos_devuelve_el_boleto_guardado(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch)
    _seed_jornada(app)
    client = _client(app, "cuenta-real-2")
    assert _votar(client, "cuenta-real-2").status_code == 200

    payload = client.get(f"/api/pena/mis-votos?j={JORNADA}").get_json()
    assert payload["votos"] == SIGNO


def test_el_cooldown_anti_flood_corta_los_post_seguidos(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch)
    _seed_jornada(app)
    monkeypatch.setattr(pena_route, "is_rate_limited", lambda *args, **kwargs: True)

    respuesta = _votar(_client(app, "cuenta-real-9"), "cuenta-real-9")

    assert respuesta.status_code == 429
    with app.app_context():
        assert get_db().execute("SELECT COUNT(*) FROM votos_pena").fetchone()[0] == 0


def test_un_voto_a_medias_o_fuera_de_plazo_se_rechaza(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch)
    _seed_jornada(app)
    client = _client(app, "cuenta-real-3")

    incompleto = _votar(client, "cuenta-real-3", signos=["1"] + ["-"] * 14)
    assert incompleto.status_code == 400
    assert "Completa los 15" in incompleto.get_json()["message"]

    assert _votar(client, "cuenta-real-3", jornada="no-es-un-numero").status_code == 400
    assert _votar(client, "cuenta-real-3", jornada=99).status_code == 404


def test_un_partido_sin_votos_no_hereda_porcentajes_ni_el_total_global(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch)
    _seed_jornada(app)
    client = _client(app, "cuenta-real-4")
    with app.app_context():
        conn = get_db()
        # Solo el partido 1 y el pleno: los otros trece no tienen votos.
        conn.execute(
            "INSERT INTO votos_pena (user_id, jornada, partido_id, signo) VALUES (?, ?, 1, 'X')",
            ("cuenta-real-4", JORNADA),
        )
        conn.execute(
            "INSERT INTO votos_pena (user_id, jornada, partido_id, signo) VALUES (?, ?, 15, '1-0')",
            ("cuenta-real-4", JORNADA),
        )
        conn.commit()

    payload = client.get(f"/api/pena/consenso?j={JORNADA}").get_json()
    consenso = {item["id"]: item for item in payload["consenso"]}
    assert payload["total_votantes"] == 1
    assert consenso[1]["ganador"] == "X"
    assert (consenso[1]["p1"], consenso[1]["px"], consenso[1]["p2"]) == (0, 100, 0)
    # Antes: total=1 (global) con p1/px/p2 a cero, un consenso que nadie votó.
    assert consenso[2]["total"] == 0
    assert (consenso[2]["p1"], consenso[2]["px"], consenso[2]["p2"]) == (0, 0, 0)
    assert payload["pleno"] == {"1-0": 1}


def test_los_maestros_no_cuentan_como_la_pena(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch)
    _seed_jornada(app)
    client = _client(app, "claude")
    with app.app_context():
        conn = get_db()
        conn.execute(
            "INSERT INTO votos_pena (user_id, jornada, partido_id, signo) VALUES ('claude', ?, 1, '1')",
            (JORNADA,),
        )
        conn.commit()

    payload = client.get(f"/api/pena/consenso?j={JORNADA}").get_json()
    assert payload["total_votantes"] == 0
    assert all(item["total"] == 0 for item in payload["consenso"])


def test_el_voto_de_la_bd_pisa_el_boleto_del_seed_del_mismo_penista():
    contract = {"visible_ai_columns": [{"id": "claude"}], "hidden_ids": [], "pena_ids": ["chipi", "geli"]}
    preds = {
        "chipi": {"signos": ["1"] + ["-"] * 14},
        "geli": {"signos": ["2"] + ["-"] * 14},
    }
    votos = {"chipi": {1: "X"}}

    consenso = _build_pena_consensus_from_preds(preds, contract, votos)[0]

    assert consenso["votes"] == {"1": 0.0, "X": 1.0, "2": 1.0}
    assert consenso["total"] == 2
    assert (consenso["p1"], consenso["px"], consenso["p2"]) == (0, 50, 50)
    # Empate real: no se inventa un ganador.
    assert consenso["ganador"] == "-"


def test_load_pena_votes_aguanta_una_bd_sin_la_migracion_6():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    try:
        assert load_pena_votes(conn, 1) == {}
    finally:
        conn.close()


def test_la_migracion_6_crea_la_tabla_y_es_idempotente():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    try:
        migrations.ensure_votos_pena_table(conn)
        migrations.ensure_votos_pena_table(conn)
        columnas = {row["name"] for row in conn.execute("PRAGMA table_info(votos_pena)")}
        assert {"user_id", "jornada", "partido_id", "signo", "created_at", "updated_at"} <= columnas
        indices = {row["name"] for row in conn.execute("PRAGMA index_list(votos_pena)")}
        assert {"idx_votos_pena_jornada", "idx_votos_pena_user"} <= indices
    finally:
        conn.close()


@pytest.mark.parametrize("signo", ["1", "X", "2", "1X", "X2", "12"])
def test_los_dobles_y_triples_del_seed_siguen_repartiendo_el_voto(signo):
    contract = {"visible_ai_columns": [], "hidden_ids": [], "pena_ids": ["chipi"]}
    preds = {"chipi": {"signos": [signo] + ["-"] * 14}}

    primero = _build_pena_consensus_from_preds(preds, contract)[0]

    assert primero["total"] == 1
    assert sum(primero["votes"].values()) == 1
