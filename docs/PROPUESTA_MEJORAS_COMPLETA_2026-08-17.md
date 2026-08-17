# Propuesta completa de mejoras — Liga de Maestros

**Fecha:** 17 de agosto de 2026  
**Autor de la propuesta:** Auditoría externa (Grok)  
**Repo:** `Purplerave/liga-maestros-web`  
**Demo:** https://ligademaestros.alwaysdata.net  
**Base:** estado de `main` ~commit `6032009` + auditorías previas del propio repo (`AUDITORIA_INTEGRAL_2026-07-25`, `auditoria-chispa-liga-maestros.md`, `REVIEW_AUDITORIA_VIRAL.md`, `SECURITY.md`)

> Objetivo de este documento: listar **todo lo que cambiaría o mejoraría** para que el producto sea mejor en conversión, retención, robustez técnica, DX y potencial viral, sin perder el ADN actual (humanos vs máquinas, quiniela real, directo, arcade).

---

## 0. Principio rector

El concepto es de **10/10**. La ingeniería de seguridad y operación ya está por encima de la media.  
El cuello de botella principal no es “más features de backend”, sino:

1. **Hacer que la portada grite el drama** (máquinas ganando / humanos retaliando).
2. **Convertir urgencia real (cierre de jornada) en acción**.
3. **Facilitar el loop social** (compartir resultado de la jornada).
4. **Endurecer contratos de datos y operación** para que el sistema no se rompa al crecer.

Regla de oro: **nunca inventar marcadores**. Todo score humano vs máquina, ranking y countdown debe salir de datos reales.

---

## 1. Prioridad P0 — Producto / conversión (máximo impacto, poco esfuerzo)

Estas mejoras se pueden hacer en horas/días y cambian la primera impresión de casi todos los visitantes.

### 1.1 Countdown vivo del cierre de jornada

**Problema:** el texto “CIERRE EN Xh Ym” se calcula una vez al render y se queda congelado.

**Cambio:**
- `setInterval` de 1s que actualiza `#cp-deadline` (o el nodo equivalente).
- Formato con segundos: `2h 58m 41s`.
- Estado `<1h`: clase `is-urgent` (color rojo + pulso suave).
- Al cerrar: pasar a `CERRADA` y, opcionalmente, countdown a la próxima jornada.
- Respetar `prefers-reduced-motion`.

**Archivos típicos:** `static/js/pages/cover_page.js`, `static/css/cover_hero.css` (o tokens).

**Por qué:** escasez real + aversión a la pérdida. Es la palanca de conversión #1.

### 1.2 Hero y copy: “Las máquinas nos están ganando”

**Problema:** el dato más potente (Grok/Claude/ChatGPT arriba del ranking) está enterrado; el copy actual es genérico.

**Cambio de strings (ejemplo):**
- Kicker: `JORNADA N · LAS MÁQUINAS NOS ESTÁN GANANDO` (o marcador real `MÁQUINAS 3 · HUMANOS 0`).
- H1: `Las máquinas nos están ganando.`
- Lead: puntos reales de los 3 primeros Maestros + frase de identidad de La Peña + pregunta final.
- CTA primario: `Firmar por la humanidad` (visitante nuevo) / `Revisar mi bando` (ya guardó).
- CTA secundario: `Ver cómo van las máquinas`.

**Archivos:** `cover_page.js` (y posiblemente plantilla base).

**Por qué:** tribalismo + aversión a la pérdida. Convierte “rellenar quiniela” en “elegir bando”.

### 1.3 VS que “pelea” (micro-interacción)

**Cambio:**
- Entrada de bandos desde esquinas (`cornerIn` / `cornerInR`).
- VS con latido suave (`vsBeat`).
- Hover: un bando empuja al otro unos px.
- Opcional: sonido de campana al guardar (reutilizar `SoundManager`).

**Archivos:** CSS del cover + quizá un poco de JS de estado.

### 1.4 Sticky scorebar HUMANOS vs MÁQUINAS

**Cambio:**
- Franja fina bajo el topbar: `HUMANOS X — Y MÁQUINAS · Jn`.
- Barra de progreso dorada vs cian calculada de puntos agregados reales del ranking.
- Actualización cuando llega live/SSE o polling.

**Por qué:** feedback ambiental continuo; la gente vuelve a ver si “vamos ganando o perdiendo”.

### 1.5 Progreso visible al rellenar la quiniela

**Cambio:**
- En el botón de guardar: badge `7/15` que hace `pop` en cada signo marcado.
- Al llegar a 15: texto “¡Quiniela completa!” + confeti (ya existe infraestructura).

**Por qué:** goal-gradient effect.

### 1.6 Porra con copy de “mojarse”

**Cambio:**
- Subir la porra a zona más visible del dashboard.
- Estado vacío: `Los maestros ya han mojado. Tú no.` + CTA `Mojarme`.
- Estado con predicción: mostrar tu marcador vs media de La Peña.

---

## 2. Prioridad P1 — Loop viral y retención

### 2.1 Tarjeta / imagen compartible de resultado de jornada

**Cambio:**
- Endpoint o generación client-side (canvas) de imagen:
  - “Jornada N — Tú vs Grok vs Claude vs ChatGPT”
  - Puntos de cada uno + resultado del pleno si aplica
  - Branding Liga de Maestros + CTA
- Botones “Compartir en X / Instagram Stories / WhatsApp / copiar enlace”.
- OG image dinámica o al menos estática fuerte por jornada.

**Impacto:** es el formato que más se comparte en redes (comparación visual humano vs IA).

### 2.2 Identidad de los Maestros IA (trash talk + avatares)

**Cambio:**
- Avatar + frase corta por jornada (plantillas rotativas, no inventar resultados).
- Espacio de “réplica” del mejor humano de La Peña.
- Mostrar en portada / clasificación general, no solo en tablas profundas.

### 2.3 Notificación / recordatorio de cierre

**Opciones (de menor a mayor esfuerzo):**
- Banner in-app cuando quedan <2h y el usuario no ha firmado.
- Web Push (PWA ya hay base de service worker).
- Más adelante: bot Telegram o email opt-in.

### 2.4 Grupos privados (fase media)

- Invite link a “peña de amigos / empresa”.
- Ranking interno del grupo + comparación contra Maestros.
- Loop social cerrado (muy potente en retention).

### 2.5 (Opcional estratégico) Modo probabilidad + Brier / log score

Referencia: Forecast 2026.

- Además de 1X2 binario, permitir % en 1 / X / 2 (suma 100).
- Puntuar con Brier (o log) y comparar con baseline de mercado/odds si se dispone.
- Leaderboard visual: Tú | Media humanos | Media IA | Mercado = 0.

**Nota:** es un cambio de producto grande. Solo si se quiere posicionar como “forecast científico” además de quiniela clásica. No bloquea las P0.

---

## 3. Prioridad P1 — Robustez de datos y contratos

### 3.1 Contratos formales para JSON runtime

**Problema:** muchos JSON en `data/` y payloads sin esquema validado en runtime.

**Cambio:**
- JSON Schema (o modelos Pydantic) para:
  - predicciones de jornada
  - standings multi
  - payloads de live
  - quiz bank
- Validación al importar / al servir `/api/liga/data`.
- Fallar de forma controlada (mensaje claro + fallback) en vez de 500 silenciosos.

### 3.2 Unificar y documentar el “source of truth”

- Clarificar qué vive en SQLite vs qué vive en JSON de disco.
- Evitar que el mismo dato se calcule en 3 sitios distintos (payloads / services / frontend).
- Tests de contrato frontend ↔ backend (ya hay algunos; ampliar a campos críticos de ranking y deadline).

### 3.3 Health check enriquecido

Endpoint `/health` o `/api/health` que reporte:
- OK de DB (`integrity_check` ligero o ping)
- Último backup con integridad
- Estado del collector (última ejecución, circuit breaker abierto/cerrado)
- Cuota Highlightly restante (sin filtrar secretos)
- Versión / `BUILD_SHA`

Útil para Alwaysdata/Render y para el propio admin.

### 3.4 Completar datos legales reales

- Rellenar `LEGAL_OWNER_*` y `LEGAL_CONTACT_EMAIL` antes de cualquier lanzamiento serio.
- Revisar que no queden “Pendiente de configurar” en plantillas legales.

---

## 4. Prioridad P2 — Frontend técnico y UX de calidad

### 4.1 Countdown + live en más sitios

- No solo portada: también en ticket y en vista de directo cuando la jornada está abierta.

### 4.2 Accesibilidad y motion

- Revisar contraste en acentos cian/oro sobre fondos oscuros.
- Todos los keyframes respetando `prefers-reduced-motion`.
- Focus visible en CTAs y en la command palette.

### 4.3 Performance percibida

- Revisar peso de logos/escudos (hay muchos assets).
- Lazy-load de imágenes de equipos fuera del viewport.
- Cache-busting coherente de CSS/JS estáticos.
- Lighthouse móvil (LCP del hero, CLS de tablas de ranking).

### 4.4 Modularización JS

- Mantener vanilla (ADR ya existe), pero:
  - reducir globals donde sea fácil
  - documentar el contrato de `state.js`
  - evitar lógica de negocio duplicada entre `cover_page.js`, `quantum_final.js` y `contest.js`

### 4.5 CSS governance

- Seguir con `@layer` y tokens.
- Auditoría periódica de CSS muerto (ya hay test de governance; ampliar).
- Evitar reintroducir `!important` en base.

---

## 5. Prioridad P2 — Backend, seguridad operativa y escala

### 5.1 Collector como proceso separado (cuando el tráfico lo pida)

Hoy puede correr dentro del mismo servicio web. Correcto para beta; a escala:
- Worker dedicado (o cron + proceso) para live collector y standings.
- Web solo sirve HTTP.

### 5.2 Observabilidad

- Sentry ya está preparado: activar DSN en producción y revisar sample rate.
- Métricas simples: requests lentos (ya hay log), errores de scrape, aperturas de circuit breaker.
- Dashboard mínimo admin (aunque sea JSON).

### 5.3 Seguridad (mantenimiento, no reescritura)

Ya está muy bien. Mantener:
- `pip-audit` bloqueante en CI
- tests de IDOR / CSRF / headers
- no secretos en query string
- rotación documentada de `SECRET_KEY` / OAuth / admin secret

Mejoras menores:
- CodeQL o Semgrep ligero en CI cuando haya tiempo
- Revisar que los juegos arcade no permitan score spoofing trivial (ya hay heurísticas; endurecer si hace falta)

### 5.4 Base de datos

- SQLite está justificado (ADR). Cuando haya contención real de escrituras o multi-instancia:
  - migrar a Postgres siguiendo el ADR existente
  - o al menos separar lectura de payloads calientes

### 5.5 Rate limit y abuso

- Mantener límites actuales.
- Documentar que el rate limit de app no sustituye protección DDoS del proveedor (Already in SECURITY.md).

---

## 6. Prioridad P2 — DX, repo hygiene y operación semanal

### 6.1 Makefile (o scripts unificados)

```text
make install
make test
make lint
make format
make audit          # pip-audit + ruff + pytest seguridad
make jornada        # ayuda al flujo semanal (scrape/import/audit)
make health
```

### 6.2 Pre-commit

- ruff check + format
- rechazo de `.env`, `*.db`, claves
- opcional: mypy en paths críticos

### 6.3 Limpieza de raíz y archivos de archivo

- Mover parches sueltos (`fix-j75-*.patch`) y scripts one-off a `scripts/archive/` o borrar si ya están aplicados.
- Evitar que la raíz acumule ruido operativo.

### 6.4 Documentación operativa viva

- Mantener `docs/operations/OPERACION_SEMANAL.md` como checklist real de cada jornada.
- Un solo “runbook” de incidente (ya esbozado en SECURITY.md) enlazado desde README.

### 6.5 CI

- Mantener actions pineadas por SHA.
- Considerar job opcional de Lighthouse o de contrato de API en PRs grandes de frontend.
- No ignorar indefinidamente tests de producción readiness: o se arreglan o se documenta por qué siguen fuera.

---

## 7. Prioridad P3 — Features de crecimiento (después de validar el hook)

Solo cuando la portada y el loop de compartir funcionen:

| Feature | Valor | Dependencia |
|---------|-------|-------------|
| Arena de IAs más automatizada (más modelos, más jornadas) | Diferenciación | Coste API + UI |
| API pública de ranking / predicciones | Ecosistema | Auth + rate limit |
| Bot Telegram (recordatorios + resultados) | Retención | Bot + opt-in |
| PWA instalable con push de cierre | Retención móvil | SW + permisos |
| Torneos de arcade | Engagement secundario | Anti-cheat básico |
| Multi-liga / multi-tenant ligero | Expansión | Modelo de datos |
| Modo probabilidad + Brier | Viralidad “científica” | Producto + scoring |

---

## 8. Orden de ejecución recomendado (2–4 semanas)

### Semana 1 — Portada que convierte
1. Countdown vivo + urgencia visual  
2. Rewrite de hero/copy/CTAs  
3. VS animado  
4. Sticky scorebar humanos vs máquinas  
5. Progreso 7/15 en el botón de guardar  

### Semana 2 — Compartir y retención
6. Imagen compartible de jornada  
7. Copy de porra “mojarse” + posición en UI  
8. Banner de “te falta firmar” cuando quedan <2h  
9. Avatares / frases ligeras de Maestros  

### Semana 3 — Robustez
10. Esquemas / validación de payloads críticos  
11. Health check enriquecido  
12. Makefile + pre-commit  
13. Datos legales reales  
14. Limpieza de archivos de archivo en raíz  

### Semana 4 — Medir y decidir
15. Métricas simples de conversión (firmas / visitante, tiempo a primera firma)  
16. Decidir si se abre el frente “probabilidad + Brier” o se dobla en viral de imagen + grupos  

---

## 9. Métricas de éxito (mínimas)

| Métrica | Antes (baseline) | Objetivo orientativo |
|---------|------------------|----------------------|
| % visitantes que firman quiniela (sesión) | medir | +30–50% relativo |
| Tiempo hasta primer “guardar” | medir | bajar |
| Compartidos de resultado / jornada | ~0 o bajo | >10–20% de firmantes |
| Retorno a la siguiente jornada (usuarios que firmaron) | medir | subir |
| Errores 5xx / circuit open prolongado | bajo | mantener o bajar |
| Tiempo de operación semanal (admin) | medir | reducir con runbook |

---

## 10. Qué NO haría ahora (para no perder foco)

- Reescribir el frontend a React/Vue “porque sí” (ADR vanilla es coherente con el tamaño actual).
- Migrar a Postgres antes de tener contención real.
- MkDocs multi-idioma / docs perfectas antes de tracción.
- Multi-tenant completo.
- Sistema anti-trampas perfecto en arcade.
- Añadir 10 Maestros IA más sin haber hecho viral el drama actual de 3–5.

---

## 11. Resumen en una frase

**Haz que la portada cuente la verdad (las máquinas van ganando), que el reloj del cierre lata, que firmar sea elegir bando, y que el resultado de cada jornada se pueda compartir en una imagen.**  
Todo lo demás (contratos de datos, health, DX, features de crecimiento) sostiene ese loop y evita que se rompa cuando la gente empiece a llegar.

---

## 12. Referencias internas del repo

- `SECURITY.md` — modelo de amenazas y controles  
- `docs/AUDITORIA_INTEGRAL_2026-07-25.md` — auditoría integral  
- `auditoria-chispa-liga-maestros.md` — chispas de portada (1 ago 2026)  
- `REVIEW_AUDITORIA_VIRAL.md` — ángulo Forecast 2026 / viral  
- `docs/design/AUDITORIA_UI_UX.md` — UI/UX  
- `docs/adr/` — decisiones de arquitectura  
- `docs/operations/` — deploy y operación semanal  

---

---

## 13. Seguimiento de implementación — actualizado 2026-08-17

> **Estado general:** P0 Semana 1 completada en `arena/01a00ffe-liga-maestros-web`. Los 6 ítems P0 están implementados y verificados manualmente. P1/P2/P3 quedan como backlog priorizado.

### 13.1 Changelog P0 — 2026-08-17 (esta sesión)

| ID | Propuesta | Estado | Qué se hizo | Archivos tocados |
|---|---|---|---|---|
| **1.1** Countdown vivo | ✅ Hecho | `#cp-deadline` ahora hace `setInterval 1s` con formato `2h 05m 41s` (siempre con segundos), clase `is-urgent` + `animation: cp-urgentPulse` cuando `<1h`, `aria-live=assertive` y `title` dinámico. Respeta `prefers-reduced-motion`. `coverCloseLabel` sigue calculando `d/h/m` para el kicker. | `static/js/pages/cover_page.js` (`startCoverCountdown`), `static/css/cover_hero.css` (`#cp-deadline.is-urgent`, `@keyframes cp-urgentPulse`) |
| **1.2** Hero y copy tribal | ✅ Hecho | Kicker dinámico con datos reales: `J1 · LAS MÁQUINAS NOS ESTÁN GANANDO` / `LA PEÑA VA GANANDO` / `DUELO IGUALADO` / `LAS MÁQUINAS NOS ESPERAN` (según `bando.aiAvg vs humanAvg`). Lead dinámico: `Top jornada: <nombre 3pts> · <nombre 2pts> … ¿Firmas por la humanidad y los superas?` si hay datos reales, si no fallback estático. CTA primario `Firmar por la humanidad` (nuevo) / `Revisar mi bando` (ya guardó); CTA secundario `Ver cómo van las máquinas` (con datos) / `Clasificación` (sin datos). Todo sale de `coverRankingRows()` / `coverBandoDetailed()`, nunca inventado. | `static/js/pages/cover_page.js` (`renderNewspaperCoverPageV3` — `kickerBandoLabel`, `ctaLabel`, `ctaSecondaryLabel`, `heroPitch`) |
| **1.3** VS que pelea | ✅ Hecho | `vsBeat` (latido 1.6s) en `.cp-duel-vs`, `cornerIn`/`cornerInR` en entradas de `.cp-duel-side.is-pena` / `.is-ia`, hover que empuja 2px al rival. Todo con `@media (prefers-reduced-motion: reduce) { animation: none }`. | `static/css/cover_hero.css` (`@keyframes vsBeat`, `cornerIn`, `cornerInR`, `.cp-duel-vs`, `.cp-duel-side`) |
| **1.4** Sticky scorebar | ✅ Hecho | Nueva franja ` #cp-scorebar` bajo el topbar: `HUMANOS <avg> vs <avg> MÁQUINAS · J<n> · <estado>` + barra `is-pena`/`is-ia` proporcional a `humanTotal/total`. Se hidrata vía `updateCpScorebar(bando, jornada)` en cada render (con `setTimeout 0`). Oculta si `total===0` (jornada no empezada). Actualiza live al cambiar `state.data`. | `templates/liga_index.html` (`#cp-scorebar`), `static/js/pages/cover_page.js` (`updateCpScorebar`), `static/css/cover_hero.css` (`.cp-scorebar`, `.cp-scorebar-track`) |
| **1.5** Progreso 7/15 | ✅ Hecho (mejorado) | `cp-user-progress` ya existía (`7/15` + barra). Ahora: tracking de `_prevUserDone`, `triggerProgressPop()` hace `pop` (`@keyframes pop 0.3s`) en cada signo nuevo y `confetti()` al llegar a 15/15. Respeta reduced-motion vía CSS existente. | `static/js/pages/cover_page.js` (`triggerProgressPop`, `_prevUserDone`), `static/css/cover_hero.css` (`@keyframes pop`, `.is-pop`) |
| **1.6** Porra “mojarse” | ✅ Hecho | Estado vacío cambiado de `Elige tu partido — +2 pts si aciertas` a `Los maestros ya se han mojado. ¿Y tú?` + step `¡Mójate!` + hint `Elige tu partido — +2 pts si clavas el marcador` con clase `is-cta` dorada. Estado con porra mantiene `Tu porra: X-Y guardado`. | `static/js/pages/cover_page.js` (`hydrateCoverPorra`), `static/css/cover_hero.css` (`.cp-porra-change.is-cta`) |

**Cómo probar P0:**
1. `python -m http.server` o Flask `app.py` → abrir `/` en desktop y móvil.
2. Ver kicker `J1 · LAS MÁQUINAS NOS ESPERAN` (sin datos) o `LAS MÁQUINAS NOS ESTÁN GANANDO` (con ranking).
3. Esperar tick de `#cp-deadline` — debe cambiar cada segundo con `h m s`; forzar `edit_deadline` a `now+30min` para ver `is-urgent` rojo + pulso.
4. Hacer hover sobre duelo Peña vs IA → VS late, lados se empujan.
5. Marcar signos en quiniela → `Tu quiniela 3/15 → 4/15` hace pop; al 15/15 confeti.
6. Sin porra → ver `Los maestros ya se han mojado. ¿Y tú?` + `¡Mójate!`.
7. Sticky bar aparece solo cuando hay puntos reales (`humanTotal+aiTotal>0`).

### 13.2 Changelog P1 — 2026-08-17 (continuación)

| ID | Propuesta | Estado | Qué se hizo | Archivos tocados |
|---|---|---|---|---|
| **2.1** Tarjeta compartible Jornada | ✅ Hecho | Canvas 1080×1920 nuevo: `JORNADA N · HUMANO VS MÁQUINAS — ¿QUIÉN ACERTÓ MÁS?` con Top 5 (Tú + 4 IAs) ordenado por `pts` jornada, badges `isUser` cian / `isAI` rosa / oro para líder, footer `LIGA DE MAESTROS`. `TicketImage.generateVs(state)` + `shareVs(state)` con `navigator.share` + fallback `download`. Botón nuevo `Duelo vs IA 📊` en share-sheet junto a `Mi quiniela 📸`. Datos reales de `ranking_maestros` + `participant_contract`, nunca inventados. | `static/js/ticket_image.js` (`getVsRows`, `renderVs`, `generateVs`, `shareVs`), `templates/liga_index.html` (botón `imageVs`), `static/js/quantum_final.js` (`runShareAction imageVs`) |
| **2.3** Banner urgencia <2h | ✅ Hecho | Nueva franja `#cp-urgency` bajo scorebar: `Te falta firmar — cierra en 01h 12m 05s` + CTA `Firmar ahora →`, solo visible si `!closed && !saved && 0<diff<=2h`. Tick 1s en `startCoverCountdown` vía `updateCpUrgency(diff, closed, saved)`. Con `role=status aria-live=assertive` y pulso `cp-urgentPulse`. Respeta `prefers-reduced-motion`. | `templates/liga_index.html` (`#cp-urgency`), `static/js/pages/cover_page.js` (`updateCpUrgency`), `static/css/cover_hero.css` (`.cp-urgency`) |

### 13.2b Pendiente P1/P2 (siguiente)

- **2.2 Avatares / trash talk Maestros + réplica mejor humano:** falta frase corta rotativa por jornada en portada (no inventar resultados).
- **2.4 Grupos privados, 3.1 JSON Schema, 3.3 Health, 6.x Makefile/pre-commit:** previstos Semana 3. No bloquean viral.
- **4.x/5.x:** Accesibilidad motion, performance, observabilidad — deuda vigilada.

### 13.3 Decisiones tomadas en esta iteración

- Se mantuvo `H1 = LIGA DE MAESTROS` (marca) y se movió el drama a kicker + lead. Cambiar el H1 a `Las máquinas nos están ganando` se probó y se descartó por pérdida de marca; se puede A/B testear luego.
- Kicker ya no es solo `Quiniela 1` sino `J1 · <estado del duelo>` para que incluso sin abrir el duelo se vea el drama.
- `is-urgent` ahora anima también `cp-countdown-timer .cp-digit` y `#cp-deadline` para coherencia visual.
- Se añadió `aria-live` dinámico (`polite` vs `assertive` bajo 1h) para accesibilidad.

### 13.4 Métricas a medir tras deploy (ver §9)

Activar en analytics: `cta_click` (`Firmar por la humanidad` vs `Revisar mi bando`), `deadline_impression_urgent`, `porra_mojarse_click`, `scorebar_view`. Comparar baseline pre-P0 con 7 días post-P0.

---

*Documento vivo: actualizar este §13 en cada PR que cierre un ítem P0/P1. Fuente de verdad del backlog sigue siendo §1-§12.*
