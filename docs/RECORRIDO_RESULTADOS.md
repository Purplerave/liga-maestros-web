# Recorrido del resultado de un partido de la quiniela

Dónde nace un resultado, qué manos toca y dónde se puede perder. Escrito a
raíz del incidente J6 (11/09/2026): «el partido del Sevilla de las 9 no
aparece» aunque el directo sí lo veía.

## 1. El camino completo (en verde cuando todo va bien)

```
quiniela15.com/resultados-quiniela/N
        │  SCRAPE_QUINIELA15_DIRECTO.scrape()  (cada pasada del colector)
        ▼
data/quiniela15_directo_JN.json          ← cache en directo (15 filas)
        │  LIVE_COLLECTOR.write_q15_directo_cache()
        ▼
LIVE_COLLECTOR.apply_q15_results_to_db() ← CRUCE DE NOMBRES ← punto que falló
        │  UPDATE resultados SET goles..., status, signo
        ▼
BD SQLite · tabla resultados (jornada, partido_id)
        │  build_jornada_matches()  (payload del boleto)
        ▼
/api/liga/data  →  boleto web: marcador, signo y escudos
```

En paralelo, el mismo resultado llega por **Highlightly**
(`refresh_current_matches_from_highlightly` → `_find_feed_item`, otro cruce de
nombres) y alimenta el panel del DIRECTO (`LIVE_ALL_MATCHES_V3.json`). El
DIRECTO **no cruza con la BD**: pinta el feed tal cual. Por eso el directo
puede «funcionar» y el boleto quedarse sin resultados a la vez: son dos
caminos distintos que solo comparten el cruce de nombres contra
`resultados`.

## 2. Las reglas del cruce de nombres

Todo pasa por `liga_maestros/utils.py`:

- `clean_team_key`: mayúsculas sin acentos, sin "FC/CD/CF...", el marcador
  femenino "(F)" se conserva como sufijo y el masculino "(M)" se elimina.
- `normalize_team_key` + `TEAM_LOGO_ALIASES` (config/teams.py): canónicos
  ("Athletic" → "ATHLETIC CLUB", "R. Santander" → "RACING DE SANTANDER",
  "Edf Logroño"/"Logroño (F)" → "LOGROÑO UNITED"...).
- `team_keys_compatible`: canónicos iguales o variantes de género compatibles.
  Un masculino JAMÁS casa con un femenino.
- `team_key_variants`: variantes F/FEMENINO para el feed del proveedor.

Si el nombre de la BD y el del proveedor no canonizan igual, el resultado se
descarta **en silencio** (`q15_team_mismatch_skipped` en el log del colector)
y la fila se queda `NS` para siempre: la quiniela15 ya no se re-rasca de una
jornada cerrada.

## 3. Qué pasó en la J6

1. El boleto J6 mezcla LaLiga y Liga F (hay "Sevilla" y "Sevilla (F)" en el
   mismo ticket), así que la importación marcó los masculinos con "(M)".
2. `clean_team_key` no conocía "(M)": la clave de "Sevilla (M)" pasó a ser
   "SEVILLA M". Esa clave no la publica nadie más.
3. Viernes 22:51: quiniela15 tiene "Sevilla 1-0 Valencia, LIVE 84'" y el
   proveedor "Sevilla FC vs Valencia, IN PLAY". Los dos cruces fallan →
   0 updates → el boleto pinta "sábado/domingo..." en vez del marcador.
4. Mismo mecanismo, mismo efecto: los equipos "(M)" también salían **sin
   escudo** (`logo_for` usa el mismo canónico).

Histórico del mismo síntoma (todas «semana tras semana» con un nombre distinto):
J75 (VPS/TPS sin resultado → migración `ensure_jornada_75`), J4 2026/27
("Sporting", "Edf Logroño", horarios desfasados → `test_j4_resultados_definitivos`),
J6 2026/27 (el "(M)" → `test_j6_resultados_cruce`).

## 4. Arreglo (2026-09-11)

- `clean_team_key` elimina "(M)" y "MASCULINO/A": "Sevilla (M)" canoniza como
  "SEVILLA FC", igual que "Sevilla" y "Sevilla FC". El género sigue blindado
  ("Sevilla (M)" ≠ "Sevilla (F)").
- Aliases nuevos: "R VALLADOLID" → VALLADOLID; "BADALONA W" → LEVANTE LAS
  PLANAS (la quiniela publica "Las Planas (F)" al mismo club).
- No hace falta migrar datos: la J6 en producción conserva sus "(M)" y se
  rellena sola en la siguiente pasada del colector.

## 5. Cómo diagnosticarlo la próxima vez (checklist)

1. `GET /api/sync/status` → ¿`q15_cache.ok` con 15/15? (el scraper funciona)
2. `GET /api/q15/directo?j=N` → ¿trae el partido con `score_home/away`?
3. `GET /api/liga/data` → ¿la fila sigue `NS`?
4. Si 2 dice sí y 3 dice NS: es el **cruce de nombres**. Buscar en el log del
   colector `q15_team_mismatch_skipped` y añadir el alias que falta (o el
   marcador) en `clean_team_key`/`TEAM_LOGO_ALIASES`, con su test de
   regresión (patrón: `tests/test_j4_resultados_definitivos.py`).
5. Recordar: una jornada cerrada **no se vuelve a raspear**; el arreglo de
   nombres solo rellena la jornada dentro de su ventana (hasta 24 h después
   del último saque). Para una jornada antigua: `REPARAR_JORNADA_QUINIELA.py`
   o los resultados oficiales en `data/quiniela15_JN_resultados.json`.

## 6. Incidente J17 2026/27 (31/10/2026): «no vemos los resultados»

Ese sábado a las 16:47 el Levante–Atlético y el Rayo–Celta ya estaban jugados
o en juego y la portada seguía enseñando el horario de **todas** las casillas.
Esta vez no fallaba el render ni el payload: fallaban los **nombres** y, sobre
todo, el **número de jornada**. Tres capas, y las tres hacían falta para dejar
la jornada a cero:

### 6.1 La numeración de quiniela15 no es la del boleto

`/resultados-quiniela/17` de quiniela15.com es la **Copa del Rey del 28/10**,
un boleto extraordinario de SELAE que esta liga no juega. El boleto de la liga
(Levante–Atlético, Rayo–Celta, Betis–Málaga…) es la **J18** de quiniela15. El
colector pedía la 17, recibía 15 partidos impecables de otra quiniela y los
cruzaba por `partido_id`: 0 updates, todo `NS`.

Arreglo:

- `config/quiniela15_jornadas.py` → tabla de equivalencias
  (`QUINIELA15_JORNADA_OVERRIDES`, hoy `{17: 18}`).
- `LIVE_COLLECTOR._q15_numero_para_boleto()` → si la tabla no lo resuelve,
  prueba el número del boleto y sus vecinos y se queda con el que reproduce
  las casillas del boleto (`_q15_boleto_coverage`, 60% de coincidencia). Así un
  boleto extraordinario nuevo se resuelve solo.
- `_q15_payload_matches_boleto()` → si la quiniela descargada no es la del
  boleto, el payload se marca `boleto_comprobado: false`, **no se escribe en la
  BD** y **no se pisa el caché del directo** (`q15_cache_conservado`).
- `_q15_kickoff_order_plausible()` → última red: aunque el nombre cruce, un
  partido con fecha a más de 2 días del boleto no se aplica (la Copa numera
  «Levante–Atlético» en la casilla 1 igual que el boleto, pero otro día).
- El scraper expone `fecha` por fila y `/api/live/probe` usa la misma
  equivalencia.

### 6.2 Las grafías del boleto y de la quiniela15

`At. Madrid` en la J2/J3/J4/J12, `Atlético` a secas en la J17 (¡y en el mismo
boleto!). Lo mismo con `Racing`/`Racing Santander`, `R. Madrid (F)`/
`Real Madrid (F)` y `R. Sociedad (F)`/`Real Sociedad (F)`. Sin alias, el cruce
se descartaba (`q15_team_mismatch_skipped`) y el equipo salía además **sin
escudo**, porque `logo_for` usa el mismo canónico.

Aliases nuevos en `config/teams.py`: `ATLETICO`, `RACING`, `R MADRID F`,
`R SOCIEDAD F`, `ATHLETIC BILBAO FEMENINO`, `UD TENERIFE`,
`DEPORTIVO DE LA CORUNA FEMENINO`.

`UD Tenerife` es el Costa Adeje Tenerife de Liga F, pero sin forma jurídica
canonizaba igual que el Tenerife masculino: por eso se añade
`FEMININE_TEAM_KEYS` + `raw_team_key()` (clave con «UD/CD/FC»), que marca esos
nombres como femeninos y permite que el alias `UD TENERIFE` sea alcanzable sin
abrir el cruce masculino ↔ femenino.

### 6.3 El fallback del proveedor (Highlightly)

`_core_team_key` troceaba el nombre y ordenaba los tokens: `Atlético` daba
`("ATL", "TICO")` y `Málaga` `("LAGA", "M")`, claves que solo casaban con otro
nombre partido igual. Ahora parte del canónico y devuelve una clave estable
(`ATLETICO MADRID`, `MALAGA`), conserva el sufijo de género (un masculino no
puede cruzar con un femenino por el fallback) y un nombre que solo es forma
jurídica devuelve `()` para que no se acepte.

### 6.4 Checklist actualizado

1. `GET /api/sync/status` → ¿`q15_cache.ok` con 15/15?
2. `GET /api/q15/directo?j=N` → ¿trae el partido con `score_home/away`?
3. **¿`q15_jornada` del JSON es el número del boleto?** Si no, es la
   numeración (§6.1). Mirar `q15_origen`, `boleto_comprobado` y los logs
   `q15_jornada_autodetectada` / `q15_jornada_no_confirma_boleto`.
4. Si el payload es correcto y la fila sigue `NS`: es el **cruce de nombres**
   (§6.2). Buscar `q15_team_mismatch_skipped` y añadir el alias que falta.
5. Regresión: `tests/test_j17_resultados_grafias_y_numeracion.py`.
