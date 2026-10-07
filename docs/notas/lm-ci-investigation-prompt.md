PROMPT PARA OTRA IA — INVESTIGAR CI FAILURE EN liga-maestros-web

## Contexto

Estoy trabajando en el repo `liga-maestros-web` (GitHub: Purplerave/liga-maestros-web). Hay un branch de producción en alwaysdata que despliega vía GitHub Actions cuando se hace push a `main`.

## Estado actual de commits (origin/main)

```
0ff2ee6 fix(directo): permitir expansion vertical completa de partidos por liga
382257f fix: resolve pre-existing lint/format/JS errors blocking CI deploy
f277d01 fix: la pestaña Directo ahora muestra todos los partidos (scroll real)
d9ad0f1 fix(directo): add missing match_cards.css link for live-grouped-grid display
33d0d35 fix(cover): shrink brand logo height on short screens
5804c41 fix: adjust cover brand image height for short screens...
```

Todo el mundo está alineado con `origin/main` en `0ff2ee6`.

## El problema

**GitHub Actions CI está fallando en el paso "Tests" (pytest -q).** 

- URL del run fallido: https://github.com/Purplerave/liga-maestros-web/actions/runs/30737373655
- Job ID: 91468543788 — steps: checkout ✓, setup-python ✓, setup-node ✓, install deps ✓, lint ✓, format ✓, pip-audit ✓, reject sensibles ✓, py_compile ✓, js syntax ✓, **Tests: FAILURE**

Los steps de `ruff check`, `ruff format --check`, `pip-audit`, `py_compile`, y `node --check` **todos pasan**. Solo falla `pytest -q`.

## Lo que YA probé localmente (todo pasa)

- `ruff check .` → All checks passed (0 errors)
- `ruff format --check .` → 93 files already formatted
- `python -m py_compile app.py liga_maestros/__init__.py liga_maestros/workers/web_collector.py tools/ops/LIVE_COLLECTOR.py` → all OK
- `node --check` on every JS file → all OK
- `python -m pytest -q` → **133 passed**

## Lo que necesito que investigues

1. **Obtén los logs del paso "Tests" del CI run 30737373655.** Intenta usar `gh` CLI (`gh api repos/Purplerave/liga-maestros-web/actions/runs/30737373655/logs --jq '.'` o similar) o cualquier método que funcione para descargar el zip de logs y extraer el output del step que falla.

2. **Compara local vs CI:** Localmente los tests pasan, pero CI falla. Las posibles causas:
   - Diferencia de versión de pytest (CI instala `pytest>=8.0` desde `requirements-dev.txt`; local es pytest 9.1.1)
   - Dependencia faltante (`pytest-cov>=5.0` está en requirements-dev.txt; verifica si CI instala algo que interfiere)
   - Tests que dependen de archivos/gitignored data que no existen en CI checkout
   - Tests que dependen de `QUINIELA_MOTOR` package (está fuera del repo, importado lazy dentro de funciones)
   - Tests que dependen de la base de datos o fixtures externos

3. **Si encuentras el error específico,** arregla el código (NO los tests — los tests definen el contrato esperado). Haz commit con un mensaje claro y push a `main` para que se dispare el deploy automático.

## Archivos clave involucrados en el fix del Directo

- `templates/liga_index.html` — agregué `<link>` a `match_cards.css` (faltaba)
- `static/css/components/match_cards.css` — define `.live-grouped-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(420px, 1fr), 1fr)); }`
- `static/css/themes/newspaper/page_foundations.css` — arregla `.arena-content { height: auto }` en modo `newspaper-live-active`
- `static/js/arena.js:171` — JS que asigna `container.className = "arena-content arena-grid live-grouped-grid"`

## Lo que NO debes tocar

- `auditoria-chispa-liga-maestros.md` (es un archivo de notas, déjalo como untracked file)
- Los archivos de test son el contrato — NO los modifiques para que "pasen". Si un test revela un bug real, arregla el código fuente, no el test.

## Verificación final

Después de tu fix, asegúrate de:
1. `ruff check .` → 0 errors
2. `ruff format --check .` → 0 files need reformatting  
3. `python -m pytest -q` → 133 passed
4. `python -m py_compile` en los 4 archivos → OK
5. `node --check` en todos los JS → OK
6. Push a main — el workflow `deploy-alwaysdata.yml` debe correr y producción debe quedar en `https://ligademaestros.alwaysdata.net` con `data-assets-v` incrementado y `match_cards.css` presente en el HTML.

## Comando de deploy verification

```bash
curl -s https://ligademaestros.alwaysdata.net/ | grep match_cards
# Debe mostrar el link a match_cards.css
```

Por favor, comunica tanto el error exacto que encuentres como el fix que aplicas.