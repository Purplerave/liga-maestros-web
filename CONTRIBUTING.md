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

## Proceso

1. Abre un issue antes de trabajar en algo grande
2. Crea una rama desde `main` (`git checkout -b feat/nombre-descriptivo`)
3. Haz commits pequeños y descriptivos
4. Abre un PR contra `main` con el checklist del PR template
5. Espera review antes de merge
