"""Integridad del boleto: nada de esto puede fallar en silencio.

Los cinco primeros tests cubren fallos que costaban el trabajo del usuario sin
darle ningun aviso:

1. El front dejaba firmar y el backend respondia 403 (o al reves), y los 15
   signos se perdian. El motivo era que el "esta cerrada?" se respondia con dos
   listas de estados distintas en dos ficheros.
2. Dos guardados concurrentes pasaban los dos el control de cierre y el segundo
   borraba los signos del primero: el cierre se comprobaba antes de tomar el
   lock de escritura.
3. `/api/liga/data` llevaba `Cache-Control: public` siendo un payload por
   usuario. Un CDN o un proxy compartido podia servir el boleto de A a B.
4. El ranking puntuaba contra la columna cruda `signo_actual` mientras el front
   recalculaba el signo desde los goles. Con el collector dejando `'-'` y el
   marcador puesto, la pantalla marcaba acierto y el ranking sumaba 0.
5. La Peña solo contaba partidos finalizados y el TICKET contaba tambien los
   que estaban en juego: el mismo usuario veia dos numeros distintos.

El caso 1 resulto ser mas grave de lo que decia la auditoria: no solo la lista de
estados estaba corta, es que el bloqueo miraba el partido ya "autorreparado" por
la pantalla mientras el guardado leia la tabla cruda. Con un collector caido
(estado vivo y saque aun por llegar) la pagina ofrecia los 15 selectores y el
POST devolvia 403: quiniela perdida sin aviso. El test que lo cubre compara las
dos respuestas de la misma app, no dos listas escritas a mano.
"""

import shutil
import subprocess
from datetime import timedelta
from pathlib import Path

import pytest

import config
from liga_maestros import create_app
from liga_maestros.db.connection import get_db
from liga_maestros.routes import predictions as predictions_route
from liga_maestros.services import contest as contest_service
from liga_maestros.services.payloads.predictions import build_predictions_payload
from liga_maestros.services.teams import is_live_scored_status, is_scored_status
from liga_maestros.services.ticket import madrid_now

RAIZ = Path(__file__).resolve().parents[1]
JORNADA = 1
VALID_SIGNS = ["1", "X", "2", "1", "X", "2", "1", "X", "2", "1", "X", "2", "1", "X", "1-0"]

# Todos los estados que el guardado considera "ya no se puede cambiar". La lista
# esta duplicada a proposito en el test: si alguien la cambia en el codigo sin
# actualizar el frontend, este test falla.
ESTADOS_CERRADOS = ["FT", "FINISHED", "TERMINADO", "LIVE", "IN PLAY", "HT", "HALF TIME BREAK", "EN JUEGO"]


def _app(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "integridad.db"))
    monkeypatch.setattr(config, "BOOTSTRAP_DB_PATH", str(tmp_path / "missing.db"))
    monkeypatch.setattr(config, "PRODUCTION_SEED_PATH", str(tmp_path / "missing-seed.json"))
    monkeypatch.setattr(config, "DB_BACKUP_DIR", str(tmp_path / "backups"))
    monkeypatch.setenv("SECRET_KEY", "integridad-test-secret")
    monkeypatch.setenv("WEB_COLLECTOR_ENABLED", "0")
    monkeypatch.setenv("DB_BACKUP_ENABLED", "0")
    monkeypatch.setenv("ALLOW_LOCAL_ADMIN", "0")
    monkeypatch.setenv("TRUSTED_HOSTS", "localhost,127.0.0.1")
    return create_app()


def _seed(app, estados, *, goles=None, jornada=JORNADA, kickoff_hours=-2):
    """15 partidos con los estados indicados.

    El saque va en el pasado por defecto: el read-path resetea a NS un LIVE cuyo
    saque aun no ha llegado (un collector caido no debe dejar partidos fantasma en
    vivo), asi que un LIVE con saque futuro se veria como NS y el test pasaria por
    el motivo equivocado.
    """
    kickoff = madrid_now() + timedelta(hours=kickoff_hours)
    minuto = "45" if kickoff_hours < 0 else ""
    with app.app_context():
        conn = get_db()
        conn.execute("DELETE FROM resultados WHERE jornada = ?", (jornada,))
        for partido_id in range(1, 16):
            estado = estados[partido_id - 1]
            gh, ga = (goles or {}).get(partido_id, (None, None))
            conn.execute(
                """
                INSERT INTO resultados
                    (jornada, partido_id, local, visitante, goles_local, goles_visitante,
                     status, fecha, hora, minuto, signo_actual)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    jornada,
                    partido_id,
                    f"Local {partido_id}",
                    f"Visitante {partido_id}",
                    gh,
                    ga,
                    estado,
                    kickoff.strftime("%Y-%m-%d"),
                    kickoff.strftime("%H:%M"),
                    minuto if gh is not None else "",
                    "-" if gh is None and ga is None else "",
                ),
            )
        conn.commit()


def _client(app, user_id):
    client = app.test_client()
    with client.session_transaction() as sesion:
        sesion["user"] = {"id": user_id, "name": f"User {user_id}", "is_admin": False}
        sesion["csrf_token"] = f"csrf-{user_id}"
    return client


# ── 1. El cierre se decide igual en el front y en el guardado ────────────────


@pytest.mark.parametrize("estado", ESTADOS_CERRADOS)
def test_todo_estado_de_juego_en_juego_bloquea_el_boleto(tmp_path, monkeypatch, estado):
    """El defecto: `_is_ticket_locked` comparaba contra `("LIVE","FT","FINISHED")`
    a mano, mientras el guardado usa `is_scored_status`/`is_live_scored_status`,
    que reconocen mas estados. Con un partido en IN PLAY o HT el selector de
    signos quedaba editable y el POST devolvia 403: el usuario perdia la
    quiniela entera sin saber por que.

    El saque va en el futuro a proposito. Si fuera en el pasado, el reloj habria
    cerrado el boleto igual y el test pasaria sin haber mirado el estado: verde
    falso. Asi el unico cierre posible es el del estado."""
    app = _app(tmp_path, monkeypatch)
    _seed(app, [estado] + ["NS"] * 14, kickoff_hours=8)

    client = _client(app, "u1")
    respuesta = client.get("/api/liga/data?jornada=1")
    assert respuesta.status_code == 200
    assert respuesta.get_json()["is_locked"] is True, (
        f"con un partido en {estado} la quiniela esta cerrada, pero la pagina la "
        "ofrece editable y el guardado la rechazara"
    )


def test_la_pantalla_y_el_guardado_no_se_pueden_desacordar(tmp_path, monkeypatch):
    """El contrato, verificado partido a partido en vez de estado a estado:

    para cada estado, lo que la pantalla ofrece y lo que el guardado acepta tienen
    que decir lo mismo. Es el test que habría detectado el bug de raíz, porque
    compara las dos respuestas de la misma app en lugar de dos listas escritas a
    mano."""
    for indice, estado in enumerate([*ESTADOS_CERRADOS, "NS"]):
        app = _app(tmp_path, monkeypatch)
        _seed(app, [estado] + ["NS"] * 14, kickoff_hours=8)
        # Usuario distinto en cada vuelta: el guardado tiene un rate-limit
        # anti-flood por usuario y sin esto la segunda iteracion lee
        # "Espera unos segundos" en vez del veredicto real del cierre.
        client = _client(app, f"u{indice}")

        bloqueado = client.get("/api/liga/data?jornada=1").get_json()["is_locked"]
        guardado = client.post(
            "/api/predicciones/save",
            json={"user_id": f"u{indice}", "jornada": JORNADA, "signos": VALID_SIGNS},
            headers={"X-CSRF-Token": f"csrf-u{indice}"},
        )
        acepta = guardado.status_code == 200
        assert bloqueado != acepta, (
            f"con el partido 1 en {estado} la pantalla dice bloqueado={bloqueado} "
            f"pero el guardado {'acepta' if acepta else 'rechaza'}: "
            f"el usuario firmaria de mas o perderia la quiniela. "
            f"Respuesta del guardado: {guardado.get_json()}"
        )


@pytest.mark.parametrize("estado", ESTADOS_CERRADOS)
def test_los_mismos_estados_rechazan_el_guardado(tmp_path, monkeypatch, estado):
    """La otra mitad del contrato: lo que el front enseña bloqueado tiene que
    ser exactamente lo que el guardado rechaza."""
    app = _app(tmp_path, monkeypatch)
    _seed(app, [estado] + ["NS"] * 14)

    client = _client(app, "u1")
    respuesta = client.post(
        "/api/predicciones/save",
        json={"user_id": "u1", "jornada": JORNADA, "signos": VALID_SIGNS},
        headers={"X-CSRF-Token": "csrf-u1"},
    )
    assert respuesta.status_code == 403
    assert respuesta.get_json()["status"] == "error"


def test_una_jornada_sin_juego_sigue_abierta(tmp_path, monkeypatch):
    """El otro extremo: si el test anterior pasara por un `return True` sin mirar
    los partidos, este lo detecta."""
    app = _app(tmp_path, monkeypatch)
    _seed(app, ["NS"] * 15, kickoff_hours=8)

    client = _client(app, "u1")
    assert client.get("/api/liga/data?jornada=1").get_json()["is_locked"] is False
    respuesta = client.post(
        "/api/predicciones/save",
        json={"user_id": "u1", "jornada": JORNADA, "signos": VALID_SIGNS},
        headers={"X-CSRF-Token": "csrf-u1"},
    )
    assert respuesta.status_code == 200


def test_los_estados_de_la_lista_coinciden_con_los_predicados_compartidos():
    """Si alguien anade un estado a `is_scored_status` y olvida la lista del
    front, este test lo dice en la CI y no en produccion."""
    for estado in ESTADOS_CERRADOS:
        assert is_scored_status(estado) or is_live_scored_status(estado), (
            f"{estado} esta en ESTADOS_CERRADOS pero los predicados compartidos no lo "
            "reconocen: el front lo daria por editable"
        )


# ── 2. El cierre se comprueba DENTRO de la transaccion ──────────────────────


def test_el_cierre_se_vuelve_a_comprobar_dentro_de_la_transaccion(tmp_path, monkeypatch):
    """La carrera: se comprobaba el cierre, y despues se tomaba el lock para
    escribir. Entre medias otro guardado (o el collector) podia cerrar la
    jornada, y el segundo POST se comia los signos del primero.

    Se fuerza esa ventana sin hilos: el primer chequeo (el rapido, de fuera) dice
    "abierta" y el segundo (bajo el lock) dice "cerrada", que es exactamente lo
    que ocurre si la jornada se cierra entre ambos."""
    app = _app(tmp_path, monkeypatch)
    _seed(app, ["NS"] * 15, kickoff_hours=8)

    llamadas = []
    original = predictions_route._motivo_de_cierre

    def que_se_cierra_entre_medias(filas, close_at):
        llamadas.append(len(filas))
        if len(llamadas) == 1:
            return None  # fuera de la transaccion: aun abierta
        return "La quiniela ya esta cerrada: empezo el primer partido."

    monkeypatch.setattr(predictions_route, "_motivo_de_cierre", que_se_cierra_entre_medias)

    client = _client(app, "u1")
    respuesta = client.post(
        "/api/predicciones/save",
        json={"user_id": "u1", "jornada": JORNADA, "signos": VALID_SIGNS},
        headers={"X-CSRF-Token": "csrf-u1"},
    )

    assert len(llamadas) == 2, "el cierre solo se comprobo una vez: hay ventana de carrera"
    assert respuesta.status_code == 403, (
        "la jornada se cerro entre el chequeo y la escritura, asi que el guardado "
        "debia rechazarse en vez de pisar lo que hubiera"
    )
    assert original is not None  # sanity: la funcion original existe


def test_el_guardado_correcto_no_se_rompe(tmp_path, monkeypatch):
    """Con la jornada abierta de verdad, guardar sigue funcionando: el segundo
    chequeo tiene que dejar pasar los signos."""
    app = _app(tmp_path, monkeypatch)
    _seed(app, ["NS"] * 15, kickoff_hours=8)

    client = _client(app, "u1")
    respuesta = client.post(
        "/api/predicciones/save",
        json={"user_id": "u1", "jornada": JORNADA, "signos": VALID_SIGNS},
        headers={"X-CSRF-Token": "csrf-u1"},
    )
    assert respuesta.status_code == 200
    assert respuesta.get_json()["signos"] == VALID_SIGNS


# ── 3. El payload por usuario no puede cachearse en compartido ──────────────


# ── 4. El ranking puntua lo mismo que pinta la pantalla ─────────────────────


def test_el_ranking_puntua_aunque_el_collector_dejara_el_signo_vacio(tmp_path, monkeypatch):
    """`payloads/matches.py` calcula el signo desde los goles siempre que los
    haya. El ranking leia la columna cruda y, si el collector dejaba `'-'` con el
    marcador ya puesto, no encontraba el partido: 0 puntos mientras la pantalla
    marcaba acierto."""
    app = _app(tmp_path, monkeypatch)
    # 3 partidos con marcador y signo_actual vacio (el fallo del collector),
    # todos ganados por el local, y el usuario firmando "1" en los tres.
    _seed(app, ["FT"] * 15, goles={1: (2, 0), 2: (1, 0), 3: (3, 1)})
    with app.app_context():
        conn = get_db()
        conn.execute("UPDATE resultados SET signo_actual = '-' WHERE jornada = ?", (JORNADA,))
        for partido_id in (1, 2, 3):
            conn.execute(
                "INSERT INTO predicciones (user_id, jornada, partido_id, signo) VALUES ('u1', ?, ?, '1')",
                (JORNADA, partido_id),
            )
        conn.commit()

        payload = build_predictions_payload(conn, JORNADA, current_user_id="u1")
        aciertos = payload["ranking_maestros"]["u1"]["total"]
        assert aciertos == 3, f"el usuario acerto los 3 partidos segun el marcador, pero el ranking le da {aciertos}"


def test_el_signo_se_deriva_tambien_del_marcador_para_el_pleno(tmp_path, monkeypatch):
    """El partido 15 se puntua con el marcador exacto, no con 1X2. Si la columna
    viene vacia hay que seguir sacando el marcador de los goles."""
    app = _app(tmp_path, monkeypatch)
    _seed(app, ["FT"] * 15, goles={15: (2, 1)})
    with app.app_context():
        conn = get_db()
        conn.execute("UPDATE resultados SET signo_actual = '-' WHERE jornada = ?", (JORNADA,))
        conn.execute(
            "INSERT INTO predicciones (user_id, jornada, partido_id, signo) VALUES ('u1', ?, 15, '2-1')",
            (JORNADA,),
        )
        conn.commit()

        payload = build_predictions_payload(conn, JORNADA, current_user_id="u1")
        assert payload["ranking_maestros"]["u1"]["total"] == 1, (
            "el pleno se resolvio 2-1 y el usuario firmo 2-1: deberia contar"
        )


def test_sin_marcador_no_hay_signo_que_inventar(tmp_path, monkeypatch):
    """Lo contrario: un partido sin goles no se puede puntuar, aunque el status
    diga FT. Inventar un signo dari aciertos a todo el mundo."""
    app = _app(tmp_path, monkeypatch)
    _seed(app, ["FT"] * 15)
    with app.app_context():
        conn = get_db()
        conn.execute("UPDATE resultados SET signo_actual = '-' WHERE jornada = ?", (JORNADA,))
        for partido_id in range(1, 16):
            conn.execute(
                "INSERT INTO predicciones (user_id, jornada, partido_id, signo) VALUES ('u1', ?, ?, '1')",
                (JORNADA, partido_id),
            )
        conn.commit()

        payload = build_predictions_payload(conn, JORNADA, current_user_id="u1")
        assert payload["ranking_maestros"]["u1"]["total"] == 0


# ── 5. La Peña y el TICKET dicen lo mismo ───────────────────────────────────


def test_la_pena_cuenta_los_partidos_en_juego_como_el_ticket(tmp_path, monkeypatch):
    """La Peña solo miraba `is_scored_status`, el TICKET contaba final o vivo. El
    mismo usuario veia 12 aciertos en su quiniela y 11 en La Peña, sin que nada
    explicara la diferencia."""
    app = _app(tmp_path, monkeypatch)
    # 2 finalizados y 1 en juego, los tres ganados por el local.
    _seed(
        app,
        ["FT", "FT", "LIVE"] + ["NS"] * 12,
        goles={1: (2, 0), 2: (1, 0), 3: (3, 1)},
    )
    with app.app_context():
        conn = get_db()
        conn.execute("UPDATE resultados SET signo_actual = '-' WHERE jornada = ?", (JORNADA,))
        for partido_id in (1, 2, 3):
            conn.execute(
                "INSERT INTO predicciones (user_id, jornada, partido_id, signo) VALUES ('u1', ?, ?, '1')",
                (JORNADA, partido_id),
            )
        conn.commit()

        predictions = build_predictions_payload(conn, JORNADA, current_user_id="u1")
        aciertos_ticket = predictions["ranking_maestros"]["u1"]["jornada"]

    contest_service._contest_payload_cache.clear()
    pena = contest_service.build_contest_payload(JORNADA, "u1")
    aciertos_pena = pena["profile"]["hits"]

    assert aciertos_ticket == aciertos_pena, (
        f"el TICKET dice {aciertos_ticket} aciertos y La Peña {aciertos_pena}: "
        "el usuario ve dos numeros distintos para el mismo boleto"
    )
    assert aciertos_ticket == 3


def test_la_pena_no_cuenta_partidos_sin_jugar(tmp_path, monkeypatch):
    """El extremo contrario: un NS no cuenta aunque el usuario lo haya firmado."""
    app = _app(tmp_path, monkeypatch)
    _seed(app, ["FT", "NS"] + ["NS"] * 13, goles={1: (2, 0)})
    with app.app_context():
        conn = get_db()
        conn.execute("UPDATE resultados SET signo_actual = '-' WHERE jornada = ?", (JORNADA,))
        for partido_id in (1, 2):
            conn.execute(
                "INSERT INTO predicciones (user_id, jornada, partido_id, signo) VALUES ('u1', ?, ?, '1')",
                (JORNADA, partido_id),
            )
        conn.commit()

    contest_service._contest_payload_cache.clear()
    pena = contest_service.build_contest_payload(JORNADA, "u1")
    assert pena["profile"]["hits"] == 1


# ── 6. El marcador de pleno se interpreta igual en los dos lados ────────────


@pytest.mark.parametrize(
    ("crudo", "esperado"),
    [
        ("2-1", "2-1"),
        ("AET 2-1", ""),
        ("Pen. 1-0", ""),
        ("2 - 1", "2-1"),
        ("M-M", "M-M"),
        ("4-0", "M-0"),
        ("roto", ""),
    ],
)
def test_el_pleno_no_acepta_un_prefijo_que_el_front_rechaza(crudo, esperado):
    """El backend buscaba con `re.search` y el front con un patron anclado: con
    "AET 2-1" el ranking contaba el acierto y la pantalla pintaba un fallo. El
    mismo partido, dos verdades."""
    from liga_maestros.scoring import pleno_score_key

    assert pleno_score_key(crudo) == esperado


# ── 7. El cerrojo del guardado vive en el modulo, no en el DOM ──────────────


def test_el_guardado_tiene_un_cerrojo_reentrante():
    """`if (saveButton?.disabled) return` no protege: `hydrateHero()` vuelve a
    pintar el boton mientras la peticion sigue viva. Con dos POST en vuelo, el
    backend borra y reinserta y el que llega ultimo manda, asi que cambiar un
    signo y volver a guardar perdia el boleto nuevo en silencio."""
    fuente = (RAIZ / "static" / "js" / "quantum_final.js").read_text(encoding="utf-8")
    assert "guardadoEnCurso" in fuente, "no hay cerrojo de reentrada en el guardado"

    # El orden importa dentro de savePredictions: si se coge el cerrojo despues
    # de tocar el boton, entre el chequeo y el bloqueo cabe otro clic.
    inicio = fuente.index("async function savePredictions()")
    cuerpo = fuente[
        inicio : fuente.index("\nasync function ", inicio + 10)
        if "\nasync function " in fuente[inicio + 10 :]
        else len(fuente)
    ]
    assert "if (guardadoEnCurso) return;" in cuerpo
    assert cuerpo.index("if (guardadoEnCurso) return;") < cuerpo.index("guardadoEnCurso = true")
    assert "guardadoEnCurso = false" in cuerpo, "el cerrojo no se libera: la app se queda bloqueada para siempre"
    # Y tiene que liberarse DESPUES del await, no antes.
    assert cuerpo.index("await refreshData()") < cuerpo.rindex("guardadoEnCurso = false"), (
        "liberar el cerrojo antes del ultimo await deja pasar un segundo POST"
    )


CASOS_BORRADOR = [
    "el-servidor-gana-al-borrador",
    "borrador-obsoleto-se-ignora",
    "borrador-reciente-se-restaura",
    "borrador-igual-al-servidor-no-esta-sucio",
    "borrador-parcial-se-respeta",
    "boleto-completo-sin-borrador-es-solo-lectura",
]


@pytest.mark.parametrize("caso", CASOS_BORRADOR)
def test_la_logica_de_borradores_se_comporta_como_debe(caso):
    """Ejecuta el `state.js` de verdad en Node, no lo busca con `in`.

    La version anterior comprueba que en el fuente existan las cadenas
    `DRAFT_MAX_AGE_MS` y `sameSigns(draft, serverSigns)`. Eso no puede detectar el
    fallo: con el codigo original, `draft || serverSigns` hacia ganar al draft y
    las dos cadenas seguian ahi, asi que el test pasaba con la regresion viva. El
    arnes ejecuta `utils.js` y `state.js` en un `vm` con localStorage simulado, y
    `el-servidor-gana-al-borrador` es justo el caso que se rompia.

    El arnes es `tools/js/state_draft_harness.js`. Si Node no esta disponible el
    test se salta en vez de dar un verde falso."""
    harness = RAIZ / "tools" / "js" / "state_draft_harness.js"
    node = shutil.which("node")
    if not node:
        pytest.skip("node no esta disponible para ejecutar el arnes de state.js")

    resultado = subprocess.run(
        [node, str(harness), caso],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=RAIZ,
    )
    salida = (resultado.stdout or "") + (resultado.stderr or "")
    assert resultado.returncode == 0, (
        f"el arnes de state.js fallo en el caso {caso!r} (codigo {resultado.returncode}):\n{salida.strip()}"
    )
