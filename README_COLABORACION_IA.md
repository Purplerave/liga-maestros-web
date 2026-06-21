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

## Tareas de revision recomendadas

1. Persistencia real de datos en produccion: disco Render o PostgreSQL.
2. Backup diario de la DB y JSON criticos.
3. Reforzar tests de ranking, concurso y cierre de quinielas.
4. Revisar OAuth Google y registro de usuarios en produccion.
5. Control de consumo de API Highlightly.
6. UX mobile/desktop.
7. Limpieza de mojibake/UTF-8.
8. Modularizar `app.py`, `quantum_final.js` y `quantum_pro.css` cuando haya margen.

## Reglas de colaboracion IA

- No pedir ni exponer claves reales.
- No devolver trazas internas o `str(e)` al cliente.
- Mantener SQL parametrizado.
- Verificar sintaxis y tests antes de proponer deploy.
- Priorizar cambios pequenos y reversibles.
- Si se toca Render o persistencia, explicar impacto en coste y datos antes de cambiar configuracion.
