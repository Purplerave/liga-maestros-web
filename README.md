# Liga de Maestros

Web Flask para gestionar una jornada de quiniela competitiva: Programa, Maestros IA, La Pena, directo, porra, Snake Gol, quiz y rankings.

## Arranque local

```powershell
git clone https://github.com/Purplerave/liga-maestros-web.git
cd liga-maestros-web
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
python app.py
```

La web local queda en `http://127.0.0.1:5000/`.

## Variables importantes

Configura `.env` a partir de `.env.example`.

- `SECRET_KEY`: obligatoria fuera de desarrollo.
- `GOOGLE_CLIENT_ID` y `GOOGLE_CLIENT_SECRET`: login Google.
- `HIGHLIGHTLY_API_KEY`: datos en directo.
- `DB_PATH`: ruta de SQLite si usas disco persistente.
- `DATA_DIR`: carpeta de JSON/logs runtime si usas disco persistente.
- `ADMIN_EMAILS`: emails con permisos de administracion.

No subas `.env` ni bases de datos vivas con usuarios reales.

## Flujo semanal

1. Importar o actualizar partidos de la jornada.
2. Importar predicciones del Programa, Maestros IA y La Pena.
3. Revisar horarios y cierre.
4. Probar `/api/liga/data?j=XX`.
5. Arrancar collector solo cuando interese seguir directo.
6. Auditar resultados y rankings tras la jornada.

## Scripts utiles

- `SCRAPE_QUINIELA15_PROXIMA.py`: apoyo para proxima jornada.
- `SCRAPE_QUINIELA15_DIRECTO.py`: apoyo para directo Quiniela15.
- `LIVE_COLLECTOR.py`: refresco de directo con control de llamadas.
- `IMPORTAR_PROGRAMA_JORNADA.py`: carga de columna Programa.
- `IMPORTAR_QUIZ_JORNADA.py`: carga de preguntas del quiz.
- `AUDITAR_JORNADA_LIGA_MAESTROS.py`: revision de jornada.

## Tests

```powershell
python -m pytest -q
node --check static\js\quantum_final.js
node --check static\js\snake_gol_arcade.js
```

## Estructura

- `app.py`: entrada minima.
- `liga_maestros/`: factory Flask, rutas, servicios, DB y middleware.
- `templates/`: shell HTML principal.
- `static/`: CSS, JS e imagenes.
- `data/`: JSON publicos/semillas.
- `DATOS/`: base SQLite y datos runtime locales.
- `tests/`: pruebas unitarias.

## Seguridad practica

- La quiniela se cierra por sesion, jornada, longitud de 15 signos y hora de inicio.
- Snake y Quiz tienen validaciones servidor para evitar puntuaciones triviales inventadas desde consola.
- La base `DATOS/LIGA_MAESTROS_PRO.db` debe tratarse como dato vivo local o de disco persistente, no como fuente de codigo.
