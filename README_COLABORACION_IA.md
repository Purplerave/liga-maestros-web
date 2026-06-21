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

Estos puntos son sobre codigo real. Clonar y verificar antes de tocar.

1. `get_contest_profile` recalcula el ranking general hasta 3 veces para un solo perfil (`app.py`, funciones `get_contest_profile` y `build_contest_payload`). La segunda y la tercera llamada usan los mismos argumentos (`jornada`, `target`); si la segunda no encuentra perfil, la tercera repite lo mismo y no puede dar un resultado distinto. Ademas `profile_for` esta definida dentro de `build_contest_payload`, asi que no se puede pedir un perfil suelto sin reconstruir el ranking general completo.
2. El contador diario de Highlightly tiene condicion de carrera entre workers (`get_highlightly_usage`, `record_highlightly_call`, `reserve_highlightly_calls`). El contador vive en JSON protegido solo por un `threading.Lock` de proceso. Con `gunicorn --workers 2`, cada worker tiene su propio lock y pueden perderse actualizaciones. Esto puede gastar mas cupo diario de Highlightly del limite configurado.
3. El scraper de Quiniela15 puede romperse en silencio (`SCRAPE_QUINIELA15_DIRECTO.py`, funcion `scrape`). Si cambia el HTML, puede devolver `matches: []` o lista parcial sin excepcion. `live_probe` puede mostrar `ok: true` si hubo respuesta HTTP valida aunque no haya 15 partidos.
4. No habia snapshot SQL del esquema para `usuarios`, `resultados`, `predicciones`, `clasificacion` ni `consenso`. Mitigacion aplicada: `schema.sql` generado desde `DATOS/LIGA_MAESTROS_PRO.db`.

### Mejoras que resuelven los bugs de raiz

- Cachear `build_contest_payload` por `jornada`, invalidando por cambios en `predicciones`/`resultados`.
- Sacar `profile_for` de dentro de `build_contest_payload` para pedir perfiles sin recalcular el ranking general entero.
- Mover el contador de Highlightly y, si hace falta, el rate limit de comentarios/guardado a SQLite con `UPSERT`, para que funcione correctamente con varios workers de Gunicorn.
- En `live_probe` y `/api/live/health`, exponer `matches_esperados` frente a `matches_recibidos` para detectar scraper roto de un vistazo.

## Tareas de revision recomendadas

1. Persistencia real de datos en produccion: disco Render o PostgreSQL.
2. Backup diario de la DB y JSON criticos.
3. Mantener `schema.sql` actualizado antes de migraciones.
4. Arreglar condicion de carrera del contador Highlightly entre workers de Gunicorn.
5. Quitar llamadas redundantes a `build_contest_payload` en `get_contest_profile`.
6. Anadir chequeo de `matches` esperados frente a recibidos en el scraper de Quiniela15.
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
