# Roadmap Liga de Maestros — Mejora Continua

**Objetivo**: Transformar la web en una app robusta, rápida, accesible y operable en producción.

---

## Principios
- **Entrega incremental**: cada fase termina con algo desplegable y testeado.
- **Cero regresiones**: tests + CI verdes antes de merge.
- **Métricas primero**: si no se mide, no se mejora.

---

## FASE 1 — Quick Wins (1-2 semanas) — *Impacto alto / Esfuerzo bajo*

| # | Acción | Archivos clave | Done |
|---|--------|----------------|------|
| 1.1 | Cache standings (TTL 5 min) + ETag/If-None-Match en `/api/liga/data` | `routes/liga_data.py`, `services/payloads/standings.py` | ☐ |
| 1.2 | CSP estricto + rate-limit (120 req/min/IP) en `/api/*` | `app.py`, `middleware/security.py` (nuevo) | ☐ |
| 1.3 | Headers hardening: `Referrer-Policy`, `Permissions-Policy`, `X-Content-Type-Options`, `X-Frame-Options` | `app.py` / `middleware/security.py` | ☐ |
| 1.4 | `Cache-Control: public, max-age=31536000, immutable` en assets con hash (`style.<hash>.css`, `app.<hash>.js`) | `templates/base.html`, `build.py` (nuevo) / `vite.config.js` | ☐ |
| 1.5 | Build script que inyecta hash en `<link>`/`<script>` y genera `manifest.json` | `build.py`, `templates/base.html` | ☐ |

**Definición de hecho**: payload portada < 200 ms (p95), Lighthouse Performance ≥ 90, CSP sin violations en consola.

---

## FASE 2 — Tiempo Real & Arquitectura Frontend (2-3 semanas) — *Impacto alto / Esfuerzo medio*

| # | Acción | Archivos clave | Done |
|---|--------|----------------|------|
| 2.1 | SSE endpoint `/api/live/stream` → push real de goles/tarjetas/estado | `routes/live.py`, `services/live_state.py`, `static/js/pages/direct.js` | ☐ |
| 2.2 | Cliente SSE con reconexión exponencial + fallback polling | `static/js/pages/direct.js` | ☐ |
| 2.3 | Split `arena.js` → `features/directo/`, `features/portada/`, `shared/` (ES modules) | `static/js/arena.js` → `static/js/features/*` | ☐ |
| 2.4 | Split `cover_page.js` → `features/portada/` | `static/js/pages/cover_page.js` → `static/js/features/portada/*` | ☐ |
| 2.5 | `tsconfig.json` (`allowJs: true`, `checkJs: true`), JSDoc en módulos compartidos | `tsconfig.json`, `static/js/**/*.js` | ☐ |
| 2.6 | CSS: variables globales en `:root`, eliminar duplicados (`.cx-up-when`, `.cx-ia-sign`), design tokens | `static/css/cover_hero.css`, `static/css/pages/direct.css` | ☐ |

**Definición de hecho**: Directo recibe eventos < 1 s sin polling, 0 errores JS en consola, `npm run typecheck` pasa.

---

## FASE 3 — Accesibilidad, Observabilidad & Resiliencia (2-3 semanas) — *Impacto medio / Esfuerzo medio*

| # | Acción | Archivos clave | Done |
|---|--------|----------------|------|
| 3.1 | Pills Directo: `role="tablist"`, `aria-selected`, roving tabindex, foco visible | `static/js/pages/direct.js`, `direct.css` | ☐ |
| 3.2 | Contraste: ajustar `--cx-dim` a ≥ 4.5:1, focus-visible global | `static/css/cover_hero.css`, `variables.css` | ☐ |
| 3.3 | Tabla boleto responsive: `overflow-x:auto` + `thead` sticky | `static/css/cover_hero.css`, `cover_page.js` | ☐ |
| 3.4 | Logs JSON estructurados (request_id, latency, component) | `app.py`, `services/*.py` | ☐ |
| 3.5 | `/metrics` Prometheus: requests_total, latency_seconds, highlightly_calls_used, matches_live | `middleware/metrics.py` (nuevo), `app.py` | ☐ |
| 3.6 | Health check profundo: BD, último fetch OK, collector vivo, versión | `routes/live.py` (`/api/live/health`) | ☐ |
| 3.7 | Fallback graceful Highlightly: si API cae → servir `LIVE_ALL_MATCHES_V3.json` stale + banner “Datos de hace X min” | `services/daily_matches.py`, `routes/liga_data.py`, `static/js/state.js` | ☐ |

**Definición de hecho**: axe-core 0 violations, Prometheus scrape OK, collector caído detectado < 30 s, fallback probado.

---

## FASE 4 — Optimización Avanzada (continuo) — *Impacto medio-bajo / Esfuerzo medio*

| # | Acción | Archivos clave | Done |
|---|--------|----------------|------|
| 4.1 | Budget tracker Highlightly: pausar ligas extranjeras si `remaining < 10%` | `services/daily_matches.py`, `config.py` | ☐ |
| 4.2 | Endpoints granulares: `/api/liga/standings`, `/api/liga/live`, `/api/liga/matches` | `routes/liga_data.py` | ☐ |
| 4.3 | Service Worker (offline-first para portada + Directo) | `static/sw.js`, `vite.config.js` (Workbox) | ☐ |
| 4.4 | Tests E2E (Playwright) flujos críticos: portada → directo → boleto | `tests/e2e/` | ☐ |

---

## Métricas de éxito globales

| KPI | Objetivo |
|-----|----------|
| Time to Interactive (portada) | < 1.5 s (4G) |
| Latencia evento vivo → UI | < 1 s |
| Disponibilidad collector | 99.9 % |
| Budget Highlightly usado | ≤ 85 % diario |
| Accesibilidad (axe) | 0 critical/serious |
| CSP violations | 0 |

---

## Orden de ejecución sugerido
1. **1.1 → 1.4** (se pueden hacer en paralelo, son independientes)
2. **2.1 → 2.2** (SSE antes de refactor frontend)
3. **2.3 → 2.6** (split + TS + CSS limpio)
4. **3.1 → 3.7** (accesibilidad + obs + resiliencia)
5. **4.x** (cuando las anteriores estén estables)

---

## Notas de implementación
- Cada fase tiene su **branch** (`feat/fase-1-cache`, `feat/fase-2-sse`, etc.).
- PR pequeño, revisado, CI verde → merge a `main` → deploy automático.
- `roadmap.md` se actualiza al cerrar cada tarea (checkbox → ✅).