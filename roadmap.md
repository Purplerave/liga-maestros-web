# Roadmap Liga de Maestros — Mejora Continua

**Objetivo**: Transformar la web en una app robusta, rápida, accesible y operable en producción.

---

## Estado Actual de la Aplicación
- **Producción**: Jornada activa 8, `/health/ready` responde 200 OK.
- **Seguridad**: CSRF por sesión, CSP real, headers de hardening (`nosniff`, `Referrer-Policy`, `Permissions-Policy`, HSTS, COOP/CORP), rate limiting por IP, Google OAuth opaco y sin almacenamiento de correos.
- **Rendimiento**: Caching de standings (TTL 5 min), ETag/If-None-Match (304 Not Modified), `?slim=1` y `?first=1` para peticiones móviles optimizadas.
- **Service Worker & PWA**: Service Worker registrado con scope `/` y cabecera `Service-Worker-Allowed: /`.
- **Ops & Observabilidad**: Health probes (`/health/live` y `/health/ready`), métricas Prometheus (`/metrics`), SQLite WAL con backups verificados.

---

## FASE 1 — Quick Wins — *Impacto alto / Esfuerzo bajo*

| # | Acción | Archivos clave | Estado |
|---|--------|----------------|--------|
| 1.1 | Cache standings (TTL 5 min) + ETag/If-None-Match en `/api/liga/data` | `routes/liga_data.py`, `services/payloads/standings.py` | ✅ Completado |
| 1.2 | CSP estricto + rate-limit en `/api/*` | `app.py`, `middleware/security.py` | ✅ Completado |
| 1.3 | Headers hardening: `Referrer-Policy`, `Permissions-Policy`, `X-Content-Type-Options`, `X-Frame-Options`, COOP/CORP | `app.py`, `middleware/security.py` | ✅ Completado |
| 1.4 | `Cache-Control: public, max-age=31536000, immutable` en assets fingerprinted | `routes/main.py` | ✅ Completado |
| 1.5 | Build script que inyecta hash en assets y genera `manifest.json` | `build.py`, `static/manifest.json` | ✅ Completado |

---

## FASE 2 — Tiempo Real & Arquitectura Frontend — *Impacto alto / Esfuerzo medio*

| # | Acción | Archivos clave | Estado |
|---|--------|----------------|--------|
| 2.1 | SSE endpoint `/api/live/stream` → push real de goles/tarjetas/estado | `routes/live.py`, `services/live_state.py` | ✅ Endpoint existe (desactivado por defecto en Gunicorn sincrono) |
| 2.2 | Cliente SSE con reconexión exponencial + fallback polling | `static/js/events.js`, `static/js/live.js` | ✅ Polling acotado con `?slim=1` y ETag activo |
| 2.3 | Split `arena.js` → `features/` y `pages/` (módulos ES) | `static/js/arena.js`, `static/js/pages/*` | ✅ Estructurado en módulos por página |
| 2.4 | Split `cover_page.js` → `features/portada/` | `static/js/pages/cover_page.js` | ✅ Completado |
| 2.5 | `tsconfig.json` (`allowJs: true`, `checkJs: true`), JSDoc en módulos compartidos | `tsconfig.json`, `static/js/**/*.js` | ✅ Completado |
| 2.6 | CSS: variables globales en `:root`, design tokens y capas `@layer` | `static/css/base/tokens.css`, `mobile_v2.css` | ✅ Completado |

---

## FASE 3 — Accesibilidad, Observabilidad & Resiliencia — *Impacto medio / Esfuerzo medio*

| # | Acción | Archivos clave | Estado |
|---|--------|----------------|--------|
| 3.1 | Pills Directo: `role="tablist"`, `aria-selected`, roving tabindex, foco visible | `static/js/pages/direct.js`, `direct.css` | ✅ Completado |
| 3.2 | Contraste: ajustar `--cx-dim` a ≥ 4.5:1, focus-visible global | `static/css/base/tokens.css`, `typography.css` | ✅ Completado |
| 3.3 | Tabla boleto responsive: tarjetas móviles y scroll táctil nativo | `static/css/mobile_v2.css` | ✅ Completado |
| 3.4 | Logs estructurados con `request_id` y trazabilidad | `app.py`, `liga_maestros/__init__.py` | ✅ Completado |
| 3.5 | `/metrics` Prometheus: requests_total, latency, collector status | `middleware/metrics.py`, `app.py` | ✅ Completado |
| 3.6 | Health check profundo (`/health` con DB, integrity, backups y collector) | `routes/main.py` | ✅ Completado |
| 3.7 | Fallback graceful Highlightly: datos stale + banner informativo | `services/daily_matches.py`, `routes/liga_data.py` | ✅ Completado |

---

## FASE 4 — Optimización Avanzada & Próximos Pasos — *Impacto medio-bajo / Esfuerzo medio*

| # | Acción | Archivos clave | Estado |
|---|--------|----------------|--------|
| 4.1 | Budget tracker Highlightly: pausar ligas extranjeras si `remaining < 10%` | `services/daily_matches.py` | ☐ En progreso |
| 4.2 | Endpoints granulares: `/api/liga/standings`, `/api/liga/live`, `/api/liga/matches` | `routes/liga_data.py` | ✅ Completado |
| 4.3 | Service Worker offline-first con scope `/` | `static/sw.js`, `routes/main.py` | ✅ Completado |
| 4.4 | Tests E2E (Playwright) para flujos críticos | `tests/e2e/` | ☐ Próximo backlog |
