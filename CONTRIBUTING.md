# Contribuir a Liga de Maestros

Gracias por tu interés en contribuir. Esta guía te explica cómo empezar.

## Setup local

```bash
git clone https://github.com/Purplerave/liga-maestros-web.git
cd liga-maestros-web
python -m venv venv
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate     # Windows
pip install -r requirements.txt
pip install ruff pytest pytest-cov
```

## Ejecutar

```bash
python app.py
# Abre http://localhost:5000
```

## Ejecutar tests

```bash
python -m pytest -q
```

## Lint

```bash
ruff check .
ruff format --check .
```

## Estructura del proyecto

```
app.py                    # Punto de entrada Flask
liga_maestros/            # Paquete principal
  routes/                 # Blueprints
  services/               # Lógica de negocio
  middleware/             # CSRF, auth, rate limit
  models/                 # Modelos de datos
static/                   # CSS, JS, imágenes
templates/                # HTML (Jinja2)
tools/                    # Scripts de operación
  scrapers/               # Scrapeo de datos
  importers/              # Importación de jornadas
  ops/                    # Backups, inicialización
  audit/                  # Auditorías
tests/                    # Suite de tests
docs/                     # Documentación
data/                     # Datos en runtime (no versionar JSON temporales)
```

## Convenciones

- **Commits**: [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `docs:`, `refactor:`, etc.)
- **Python**: ruff format + ruff check (configurado en CI)
- **CSS**: usar `@layer` para especificidad; seguir la cascada tokens → base → components → pages
- **JS**: vanilla sin bundler; funciones globales bien nombradas
- **Tests**: todo cambio de lógica debe incluir test

## Runbook Operativo

### Despliegue (Deploy)
1. **Alwaysdata / Servidor de Producción**:
   - El despliegue automático se ejecuta desde la acción `.github/workflows/deploy-alwaysdata.yml`.
   - Requisitos: variables de entorno en servidor (`SECRET_KEY`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `ADMIN_SECRET`).
   - Tras el despliegue, el servidor verifica la migración de la base de datos de SQLite en WAL mode.

### Restauración de Backups y Rollback
1. **Localizar copias de seguridad**:
   - Los backups automatizados de SQLite se generan en `data/backups/liga_maestros_YYYYMMDD_HHMMSS.db`.
2. **Restaurar base de datos**:
   ```bash
   cp data/backups/liga_maestros_XXXXXXXX_XXXXXX.db data/liga_maestros.db
   python3 -m liga_maestros.db.migrations
   ```
3. **Rollback de código**:
   ```bash
   git checkout main
   git reset --hard <COMMIT_SHA_ESTABLE>
   python3 build.py
   ```

### Migraciones de Esquema (Schema Ledger)
- El esquema utiliza un ledger versionado (`schema_migrations`) con control de estado y `schema.lock`.
- Para aplicar o verificar migraciones de forma manual:
  ```bash
  python3 -m liga_maestros.db.migrations
  ```

### Escalado Multi-worker y Leader Election
- La recolección en directo y backups background utilizan **leader election** basado en locks de archivo (`.collector_leader.lock`).
- Al escalar horizontalmente a N workers, solo un nodo actúa como líder para polling externo de Highlightly y mantenimiento, previniendo duplicación de llamadas a la API o contención de bloqueos.

### Observabilidad y Métricas
- Endpoint de métricas Prometheus: `GET /metrics` (requiere cabecera `X-Admin-Secret` o token de servicio).
- Métricas expuestas:
  - Contador de peticiones (`http_requests_total`)
  - Duración acumulada (`http_request_duration_seconds_sum`)
  - Percentiles de latencia recent (`http_request_duration_seconds_p50`, `p90`, `p95`)
  - Cuota diaria y estado del circuit breaker de Highlightly (`highlightly_calls_used`, `highlightly_circuit_open`, `highlightly_quota_warning`).

## Proceso

1. Abre un issue antes de trabajar en algo grande
2. Crea una rama desde `main` (`git checkout -b feat/nombre-descriptivo`)
3. Haz commits pequeños y descriptivos
4. Abre un PR contra `main` con el checklist del PR template
5. Espera review antes de merge
