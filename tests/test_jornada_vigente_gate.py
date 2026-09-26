"""Gate bloqueante de la jornada vigente.

La puerta de CI que existía (`test_ensure_jornada_completa.py` +
`test_production_readiness.py`) valida íntegramente la **jornada 75**: una
numeración vieja (2025-26, Veikkausliiga finlandesa — "VPS Vaasa", "Inter Turku",
"AIK", "Aalesunds FK", "Orgryte IS"). Desde `test_security_hardening.py:186-187`
ya se sabe que "las de pruebas (51-76) ya no alimentan el concurso", así que la
única comprobación capaz de bloquear la CI no vigilaba nada del concurso real.

Este módulo cierra ese hueco. Valida los **datos versionados que se despliegan**
(`data/`), no la base de datos de producción: así el gate es determinista en CI y
sigue siendo significativo sin acceso a Alwaysdata.

Lo que vigila:
- la jornada declarada en el seed está dentro de la temporada vigente;
- existen exactamente 15 partidos con fecha y hora;
- el boleto `programa` tiene 15 signos y es un boleto válido según el backend;
- Pavo tiene boleto completo (es fuente de verdad, no se degrada);
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
MATCH_DURATION = timedelta(hours=2)
# Margen para que el gate no se ponga rojo a los 2 minutos del saque, en la
# ventana entre el push y la ejecución del job.
SAFETY_MARGIN = timedelta(minutes=30)


def _load(path: Path) -> dict:
    assert path.is_file(), f"falta {path.relative_to(ROOT)}"
    return json.loads(path.read_text(encoding="utf-8"))


def _seed_jornada_de_un_fichero(path: Path) -> int | None:
    match = re.fullmatch(r"predicciones_J(\d+)\.json", path.name)
    return int(match.group(1)) if match else None


@pytest.fixture(scope="module")
def current_jornada() -> int:
    """Jornada vigente según los seeds de la repo.

    Se descubre sola (no está codificada) para que el gate siga a la jornada
    real cuando se suba la siguiente: se queda con el `predicciones_J*.json` de
    mayor número que siga dentro de la temporada publicada.
    """
    from liga_maestros.services.jornada import CURRENT_SEASON_MAX_JORNADA

    candidatas = []
    for path in DATA.glob("predicciones_J*.json"):
        jornada = _seed_jornada_de_un_fichero(path)
        if jornada is not None and 1 <= jornada <= CURRENT_SEASON_MAX_JORNADA:
            candidatas.append(jornada)

    assert candidatas, (
        f"no hay ningún data/predicciones_J*.json de la temporada vigente (1..{CURRENT_SEASON_MAX_JORNADA})"
    )
    return max(candidatas)


@pytest.fixture(scope="module")
def horarios(current_jornada: int) -> dict:
    return _load(DATA / f"horarios_J{current_jornada}.json")


@pytest.fixture(scope="module")
def predicciones(current_jornada: int) -> dict:
    return _load(DATA / f"predicciones_J{current_jornada}.json")


def test_la_jornada_del_seed_esta_en_la_temporada_vigente(current_jornada):
    from liga_maestros.services.jornada import CURRENT_SEASON_MAX_JORNADA, is_current_season_jornada

    assert 1 <= current_jornada <= CURRENT_SEASON_MAX_JORNADA, (
        f"la jornada del seed ({current_jornada}) está fuera de la temporada vigente (1..{CURRENT_SEASON_MAX_JORNADA})"
    )
    assert is_current_season_jornada(current_jornada), "la jornada del seed no es de la temporada vigente"


def test_hay_quince_partidos_con_fecha_y_hora(horarios):
    esperado = {str(i) for i in range(1, MATCHES_PER_JORNADA + 1)}
    assert set(horarios) == esperado, f"partidos esperados 1..{MATCHES_PER_JORNADA}, recibidos {sorted(horarios)}"

    for partido_id in sorted(esperado, key=int):
        row = horarios[partido_id]
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


def test_pavo_tiene_boleto_completo(predicciones):
    assert "pavo" in predicciones, "el seed no contiene a Pavo"
    signos = predicciones["pavo"]["signos"]
    assert len(signos) == MATCHES_PER_JORNADA, f"Pavo tiene {len(signos)} signos, no {MATCHES_PER_JORNADA}"


def test_el_calendario_no_esta_congelado_en_el_pasado(horarios, current_jornada):
    """La jornada en juego puede tener partidos ya terminados; lo raro es que
    los quince estén atrás, señal de que el calendario se quedó congelado y la
    web sigue pidiendo quinielas para una jornada que ya no existe."""
    ahora = datetime.now(MADRID)
    terminados = 0

    for partido_id, row in sorted(horarios.items(), key=lambda kv: int(kv[0])):
        kickoff = datetime.strptime(f"{row['fecha']} {row['hora']}", "%Y-%m-%d %H:%M").replace(tzinfo=MADRID)
        if kickoff + MATCH_DURATION + SAFETY_MARGIN < ahora:
            terminados += 1

    assert terminados < MATCHES_PER_JORNADA, (
        f"el calendario de la jornada {current_jornada} está congelado: los {MATCHES_PER_JORNADA} partidos "
        f"ya deberían haber terminado. Sube el seed de la jornada siguiente."
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
