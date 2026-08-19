# Prompt Deep Search — Quiniela Jornada 2

```text
Analiza en profundidad la Jornada 2 de La Quiniela 2026-2027 y pronostica los 15 partidos.

Haz una búsqueda web actualizada antes de responder. Para cada partido debes comprobar:

- El primer partido oficial de esta temporada de ambos equipos: resultado, rendimiento, ocasiones, estadísticas, once inicial y contexto.
- La pretemporada completa: resultados, nivel de los rivales, goles y participación de los titulares.
- Lesiones, sanciones, fichajes, salidas, convocatorias y posibles rotaciones.
- Estado de forma, localía, descanso y desplazamientos.
- Encaje táctico, fortaleza ofensiva y defensiva y balón parado.
- Cuotas y pronósticos recientes únicamente como contraste, sin copiarlos automáticamente.

Da más importancia al primer partido oficial, las bajas actuales y el once probable que a amistosos antiguos. Contrasta la información, no inventes datos y no muestres todo el proceso de investigación.

PARTIDOS

1. Athletic Club - Sevilla — 22/08/2026 17:00
2. Valencia - Celta — 22/08/2026 19:30
3. Espanyol - Real Madrid — 22/08/2026 21:30
4. Getafe - Racing de Santander — 23/08/2026 19:30
5. Elche - Barcelona — 23/08/2026 21:30
6. Osasuna - Levante — 24/08/2026 19:30
7. Málaga - Deportivo — 24/08/2026 21:30
8. Real Oviedo - Leganés — 22/08/2026 17:00
9. Ceuta - Las Palmas — 22/08/2026 19:00
10. Eldense - Cádiz — 22/08/2026 21:30
11. Eibar - Valladolid — 23/08/2026 17:00
12. Castellón - Sabadell — 23/08/2026 19:00
13. Sporting de Gijón - Burgos — 23/08/2026 19:00
14. Tenerife - Almería — 23/08/2026 21:30
15. Atlético de Madrid - Villarreal — 23/08/2026 17:00 — PLENO AL 15

FORMATO DE RESPUESTA

Devuelve solamente un array JSON válido con exactamente 15 elementos. Cada elemento debe incluir:

- "numero": número del partido.
- "partido": nombres de los dos equipos.
- "resultado": pronóstico.
- "explicacion": explicación concreta de entre 8 y 18 palabras.

Para los partidos 1-14, el resultado debe ser exclusivamente "1", "X" o "2".

Para el partido 15, escribe el resultado oficial del Pleno al 15 usando 0, 1, 2 o M para cada equipo. M significa tres o más goles. Ejemplos: "2-1", "M-1" o "1-M".

No incluyas introducciones, fuentes, tablas, probabilidades, conclusiones ni texto fuera del JSON.

Ejemplo del formato:

[
  {
    "numero": 1,
    "partido": "Athletic Club - Sevilla",
    "resultado": "1",
    "explicacion": "El Athletic llega más sólido, juega en casa y presenta menos bajas importantes."
  },
  {
    "numero": 2,
    "partido": "Valencia - Celta",
    "resultado": "X",
    "explicacion": "Partido equilibrado tras un estreno similar y sin superioridad ofensiva clara."
  }
]

Antes de responder, comprueba que hay 15 partidos, que están ordenados y que el JSON es válido.

Responde únicamente con el JSON final.
```
