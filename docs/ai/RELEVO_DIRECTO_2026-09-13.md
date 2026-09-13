# Relevo — DIRECTO congelado con partidos en juego

Fecha: 2026-09-13 · Autor: Arena (sesión `arena/01a09acf-liga-maestros-web`) · PR #117 (merged, `73f6998`)

## Síntoma

«Sigue sin funcionar correctamente el directo… ahora no funciona y están
jugando.» Con la J6 en marcha (13/09 14:47, Celta - Málaga en juego), la página
de DIRECTO no cargaba o se quedaba con el marcador y el minuto congelados.

## Qué se midió (producción, no suposiciones)

Todo vía `https://ligademaestros.alwaysdata.net`:

| Comprobación | Resultado | Lectura |
|---|---|---|
| `/api/live/health` | `status ok`, `jornada_activa 6`, `build_sha 0a410c1` | despliegue al día |
| `/api/sync/status` | `last_sync 14:47`, `last_sync_source quiniela15`, caché 15/15 ok | colector y scrape vivos |
| `/api/q15/directo?j=6` | 8 con marcador (`FT`/`STALE`), 7 `NS` | quiniela15 responde |
| `/api/liga/live` | Celta 1-0 Málaga `IN PLAY 45'`, Sporting 0-0 Eldense `HT` | el directo **sí** existe en el servidor |
| `/api/liga/matches` | 15 filas J6 con fechas y horas correctas (11–14/09) | horarios bien |
| `/api/ai/status` | `enabled: true` | **la IA se llamaba de verdad en cada refresco** |
| `/metrics` | `/api/liga/data` 3,94 s / 3 peticiones = **1,31 s**; `/api/noticias/radar` **4,28 s**; Highlightly 330/7500 | endpoint lento |

Conclusión: el dato llegaba bien hasta la API. Se rompía entre la API y la
pantalla.

## Causa raíz

1. **La IA dentro del ciclo de petición (la principal).**
   `_build_comentarista_payload` → `construir_comentarios()` → `chat()` con
   `AI_TIMEOUT_SECONDS=10` **por proveedor**, 2 reintentos y 3 proveedores:
   hasta ~60 s de petición bloqueada. Y el comentarista solo dispara **con
   partidos en juego** (cadencia de 10 min), que es exactamente cuando el usuario
   mira el directo. Con `/api/ai/status` en `enabled: true`, cada refresco de la
   web (poll de 30 s por cliente) podía quedarse colgado detrás de una llamada a
   MiMo, y varias peticiones apiladas se comían los workers de Alwaysdata.
2. **El frontend no reintentaba nada que no fuera `cold_start`.** El arreglo del
   12/09 (PR #115/#116) solo cubría `status === "cold_start"`: cualquier otra
   respuesta lenta o fallida dejaba la portada clavada en «No se pudo cargar la
   Arena» hasta recargar a mano, y `refreshLiveSnapshot()` descartaba el fallo en
   silencio (`if (!response.ok) return`) y esperaba 30 s al ciclo siguiente. De
   ahí el «*sigue* sin funcionar» con el arreglo ya desplegado.
3. **`/api/liga/data` costaba 1,31 s de media** (y el poll lo pedía entero, 125 KB,
   cada 30 s). Perfil local con ese payload: `load_team_logos()` reparseaba ~100 KB
   y canonicalizaba ~600 nombres **en cada petición** (45 % del tiempo) y
   `clean_team_key()` se invocaba 8.770 veces con 6 `re.sub` cada una (52 %).

### La guillotina del service worker: armada, pero inactiva

`static/sw.js` cortaba todo `/api/` GET a los **4000 ms** y fabricaba
`503 {"status":"error","message":"Offline"}` con el servidor vivo —y
`/api/noticias/radar` medía 4,28 s, por encima del tope—. Fue la primera
hipótesis y es un bug real, **pero no llegó a morder**: el SW se registra en
`/static/sw.js` sin opción `scope`, así que su scope es `/static/` y ni `/` ni
`/api/*` pasan por su `fetch`. Además, antes del PR #116 ni siquiera se
registraba (el `<script>` inline lo bloqueaba la CSP `script-src 'self'`), por lo
que **nunca hubo un SW zombie controlando la raíz** que hubiera que limpiar.

Se corrige igualmente (ver abajo) porque es una trampa armada: en cuanto alguien
amplíe el scope a `/`, un tope de 4 s volvería a romper el directo.

## Qué se cambió

- `liga_maestros/services/ai/comentarista.py` + `routes/liga_data.py`: nuevo
  `comentarios_para_web()` que **nunca llama a la IA dentro de la petición**
  (sirve caché y encarga la generación a un hilo *daemon* single-flight, con la
  misma cadencia de 10 min y la misma cuota; `REINTENTO_SEGUNDOS=60` entre
  intentos fallidos). La cola de generación se extrajo a `_generar()`, compartida
  con `construir_comentarios()` (bloqueante: colector, scripts y tests).
- `static/js/quantum_final.js`: `fetchLigaDataWithRetry` reintenta 503/504
  reintentables **y** las excepciones de red (3 intentos, `Retry-After`, espera
  creciente); la carga inicial se reintenta sola hasta 4 veces
  (`INITIAL_LOAD_MAX_RETRIES`) y ofrece «Reintentar ahora» cableado por
  `addEventListener` (un `onclick` inline no se ejecuta con esta CSP).
- `static/js/events.js`: `refreshLiveSnapshot()` devuelve si llegó o no; tras un
  fallo el siguiente poll va a los **6 s** (`LIVE_FAILURE_RETRY_MS`) en vez de 30 s.
- `liga_maestros/utils.py`: `clean_team_key()` memoizada (`lru_cache`) y
  `load_team_logos()` cacheada por `mtime_ns` + tamaño (un scrape nuevo de
  escudos entra sin reiniciar la app).
- `static/sw.js`: tope de API 4 s → **30 s** (`API_TIMEOUT_MS`); la respuesta
  sintética pasa a `504` + `{"status":"network_error","retryable":true}`, que ya
  no se confunde con el `503 cold_start` del backend; cachés `v12` → `v13`.
- `tests/test_directo_resiliente.py`: 11 tests que fijan todo lo anterior.
- `tests/test_cold_start_retry.py`, `tests/test_j6_resultados_cruce.py`:
  reformateados (tenían el `ruff check` de CI en rojo desde el 12/09; el paso de
  lint fallaba y no dejaba correr nada más).

## Rendimiento

Perfil local con el payload real de producción (126 KB, panel de 600 partidos):

| | antes | después |
|---|---|---|
| `/api/liga/data` (in-process) | 110 ms | **26 ms** |
| llamadas a función por petición | 245k | **74k** |
| por HTTP | — | **28 ms** |

## Verificación

- `python -m pytest -q`: 452 pasan.
- `ruff check .` / `ruff format --check .`: limpios (antes: 1 error + 2 ficheros).
- `mypy liga_maestros`: 14 errores, todos preexistentes (ninguno en los ficheros
  tocados).
- `node --check` sobre `sw.js`, `quantum_final.js`, `events.js`.
- Cruce de nombres quiniela15 ↔ BD de la J6: **15/15**, incluidos «Edf Logroño» ↔
  «Logroño (F)», «Las Planas (F)» ↔ «Badalona W. (F)» y «Valladolid» ↔
  «R. Valladolid (M)».

## Despliegue y comprobación en vivo

`push` a `main` → workflow **Deploy Alwaysdata** (SSH + `pytest` previo).
PR #117 mergeado a las 15:22, deploy en verde en 1 m 24 s. Comprobado después:

- `/api/live/health` → `build_sha 73f6998c87dce6e84967abd4a3ffeb84dd948aba`.
- `/static/sw.js` → ya sirve `liga-maestros-v13` y `API_TIMEOUT_MS = 30000`.

Con un partido en juego (J6: 16:15, 17:00, 19:30 y 21:00):

1. `/metrics`: la media de `/api/liga/data` debe bajar de ~1,3 s a <0,5 s.
2. DIRECTO: el minuto avanza solo (poll de 30 s, o 6 s si una petición falla).
   Ningún «No se pudo cargar la Arena».
3. Las frases del comentarista aparecen con hasta 10 min de retraso (cadencia)
   pero **sin** frenar la página.
4. DevTools → Application → Service Workers: `liga-maestros-v13`, scope
   `https://ligademaestros.alwaysdata.net/static/` (sí: solo `/static/`, ver
   arriba).

## Decisiones pendientes

- **Scope del service worker.** Hoy es `/static/`: el offline del HTML y el tope
  de la API no se ejecutan nunca. Opciones: (a) dejarlo así (el SW solo cachea
  estáticos, que ya van con `?v=<mtime>` y `immutable`); (b) registrarlo con
  `scope: '/'` + cabecera `Service-Worker-Allowed: /` en `/static/sw.js`, que
  activa el offline de verdad y mete al SW en el camino de todas las peticiones;
  (c) quitar el registro y vivir sin SW. No se ha tocado en caliente con
  partidos a punto de empezar.

## Cabos sueltos (no tocados en este cambio)

- `validate_liga_data` registra *schema drift* en cada petición
  (`jornada: string_type; consenso_pleno_pena: list_type`): la validación no
  aporta nada hoy y se descarta al payload original. Conviene alinear el schema.
- `static/js/contest.js:117` tiene un `onclick` inline: con `script-src 'self'`
  ese botón «Entrar con Google» **no hace nada**.
- `/api/live/ticker` sirve un `LIVE_TICKER.json` que nadie escribe en este repo
  (última actualización 20:42 del día anterior) y que ningún JS consume.
- `static/js/*.HASH.js` (salida de `build.py`) están desincronizados de sus
  fuentes; las plantillas no los usan, pero confunden al leer el repo.
- El poll del directo sigue pidiendo el payload completo (~125 KB cada 30 s por
  cliente). Con `/api/liga/live` (0,12 s) o un `?slim=1` sería ~10× más barato.
- `_get_assets_version()` va con `lru_cache(maxsize=1)`: si un despliegue no
  reiniciara el proceso, los `?v=` de los estáticos se quedarían viejos y el SW
  serviría JS antiguo desde su caché *cache-first*. Hoy el despliegue sí
  reinicia, pero es frágil.
