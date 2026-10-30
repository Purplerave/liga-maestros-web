"""Gate bloqueante de la jornada vigente.

La puerta de CI que existía (`test_ensure_jornada_completa.py` +
`test_production_readiness.py`) valida íntegramente la **jornada 75**: una
numeración vieja (2025-26, Veikkausliiga finlandesa — "VPS Vaasa", "Inter Turku",
"AIK", "Aalesunds FK", "Orgryte IS"). Desde `test_security_hardening.py:186-187`
ya se sabe que "las de pruebas (51-76) ya no alimentan el concurso", así que la
única comprobación capaz de bloquear la CI no vigilaba nada del concurso real.

Este módulo cierra ese hueco. Valida los **datos versionados que se despliegan**
(`data/` y, desde la J17, los boletos editoriales de `migrations.py`), no la base
de datos de producción: así el gate es determinista en CI y sigue siendo
significativo sin acceso a Alwaysdata.

Lo que vigila:
- la jornada en juego está dentro de la temporada vigente;
- existen exactamente 15 partidos y su horario es el verificado (una casilla
  marcada como no verificada en el scrape no se rellena a mano);
- el boleto `programa` tiene 15 signos y es un boleto válido según el backend;
- todos los boletos de la jornada están completos (Pavo en los seeds antiguos,
  los cinco maestros en la J17);
- el calendario no está congelado en el pasado;
- el resumen de temporada se sirve desde la temporada vigente.
"""

import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
MADRID = ZoneInfo("Europe/Madrid")

MATCHES_PER_JORNADA = 15
# Los cinco participantes cerrados desde la J17: liga simple, sin dobles.
JUGADORES_J17 = {"mrpurple", "programa", "tecnotron", "grok", "sonia"}
MATCH_DURATION = timedelta(hours=2)
# Margen para que el gate no se ponga rojo a los 2 minutos del saque, en la
# ventana entre el push y la ejecución del job.
SAFETY_MARGIN = timedelta(minutes=30)
# La semilla de la jornada siguiente se publica a mitad de semana, cuando el
# scraper ya puede ver el calendario: entre que una jornada termina (domingo)
# y se sube la siguiente pasan 1-3 días. Sin esta gracia el gate estaba en rojo
# cada lunes aunque nada estuviera roto de verdad. Cuando el plazo se pasa y la
# web sigue mirando una jornada ya cerrada, sí hay un problema real.
SEED_PUBLICATION_GRACE = timedelta(days=3)


def _load(path: Path) -> dict:
    assert path.is_file(), f"falta {path.relative_to(ROOT)}"
    return json.loads(path.read_text(encoding="utf-8"))


def _jornada_de_un_fichero(path: Path, prefijo: str) -> int | None:
    match = re.fullmatch(rf"{prefijo}_J(\d+)\.json", path.name)
    return int(match.group(1)) if match else None


@pytest.fixture(scope="module")
def current_jornada() -> int:
    """Jornada en juego según los datos versionados de la repo.

    Se descubre sola (no está codificada) para que el gate siga a la jornada
    real cuando se suba la siguiente. Se miran tanto los boletos
    (`predicciones_J*.json`) como los fixtures (`horarios_J*.json`): la J17
    tiene calendario y scrape, pero sus boletos viven en `migrations.py`, y
    mirar solo `predicciones_J*.json` dejaba el gate validando la J16 ya cerrada.
    """
    from liga_maestros.services.jornada import CURRENT_SEASON_MAX_JORNADA

    candidatas = set()
    for prefijo in ("predicciones", "horarios"):
        for path in DATA.glob(f"{prefijo}_J*.json"):
            jornada = _jornada_de_un_fichero(path, prefijo)
            if jornada is not None and 1 <= jornada <= CURRENT_SEASON_MAX_JORNADA:
                candidatas.add(jornada)

    assert candidatas, (
        f"no hay ningún data/(predicciones|horarios)_J*.json de la temporada vigente (1..{CURRENT_SEASON_MAX_JORNADA})"
    )
    return max(candidatas)


@pytest.fixture(scope="module")
def horarios(current_jornada: int) -> dict:
    return _load(DATA / f"horarios_J{current_jornada}.json")


@pytest.fixture(scope="module")
def predicciones(current_jornada: int) -> dict:
    """Boletos de la jornada: del seed si existe, o de la importación editorial.

    La J17 no tiene `data/predicciones_J17.json`: sus cinco líneas se despliegan
    desde `J17_EDITORIAL_TICKETS`. Se normaliza la forma para que los tests no
    distingan entre las dos fuentes.
    """
    path = DATA / f"predicciones_J{current_jornada}.json"
    if path.is_file():
        return _load(path)

    from liga_maestros.db import migrations

    tickets = getattr(migrations, f"J{current_jornada}_EDITORIAL_TICKETS", None)
    assert tickets, (
        f"falta data/predicciones_J{current_jornada}.json y no hay "
        f"J{current_jornada}_EDITORIAL_TICKETS en migrations.py"
    )
    return {uid: {"signos": list(signos)} for uid, signos in tickets.items()}


def _kickoffs_sin_verificar(current_jornada: int) -> set[int]:
    """Casillas que el scrape marca como pendientes de horario verificado."""
    path = DATA / f"quiniela15_J{current_jornada}_scrape.json"
    if not path.is_file():
        return set()
    scrape = _load(path)
    return {
        int(partido["num"])
        for partido in scrape.get("partidos", [])
        if not str(partido.get("hora") or "").strip() and partido.get("nota")
    }


def test_la_jornada_del_seed_esta_en_la_temporada_vigente(current_jornada):
    from liga_maestros.services.jornada import CURRENT_SEASON_MAX_JORNADA, is_current_season_jornada

    assert 1 <= current_jornada <= CURRENT_SEASON_MAX_JORNADA, (
        f"la jornada del seed ({current_jornada}) está fuera de la temporada vigente (1..{CURRENT_SEASON_MAX_JORNADA})"
    )
    assert is_current_season_jornada(current_jornada), "la jornada del seed no es de la temporada vigente"


def test_hay_quince_partidos_con_horario_verificado(horarios, current_jornada):
    esperado = {str(i) for i in range(1, MATCHES_PER_JORNADA + 1)}
    assert set(horarios) == esperado, f"partidos esperados 1..{MATCHES_PER_JORNADA}, recibidos {sorted(horarios)}"

    sin_verificar = _kickoffs_sin_verificar(current_jornada)
    for partido_id in sorted(esperado, key=int):
        row = horarios[partido_id]
        if int(partido_id) in sin_verificar:
            # Pendiente documentado en el scrape: no se inventa ni fecha ni hora.
            assert not str(row.get("hora") or "").strip(), f"partido {partido_id}: hora inventada"
            continue
        assert row.get("fecha"), f"partido {partido_id} sin fecha"
        assert row.get("hora"), f"partido {partido_id} sin hora"
        datetime.strptime(row["hora"], "%H:%M")


def test_el_programa_tiene_boleto_completo_y_valido(predicciones):
    from liga_maestros.scoring import normalize_prediction_sign

    signos = predicciones["programa"]["signos"]
    assert len(signos) == MATCHES_PER_JORNADA, (
        f"el boleto del programa tiene {len(signos)} signos, no {MATCHES_PER_JORNADA}"
    )

    for partido_id, sign in enumerate(signos, start=1):
        assert normalize_prediction_sign(partido_id, sign), (
            f"el signo del programa en el partido {partido_id} no es válido: {sign!r}"
        )


def test_todos_los_boletos_de_la_jornada_estan_completos(predicciones, current_jornada):
    """Pavo era la fuente de verdad de los seeds antiguos; desde la J17 la liga
    es de cinco maestros y se validan los cinco."""
    from liga_maestros.scoring import normalize_prediction_sign

    if current_jornada == 17:
        assert set(predicciones) == JUGADORES_J17, f"la J17 debe tener los cinco maestros, tiene {sorted(predicciones)}"
    else:
        assert "pavo" in predicciones, "el seed no contiene a Pavo"

    for uid, data in predicciones.items():
        signos = data["signos"]
        assert len(signos) == MATCHES_PER_JORNADA, f"{uid} tiene {len(signos)} signos, no {MATCHES_PER_JORNADA}"
        for partido_id, sign in enumerate(signos, start=1):
            assert normalize_prediction_sign(partido_id, sign), (
                f"el signo de {uid} en el partido {partido_id} no es válido: {sign!r}"
            )


def test_el_calendario_no_esta_congelado_en_el_pasado(horarios, current_jornada):
    """La jornada en juego puede tener partidos ya terminados; lo raro es que
    siga siendo la vigente cuando ya pasó su ventana de publicación, señal de
    que el calendario se quedó congelado y la web sigue pidiendo quinielas
    para una jornada que ya no existe."""
    ahora = datetime.now(MADRID)

    fins = []
    for partido_id in sorted(horarios, key=int):
        row = horarios[partido_id]
        fecha = str(row.get("fecha") or "").strip()
        hora = str(row.get("hora") or "").strip()
        if not fecha or not hora:
            continue
        kickoff = datetime.strptime(f"{fecha} {hora}", "%Y-%m-%d %H:%M").replace(tzinfo=MADRID)
        fins.append(kickoff + MATCH_DURATION)

    assert fins, f"la jornada {current_jornada} no tiene ningún horario verificado"
    ultimo_fin = max(fins)
    assert ahora <= ultimo_fin + SAFETY_MARGIN + SEED_PUBLICATION_GRACE, (
        f"el calendario de la jornada {current_jornada} está congelado: los {MATCHES_PER_JORNADA} partidos "
        f"terminaron y ya pasó la gracia de {SEED_PUBLICATION_GRACE.days} días para publicar la semilla "
        f"de la siguiente. Sube el seed (make jornada J={current_jornada + 1})."
    )


def test_el_resumen_de_temporada_apunta_a_la_vigente():
    """`/api/season-summary` servía `season_2025_2026_summary.json` hardcodeado."""
    from config.game import CURRENT_SEASON_ID, season_summary_filename

    assert season_summary_filename() == f"season_{CURRENT_SEASON_ID.replace('-', '_')}_summary.json"

    source = (ROOT / "liga_maestros" / "routes" / "main.py").read_text(encoding="utf-8")
    assert "config.season_summary_filename()" in source, "el endpoint sigue con el nombre de temporada hardcodeado"
    assert "season_2025_2026_summary" not in source, "queda una referencia al resumen de la temporada anterior"

    reset = (ROOT / "tools" / "ops" / "RESET_TEMPORADA.py").read_text(encoding="utf-8")
    assert "season_2025_2026_summary" not in reset, (
        "RESET_TEMPORADA sigue escribiendo el resumen de la temporada anterior"
    )


# La puerta anti-secretos de la CI estuvo mucho tiempo rota: dentro de comillas
# simples `\\.env` llega a grep como un backslash literal, así que un fichero
# `.env` real no podía detectarse nunca. Cuando se arregló, `.env.example`
# (plantilla legítima) empezó a casar. Estos tests fijan el comportamiento.
SECRET_GATE_PATTERN = r"(^|/)(\.env$|.*\.(db|sqlite|sqlite3|pem|key)$|id_rsa$|id_ed25519$)"
DEBE_CASAR = (".env", "app/.env", "secret.db", "datos.sqlite3", "server.pem", "deploy.key", "home/id_rsa", "id_ed25519")
NO_DEBE_CASAR = (".env.example", ".env.sample", "environment.md", "data.json", "readme.md", "keyboard.js")


@pytest.mark.parametrize("nombre", DEBE_CASAR)
def test_la_puerta_anti_secretos_detecta_lo_prohibido(nombre):
    assert re.search(SECRET_GATE_PATTERN, nombre), f"la puerta de secretos NO detecta {nombre!r}"


@pytest.mark.parametrize("nombre", NO_DEBE_CASAR)
def test_la_puerta_anti_secretos_no_da_falsos_positivos(nombre):
    assert not re.search(SECRET_GATE_PATTERN, nombre), f"la puerta de secretos marca {nombre!r} y es legítimo"


def test_la_puerta_anti_secretos_esta_live_en_ambos_workflows():
    """Si el gate no está en los dos workflows, el deploy se salta la comprobación."""
    for workflow in ("ci.yml", "deploy-alwaysdata.yml"):
        source = (ROOT / ".github" / "workflows" / workflow).read_text(encoding="utf-8")
        assert "git ls-files" in source, f"{workflow} no comprueba ficheros sensibles"
        # El bug original: un backslash literal que hacía la regla inerte.
        assert r"\\.env" not in source, f"{workflow} conserva el regex roto (\\\\.env) del gate"
        assert r"\.env$" in source, f"{workflow} no ancla el gate a .env$, así que .env.example da falso positivo"
