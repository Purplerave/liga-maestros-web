# Relevo — DIRECTO congelado con partidos en juego

Fecha: 2026-09-13 · Autor: Arena (sesión `arena/01a09acf-liga-maestros-web`)

## Síntoma

«Sigue sin funcionar correctamente el directo… ahora no funciona y están
jugando.» Con la J6 en marcha (13/09 14:47, Celta - Málaga en juego), la página
de DIRECTO no cargaba o se quedaba con el marcador y el minuto congelados.

## Qué se midió (producción, no suposiciones)

Todo vía `https://ligademaestros.alwaysdata.net`:

| Comprobación | Resultado | Lectura |
|---|---|---|
| `/api/live/health` | `status ok`, `jornada_activa 6`, `build_sha 0a410c1` | despliegue al día |
| `/api/sync/status` | `last_sync 14:47`, `last_sync_source quiniela15`, `q15_cache 15/15 ok` | colector y scrape vivos |
| `/api/q15/directo?j=6` | 8 con marcador (`FT`/`STALE`), 7 `NS` | quiniela15 responde |
| `/api/liga/live` | Celta 1-0 Málaga `IN PLAY 45'`, Sporting 0-0 Eldense `HT` | el directo **sí** existe en el servidor |
| `/api/liga/matches` | 15 filas J6 con fechas y horas correctas (11–14/09) | horarios bien |
| `/metrics` | `/api/liga/data` 3,94 s / 3 peticiones = **1,31 s**; `/api/noticias/radar` **4,28 s**; Highlightly 330/7500 | **aquí está el fallo** |

Conclusión: el dato llegaba bien hasta la API. Se rompía en la entrega.

## Causa raíz (tres piezas que se sumaban)

1. **Guillotina del service worker.** `static/sw.js` cortaba todo `/api/` GET a
   los **4000 ms** y fabricaba `503 {"status":"error","message":"Offline"}`.
   Con `/api/liga/data` en 1,31 s de media y picos por encima de 4 s
   (clasificaciones cada 5 min, arranque en frío, la IA), el navegador recibía
   un fallo inventado con el servidor vivo.
2. **El frontend no reintentaba ese fallo.** `fetchLigaDataWithRetry` (añadido
   el 12/09) solo reintentaba `status === "cold_start"`. El 503 del SW mataba la
   carga inicial («No se pudo cargar la Arena») y `refreshLiveSnapshot` lo
   descartaba en silencio → directo congelado.
3. **La IA dentro de la petición.** `_build_comentarista_payload` llamaba a
   `construir_comentarios()` → `chat()` con `AI_TIMEOUT_SECONDS=10` por
   proveedor, 2 reintentos y 3 proveedores. Solo dispara **con partidos en
   juego**: de ahí el «no funciona *cuando están jugando*».

Coste adicional medido con perfil local (payload real de 126 KB):
`load_team_logos()` reparseaba ~100 KB y canonicalizaba ~600 nombres en **cada**
petición (45 % del tiempo) y `clean_team_key()` se llamaba 8.770 veces con 6
`re.sub` cada una (52 %).

## Qué se cambió

- `static/sw.js`: tope de API 4 s → **30 s** (`API_TIMEOUT_MS`); la respuesta
  sintética pasa a `504` + `{"status":"network_error","retryable":true}`;
  cachés `v12` → `v13` para que los clientes descarguen el SW nuevo.
- `static/js/quantum_final.js`: reintento de 503/504 reintentables **y** de
  excepciones de red (3 intentos, `Retry-After`, espera creciente); la carga
  inicial se reintenta sola hasta 4 veces y ofrece un botón «Reintentar ahora»
  cableado por `addEventListener` (la CSP no permite `onclick` inline).
- `static/js/events.js`: `refreshLiveSnapshot()` devuelve si llegó o no; tras un
  fallo el siguiente poll se programa a los **6 s** (`LIVE_FAILURE_RETRY_MS`) en
  vez de 30 s.
- `liga_maestros/services/ai/comentarista.py`: nuevo `comentarios_para_web()`
  (nunca bloquea; sirve caché y encarga la generación a un hilo single-flight
  con `REINTENTO_SEGUNDOS=60`). La cola de generación se extrajo a `_generar()`,
  compartida con `construir_comentarios()`.
- `liga_maestros/routes/liga_data.py`: la ruta usa la variante no bloqueante.
- `liga_maestros/utils.py`: `clean_team_key()` memoizada (`lru_cache`) y
  `load_team_logos()` cacheada por `mtime_ns` + tamaño.
- `tests/test_directo_resiliente.py`: 11 tests que fijan todo lo anterior.
- `tests/test_cold_start_retry.py`, `tests/test_j6_resultados_cruce.py`:
  reformateados (tenían el `ruff check` de CI en rojo desde el 12/09).

Resultado local: **110 ms → 26 ms** por petición (28 ms por HTTP) con el mismo
payload de producción. En Alwaysdata eso debería bajar de ~1,3 s a ~0,3 s.

## Verificación

- `python -m pytest -q`: 452 pasan.
- `ruff check .` / `ruff format --check .`: limpios (antes: 1 error + 2 ficheros).
- `mypy liga_maestros`: 14 errores, todos preexistentes (ninguno en los ficheros
  tocados).
- `node --check` sobre `sw.js`, `quantum_final.js`, `events.js`.

## Despliegue y comprobación en vivo

`push` a `main` → workflow **Deploy Alwaysdata** (SSH + `pytest` previo). Tras
desplegar, con un partido en juego:

1. `/metrics`: la media de `/api/liga/data` debe bajar de ~1,3 s a <0,5 s.
2. En el navegador, DevTools → Application → Service Workers: `liga-maestros-v13`.
3. DIRECTO: el minuto debe avanzar solo (poll de 30 s, o 6 s si una petición
   falla). Ningún «No se pudo cargar la Arena».
4. Si `MIMO_API_KEY` está activa, las frases del comentarista aparecen con hasta
   10 min de retraso (cadencia) pero **sin** frenar la página.

## Cabos sueltos (no tocados en este cambio)

- `validate_liga_data` registra *schema drift* en cada petición
  (`jornada: string_type; consenso_pleno_pena: list_type`): la validación no
  aporta nada hoy y se descarta al payload original. Conviene alinear el schema.
- `static/js/contest.js:117` tiene un `onclick` inline: con
  `script-src 'self'` ese botón «Entrar con Google» no hace nada.
- `/api/live/ticker` sirve un `LIVE_TICKER.json` que nadie escribe en este repo
  (última actualización 20:42 del día anterior) y que ningún JS consume.
- `static/js/*.HASH.js` (salida de `build.py`) están desincronizados de sus
  fuentes; las plantillas no los usan, pero confunden al leer el repo.
- El poll del directo sigue pidiendo el payload completo (~125 KB cada 30 s por
  cliente). Con `/api/liga/live` (0,12 s) o un `?slim=1` sería ~10× más barato.
