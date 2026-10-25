# INFORME — Revisión del estudio «futurista-2099» + Fase 0 ejecutada

**De:** DinoPablo (OpenClaw) · **Para:** Tecnotron (CEO) · **Copia:** Pablo
**Fecha:** 25-oct-2026 · **Repo:** `Purplerave/liga-maestros-web` · **Rama de trabajo:** `redesign/futurista-2099`

---

## 1. Revisión del estudio (Tecnotron, 25-oct)

**Veredicto: sólido y accionable — lo ejecuto tal cual.** Verificado contra el código real:

- ✅ El diagnóstico (portada + apps heredadas, colores de 5 CSS) coincide con el repo.
- ✅ Los «rojos» del informe (no borrar CSS/scripts, `data-page-action`/`view=`, service worker, lang, `prefers-reduced-motion`, marcado de pago) — correctos y ahora son mis reglas de trabajo.
- ✅ Las rutas de vistas reales confirmadas: `/?view=TICKET|LIVE|STANDINGS|CONTEST|SNAKE` (+ `QUIZ`, `NEWS_PAGE`) y `/landing`, `/app`.
- **2 precisiones:**
  1. El informe lista 4 ficheros «sin confirmar» — **ya están commiteados en `origin/main`** (PR #194/#195). El árbol local estaba limpio; corrección aplicada en §2.
  2. Dice `src/static/css/…` — la ruta real del repo es **`static/css/…`** (mando al código, como pide el propio informe).

## 2. Fase 0 — ejecutada completa (foto y seguridad)

| Entregable | Resultado |
|---|---|
| Estado del repo auditado | ✅ árbol limpio; cambios «sin confirmar» = ya en `origin/main` |
| Rama creada | ✅ `redesign/futurista-2099` desde `1c58b8a` (= `origin/main`) |
| Guardado de cambios previos | ✅ innecesario (no los había) |
| App en local | ✅ arrancada en `http://127.0.0.1:5000` (`SECRET_KEY` local) |
| **Baseline (espejo exacto del CI)** | ✅ **6/6 en verde** (tabla abajo) |
| **Capturas de referencia** | ✅ **14 PNG** en `screenshots/fase0-antes/` |

### Baseline (comandos = los del CI)
| Check | Comando | Resultado |
|---|---|---|
| Suite principal | `pytest -q --ignore=…readiness… -o addopts=` | **765 passed / 72,75 s** |
| Readiness (bloqueante) | `pytest tests/test_ensure_jornada_completa.py tests/test_production_readiness.py` | 20 passed |
| Gate jornada (bloqueante) | `pytest tests/test_jornada_vigente_gate.py` | 21 passed |
| Lint | `ruff check .` | All checks passed |
| Formato | `ruff format --check .` | 210 ficheros OK |
| Tipos | `mypy liga_maestros` | 0 errores / 74 ficheros |

### Capturas (misma jornada, para comparar con los «después»)
Carpeta `screenshots/fase0-antes/` — 7 vistas × 2 viewports = 14 ficheros PNG verificados:
`01-portada · 02-quiniela · 03-directo · 04-ligas · 05-pena · 06-juegos · 07-landing` — **1440×900** (desktop) y **390×ancho completo** (móvil), `full_page`, `reduced-motion: reduce` para capturas deterministas.

## 3. Incidencias de entorno resueltas (para que conste)

1. **Arranque local:** `SECRET_KEY` obligatoria (no hay `.env`; se usó valor local efímero `***`).
2. **La máquina no tiene navegador** (OpenClaw: «No supported browser found») → Chromium de Playwright descargado en `.venv` del repo; **faltaron libs de sistema** → Pablo ejecutó `playwright install-deps chromium` (sudo) y las capturas salieron.
3. **Política SSRF del navegador:** localhost estaba bloqueado → `browser.ssrfPolicy.allowedHostnames = ["localhost","127.0.0.1"]` (lista mínima) — **se aplica en el próximo reinicio del Gateway**. Sin cambios de política de red más allá de esto.
4. Servidor local vivo en `127.0.0.1:5000` durante toda la sesión (no afecta a producción).

## 4. Estado y siguientes pasos

- **Fase 1 (arquitectura + tokens) lista para arrancar**: `static/css/architecture.css` nuevo con variables globales (`--bg --surface --ink --accent --warn…`) en `:root`, enlazado **después** de los CSS existentes, **sin borrar nada** (duplicar y enlazar, como dice el estudio). Entrega: 1 PR pequeño con capturas ANTES/DESPUÉS de portada.
- **Pendiente del CEO:** revisar este informe y dar luz verde a Fase 1 (o pedir ajustes).
- **Pendiente de Pablo:** abrir el PR cuando le pida la rama (mi PAT no tiene permiso `Pull requests: write` — 403 conocido de octubre; se arregla añadiéndolo a la PAT).
- **Flujo acordado:** ChatGPT diseña/revisa código · OpenClaw ejecuta en local y verifica · Tecnotron revisa · Pablo aprueba con capturas antes de cualquier deploy.

## 5. Evidencia resumida

```
ruff check .                    → All checks passed!
ruff format --check .           → 210 files already formatted
mypy liga_maestros              → Success: no issues found in 74 source files
pytest (principal)              → 765 passed in 72.75s
pytest (readiness)              → 20 passed
pytest (gate jornada)           → 21 passed
capturas                        → 14/14 PNG (1440×900 y 390-wide full-page)
git: HEAD                       → redesign/futurista-2099 @ 1c58b8a (de origin/main)
```

*Informe generado por DinoPablo (OpenClaw) — toda cifra procede de comandos ejecutados en esta sesión.*
