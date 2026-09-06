# Operacion semanal Liga de Maestros

Objetivo: que cada jornada salga igual de limpia sin revisar todo a mano.

## 1. Cargar jornada

- Importar o scrapear la jornada oficial.
- Confirmar que hay 15 partidos en `resultados`.
- Confirmar horas y fechas antes de generar predicciones.

Camino rapido recomendado:

```powershell
# 1) Ver que extrae Quiniela15 sin escribir nada
python SCRAPE_QUINIELA15_PROXIMA.py --dry-run

# 2) Si esta bien, generar archivos base
python SCRAPE_QUINIELA15_PROXIMA.py

# 3) Importar a Liga de Maestros. Cambia N por la jornada nueva.
python IMPORTAR_PROGRAMA_JORNADA.py --jornada N --dry-run --usar-q15-base
python IMPORTAR_PROGRAMA_JORNADA.py --jornada N --usar-q15-base

# 4) Auditoria obligatoria
python AUDITAR_JORNADA_LIGA_MAESTROS.py --jornada N
```

Regla: si la auditoria no dice que hay 15/15 partidos y predicciones completas, la jornada no se da por lista.

## 2. Generar predicciones

Capas separadas:

- `programa`: motor propio.
- `consejo_ias`: consenso final de modelos, solo cuando se decida usarlo en una jornada concreta.
- `gemini`, `grok`, `claude`, `copilot`, `chatgpt`: maestros individuales cuando existan.
- Usuario: quiniela personal autenticada.
- La Pena: grupo social y aliases, nunca usuario unico.

Regla: Programa y usuario deben tener 15/15 antes de dar la jornada por lista. Consejo IA es opcional.

## 3. Generar y importar el Quiz (Reto 10 LaLiga)

Cada jornada se genera un banco de 10 preguntas de quiz. Flujo:

### 3.1 Generar preguntas con IA

Pedir a una IA que genere un JSON con este formato exacto:

```json
{
  "jornada": 72,
  "generated_at": "2026-07-05T12:00:00",
  "preguntas": [
    {
      "tipo": "multiple",
      "enunciado": "Texto de la pregunta",
      "opcion_a": "Respuesta A",
      "opcion_b": "Respuesta B",
      "opcion_c": "Respuesta C",
      "respuesta_correcta": "B",
      "explicacion": "Breve explicacion.",
      "dificultad": 1,
      "tema": "actualidad"
    }
  ]
}
```

**Reglas para las preguntas:**
- Siempre 10 preguntas exactas.
- `respuesta_correcta` debe ser "A", "B" o "C".
- Mezclar temas: actualidad, historia, estadistica, jugadores, estadios, entrenadores, quiniela, Liga de Maestros.
- Dificultad: 1=facil, 2=medio, 3=dificil.
- Las preguntas deben conectar con la jornada actual (clasificacion, partidos, rachas).
- Evitar preguntas ambiguas o con multiples respuestas validas.

Guardarlo como `data/QUIZ_BANK_J{N}.json`.

### 3.2 Revisar el JSON

Abrir el JSON y comprobar:
- Las 3 respuestas son plausibles.
- La respuesta correcta es efectivamente correcta.
- No hay errores ortograficos.
- Las preguntas no se repiten de jornadas anteriores.

### 3.3 Importar a la BD

```powershell
# Dry-run primero para ver las preguntas
python IMPORTAR_QUIZ_JORNADA.py --jornada 72 --dry-run

# Importar definitivamente
python IMPORTAR_QUIZ_JORNADA.py --jornada 72
```

El importador crea backup automatico de la BD antes de escribir.

### 3.4 Verificar en la web

Abrir la web y comprobar que el "Reto 10" aparece con las 10 preguntas.

## 4. Revisar antes de sellar

Comprobar:

- Programa 15/15.
- Consejo IA 15/15 solo si esa jornada se juega con consenso IA.
- Usuario 15/15 si ya se ha guardado.
- Pleno al 15 en formato Quiniela: `0`, `1`, `2`, `M` por cada equipo. Ejemplo: `M-0`, no `3-0`.
- Escudos/banderas resuelven desde `utils.load_team_logos()`.

## 4. Durante la jornada

- La web puede refrescar datos internos sin gastar API.
- Las llamadas externas tienen que venir del colector/controlador, no del refresco del navegador.
- Si hay partido suspendido, bloquear el resultado oficial LAE manualmente y auditar.

Pruebas utiles antes de que empiece:

```powershell
# No debe gastar API si la ventana esta cerrada.
python LIVE_COLLECTOR.py --once --jornada N

# Solo para admin/local cuando quieras forzar una prueba puntual.
python LIVE_COLLECTOR.py --once --force --jornada N
```

En produccion Render, el collector interno se activa con `WEB_COLLECTOR_ENABLED=1`.
El navegador nunca debe llamar a Highlightly por refrescar la pagina.

### Fin de semana: Directo, horarios y cierre de resultados

Los findes son donde todo esto se rompe, y es lo primero que hay que mirar si un
sábado o un domingo «no se actualiza» o «faltan los partidos de ayer».

- **Las horas.** El proveedor (Highlightly) responde en UTC; la web guarda y sirve
  reloj de Madrid sin zona (`added`, `fecha_raw`, `hora`). Si en la web se ve una
  hora dos horas retrasada, el panel no se está reconvirtiendo: comprobar
  `data/LIVE_ALL_MATCHES_V3.json` (`added` tiene que decir `21:30:00`, no
  `19:30:00.000Z`).
- **El boleto sin horarios.** `python SCRAPE_QUINIELA15_PROXIMA.py --dry-run` tiene
  que sacar `fecha` y `hora` en las 15 filas. Si salen vacías, el programa se pinta
  «Horario por confirmar»: el collector sigue refrescando (`reason=sin_horarios`),
  pero la peña no ve la hora.
- **Ventana rodada.** El DIRECTO y la portada enseñan ayer..mañana y se estiran a
  toda la jornada en curso mientras no haya quedado atrás: el lunes se puede
  revisar el finde, y un partido en juego se ve sea del día que sea (hasta seis
  horas después de su saque real).
- **Cierre de resultados.** Mientras quede una fila sin `FT` la ventana sigue
  abierta: cada 15 minutos si el partido es reciente y tres veces al día si es un
  aplazado viejo (hasta 7 días). Con el tope de llamadas por pasada
  (`HIGHLIGHTLY_MAX_CALLS_PER_REFRESH`, 4) las ligas del boleto van primero, así
  que Liga F no se queda fuera de presupuesto.
- **Un solo collector por disco.** El worker en proceso y un `LIVE_COLLECTOR.py`
  lanzado a mano compiten por un `flock` en `DATA_DIR`; el que no lo coge no gasta
  cuota. Al arrancar, el worker fuerza una pasada de cierre (si el servidor estuvo
  caído durante el partido, eso recupera el resultado en cuanto vuelve).
- **Forzar una pasada.** `python LIVE_COLLECTOR.py --once --force --jornada N`.
- **Caché del navegador.** Tocada una URL de `/static/*` en el HTML, hay que subir
  el `?v=` correspondiente y el `STATIC_CACHE` de `static/sw.js`; si no, los que
  tienen la app instalada siguen ejecutando el JS viejo y nada de lo anterior se
  nota en su pantalla.

## 5. Despues de la jornada

- Ejecutar auditoria.
- Revisar ranking de jornada.
- Revisar ranking general.
- Revisar ranking del Reto 10 (quiz).
- Guardar ganador de jornada y, si toca, ganador mensual.
- No borrar predicciones historicas; ocultar IDs obsoletos desde configuracion.
- Generar banco de preguntas del quiz para la proxima jornada (ver paso 3).

## 6. Endpoints del quiz

- `GET /api/quiz/preguntas?j=72` — Devuelve las 10 preguntas de la jornada.
- `POST /api/quiz/submit` — Guarda respuestas y devuelve resultado + ranking.
- `GET /api/quiz/ranking?tipo=jornada&j=72` — Ranking semanal.
- `GET /api/quiz/ranking?tipo=temporada` — Ranking de temporada.
- `GET /api/quiz/ranking?tipo=mensual&mes=2026-07` — Ranking mensual.
- `GET /api/quiz/mi-historial` — Historial del usuario actual.

## 7. Puntuacion del quiz

| Accion | Puntos |
|--------|--------|
| Respuesta correcta (dificultad 1) | 100 |
| Respuesta correcta (dificultad 2-3) | 150 |
| Racha de 5 correctas seguidas | +50 bonus |
| Perfecto 10/10 | +300 bonus |
| Bonus rapidez (max) | +30 |
| Participar cada jornada | +25 |

## Comandos rapidos

```powershell
# Auditoria
python AUDITAR_JORNADA_LIGA_MAESTROS.py --jornada N

# Nueva jornada desde Quiniela15
python SCRAPE_QUINIELA15_PROXIMA.py --dry-run
python SCRAPE_QUINIELA15_PROXIMA.py
python IMPORTAR_PROGRAMA_JORNADA.py --jornada N --dry-run --usar-q15-base
python IMPORTAR_PROGRAMA_JORNADA.py --jornada N --usar-q15-base

# Quiz - dry-run
python IMPORTAR_QUIZ_JORNADA.py --jornada N --dry-run

# Quiz - importar
python IMPORTAR_QUIZ_JORNADA.py --jornada N

# Compilar todo
python -m py_compile app.py liga_maestros/__init__.py liga_maestros/services/quiz.py liga_maestros/routes/quiz.py
node --check static/js/quantum_final.js

# Tests
pytest -q
```
