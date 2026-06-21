# Revision por IA

## Contexto

Liga de Maestros es una app Flask de quinielas con:
- predicciones de usuarios y maestros IA;
- rankings;
- directo de partidos;
- consumo de Highlightly;
- login Google OAuth;
- despliegue previsto en Render mediante `render.yaml`.

Este archivo es el punto de entrada para que otra IA revise el repo publico y proponga cambios sin perder contexto.

## Estado actual

- Rama principal: `main`.
- Ultimos arreglos aplicados:
  - `65fac90 Persist API rate limits in SQLite`
    - rate limit de guardado de quiniela y comentarios pasa a SQLite con transaccion.
    - `schema.sql` incluye `api_rate_limit`.
  - `bcd0508 Cache contest payloads with database signature`
    - `build_contest_payload` queda cacheado con firma de datos para reducir recalculos.
  - `e1a8223 Add collector backups and stricter Q15 checks`
    - `LIVE_COLLECTOR.py --backup-now` crea backup local de DB y JSON criticos.
    - el colector hace backup diario local y retiene backups recientes.
    - Quiniela15 incompleta deja de aplicarse a resultados.
  - `2c031d4 Improve live reliability and contest profile performance`
    - `get_contest_profile` pasa de varias reconstrucciones del ranking a una sola.
    - el contador diario de Highlightly se mueve a SQLite con transacciones `BEGIN IMMEDIATE`.
    - `/api/live/probe`, `/api/live/health` y `/api/sync/status` exponen partidos Q15 esperados/recibidos.
    - `schema.sql` incluye la tabla `api_usage_daily`.
  - `2ad5a1b Add safety checks and scoring tests`
    - CI minimo en GitHub Actions.
    - tests de scoring para pleno al 15 y signos dobles.
    - mensajes de error genericos en guardado de quiniela y comentarios.
    - rate limit simple en memoria para guardado y comentarios.
  - `0344366 Update AI collaboration notes`
    - README de colaboracion actualizado con verificacion local, Render y reglas de trabajo.
  - `1fce4b6 Fix app startup and stabilize match list`
    - eliminado bloque indentado roto en `app.py`.
    - `/api/liga/data` devuelve siempre 15 partidos.
    - auto-refresh frontend cambiado a 120 segundos.

## Archivos principales

- `app.py`: backend Flask, endpoints, rankings, OAuth, live refresh, scoring.
- `config.py`: rutas, ligas, variables de entorno.
- `utils.py`: normalizacion, helpers de equipos, JSON, horarios.
- `LIVE_COLLECTOR.py`: refresco live fuera de peticiones web.
- `SCRAPE_QUINIELA15_DIRECTO.py`: scraper de resultados Quiniela15.
- `templates/liga_index.html`: layout principal.
- `static/js/quantum_final.js`: frontend principal.
- `static/css/quantum_pro.css`: estilos.
- `DATOS/LIGA_MAESTROS_PRO.db`: SQLite base beta.
- `schema.sql`: snapshot del esquema SQLite actual para migraciones y recuperacion.
- `tests/test_scoring.py`: pruebas de scoring critico.
- `.github/workflows/ci.yml`: checks automaticos.

## Verificacion local

Antes de proponer o subir cambios, ejecutar:

```powershell
$env:SECRET_KEY='codex-local-check'
python -m py_compile app.py LIVE_COLLECTOR.py AUDITAR_JORNADA_LIGA_MAESTROS.py
node --check static/js/quantum_final.js
pytest -q
python LIVE_COLLECTOR.py --backup-now
```

Para arrancar localmente, `SECRET_KEY` debe estar definida en `.env` o en el entorno.

## Render

Variables privadas necesarias en Render:
- `SECRET_KEY`
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `HIGHLIGHTLY_API_KEY`
- `ADMIN_EMAILS`

Variables de produccion importantes:
- `SESSION_COOKIE_SECURE=1`
- `SESSION_COOKIE_SAMESITE=Lax`
- `PREFERRED_URL_SCHEME=https`
- `ALLOW_LOCAL_ADMIN=0`

Riesgo pendiente importante: `render.yaml` no define disco persistente. Si `DB_PATH` apunta al SQLite dentro del repo, los datos escritos en produccion pueden perderse en redeploys/reinicios. Salidas posibles:
- confirmar plan de pago y anadir disco persistente en Render con `DB_PATH=/var/data/LIGA_MAESTROS_PRO.db`;
- migrar a PostgreSQL.

No activar disco persistente sin confirmar coste/plan con el propietario.

Pendiente de confirmar: el commit `369849c` quito la linea `plan: starter` de `render.yaml` sin mencionarlo en el mensaje. Si no fue intencional, revisar antes del proximo sync de Blueprint en Render. El plan condiciona si se puede anadir disco persistente.

## Revision Claude sobre 0344366

Estos puntos son sobre codigo real. Estado tras `2c031d4`:

1. Resuelto: `get_contest_profile` ya no recalcula el ranking general hasta 3 veces.
2. Resuelto en la ruta Highlightly: el contador diario ahora usa SQLite y transaccion `BEGIN IMMEDIATE`, no JSON con lock de proceso.
3. Parcialmente resuelto: `live_probe`, `/api/live/health` y `/api/sync/status` ya muestran `matches_expected` y `matches_received`, y `ok=false` si Quiniela15 no devuelve 15 partidos.
4. Resuelto: `schema.sql` generado desde `DATOS/LIGA_MAESTROS_PRO.db`.

### Mejoras que resuelven los bugs de raiz

- Pendiente: cachear `build_contest_payload` por `jornada`, invalidando por cambios en `predicciones`/`resultados`.
- Pendiente opcional: sacar `profile_for` de dentro de `build_contest_payload` si se necesita reutilizarlo sin payload completo.
- Pendiente opcional: mover tambien el rate limit de comentarios/guardado a SQLite si se quiere control estricto entre workers.
- Pendiente: hacer que el scraper Quiniela15 lance error o alerta fuerte cuando reciba menos de 15 partidos, no solo exponerlo en health/probe.

## Tareas de revision recomendadas

1. Persistencia real de datos en produccion: disco Render o PostgreSQL.
2. Backup externo de la DB y JSON criticos fuera del filesystem de Render.
3. Mantener `schema.sql` actualizado antes de migraciones.
4. Revisar si el cache de `build_contest_payload` debe ser compartido entre workers con Redis/Postgres si el trafico crece.
5. Convertir incompletos de Quiniela15 en alerta visible de UI/admin, ademas de health/probe/colector.
6. Anadir tests de endpoints para comentarios, guardado y API de concurso.
7. Reforzar tests de ranking, concurso y cierre de quinielas.
8. Revisar OAuth Google y registro de usuarios en produccion.
9. UX mobile/desktop.
10. Limpieza de mojibake/UTF-8.
11. Modularizar `app.py`, `quantum_final.js` y `quantum_pro.css` cuando haya margen.

## Reglas de colaboracion IA

- No pedir ni exponer claves reales.
- No devolver trazas internas o `str(e)` al cliente.
- Mantener SQL parametrizado.
- Verificar sintaxis y tests antes de proponer deploy.
- Priorizar cambios pequenos y reversibles.
- Si se toca Render o persistencia, explicar impacto en coste y datos antes de cambiar configuracion.
