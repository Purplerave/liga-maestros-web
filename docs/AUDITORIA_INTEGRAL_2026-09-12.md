# 🔎 Auditoría integral — Liga de Maestros Web

> **Fecha:** 12 de septiembre de 2026
> **Rama auditada:** `arena/01a094ec-liga-maestros-web` (base `main` @ `7cece2d`)
> **Alcance:** todo el sitio — portada/SPA (`/`, `/app`), landing (`/landing`), legales (`/ayuda`, `/privacidad`, `/cookies`, `/aviso-legal`), juegos, backend Flask, API, assets y repositorio.
> **Método:** arranque real de la app en local + inspección de código fuente + instrumentación (jsdom para el DOM renderizado, analizador propio de CSS muerto, `curl` para pesos/cabeceras/tiempos, `pytest`/`ruff`). **Cada hallazgo cita archivo y línea.** No se modificó código del repo.
> **Limitación declarada:** el sandbox no pudo descargar un binario de Chrome, así que no hay Lighthouse real. Las métricas de rendimiento son **medidas** (pesos, nº de peticiones, tiempos de API, DOM renderizado vía jsdom) y **estimadas** (waterfall/critical path a partir del código). Se indica en cada caso.

---

## 0. Resumen ejecutivo

**El concepto y la ingeniería de base siguen siendo de lo mejor que hay en un proyecto aficionado:** CSP real, rate limiting, ETag, backups verificados, borrado GDPR, middleware de seguridad, tests de gobernanza CSS, service worker y datos estructurados. No hay que rehacer nada de eso.

**Pero hay tres problemas estructurales que hoy lastran el producto**, y varios de ellos son *regresiones* respecto a auditorías previas del propio repo:

1. **La portada no pinta nada hasta completar un *waterfall* de 4 niveles** (27 CSS + 17 JS → API de 92 KB → `cover_page.js` de 45 KB → render). No hay ni un `<h1>` ni contenido en el HTML que sirve Flask: todo es client-side. Penaliza rendimiento percibido **y** SEO.
2. **El repo y la CI están en rojo y con grasa:** 1 test de seguridad falla en `main`, `ruff check` y `ruff format --check` fallan, y hay **~4 MB de artefactos muertos** trackeados (`.arena/`, `image-search/`, 41 duplicados CSS/JS con hash que nadie referencia).
3. **La capa móvil vuelve a estar por debajo del umbral** que la propia `AUDITORIA_MOVIL_2026-08-20` señaló: doble scroll con `height:100vh; overflow:hidden`, **149 reglas con fuente < 0.65 rem** (mínimo 8.3 px) y tablas con `min-width:1040px`.

### Top 10 acciones (por impacto/esfuerzo)

| # | Acción | Área | Severidad | Esfuerzo |
|---|--------|------|-----------|----------|
| 1 | Arreglar la CI en rojo: test de seguridad + `ruff` lint/format | Repo/CI | 🔴 Crítica | XS |
| 2 | Hacer cumplir `TRUSTED_HOSTS` (hoy se configura y **no se aplica**) | Seguridad | 🔴 Alta | S |
| 3 | Arreglar/borrar `escapeHtml` **roto** (no-op) en `features/shared/utils.js` | Seguridad | 🔴 Alta | XS |
| 4 | Live polling: usar `/api/liga/live` (75 B) o quitar `cache:"no-store"` para que el ETag/304 funcione (hoy baja 92 KB cada 30 s) | Rendimiento | 🔴 Alta | S |
| 5 | Añadir `<h1>` + contenido crítico SSR (o skeleton) en `liga_index.html` | SEO/Rend. | 🟠 Media | S |
| 6 | Comprimir la imagen de cabecera (236 KB PNG → WebP/AVIF + `srcset`) | Rendimiento | 🟠 Media | S |
| 7 | Borrar del repo `.arena/`, `image-search/` y los 41 duplicados con hash de `build.py` | Higiene | 🟠 Media | XS |
| 8 | Accesibilidad de la tabla quiniela (`scope`/`caption`) y de las 16 filas *clickables* no-`<button>` | A11y | 🟠 Media | M |
| 9 | Legibilidad móvil: erradicar fuentes < 0.75 rem y el `100vh; overflow:hidden` | Móvil/UX | 🟠 Media | M |
| 10 | Cablear analítica de verdad (hoy `LMAnalytics` no envía a ningún backend) | Producto | 🟡 Baja | S |

**Veredicto:** producto sólido y seguro por diseño, pero con **deuda de mantenimiento visible** (CI roja, código muerto, stubs) y una **capa de presentación que ha vuelto a derivar** en rendimiento y móvil. Todo es acotado y corregible sin tocar el stack.

---

## 1. Lo que ya está bien (no romper)

Confirmado por inspección, sirve de base para el resto:

- **Cabeceras de seguridad completas** en todas las rutas (`liga_maestros/__init__.py:170-230`): CSP con `frame-ancestors 'none'` en producción, `X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy`, HSTS condicional, `X-Request-ID` y `Server-Timing`.
- **CSRF global** sobre escrituras autenticadas (`__init__.py:120-133`) + validación de `Content-Type` (`135-146`) + bloqueo de *request smuggling* (`148-153`). Buenas defensas en profundidad.
- **Rate limiting** con cabeceras `X-RateLimit-*` visibles en `/api/liga/data`.
- **ETag + 304 + `Cache-Control`** en el API (`routes/liga_data.py:138-155`) y cacheo `immutable` de assets con fingerprint (`routes/main.py:96-105`).
- **Gobernanza CSS por `@layer`** (0 `!important`, test `test_css_governance.py`) y orden de cascada canónico declarado en el `<head>`.
- **SQLite WAL** con `busy_timeout`, `foreign_keys`, backups rotativos e `integrity_check`.
- **Datos estructurados** `schema.org/WebApplication`, `og:`/`twitter:` completos, `robots.txt` y `sitemap.xml`.
- **Service worker** con estrategia correcta: la API **nunca** va a Cache Storage (`static/sw.js:70-79`), estáticos cache-first, HTML network-first con fallback offline.
- **`escapeHtml` global correcto** (`static/js/utils.js:12-19`, usa el truco `"&"+"amp;"`) y aplicado de forma sistemática en el render activo.
- **Imágenes con `alt`:** en el DOM renderizado, 0 imágenes sin `alt`.

---

## 2. Hallazgos por área

Leyenda de severidad: 🔴 Crítica/Alta · 🟠 Media · 🟡 Baja. Cada uno lleva **evidencia** (archivo:línea), **impacto** y **propuesta**.

### 2.1 Salud del repo y CI 🔴

**H2.1 — La CI está en rojo en `main`.** `.github/workflows/ci.yml` ejecuta `ruff check .`, `ruff format --check .` y `pytest` como pasos **bloqueantes**. Reproducido en local:

- `pytest` → **1 fallo**: `tests/test_security_hardening.py::test_security_headers_host_validation_and_request_limits`. Espera `400` ante `Host: attacker.invalid` y recibe `200` (ver H2.2 — no es un test malo, es un bug real).
- `ruff check .` → **1 error**: `tests/test_j6_resultados_cruce.py:35:1 I001` (bloque de imports sin ordenar).
- `ruff format --check .` → **"1 file would be reformatted, 179 already formatted"** — y es **el mismo fichero** `tests/test_j6_resultados_cruce.py` (dos llamadas a `apply_q15_results_to_db` sin plegar). O sea: lint + format se arreglan con un solo `ruff format tests/test_j6_resultados_cruce.py`.

**Impacto:** si la CI refleja `main`, el *gate* de despliegue está fallando (o se está ignorando), lo que normaliza el rojo y deja pasar regresiones reales (como la de seguridad).
**Propuesta (XS):** `ruff check --fix . && ruff format .` (resuelve lint+format de golpe) + arreglar el test de seguridad arreglando el bug subyacente (H2.2). Añadir a `CONTRIBUTING` la regla "CI verde o no se mergea" y, si procede, un `pre-commit` que ya existe (`.pre-commit-config.yaml`) pero conviene verificar que corre `ruff`+`pytest`.

---

### 2.2 Seguridad 🔴

**H2.2 — `TRUSTED_HOSTS` se configura pero NO se aplica.** `liga_maestros/__init__.py:75-90` calcula `app.config["TRUSTED_HOSTS"]`, pero **no existe ningún `before_request` que valide `request.host`** contra esa lista (búsqueda global: sólo aparece escrito, nunca leído). Por eso el test de seguridad falla.

**Impacto:** sin validación de `Host`, hay superficie para *host-header injection* (envenenamiento de caché, resets de contraseña/links absolutos construidos con `url_for(_external=True)` como el `canonical`/`og:url` de la portada, que usarían el `Host` atacado). Mitigado en parte por el proxy de Alwaysdata/Render, pero la defensa declarada no existe.
**Propuesta (S):** añadir un `@app.before_request` que, cuando `app.config["TRUSTED_HOSTS"]` no sea `None`, compare `request.host.split(':')[0]` con la lista y devuelva `400` si no coincide. Esto hace pasar el test y cierra el hueco.

**H2.3 — `escapeHtml` ROTO (no-op) en el árbol ESM.** `static/js/features/shared/utils.js:3-11`:
```js
export function escapeHtml(text) {
  return String(text)
    .replace(/&/g, "&")   // ← reemplaza & por & (nada)
    .replace(/</g, "<")   // ← idem
    .replace(/>/g, ">")
    .replace(/"/g, "\"")
    .replace(/'/g, "&#039;");
}
```
Las entidades se colapsaron a literales: **no escapa nada**. Lo importa `static/js/features/arena/match-cards.js:3`, que construye HTML de tarjetas con `escapeHtml(name)`, `escapeHtml(score)`, etc. (`match-cards.js:22,51,55,84,86`).

**Impacto:** hoy es **código muerto** (ese árbol ESM no se carga: no hay `<script type="module">` ni `import()` que lo referencie — ver H2.7), así que no hay XSS activo. Pero es una **trampa latent**e: en cuanto alguien conecte el refactor ESM, inyecta XSS con nombres de equipo/comentarios. El `escapeHtml` global bueno (`utils.js`) y éste conviven y se confunden.
**Propuesta (XS):** o borrar el árbol `features/` muerto, o corregir este `escapeHtml` con el mismo truco `"&"+"amp;"` del global. Ideal: una única fuente de verdad.

**H2.4 — `Cache-Control: public` sobre un payload personalizado.** `routes/liga_data.py:150-154` responde `/api/liga/data` con `public, max-age=60` **incluyendo datos del usuario** (`ticket_guardado`, `predicciones_actuales` del `current_user_id`, `is_admin`). Hay `Vary: Cookie` (mitiga), pero `public` autoriza a caches compartidas/CDN a almacenarlo.
**Impacto:** riesgo de fuga entre usuarios si se pone una CDN que respete `public` y trate mal `Vary`.
**Propuesta (XS):** `private, max-age=60, must-revalidate` cuando haya sesión; `public` sólo para la variante anónima. O separar un endpoint público cacheable y uno privado `no-store`.

**H2.5 — Rutas de administración *hardcoded* a jornadas concretas.** `routes/live.py:433 /api/admin/reset-j75`, `:457 /api/admin/setup-j76`, `:551 /api/admin/debug-files`. Están protegidas por `protect_admin_api` (`__init__.py:112-118`), pero son endpoints de una sola jornada que quedaron fijos en el código.
**Impacto:** deuda y superficie de admin innecesaria; `debug-files` es info-disclosure si la auth de admin flaquea.
**Propuesta (S):** parametrizar (`/api/admin/reset-standings?j=`), mover `reset-j75`/`setup-j76` a un script de `tools/ops/`, y quitar `debug-files` de producción o gatearlo tras `FLASK_DEBUG`.

---

### 2.3 Rendimiento / Core Web Vitals 🔴🟠

**H2.6 — Waterfall de 4 niveles y 44+ peticiones antes de pintar. (medido)**
- La portada carga **27 `<link rel="stylesheet">` + 17 `<script defer>`** (`templates/liga_index.html:52-78` y `155-172`) = **44 recursos** de primer nivel, más Google Fonts, favicons, manifest y el logo.
- Peso crítico: **CSS 219 KB sin comprimir / 49 KB gzip · JS 201 KB / 59 KB gzip** (medido fichero a fichero).
- Ningún contenido pinta hasta: CSS+JS → `DOMContentLoaded` → `refreshData()` que hace `fetch('/api/liga/data')` (**92 KB**, `events.js:291`) → `renderArena()` que **inyecta `cover_page.js` (45 KB) en runtime** (`navigation.js:48`, vía `loadScriptOnce`) → entonces se renderiza la portada.
- El propio *skeleton* (`arena.js:52-56`) no aparece hasta que `utils/state/navigation/arena` se han parseado: antes hay **pantalla en blanco**.

**Impacto:** LCP y *first paint* tardíos, sobre todo en móvil/red lenta. Es el problema de rendimiento nº1.
**Propuesta (M):**
  1. **Concatenar/minificar** los 27 CSS en 1-2 hojas críticas (o al menos las de la portada) y los 17 JS en 1 bundle de arranque. Sin build moderno, un script tipo `build.py` que concatene+minifique basta (ADR-0002 dice "vanilla sin build", pero ya hay `build.py`).
  2. **Cargar `cover_page.js` de entrada** (es la vista por defecto) en vez de inyectarlo en runtime, o incluirlo en el bundle de arranque → elimina un nivel del waterfall.
  3. **Precargar el API** con `<link rel="preload" as="fetch" href="/api/liga/data" crossorigin>` para solapar la petición con la descarga de JS.
  4. **SSR del skeleton** (ver H2.10) para que haya algo pintado en el primer byte.

**H2.7 — El live polling baja 92 KB cada 30 s y el ETag no sirve de nada. (medido)**
`events.js:291` → `fetch('/api/liga/data?j=...', { cache: "no-store" })`. Con `no-store` el navegador **no revalida ni manda `If-None-Match`**, así que el ETag/304 del servidor (`liga_data.py:139-155`) **nunca se aprovecha**: cada tick transfiere los 92 KB completos. Y eso que existe `/api/liga/live` que pesa **75 B** (medido).
**Impacto:** en jornada, cada cliente abierto descarga ~92 KB cada 30-45 s (≈11 MB/hora por pestaña) y el servidor recalcula standings+multi-liga en cada petición. Escala mal y gasta datos móviles.
**Propuesta (S):**
  - Polling ligero contra `/api/liga/live` (o un delta con sólo `partidos`+firmas) y **sólo** re-descargar `/api/liga/data` cuando cambie la firma.
  - Si se sigue usando `/api/liga/data`, **quitar `cache:"no-store"`** para que el 304 funcione (el SW ya evita cachear la API en disco, `sw.js:70-79`, así que no hay riesgo de datos privados persistentes).
  - En servidor: no reconstruir `multi_league_standings` (20 KB, lo más gordo del payload) si la petición es de polling; cachearlo igual que `standings`.

**H2.8 — Imagen de cabecera de 236 KB, sin WebP/AVIF ni `srcset`. (medido)**
`templates/liga_index.html:82` carga `img/ligademaestroslogo_trans.png` = **236 KB** (PNG sin optimizar). No hay ningún `.webp`/`.avif` en `static/img` y ninguna imagen usa `srcset`/`sizes`. Además es `loading="lazy"` estando *above the fold* (debería ser `eager` + `fetchpriority="high"` si se queda, o mejor aligerarla).
**Impacto:** 236 KB bloqueando/demorando el LCP visual de la cabecera. `og-image.png` son otros **449 KB** (sólo social, no pinta en página, OK).
**Propuesta (S):** convertir a **WebP/AVIF** (el logo con transparencia suele quedar en <30 KB), servir `<picture>` con fallback PNG, `width`/`height` explícitos (evita CLS) y `srcset` para móvil. Aplicar lo mismo a los 165 logos de `static/img/team_logos/` (2.3 MB en total; hay SVG de banderas de 200-234 KB con raster embebido, p.ej. `NAT_BOLIVIA.svg` 234 KB).

**H2.9 — `build.py` genera 41 duplicados con hash que nadie usa. (medido)**
`build.py` copia cada CSS/JS a `nombre.<hash>.css` y escribe `static/manifest.json`. Pero las plantillas versionan con `?v={{assets_v}}` (`main.py:_get_assets_version` recorre todo `static/` y usa el mtime máximo), **no** con el manifest. Resultado: **41 ficheros duplicados byte a byte (534 KB)** trackeados en git y **0 referencias** (verificado con `grep`), y `static/manifest.json` que sólo lee… nadie (`utils.py:192` lee `img/team_logos/manifest.json`, otro fichero).
**Impacto:** grasa en repo y deploy, y dos sistemas de cache-busting a medias que se pisan conceptualmente.
**Propuesta (XS):** decidir **un** sistema. O (a) usar de verdad `build.py`+manifest en las plantillas y borrar los `?v=` manuales, o (b) borrar `build.py`, los 41 duplicados y `manifest.json`. Lo simple: (b) + `?v=` con el SHA del commit.

**H2.10 — ~9.6% de CSS muerto. (medido, heurístico)**
Analizador propio sobre las 37 hojas: **241 de 1928 reglas** referencia clases que no aparecen en ningún HTML/JS → **~31 KB** muertos. Peores: `pages/ticket.css` (46.5% muerto, 11.6 KB), `pages/contest.css` (20%), `themes/newspaper/ticket_readability.css` (36.7%), `mobile_responsive.css` (46%).
**Impacto:** peso y complejidad de cascada innecesarios.
**Propuesta (M):** pasada de PurgeCSS/`csstree` contra el corpus HTML+JS en el build, o limpieza manual de los ficheros con más %. Cuidado con clases generadas dinámicamente (`is-*`): mantener safelist.

---

### 2.4 SEO y renderizado 🟠

**H2.11 — Cero contenido *server-rendered*: sin `<h1>`, `<main>` vacío. (medido)**
El HTML que sirve Flask para `/` tiene el `<main class="main-arena">` con un `<section id="matches-body">` **vacío** y **ningún `<h1>`** (verificado con `curl | grep '<h1'` → 0 resultados). El `<h1>LA PEÑA vs MÁQUINAS` y toda la tabla se inyectan con JS (`cover_page.js:498`). El *structured data* y los `meta` están bien, pero el cuerpo no.
**Impacto:** Google renderiza JS, pero con presupuesto limitado y latencia; cualquier crawler/preview de redes que no ejecute JS ve una página vacía. El `/landing` sí tiene contenido SSR, pero `/` (la canónica principal) no.
**Propuesta (M):**
  - Mínimo: **SSR del `<h1>` y un skeleton/contenido semántico** en `liga_index.html` (Jinja ya tiene `jornada` y `user`), de modo que el primer byte traiga título y estructura.
  - Ideal: hidratar server-side la tabla de la quiniela (los 15 partidos) con Jinja y que el JS la mejore (*progressive enhancement*). Los datos ya están en el backend (`build_jornada_matches`).

**H2.12 — `/landing`: canonical/og:url relativos y JSON-LD con URL relativa.** `templates/landing.html:9,15,42` usan `href="/landing"` y `"url":"/landing"` (relativos). Los absolutos de `og:url`/`canonical` y el `url` de JSON-LD deberían ser absolutos (`main.index` sí usa `url_for(_external=True)`).
**Impacto:** algunos validadores/procesadores de OG y rich-results rechazan URLs relativas.
**Propuesta (XS):** `url_for('main.landing', _external=True)` en canonical/og:url/JSON-LD.

---

### 2.5 Accesibilidad 🟠 (medido sobre el DOM renderizado con jsdom)

**H2.13 — Tabla de la quiniela sin `scope` ni `<caption>`.** En portada y en TICKET, la tabla renderiza **11 `<th>` con 0 `scope`** y sin `<caption>` (medido). Es la tabla de datos central del producto.
**Impacto:** lectores de pantalla no asocian cabeceras a celdas → la quiniela es ininteligible con NVDA/VoiceOver.
**Propuesta (S):** `scope="col"` en `<th>` de cabecera y `scope="row"` en la 1ª columna; `<caption class="sr-only">` describiendo la tabla. Está en `cover_page.js` (tabla `.cx-boleto-table`) y `ticket_page.js`.

**H2.14 — 16 elementos *clickables* que no son botones ni enlaces.** En la portada, **16 nodos** con `data-page-action` sobre `<tr>`/`<div>`/`<td>` (`cover_page.js:606` `<tr data-page-action="TICKET">`, `:672` `.cx-live-card`, `:733` `.cx-porra`) que responden al clic delegado (`events.js:96-104`) pero **no son foco por teclado ni anuncian su rol**.
**Impacto:** inalcanzables con teclado/lector. Es la interacción principal ("ir a la quiniela").
**Propuesta (M):** convertir a `<button>`/`<a href>` reales (mejor: `<a>` a `/?view=TICKET`, que ya es *deep-linkable*), o añadir `role="button"`+`tabindex="0"`+manejador `keydown` (Enter/Space). Preferible enlace real por SEO y por el H2.16.

**H2.15 — Input de la paleta de comandos sin nombre accesible.** `command_palette.js:153-155`: `<input class="cmdk-input" role="combobox" placeholder="Busca…">` **sin `aria-label` ni `<label>`** (medido: aparece como control sin nombre en todas las vistas).
**Impacto:** el `role="combobox"` exige nombre accesible; `placeholder` no cuenta de forma fiable.
**Propuesta (XS):** `aria-label="Buscar vista, jornada o acción"`.

**H2.16 — Navegación por `replaceState`: el botón Atrás no viaja entre vistas.** `navigation.js:249 syncUrlState()` usa `history.replaceState`, y los *deep links* `<a href="/?view=NEWS_PAGE">` (`cover_page.js:742`) son interceptados con `preventDefault()` (`events.js:98`).
**Impacto:** el usuario no puede volver con Atrás a la vista anterior; compartir/renombrar pestañas se rompe; y los `<a>` que no navegan de verdad confunden. Además la analítica de "page_view" no se dispara por vista.
**Propuesta (S):** usar `pushState` en cambios de vista reales + manejar `popstate`; dejar que los `<a href>` internos naveguen de verdad (con interceptación sólo para el estado, no para cancelar).

**H2.17 — `aria-live="polite"` en el contenedor que se re-renderiza entero.** `liga_index.html:120` `<section id="matches-body" aria-live="polite">` y `renderArena()` hace `container.innerHTML = …` en cada tick del directo (`arena.js:52+`).
**Impacto:** el lector de pantalla puede re-anunciar la página entera cada 30 s; y el `innerHTML` completo **destruye el foco** si el usuario estaba interactuando.
**Propuesta (M):** acotar el `aria-live` a la zona de marcador/comentarista (ya hay `patchLiveArena()` que hace parches quirúrgicos: extender esa vía y evitar el re-render total). Quitar `aria-live` del contenedor raíz.

---

### 2.6 Móvil y legibilidad 🟠 (regresión vs `AUDITORIA_MOVIL_2026-08-20`)

**H2.18 — Doble scroll: `height:100vh; overflow:hidden` en el app shell.** `static/css/layout/app_shell.css:6-7,14,18,22,…` (10+ reglas `overflow:hidden`). Es el anti-patrón que la auditoría móvil de agosto señaló; sigue ahí en la portada v19.
**Impacto:** en móvil el contenido queda atrapado en scroll interno anidado; `100vh` (no `dvh`) se solapa con la barra del navegador. Hay 14 usos de `dvh` en el CSS pero **no** en el shell.
**Propuesta (M):** en móvil, contenedor de scroll nativo (`min-height:100dvh`, sin `overflow:hidden` global) y reservar `overflow:hidden` sólo a widgets concretos (ticker, tablas con scroll propio).

**H2.19 — 149 reglas con fuente < 0.65 rem; mínimo 8.3 px. (medido)**
`grep` sobre el CSS activo: **149** `font-size:0.[0-6]*rem`, con `0.52rem` (≈8.3 px) y varios `0.55rem` en `cover_hero.css` y `command_center.css` (la portada y el HUD nuevos).
**Impacto:** ilegible en teléfono; por < 16 px además dispara el auto-zoom de iOS en inputs.
**Propuesta (M):** suelo tipográfico de **0.75 rem (12 px)** para texto y **≥16 px** en inputs. La auditoría de agosto ya lo pedía; la portada v19 lo re-introdujo. Añadir un **test de gobernanza** (como el de `!important`) que falle si aparece `font-size < 0.7rem`.

**H2.20 — Tabla con `min-width:1040px` obliga a scroll horizontal.** `themes/newspaper/ticket_compact.css:246`.
**Impacto:** el gesto de "arrastrar la tabla" en móvil. Sólo Quiniela tenía transformación a tarjetas ≤700px; el resto depende de scroll horizontal.
**Propuesta (M):** apilar a tarjetas también en Directo/Ligas (la auditoría móvil lo detalla), o `min-width` responsivo con `clamp()`.

---

### 2.7 Arquitectura y calidad del frontend 🟠

**H2.21 — Refactor ESM a medias, duplicado y muerto.** Conviven dos árboles que hacen lo mismo:
- Global (activo, por `<script>`): `arena.js` con `renderMatchCard`, `initLazyMatchRendering`, `lazyMatchPlaceholder` (`arena.js:8,28,316`).
- ESM (muerto, sin cargar): `static/js/features/arena/match-cards.js`, `features/arena/lazy.js`, `features/shared/*.js` — que **duplican** esas funciones y además arrastran el `escapeHtml` roto (H2.3).

Ningún `<script type="module">` ni `import()` referencia `features/arena/*` (verificado). Sólo `games_hub.js:19` importa de verdad `snake/index.js`.
**Impacto:** confusión ("¿cuál es el bueno?"), riesgo de arreglar el fichero equivocado, y el XSS latente.
**Propuesta (S):** decidir. Si el futuro es ESM, migrar de verdad (módulos + un bundler ligero) y borrar los globales; si no, **borrar `static/js/features/arena` y `features/shared`** y dejar `snake/` (que sí se usa).

**H2.22 — ~10 funciones *stub* vacías en la portada v19.** `cover_page.js:15-17,45,82-85,208-209`: `loadSacramentoFont(){}`, `hydrateCoverTypewriter(){}`, `startCoverScorebar(){}`, `updateCpUrgency(){}`, `setTrashTalkIdx(){}`, `startTrashTalkRotation(){}`, `triggerProgressPop(){}`, `loadSeasonSummary(){}`, `updateCoverPorraStep(){}`, `hydrateCoverPorra(){}`; y `coverBandoState()` devuelve `"primera"` fijo, `coverTrashTalkMasters()` devuelve `[]`. `arena.js:69,134` **llama** a varias de ellas.
**Impacto:** *scaffolding* de features que no hacen nada (typewriter, scorebar, trash-talk rotativo, season summary). Se carga CSS para ello (`typewriter_system.css` está en el `<head>`, `hydraulateCoverTypewriter` está vacío) → peso y falsas expectativas. También hay un bloque `<div hidden class="cp-legacy-stubs">` con texto literal `"stub"` (`cover_page.js:861-887`).
**Propuesta (S):** o implementar, o eliminar stubs + su CSS + el bloque legacy. Un test que detecte `function X() {}` vacío en ficheros de página evitaría que vuelva.

**H2.23 — `renderArena()` es un *god-dispatcher* de ~180 líneas con `innerHTML` gigante.** `arena.js:52-303`: un solo `if/else` por vista que reconstruye todo el DOM con plantillas de string. Funciona, pero es difícil de testear y provoca los re-renders completos (H2.17).
**Impacto:** mantenibilidad y rendimiento (foco/scroll perdidos).
**Propuesta (M):** extraer cada vista a su propio módulo de render con *patching* incremental (ya existe la idea en `patchLiveArena`/`patchTicketArena`); generalizarla.

---

### 2.8 Backend / API / datos 🟠

**H2.24 — El payload incumple su propio contrato en TODA petición. (medido en log)**
Cada `/api/liga/data` registra: `liga_data payload no encaja con schema: jornada: string_type; consenso_pleno_pena: list_type`. O sea, `jornada` va como string donde el schema espera otro tipo y `consenso_pleno_pena` es `dict` donde se espera `list`.
**Impacto:** la validación de contrato (`validate_liga_data`) es **no-bloqueante** (sólo loguea), así que no protege de nada y además **spamea el log en cada request** (ruido que tapa problemas reales). Un contrato permanentemente en *drift* es un contrato inútil.
**Propuesta (S):** alinear el schema con la realidad (o el payload con el schema) para `jornada` y `consenso_pleno_pena`; y decidir si la validación debe ser bloqueante en CI (test de contrato) pero no en runtime.

**H2.25 — Payload monolítico de 92 KB para todas las vistas. (medido)**
Desglose medido de `/api/liga/data`: `multi_league_standings` **20.7 KB**, `standings` 9.9 KB, `all_league_matches` 8.0 KB, `partidos` 6.2 KB, resto menor. La portada no necesita `multi_league_standings` (sólo la vista Ligas).
**Impacto:** TTFB/parse inflados en cada carga y en cada poll (H2.7).
**Propuesta (M):** endpoints por vista (`/api/liga/standings` y `/api/liga/matches` ya existen) y que cada vista pida lo suyo; dejar `/api/liga/data` como "núcleo de portada" slim.

**H2.26 — `/health` y `/metrics` públicos sin auth.** `routes/main.py:130-205` (`/health` revela tamaño de BD, estado de backups, cuota de Highlightly) y `/metrics` (Prometheus) expuesto. En local respondieron 200 sin credenciales.
**Impacto:** disclosure operativo a cualquiera que conozca la URL.
**Propuesta (S):** proteger `/metrics` y el `/health` enriquecido tras token/admin (dejar un `/health` mínimo público `{status:"ok"}` para el probe del PaaS).

---

### 2.9 Higiene del repositorio 🟠 (medido)

**H2.27 — Artefactos de sesión y de diseño trackeados en git.**
- `.arena/mockup_cover_v2.png` y `v3.png`: **2.9 MB** de mockups de una sesión de Arena, commiteados. `.gitignore` **no** incluye `.arena/`.
- `image-search/*.jpg`: **10 JPG (~1 MB)** de referencia de diseño, trackeados.
- Los 41 duplicados con hash (H2.9): **534 KB**.
- Working tree 16 MB + `.git` 8.4 MB; `static/img` 3.3 MB PNG + 1.07 MB SVG; `team_logos/` 2.3 MB en 165 ficheros.

**Impacto:** repo y deploy hinchados, clones lentos, ruido en diffs. Los mockups de `.arena` no pintan nada en la app.
**Propuesta (XS):**
  - `git rm -r --cached .arena image-search` y añadir `.arena/` e `image-search/` a `.gitignore`.
  - Borrar los 41 duplicados con hash (H2.9).
  - Optimizar/externalizar logos (H2.8) y considerar Git LFS o un CDN para `static/img` si sigue creciendo.

---

## 3. UX y producto 🟡

**H2.28 — La analítica no está cableada a ningún backend.** `static/js/analytics.js` define `LMAnalytics` que intenta `window.plausible/umami/posthog/__LM_ANALYTICS__` y, si no, sólo `console.debug` en localhost. **Ninguna plantilla carga Plausible/Umami/PostHog ni define `__LM_ANALYTICS__`** (verificado). Hay `data-analytics="share_click"`, `cta_click`, etc. por todos lados y hasta un CTA "first_pick_anon" que llama a `gtag` (`events.js:179`) — pero **`gtag` no existe**.
**Impacto:** todo el embudo de conversión que el equipo cree medir (`ROADMAP_VIRAL`, `Makefile demo` lee "conversión portada") **no se está midiendo**. Se toman decisiones a ciegas.
**Propuesta (S):** elegir un proveedor privacy-first (Plausible/Umami self-hosted encaja con el ADN AGPL), cargar su snippet y definir `window.__LM_ANALYTICS__`. Eliminar la referencia muerta a `gtag`. Verificar eventos clave: `page_view` por vista, `first_pick_anon`, `save_ticket`, `share_*`, `login`.

**H2.29 — CTA "brutal" anónimo con `role="alert"` y estilos inline.** `events.js:181-193` crea un `<div role="alert">` fijo con `style.cssText` larguísimo y texto `LLEVAS X/15 — GUARDA Y HUMILLA A LA IA →`.
**Impacto:** `role="alert"` interrumpe al lector de pantalla con publicidad; estilos inline no gobernanos por tokens; el tono "humilla" puede no encajar en todos los contextos.
**Propuesta (S):** usar `role="status"` (no urgente), clases CSS con tokens, y hacer el copy testeable (A/B) en vez de fijo.

**H2.30 — Empty states y estados de error correctos, pero mejorables.** Hay buenos empty states (`"Ahora mismo no hay partidos en directo"`, `"Sin datos"`), banner de datos *stale* (`arena.js:236-243`) y fallback offline en el SW. Bien. Propuesta menor: unificar el copy de error del API (hoy `refreshLiveSnapshot` sólo hace `console.warn`, el usuario no se entera de que el directo falló).

---

## 4. Plan de acción priorizado

### P0 — Esta semana (crítico, esfuerzo bajo)
1. **CI verde** (H2.1): `ruff --fix` + `ruff format` + arreglar el test de seguridad vía H2.2. *(XS)*
2. **Aplicar `TRUSTED_HOSTS`** con un `before_request` (H2.2). *(S)*
3. **`escapeHtml` roto**: borrar árbol ESM muerto o corregirlo (H2.3 + H2.21). *(XS)*
4. **Live polling**: quitar `cache:"no-store"` (activa ETag/304) o pasar a `/api/liga/live` (H2.7). *(S)*
5. **Higiene git**: fuera `.arena/`, `image-search/` y 41 duplicados con hash (H2.27 + H2.9). *(XS)*

### P1 — Próximas 2-3 semanas (alto impacto)
6. **Imagen de cabecera** WebP/AVIF + `srcset` + dimensiones (H2.8). *(S)*
7. **SSR del `<h1>`+skeleton** en `liga_index.html`; canonical absoluto en `/landing` (H2.11 + H2.12). *(S)*
8. **Bundle/minify** de los 27 CSS + 17 JS de arranque y cargar `cover_page.js` de entrada (H2.6). *(M)*
9. **A11y tabla** (`scope`/`caption`), **16 clickables** a botones/enlaces reales, **`aria-label`** en cmdk (H2.13/14/15). *(M)*
10. **Analítica cableada** de verdad (H2.28). *(S)*
11. **Contrato de datos**: alinear schema `jornada`/`consenso_pleno_pena`; parar el log-spam (H2.24). *(S)*
12. **`/metrics` y `/health` enriquecido** tras auth (H2.26). *(S)*

### P2 — 1-2 meses (calidad/escala)
13. **Móvil de verdad**: quitar doble scroll (`100vh;overflow:hidden`→`dvh`+scroll nativo), suelo tipográfico 0.75 rem + test de gobernanza, tarjetas en Directo/Ligas (H2.18/19/20). *(M)*
14. **Payload por vista** en vez del monolito de 92 KB (H2.25). *(M)*
15. **Purga de CSS muerto** (~31 KB) integrada en build (H2.10). *(M)*
16. **Navegación con `pushState`+`popstate`** y `<a>` que navegan de verdad (H2.16). *(S)*
17. **Refactor de `renderArena`** a módulos por vista con *patching* incremental; eliminar stubs vacíos y bloque legacy (H2.22/23 + H2.17). *(L)*
18. **Rutas admin** parametrizadas, fuera los `reset-j75`/`setup-j76` hardcoded (H2.5). *(S)*

---

## 5. Métricas de éxito (cómo verificar la mejora)

| Área | Métrica | Hoy (medido/estimado) | Objetivo |
|------|---------|-----------------------|----------|
| CI | tests + lint verdes | 1 test + lint + format en rojo | 0 |
| Rendimiento | recursos de 1er nivel en `/` | 44 (27 CSS + 17 JS) | ≤ 8 |
| Rendimiento | peso crítico gzip | ~108 KB (49 CSS + 59 JS) | < 60 KB |
| Rendimiento | datos por poll de directo | 92 KB cada 30 s | < 1 KB (delta/304) |
| Rendimiento | imagen cabecera | 236 KB PNG | < 40 KB WebP/AVIF |
| SEO | `<h1>`+contenido en HTML crudo | 0 (todo JS) | H1 + skeleton SSR |
| A11y | `<th scope>` en tabla quiniela | 0 de 11 | 11 de 11 |
| A11y | clickables no-teclado | 16 | 0 |
| Móvil | reglas con fuente < 0.7rem | 149 | 0 |
| Repo | grasa trackeada muerta | ~4.4 MB | ~0 |
| Producto | eventos de analítica reales llegando | 0 (sin backend) | embudo completo |

**Lighthouse:** al no poder ejecutarse aquí (sin binario de Chrome en el sandbox), recomiendo correr `lighthouse https://ligademaestros.alwaysdata.net --preset=perf --form-factor=mobile` antes/después del P1 y fijar Performance ≥ 90 y Accessibility ≥ 95 como *gate*.

---

## Anexo A — Waterfall de la portada (estimado a partir del código)

```
HTML /  (12.4 KB, Cache-Control: no-store)
  └─▶ 27× CSS (219 KB / 49 KB gzip)  ─┐ bloquean render
  └─▶ 17× JS defer (201 KB / 59 KB gzip)
  └─▶ Google Fonts (Bebas Neue + Outfit 400-800 + JetBrains Mono)
  └─▶ logo cabecera PNG (236 KB)
        │  DOMContentLoaded
        ▼
     refreshData() ─▶ fetch /api/liga/data (92 KB, ~40 ms local)
        ▼
     renderArena() ─▶ inyecta cover_page.js (45 KB) en runtime   ← 4º nivel
        ▼
     render portada + fetch /api/porra + /api/noticias/radar + /api/season-summary
        ▼
     cada 30-180 s: fetch /api/liga/data (92 KB, cache:no-store → ETag inútil)
```

## Anexo B — Reproducción de las mediciones

```bash
# arranque local
cp .env.example .env  # SECRET_KEY=… FLASK_DEBUG=1
python app.py         # http://127.0.0.1:5000

# pesos y cabeceras
curl -s -o /dev/null -w "%{http_code} %{size_download}B %{time_total}s\n" localhost:5000/api/liga/data
curl -s localhost:5000/api/liga/live | wc -c          # 75 B
curl -s localhost:5000/ | grep -c '<h1'                # 0

# calidad
python -m pytest -q --ignore=tests/test_ensure_jornada_completa.py --ignore=tests/test_production_readiness.py
ruff check .            # 1 error (test_j6_resultados_cruce.py:35 I001)
ruff format --check .   # 1 file would be reformatted

# grasa del repo
git ls-files | grep -E '^\.arena/|^image-search/'        # 12 ficheros
git ls-files static | grep -E '\.[a-f0-9]{8}\.(css|js)$' # 41 duplicados
```

---

*Informe generado por revisión estática + arranque real en local. Ningún hallazgo es opinión sin evidencia: todos citan archivo:línea o una medición reproducible del Anexo B. Los marcados "(medido)" se obtuvieron ejecutando la app; "(estimado)" se derivan del código.*
