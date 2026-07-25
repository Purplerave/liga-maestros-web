# Auditoría Integral Maximalista — Liga de Maestros
> Rol del auditor: Diseñador de Producto Senior + Arquitecto de Software + Especialista en DX
> Fecha: 2026-07-25 · Commit base: `b7f6446` · Stack: Flask 3.1 + SQLite + JS vanilla (sin build)
---
## 0. Diagnóstico ejecutivo
**Lo que tienes es mejor de lo que parece desde fuera.** Por dentro hay una arquitectura seria:
blueprints bien separados, CSP real, CSRF propio, rate limiting, WAL + `busy_timeout`, backups
rotativos con `integrity_check`, borrado transaccional de cuenta, CI con `pip-audit` bloqueante y
SHAs de actions pineados.

| Dimensión | Nota | Comentario |
|---|---|---|
| Seguridad backend | **8,5 / 10** | Muy por encima de la media. Falta observabilidad y secretos rotables. |
| Arquitectura Python | **7 / 10** | Buena modularización, lastrada por duplicación root/paquete y I/O de JSON en caliente. |
| Frontend | **5 / 10** | 8 `<script>` globales sin módulos ni build; 15 K líneas de CSS con capas manuales. |
| Datos / persistencia | **5,5 / 10** | Híbrido SQLite + 27 JSON en disco sin contrato ni validación de esquema. |
| Testing | **6 / 10** | 1.457 líneas de tests, pero centrados en seguridad; falta cobertura de dominio y E2E. |
| DX / onboarding | **4 / 10** | Sin Makefile, sin devcontainer, sin pre-commit, sin `pyproject.toml`, raíz caótica. |
| Presentación / branding | **2,5 / 10** | README plano, sin capturas, sin badges, sin licencia, sin demo. |
| Comunidad / gobernanza | **2 / 10** | Sin LICENSE, sin CONTRIBUTING, sin plantillas de issue/PR, sin CODEOWNERS. |
**Puntuación global: 5,1 / 10 como *producto público*; 7,2 / 10 como *software*.**
---
## BLOQUE 1 — Impacto Rápido (Quick Wins)
- QW-1: LICENSE (AGPL-3.0)
- QW-2: Limpieza raíz repositorio
- QW-3: CLI unificado
- QW-4: Eliminar triplicación config/utils/scoring
- QW-5: Badges + hero README
- QW-6: pyproject.toml + ruff.toml
- QW-7: Health check enriquecido
- QW-8: .github/ completo
- QW-9: data/ con JSON Schema
- QW-10: Corregir patrón get_db()
---
## BLOQUE 2 — Rediseño Visual y Documentación
- README con hero, badges, galería, arquitectura Mermaid
- Activos gráficos (banner, GIF, capturas, social preview)
- MkDocs Material para documentación
- ADRs, glosario, README multilingüe
---
## BLOQUE 3 — Optimización de Código y Arquitectura
- P0: Duplicación root/paquete, god-endpoint, I/O síncrono, cache-busting
- Frontend: ES modules, Lighthouse CI, auditoría CSS muerto
- Backend: Pydantic, logging estructurado, Sentry, repositorio de BD
- Testing: Hypothesis, golden tests, E2E Playwright
---
## BLOQUE 4 — Nuevas Funcionalidades
- Tier S: Arena IAs automatizada, API pública, SSE directo, ligas multi-tenant
- Tier A: Bot Telegram, PWA, perfiles públicos, gamificación
- Tier B: Comentarios live, quiz elevado, arcade torneos
---
## BLOQUE 5 — Automatización GitHub
- Workflows: lint, test, e2e, CodeQL, dependabot, jornada.yml automatizado
- Comunidad: LICENSE, CONTRIBUTING, CODE_OF_CONDUCT, issue templates
