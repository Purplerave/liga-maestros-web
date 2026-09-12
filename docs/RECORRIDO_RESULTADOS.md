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
