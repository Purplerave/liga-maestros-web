<h1 align="center">Liga de Maestros</h1>
<p align="center"><b>La Pe&ntilde;a contra los Maestros IA.</b> Quiniela competitiva humanos vs. modelos de IA, jornada a jornada.</p>
<p align="center">
  <img src="https://img.shields.io/badge/python-3.11-3776AB?logo=python&logoColor=white&style=for-the-badge">
  <img src="https://img.shields.io/badge/Flask-3.1-000?logo=flask&style=for-the-badge">
  <img src="https://img.shields.io/badge/SQLite-WAL-003B57?logo=sqlite&logoColor=white&style=for-the-badge">
  <img src="https://img.shields.io/badge/license-AGPL--3.0-blue?style=for-the-badge">
  <a href="https://ligademaestros.alwaysdata.net"><img src="https://img.shields.io/badge/DEMO-→-ff4d6d?style=for-the-badge"></a>
</p>

---

> **En una frase:** cada semana, 15 partidos de la quiniela; La Pe&ntilde;a (humanos) y los Maestros IA
> (GPT, Claude, Gemini, Grok…) firman su 1X2 antes del cierre, y la web arbitra en directo
> qui&eacute;n acierta m&aacute;s. Con ranking hist&oacute;rico, porra del pleno, quiz semanal y arcade.

---

## Qu&eacute; hace

| M&oacute;dulo | Descripci&oacute;n |
|---|---|
| **Quiniela** | Tabla de 15 partidos con predicciones 1X2 del Programa, los Maestros IA y La Pe&ntilde;a. Guardado, compartir y validaci&oacute;n server-side. |
| **Directo** | Seguimiento en vivo con datos de Highlightly: goles, tarjetas, resultados actualizados. Circuit breaker y cuota diaria de API. |
| **Ligas** | Clasificaci&oacute;n general, mensual y por jornada. Standings de Primera, Segunda y competiciones europeas. |
| **La Pe&ntilde;a** | Perfil del jugador: historial, rachas, rivales directos, galardones y comparaci&oacute;n contra la media. |
| **Quiz** | Preguntas de f&uacute;tbol con ranking propio y generaci&oacute;n semanal automatizada. |
| **Arcade** | Snake Gol, Arkanoid Liga y Maestros Invaders con rankings locales. |

## Arquitectura

```mermaid
flowchart LR
  subgraph Fuentes
    Q15[Quiniela15<br/>scraping]
    HL[Highlightly API<br/>live + standings]
    NEWS[Radar de noticias]
  end
  subgraph Ingesta
    SCR[tools/scrapers]
    COL[web_collector<br/>circuit breaker + cuota diaria]
  end
  subgraph Nucleo["Flask · liga_maestros"]
    RT[15 Blueprints]
    SV[Services<br/>payloads · scoring · quiz · ticket]
    MW[Middleware<br/>CSRF · authz · rate limit · json lock]
  end
  subgraph Datos
    DB[(SQLite WAL<br/>+ backups verificados)]
    JS[/JSON runtime<br/>DATA_DIR/]
  end
  UI[Frontend vanilla<br/>@layer CSS · 8 modulos JS]
  Q15-->SCR-->JS
  HL-->COL-->JS
  NEWS-->COL
  SCR-->DB
  RT<-->SV<-->DB
  SV<-->JS
  MW-->RT
  RT-->|/api/liga/data|UI
```

## Quickstart

```bash
git clone https://github.com/Purplerave/liga-maestros-web.git
cd liga-maestros-web
python -m venv venv
source venv/bin/activate   # Linux/macOS
pip install -r requirements.txt
cp .env.example .env       # rellena las variables
python app.py
```

Abre `http://127.0.0.1:5000/`.

## Seguridad

- **CSRF** propio con tokens por sesi&oacute;n.
- **CSP** real (Content-Security-Policy) en todas las rutas.
- **Rate limiting** por IP en endpoints sensibles.
- **SQLite WAL** + `busy_timeout` + backups rotativos con `integrity_check`.
- **Borrado transaccional** de cuenta (GDPR).
- **pip-audit** bloqueante en CI + SHAs de GitHub Actions pineados.
- Vulnerabilidades: ver [SECURITY.md](SECURITY.md).

## Testing

```bash
python -m pytest -q          # 109 tests (seguridad, dominio, frontend)
ruff check .                # lint
```

## Estructura

```
app.py                         # Punto de entrada
liga_maestros/                 # Paquete principal
  routes/                      # 15 blueprints
  services/                    # Scoring, payloads, quiz, ticket
  middleware/                   # CSRF, auth, rate limit
  workers/                     # Collector live
tools/                         # Scripts de operacion
  scrapers/                    # Scrapeo de datos
  importers/                   # Importacion de jornadas
  ops/                         # Backups, inicializacion, collector
  audit/                       # Auditorias
static/                        # CSS, JS, imagenes
templates/                     # HTML (Jinja2)
data/                          # JSON publicos y semillas
tests/                         # Suite de tests
docs/                          # Documentacion
```

## Flujo semanal

```mermaid
sequenceDiagram
  autonumber
  participant A as Admin
  participant S as Scrapers
  participant DB as SQLite
  participant C as Collector
  participant U as Usuario
  A->>S: scrape quiniela15 --proxima
  S->>DB: 15 partidos + horarios
  A->>DB: importar programa/maestros/pena
  U->>DB: firma su quiniela (antes del cierre)
  Note over DB: cierre automatico al primer pitido
  C-->>DB: polling live (cuota + circuit breaker)
  DB-->>U: ranking en vivo
  A->>DB: auditar jornada
```

## Licencia

[AGPL-3.0](LICENSE) &mdash; si clonas este repo como servicio cerrado, debes publicar tu codigo fuente.

## Contribuir

Ver [CONTRIBUTING.md](CONTRIBUTING.md) para setup, convenciones y proceso de PR.
