# Auditoría exhaustiva — Liga de Maestros

**Fecha:** 2026-09-26 · **Commit base:** `f4466064` · **Método:** 4 auditorías de solo lectura + verificación manual de los hallazgos críticos
**Alcance:** portada, TICKET, backend, head/SEO/assets, service worker, tests, CI y datos.
**Resultado:** **91 hallazgos** (10 críticos, 21 altos, 38 medios, 22 bajos).

---

## Diagnóstico en una frase

La web **funciona y es visualmente cuidada**, pero está sostenida por una red de seguridad que en gran parte **no existe**: la CI no puede fallar, el service worker sirve páginas legales obsoletas, la vista TICKET carga scripts que no existen, y varios stubs en JavaScript pisan las implementaciones reales. Nada de esto rompe el resultados de hoy; todo ello rompe **el día que algo cambie**.

---

## Bloque 0 — Por qué esto importa más de lo que parece

| Mito | Realidad |
|---|---|
| "La CI está verde" | Verde por construcción: el exit code es el de `tail`. No detecta ni una regresión. |
| "Los datos de la BD están limpios" | `tests/test_arena_feedback_fixes.py` escribe en la BD real: hay una **jornada 999 con 20 filas basura**. |
| "`git status` limpio significa repo limpio" | Falso: los tests reescriben `data/MULTI_STANDINGS.json` (versionado) en cada `create_app()`. |
| "El service worker acelera la web" | Cachea `/privacidad` y `/cookies` **para siempre** y cachea tu página de cuenta con tu nombre y email. |
| "El JS de la portada está limpio" | Dos `setInterval` de 1 Hz que se acumulan en cada re-render, y dos countdowns que se pelean por el mismo nodo. |
| "El TICKET renderiza la porra y el directo Q15" | `ticket_page.js` **no se carga**, y sus stubs pisan las implementaciones reales de `quantum_final.js`. |

---

## CRÍTICOS (10)

### C1 — La CI no puede fallar aunque los tests fallen
`.github/workflows/ci.yml:74`
```bash
python -m pytest ... 2>&1 | tail -50
```
Sin `shell: bash`, GitHub ejecuta `bash -e {0}` **sin `-o pipefail`**. El exit code del pipeline es el de `tail`: **siempre 0**. `--cov-fail-under=50` tampoco se vigila. Los ~60 tests del repo son decorativos.

**Fix:** `shell: bash` + `set -o pipefail` en el step (y en cualquier otro con pipeline).

### C2 — La puerta anti-secretos es un regex roto
`.github/workflows/ci.yml:49` y `deploy-alwaysdata.yml:37`
```bash
grep -Ei '(^|/)(\\.env|.*\\.(db|sqlite|sqlite3|pem|key)|id_rsa|id_ed25519)$'
```
Dentro de comillas simples, bash entrega `\\.` literalmente: exige `<backslash><cualquier>env`. Un fichero `.env` **nunca** casa. Hay `DATOS/LIGA_MAESTROS_PRO.db` y 12 backups `DATOS/*.bak_*.db` (~7,5 MB) en el árbol de trabajo esperando un `git add -f`.

**Fix:** `(\.env|.*\.(db|sqlite|sqlite3|pem|key)$|id_rsa$|id_ed25519$)`.

### C3 — El service worker intercepta POST y rompe el borrado de cuenta
`static/sw.js:124` con `Service-Worker-Allowed: /` (`main.py:113`) y `scope:"/"` (`sw_register.js:12`).
La rama por defecto `networkFirst` intercepta **también POST**, y `cache.put()` con request no-GET lanza `TypeError` → `throw new Error('Offline')`. `POST /cuenta/eliminar` (`legal.py:97`) y todos los formularios **fallan**.

**Fix:** `if (request.method !== 'GET') { event.respondWith(fetch(request)); return; }` antes del `respondWith`.

### C4 — El service worker cachea páginas legales sin caducidad
`static/sw.js:146-159`, `:150-152`.
`networkFirst` guarda en `CACHE` toda respuesta 2xx **sin TTL ni `maxEntries`**: `/privacidad`, `/cookies`, `/aviso-legal`, `/ayuda`, una entrada por cada `/?j=N`. Offline se sirve **política de privacidad y cookies obsoleta indefinidamente**. Además ignora `Cache-Control`: `/cuenta` recibe `no-store, private` y el SW lo guarda igual (nombre y email legibles en Cache Storage).

**Fix:** respetar `no-store`/`private`, poner caducidad de 24 h, y excluir `/api/`, `/cuenta` y páginas de navegación.

### C5 — `ticket_page.js` no se carga: el TICKET nunca renderiza
`templates/liga_index.html:164-178` y `static/js/late_assets.js:44-54` **no lo incluyen**. Sus funciones (`renderLiveScrutinyBadge`, `renderTicketCommentsPanel`, `renderArenaTensionBody`, `initTicketComments`) viven solo ahí → `ReferenceError` en cuanto algo las invoca.

**Fix:** añadir `<script defer src=".../js/pages/ticket_page.js">` antes de `quantum_final.js`.

### C6 — `pleno_modal.js` no se carga: el signo 15 no se puede marcar
`static/js/components/pleno_modal.js:3`. `events.js:165` llama a `openPlenoModal()` al pulsar el Pleno → `TypeError`. Ninguna plantilla lo incluye.

**Fix:** añadir `<script defer src=".../js/components/pleno_modal.js">` antes de `events.js`.

### C7 — Dos stubs en `ticket_page.js` pisan las implementaciones reales
`static/js/pages/ticket_page.js:240-242` y `:244-247` (scripts clásicos: **gana la última declaración**).
- `ensureQ15Directo()` stub `Promise.resolve(false)` vs real en `quantum_final.js:175` → **`/api/q15/directo` nunca se pide**.
- `loadPorra()` stub que pinta "Porra de la jornada" vs real en `quantum_final.js:193` → la porra pierde formulario y reparto.

**Fix:** borrar las líneas 240-247.

### C8 — `MatchPayload` descarta los escudos de los equipos
`liga_maestros/schemas.py:74` + `:204` (`extra="ignore"`).
`payloads/matches.py:213-214` emite `logo_local`/`logo_visitante`, `ticket_page.js:201` los pinta, pero `MatchPayload` **no los declara** → se pierden en `model_dump()`. Escudos siempre vacíos.

**Fix:** declarar `logo_local: str = ""` y `logo_visitante: str = ""`.

### C9 — Dos `setInterval` de 1 Hz que se acumulan, y dos countdowns que se pelean
`static/js/pages/cover_page.js:875` y `:38`.
El `setInterval` del render se registra en **cada** `renderNewspaperCoverPageV3()` sin guarda ni `clearInterval`: cada re-render filtra un interval escribiendo `innerHTML` sobre un nodo ya desencolado. Y los dos countdown usan predicados distintos (`is_locked` vs `ms <= 0`), así que con la jornada cerrada uno escribe "CERRADA" y el otro lo sobrescribe con dígitos **cada segundo**.

**Fix:** un único countdown con `is_locked` compartido; el timer se limpia antes de re-armarse.

### C10 — La auditoría de jornada da verde falso
`tools/audit/AUDITAR_JORNADA_LIGA_MAESTROS.py:11-15`
`BASE_DIR = Path(__file__).resolve().parent` → `tools/audit/data/...`, que **no existe**. `load_json()` devuelve `{}`, y el script sigue imprimiendo `✅ J9: 15 fixtures, programa 15 predicciones, BD y payload íntegros` mientras se saltan 4 de sus 7 grupos de comprobación (nombres públicos, boleto de los maestros, presupuesto de dobles, IDs obsoletos). Además `sqlite3.connect()` **crea** la BD si falta y acaba escribiendo `J0_estado.json`.

**Fix:** `parents[2]`, abrir la BD en read-only y abortar si no existe.

---

## ALTOS (21)

### Frontend / portada
| # | Ubicación | Defecto |
|---|---|---|
| A1 | `cover_page.js:28` | `_countdownStarted = true` se asigna **antes** de `if (!el) return` → si `#cx-cd` no existe, la cuenta atrás queda deshabilitada para siempre sin reintento |
| A2 | `cover_page.js:152` | `coverPenaReading` con `total>0` y 0 votos devuelve `sign:"1X2"` → **acierta siempre**: la columna PEÑA puntúa aciertos fantasma |
| A3 | `cover_page.js:637` | `data-match-id="${match.id}"` sin `escapeHtml`, a diferencia de las líneas vecinas → inyección vía campo `id` |
| A4 | `cover_page.js:1045` | El patch empareja filas **posicionalmente** (`rows[idx]`) frente a un array que puede tener otra longitud u orden tras cambiar de jornada → signos y aciertos en la fila equivocada |
| A5 | `cover_page.js:930` | `_coverFindRowByIdx` busca `tr[data-match-idx]`, atributo que la portada nunca emite, y **no se invoca**: código muerto con selector engañoso |
| A6 | `navigation.js:173` | `querySelectorAll("[data-page-action]")` sin ámbito estampa `.active` y `aria-current="page"` en los **15 `<tr>`** del boleto y en el `<section>` de la porra → ARIA inválido |
| A7 | `cover_page.js:637` | Las 15 filas son solo clic: sin `tabindex`, sin `role`, sin handler de teclado → **la tabla es inalcanzable con teclado** |
| A8 | `cover_hero.css:966` | En móvil `td { display: contents }` anula la caja del `td`, así que **todos** los `order`/`flex` posteriores (`.cx-r-when` 1009, `.cx-r-pick` 1027, `.cx-r-ia` 1055) quedan muertos: la fila "TÚ" y las casillas no reservan línea |
| A9 | `cover_hero.css:1070` | El separador `::before` no declara `order`; con `display:contents` se pinta al principio de cada tarjeta móvil en vez de sobre PEÑA |

### Service worker / assets / SEO
| # | Ubicación | Defecto |
|---|---|---|
| A10 | `deploy-alwaysdata.yml:137` | El deploy no bumpea `CACHE`/`STATIC_CACHE` de `sw.js` (siguen en `v13`): aunque `sw.js` cambie, el navegador reutiliza el script viejo y su `activate` nunca borra la caché anterior |
| A11 | `main.py:106-107` | `img/` recibe `immutable` de 1 año aunque no lleve `?v=`, y `landing.html` pide `og-image.png`, favicons y manifest **sin versionar** → la tarjeta social no se puede refrescar en un año |
| A12 | `liga_index.html:83` | **Cero `<h1>`** en el HTML servido (solo un `<h2>` en la línea 148); el h1 lo inyecta el JS → los crawlers sin JS no lo encuentran |
| A13 | `landing.html:9-40` | `canonical`, `og:url`, `og:image` y `twitter:image` son **URLs relativas**; faltan `og:site_name` y `og:image:width/height`; segundo JSON-LD `WebApplication` con `"url":"/landing"` en conflicto con `liga_index.html`, y `"genre"` que no es propiedad de `WebApplication` |

### Backend / datos
| # | Ubicación | Defecto |
|---|---|---|
| A14 | `liga_data.py:239` (y 234, 572, 598, 630) | `Cache-Control: public, max-age=60` sobre un payload **por usuario** (`ticket_guardado`, `predicciones_actuales`, `is_admin`, `reveal_all`): un CDN/proxy compartido **sirve el boleto de A a B** |
| A15 | `liga_data.py:328` | `_is_ticket_locked` solo mira `("LIVE","FT","FINISHED")` pero `predictions.py:74-76` cierra con `is_scored_status|is_live_scored_status`: **en HT o "EN JUEGO"** el front muestra selector editable y el guardado devuelve 403 → se pierde la quiniela |
| A16 | `config/game.py:7-8` | `MAX_DOBLES_PER_TICKET=14` y `MAX_TRIPLES_PER_TICKET=14` hacen que `predictions.py:49-52` **nunca pueda fallar** (en 15 partidos no hay 15 dobles): la regla es código muerto |
| A17 | `liga_data.py:211` | `ticket_policy.max_doubles/max_triples` se envían pero **ningún JS los lee**; la UI solo produce signos simples mientras el backend acepta `"1X"`/`"X2"`/`"1X2"` |
| A18 | `predictions.py:85` | El chequeo de cierre (71-83) se hace **antes** de `BEGIN IMMEDIATE`: dos guardados concurrentes pasan ambos el control y el segundo sobrescribe al primero tras el saque |
| A19 | `payloads/predictions.py:287` | El ranking puntúa contra la columna cruda `signo_actual` mientras `payloads/matches.py:151-163` la recalcula desde goles: si el collector deja `'-'` con goles puestos, el front pinta hit/miss y el ranking suma 0 |
| A20 | `contest.py:120` | La Peña puntúa solo con final, mientras `payloads/predictions.py:291-293` puntúa con final **o** live: **el mismo usuario ve puntos distintos** en el ranking del TICKET y en La Peña |
| A21 | `multi_standings.py:63` vs `season_rosters.py:15` | `CURRENT_SEASON_ID` se deriva del reloj; `season_rosters.SEASON_ID` es constante `"2026-27"`. **El 2027-07-01** los dos escritores se pelean y borran la clasificación de Premier/Bundesliga/Ligue 1 en cada despliegue |

### Tests / CI
| # | Ubicación | Defecto |
|---|---|---|
| A22 | `ci.yml:45` y `deploy-alwaysdata.yml:36` | `pip-audit ... 2>/dev/null \|\| pip-audit -r requirements.txt`: si el **lock** (lo que se despliega) tiene CVE, reintenta con otro juego de pins y puede salir limpio |
| A23 | `ci.yml:69` | `static/js/**/*.js` sin `shopt -s globstar` = un solo nivel: **4 ficheros nunca se comprueban** (`features/arena/lazy.js`, `features/arena/match-cards.js`, `features/shared/match-helpers.js`, `features/shared/utils.js`) |
| A24 | `ci.yml:82` | La única puerta bloqueante valida la **jornada 75** (Finlandia, temporada 2025-26), no la J9 vigente. No valida nada del concurso real |
| A25 | `tests/test_arena_feedback_fixes.py:10,25` | Único test que llama a `create_app()` **sin aislar la BD**: ejecuta toda la cadena de migraciones contra `DATOS/LIGA_MAESTROS_PRO.db` y ha dejado una **jornada 999 con 20 filas** |
| A26 | `migrations.py:802` → `season_rosters.py:381-399` | `sync_runtime_standings_files()` escribe en `config.SEED_DATA_DIR` (=`data/`) en cada `create_app()`; **ningún test parchea `SEED_DATA_DIR`** y no existe `conftest.py` → `data/MULTI_STANDINGS.json` (versionado) se ensucia en cada suite |
| A27 | `tests/test_multi_standings.py:52`, `test_season_2026_27_standings.py:59` | Afirman `"2026-27"` contra un valor derivado del reloj; la CI no fija `CURRENT_SEASON_START_YEAR` → **fallarán solos el 2027-07-01** |

---

## MEDIOS (38)

**Portada / UX**
- `cover_hero.css:762` — `.is-empty` con `opacity` → ~1.9:1 y ~2.7:1, muy por debajo de AA (4.5:1) en la mayoría de celdas de una portada recién cargada.
- `cover_hero.css:812` — `cxHitPulse` anima `box-shadow` (no componible) en `infinite` sobre hasta 135 elementos → repintado por frame.
- `cover_hero.css:304,605,654` — `backdrop-filter: blur()` en 5 paneles + boleto + `thead` sticky dentro de un contenedor con scroll → recomposición de blur por frame en móvil.
- `cover_page.js:532` — ticker `aria-live="polite"` con contenido duplicado + `aria-live` en `#matches-body`: el lector de pantalla anuncia la portada entera en cada parche.
- `cover_page.js:209` — `hydrateCoverPorra()` vacía: el panel LA PORRA queda en "Cargando…" para siempre.
- `cover_page.js:71` — `role="tablist"` con 6 `<button>` sin `role="tab"`/`aria-selected`, `setTrashTalkIdx` es no-op → ~40 nodos muertos.
- `cover_page.js:473` — fallback `slice(5,10)` mete peñistas humanos en el panel "MAESTROS · TOP 5".
- `navigation.js:12` — `try/catch` envuelve el `addEventListener`, no el handler; el `<link rel="prefetch">` se añade sin deduplicar.
- `navigation.js:102` — si un script falla, el nodo queda sin `data-loaded`: cada llamada cuelga listeners nuevos en un nodo muerto y la vista queda rota para siempre.
- `pleno_modal.js` / `match-helpers.js` — módulo ES que **redefine los mismos globales** que `static/js/utils.js` con otra semántica (`isFinishedStatus` sin `STALE`/`AWARDED`) → divergencia de render entre TICKET y Directo.
- `features/shared/utils.js:6` — `escapeHtml` roto: `.replace(/&/g, "&")` es no-op; **el módulo no parsea** y, si se carga, no escapa nada (XSS).
- `utils.js` — `isFinishedStatus` incluye `STALE`, pero el backend **no lo puntúa** → la UI muestra un partido como finalizado que no suma puntos.
- `state.js:440` — un borrador viejo de `localStorage` gana al boleto del servidor → el boleto se ve como "cambios sin guardar" y el primer clic no guarda.
- `quantum_final.js:385` — `if (saveButton?.disabled) return` no es guard reentrante: un doble clic lanza dos POST y el segundo borra el boleto del primero.
- `ticket_page.js:88` — dos escritores distintos del contador de la quiniela (`checkQuinielaCompletion` vs `state.js:349-358`) → el contador parpadea entre 14/15 y 15/15.
- `predictions.py:26` — límite de 5 en el endpoint lo consumen dos veces el reintento por CSRF caducado → quedan 3 intentos y el 429 se muestra como fallo genérico.
- `scoring.py:13` — regex de pleno **sin anclar** mientras `utils.js:378` usa `^`: con `"AET 2-1"` el backend acierta y el front no.
- `contest.py:202` — `is_user` compara un uid canonicalizado con el id crudo → el resaltado "tú" se rompe.

**SEO / assets / SW**
- `legal/base.html:7` — las 5 páginas legales sin description, canonical, og:/twitter:, favicon ni manifest, y con `legal.css` **sin `?v=`** mientras el resto sí se versiona.
- `main.py:25` — `@lru_cache(maxsize=1)` sobre `_get_assets_version()` nunca recalcula: si un deploy preserva mtimes, los `?v=` no cambian y nadie descarga el CSS/JS nuevo.
- `main.py:32` — solo mira `.css/.js/.png/.jpg/.svg`: un cambio solo en `manifest.webmanifest` no bumpea `assets_v` → manifiesto PWA congelado un año.
- `main.py:222` — `robots.txt` usa el ancla no estándar `Allow: /$` y deja rastreables `/metrics` y `/health`, que filtran `build_sha` y contadores de cuota.
- `main.py:245` — el sitemap incluye `/app` (alias de `/`) y no lleva `<lastmod>`; tampoco incluye `/directo`.
- `liga_index.html:55` — sufijos `'-tokens-3'`, `'-ui-quiniela-47'`… literales que han derivado del hash real de `build.py`.
- `static/` — **42 ficheros gemelos** `*.HASH.css|js` versionados, 41 desincronizados, **610 KB** que el deploy no regenera.
- `sw.js:57` — `cache.addAll().catch()` es todo-o-nada: un 404 cancels los 25 precacheos y solo deja un `console.warn`.
- `sw.js:69` — `activate` borra **toda** caché del origen cuyo nombre no sea el suyo, incluidas caches de otras apps.
- `late_assets.js:32` — `versionedAsset()` cae al literal `"dev"` en cualquier página que no sea `liga_index.html` → assets pedidos con `?v=dev-...`.
- `errors/404.html`, `500.html` — sin `noindex`, `theme-color`, favicon ni manifest.

**Tests / datos / tooling**
- **Agujeros de test críticos sin cubrir:** exceso de dobles/triples rechazado por la API · boleto guardado "a medias" (menos de 15 signos) · `POST /api/predicciones/save` sin sesión → 401 · cambio de jornada (`?j=N`) · fallo de proveedor (timeout/500) · sincronía `PREDICCIONES_ACTUALES.json` vs `predicciones_J9.json`.
- `AUDITAR_JORNADA...:11,111` — `sqlite3.connect()` crea la BD si falta y `detect_jornada` devuelve 0 → escribe `J0_estado.json`.
- `AUDITAR_JORNADA...:14` — `LOGOS_PATH` definido y nunca usado.
- `VALIDAR_JORNADA.py` — 132 líneas sin un solo consumidor; su env `MAXJ` documentada nunca se lee; usa rutas relativas al CWD.
- `tools/audit/...` — `OUT_DIR` escribe en `tools/audit/data/auditorias/`, no ignorado por git.
- `pyproject.toml:11` — `exclude = ["docs"]` **sobrescribe** los excludes por defecto de ruff: se pierden `.git`, `node_modules`, `build`, `dist`, `.venv` → rompe el `ruff check .` local.
- `tests/test_j1_boletos.py:64`, `test_j9_predictions.py:15`, `test_arena_feedback_fixes.py:18` — rutas relativas al CWD, no a `__file__`.
- `test_security_hardening.py:385` — parchea el módulo `time` **global** de la stdlib durante el test.
- `test_payload_schemas.py:24` — `importlib.reload()` en 9 tests crea 9 clases distintas; `test_liga_data_first.py:15` importa entre ficheros de test y no hay `conftest.py` ni `tests/__init__.py`.
- `data/horarios_ACTUALES.json` — **duplicado byte a byte** de `horarios_J9.json` (SHA-256 idéntico), versionado y con **0 referencias**; en J10 Passing el nombre miente.
- **14 ficheros de `data/` versionados que el código ya no lee** (~60 KB): `partidos_ACTUALES.txt`, `jornada 1.txt`, `predicciones_J2_*_revision.json`, `predicciones_J75_maestros.md`, `quiniela15_J1/J3/J75/J76_resultados.json`, `QUIZ_BANK_J72_*`, `RESULTADOS_MAESTROS.json`, `HISTORIAL_JORNADAS_DETALLADO.json`.
- `.gitignore:97,106` — `MULTI_STANDINGS.json` y `MIMO_COMENTARISTA_EMITIDOS.json` están **en .gitignore Y versionados**; la regla da falsa sensación de protección.
- `main.py:126` — `/api/season-summary` sirve `season_2025_2026_summary.json`, la temporada **anterior**, con el nombre hardcodeado.
- `data/auditorias/J73_estado.json|.md` — salida de auditoría de la temporada 2025-26, versionada.
- `test_frontend_ticket_contract.py:48-54` — `subprocess.run` **sin `timeout`**; y ambos tests de Node se saltan en silencio si no hay Node.
- ~10 ficheros de test hacen `assert "cadena JS" in source`: verifican texto, no comportamiento.

## BAJOS (22)
`config/game.py:30` `SEASON_RESET_MARKER` es código muerto (el marcador real está hardcodeado en `deploy-alwaysdata.yml:260`) · `.gitignore` con `dev.md` duplicado y reglas solapadas · `landing.html` JSON-LD sin `screenshot` · tests de strings JS que rompen con refactors inocuos · `errors/404` sin `noindex` · reglas de `.gitignore` para `data/backups/` duplicadas · `LOGOS_PATH` muerto · `MIMO_COMENTARISTA_EMITIDOS.json` como estado de runtime cacheado en git · y otros de mantenimiento menor.

---

## Plan de ejecución

| Ola | Contenido | Ficheros | Riesgo |
|---|---|---|---|
| **1** | La red de seguridad deja de ser decorativa: C1, C2, C22, C23, C24, C25, C26, C27, C10 + `conftest.py` | `ci.yml`, `deploy-alwaysdata.yml`, `conftest.py`, `test_arena_feedback_fixes.py`, audit script | Bajo |
| **2** | Service worker y caché: C3, C4, A10, A11, `sw.js:57,69,131-144`, `main.py:25,32,106`, `late_assets.js:32` | `sw.js`, `sw_register.js`, `main.py` | Medio |
| **3** | TICKET roto: C5, C6, C7, C8, A17, A18, y el test de tickets a medias | `liga_index.html`, `ticket_page.js`, `schemas.py`, `predictions.py` | Medio |
| **4** | Portada: C9, A1–A9 y los medios de portada/UX/a11y | `cover_page.js`, `navigation.js`, `cover_hero.css` | Medio |
| **5** | Coherencia backend/frontend: A14, A15, A16, A19, A20, A21, `scoring.py:13`, `contest.py:202`, `state.js:440`, `quantum_final.js:385` | varios | Medio |
| **6** | SEO y assets: A12, A13, legales, robots, sitemap, JSON-LD, 42 duplicados, `404/500` | plantillas, `main.py` | Bajo |
| **7** | Higiene de datos y tests: ficheros muertos de `data/`, `git rm --cached`, `pyproject.toml`, rutas por CWD, `conftest`, `season-summary`, tests que faltan | varios | Bajo |

**Regla de las olas:** cada ola lleva sus tests, pasa `ruff` + `pytest` + `node --check`, y se despliega y verifica en producción antes de empezar la siguiente.

---

## Nota sobre lo que NO se toca

- `data/predicciones_J9.json` y `data/ECOSISTEMA_PARTICIPANTES.json` (Pavo) son fuente de verdad.
- El boleto `programa` de J9 (`12, 1, 2, 1, 12, 1, 1, 1, 1, 2, 2, 2, 1, 1X, 1-1`) no se altera.
- La lógica de resultados Q15/Highlightly ya verificada en producción se mantiene; `FULL_MATCH_WINDOW=150` sigue como último fallback.
- Ningún secreto se imprime, se commitea o se mueve.
