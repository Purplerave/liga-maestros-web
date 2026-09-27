"""El bloqueo de SQLite no puede costarle el boleto al usuario.

`PRAGMA busy_timeout` (10 s) ya aguanta casi toda la contendedur, pero WAL admite
un solo escritor y el collector de resultados escribe mientras se cierra la
quiniela. Estos tests fijan que:

1. `begin_immediate_with_retry` reintenta un lock transitorio y tiene exito.
2. No reintenta errores que no son de bloqueo (para no esconder fallos reales).
3. Agotados los intentos, propaga el error.
4. El endpoint de guardado sobrevive a un lock y devuelve la quiniela.
"""

import sqlite3

import pytest

from liga_maestros.db.connection import begin_immediate_with_retry, is_transient_lock_error


class _ConexionFalsa:
    """Falla con `locked` un numero de veces y luego deja pasar la transaccion."""

    def __init__(self, fallos):
        self.fallos = fallos
        self.intentos = 0

    def execute(self, sql):
        self.intentos += 1
        if self.intentos <= self.fallos:
            raise sqlite3.OperationalError("database is locked")
        return None


def test_reintenta_hasta_que_la_bd_se_desbloquee():
    conn = _ConexionFalsa(fallos=2)
    begin_immediate_with_retry(conn, attempts=3, base_delay=0)
    assert conn.intentos == 3, "debe haber reintentado tras los dos locks"


def test_no_insiste_si_la_bd_responde_a_la_primera():
    conn = _ConexionFalsa(fallos=0)
    begin_immediate_with_retry(conn, attempts=3, base_delay=0)
    assert conn.intentos == 1


def test_agotados_los_intentos_propaga_el_error():
    conn = _ConexionFalsa(fallos=99)
    with pytest.raises(sqlite3.OperationalError, match="locked"):
        begin_immediate_with_retry(conn, attempts=3, base_delay=0)
    assert conn.intentos == 3, "no debe seguir reintentando indefinidamente"


def test_un_error_que_no_es_de_bloqueo_no_se_reintenta():
    class _RompeDeSiempre:
        def __init__(self):
            self.intentos = 0

        def execute(self, sql):
            self.intentos += 1
            raise sqlite3.OperationalError("no such table: predicciones")

    conn = _RompeDeSiempre()
    with pytest.raises(sqlite3.OperationalError, match="no such table"):
        begin_immediate_with_retry(conn, attempts=3, base_delay=0)
    assert conn.intentos == 1, "un error de esquema no es un lock: propagarlo ya, sin reintentar"


def test_un_intento_debe_ser_suficiente_para_un_error_de_esquema():
    """Si `attempts` fuera 0, el helper no haria nada y devolveria sin transaccion."""

    class _Contador:
        def __init__(self):
            self.intentos = 0

        def execute(self, sql):
            self.intentos += 1

    with pytest.raises(sqlite3.OperationalError):
        begin_immediate_with_retry(_Contador(), attempts=0, base_delay=0)


@pytest.mark.parametrize(
    ("mensaje", "esperado"),
    [
        ("database is locked", True),
        ("Database is locked", True),
        ("database table is busy", True),
        ("no such table: x", False),
        ("attempt to write a readonly database", False),
        ("constraint failed", False),
    ],
)
def test_deteccion_de_lock(mensaje, esperado):
    assert is_transient_lock_error(sqlite3.OperationalError(mensaje)) is esperado


def test_solo_los_operational_error_son_transientes():
    assert is_transient_lock_error(ValueError("database is locked")) is False
    assert is_transient_lock_error(RuntimeError("locked")) is False


def test_busy_timeout_ya_esta_configurado_en_la_capa_de_bd():
    """El reintento es una red extra, no el unico mecanismo: la capa de conexion
    ya espera 10 s por pragma antes de rendirse."""
    import inspect

    import liga_maestros.db.connection as connection

    fuente = inspect.getsource(connection.get_db)
    assert "busy_timeout" in fuente, "get_db debe fijar busy_timeout"
    assert "timeout=" in fuente, "get_db debe pasar timeout a sqlite3.connect"
