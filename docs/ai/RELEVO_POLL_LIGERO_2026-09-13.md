# Relevo — poll ligero del DIRECTO (`?slim=1`)

Fecha: 2026-09-13  ·  Frente: **Frente 2 — coste del poll** (complementario al
Frente 1 Estabilidad de Kilo, no solapado: aquí no se diagnostican caídas, se
baja el coste de cada poll).

## Problema

`static/js/events.js` refrescaba el DIRECTO pidiendo **el payload completo** de
`/api/liga/data` cada 30 s por cliente (45 s en ventana de jornada, 180 s fuera
de ella). Era el cabo suelto que dejó escrito el relevo del DIRECTO:

> El poll del directo sigue pidiendo el payload completo (~125 KB cada 30 s por
> cliente). Con `/api/liga/live` (0,12 s) o un `?slim=1` sería ~10× más barato.

Reparto real del coste, medido sobre la DB del repo (`DATOS/LIGA_MAESTROS_PRO.db`):

| Parte | Coste |
| --- | --- |
| `build_predictions_payload` (predicciones, consenso, pleno, **ranking**) | 6,5 ms de 10,8 ms |
| `build_standings_payload` + `build_multi_league_standings` | 0,2 ms (caché de 5 min) |
| `load_match_info_for_jornada` + `build_trash_talk` | 0,3 ms |

Es decir: **el 60 % de cada poll se iba en recalcular el ranking de maestros,
el consenso de la Peña y las predicciones**, que no cambian en una ventana de
30 s.

## Qué se cambió

### Backend — `liga_maestros/routes/liga_data.py`

- `GET /api/liga/data?slim=1` devuelve solo lo volátil: `jornada`,
  `jornada_liga`, `max_jornada`, `today_madrid`, `is_locked`,
  `ticket_guardado`, `edit_deadline`, `kickoff_at`, `partidos`,
  `all_league_matches`, `live_matches`, `standings`,
  `multi_league_standings`, `comentarista` y el marcador `slim: true`.
- No se construye nada de lo que sale de las predicciones: ni
  `build_predictions_payload`, ni `build_trash_talk`, ni
  `load_match_info_for_jornada`, ni el contrato de participantes.
- Se aceptan `slim=1|true|yes|on` (cualquier otro valor ⇒ payload completo).
- **Sin `?slim=1` no cambia absolutamente nada**: mismo payload, mismas claves,
  mismo orden de construcción.
- El `503 cold_start` se sirve antes de la rama ligera: con `?slim=1` también.

### Contrato — `liga_maestros/schemas.py`

- `LigaDataSlimPayload` + `validate_liga_data_slim()`, con la misma filosofía
  tolerante que `validate_liga_data`: si hay drift, se loguea y se devuelve el
  payload original en vez de romper la respuesta.

### Frontend — `static/js/events.js`

- `refreshLiveSnapshot()` pide `?slim=1` y manda `If-None-Match` con el ETag
  del snapshot anterior (el endpoint ya emitía ETag desde hace tiempo, pero
  nadie lo usaba en el poll).
- `304` ⇒ no ha cambiado nada: **cero bytes** y ni un repintado.
- `200 + slim` ⇒ lo volátil se **mezcla** sobre `state.data`
  (`{ ...state.data, ...volatil }`), nunca lo sustituye: la página conserva
  participantes, consenso, ranking y predicciones de la carga completa.
- Si cambia un resultado, la clasificación **o el cierre del boleto**, se pide
  el payload completo (`refreshData({ auto: true })`), que es quien trae
  ranking en vivo, consenso y predicciones reveladas y quien decide si repinta
  con el parche barato (`patchLiveArena` / `patchTicketArena`) o entero.
- Cada 4 polls sin novedades, `syncHeavyPayload()` resincroniza en silencio las
  partes pesadas (ranking, consenso, predicciones) **sin repintar**: así el
  consenso de la Peña no se queda atrás cuando nadie marca gol.
- Si el backend desplegado no conoce `?slim=1`, responde con el payload
  completo y el código sigue la rama antigua. Compatible hacia atrás y hacia
  delante: se puede desplegar en cualquier orden.

## Medición

Sobre `DATOS/LIGA_MAESTROS_PRO.db` (copia local, mediana de 25 peticiones,
`web_collector` y backups desactivados):

| Petición | Mediana | Tamaño |
| --- | --- | --- |
| `/api/liga/data` | 10,19 ms | 46 181 B (6 489 B gzip) |
| `/api/liga/data?slim=1` | 3,28 ms | 37 698 B (4 624 B gzip) |
| `/api/liga/data?slim=1` + `If-None-Match` | 2,92 ms | **0 B** |

- **−68 % de CPU** por poll.
- **−18 % de bytes** (−29 % comprimido) cuando algo cambia; **−100 %** cuando
  no cambia nada, que es la mayoría de los polls.
- Coste medio por cliente cada 30 s, contando la resincronización pesada cada
  4 polls: ≈ 4,0 ms y ≈ 11 KB frente a los 10,2 ms y 46 KB anteriores.

Aviso honesto: la DB del repo tiene menos participantes que producción (payload
de 46 KB frente a los ~125 KB que medía el relevo anterior). El ahorro de CPU
(-68 %) es estructural y se mantendrá; el ahorro de bytes en producción debería
ser **mayor** que el medido aquí, porque lo que se quita crece con el número de
participantes.

## Verificación

- `python -m pytest -q` (sin los dos ficheros informativos de producción):
  **464 pasan**.
- `ruff check .` y `ruff format --check .`: limpios.
- `mypy liga_maestros`: 14 errores, todos preexistentes; ninguno en
  `schemas.py` ni en `routes/liga_data.py`.
- `node --check static/js/events.js`: pasa.
- Tests nuevos: `tests/test_liga_data_slim.py` (8 tests: builders que se
  saltan, claves del contrato, igualdad de lo volátil, variantes del flag,
  ETag/304, cold start, contrato del frontend y schema).

## Comprobación en vivo tras desplegar

```bash
BASE=https://ligademaestros.alwaysdata.net
ETAG=$(curl -sI "$BASE/api/liga/data?slim=1" | awk '/[Ee][Tt]ag/ {print $2}' | tr -d '\r')
curl -s -o /dev/null -w 'slim: %{http_code} %{size_download} B\n' "$BASE/api/liga/data?slim=1"
curl -s -o /dev/null -w '304:   %{http_code} %{size_download} B\n' \
     -H "If-None-Match: $ETAG" "$BASE/api/liga/data?slim=1"
curl -s "$BASE/api/liga/data?slim=1" | python -c "import json,sys; print(sorted(json.load(sys.stdin)))"
```

Esperado: `slim: 200`, `304: 304 0 B`, y una lista de claves **sin**
`ranking_maestros`, `consenso_pena`, `predicciones_actuales`,
`participant_contract`, `match_info`, `trash_talk`, `jornadas_disponibles`.

En el navegador (DevTools → Red, filtro `liga/data`):

1. Los polls del DIRECTO llevan `?j=X&slim=1`.
2. Los polls repetidos con el mismo dato responden `304` con 0 B.
3. Al entrar un gol se ven dos peticiones: el `slim` y, detrás, el payload
   completo (`refreshData`). El minuto y el marcador se actualizan igual que
   antes.

## Cabos sueltos que siguen abiertos

- `/api/liga/data` reconstruye el payload antes de comparar el ETag: un poll
  `304` todavía cuesta ~2,9 ms de CPU. Para bajarlo habría que cachear el
  payload por (jornada, sesión) con TTL corto, y el estado de cierre del boleto
  depende de la hora actual: hay que medirlo antes de tocarlo.
- `_build_ranking()` recorre **todas** las predicciones de la temporada en cada
  petición (4-5 ms). Solo las de la jornada activa pueden cambiar en directo:
  una memoización por jornada con firma de resultados bajaría también el payload
  completo. Es el siguiente paso natural de este frente.
- `/api/liga/live` sigue devolviendo solo `live_matches`: no sirve para el poll
  (hacen falta `partidos` y `multi_league_standings`), por eso se ha preferido
  `?slim=1` sobre un endpoint nuevo.
