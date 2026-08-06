# Prompt para predicciones Jornada 1 - Liga de Maestros 2026-2027

Usa este prompt con cada IA (Grok, Claude, ChatGPT, Copilot, Gemini) para obtener sus predicciones.

---

## Prompt para la IA:

```
Eres un analista de fútbol experto. Necesito que hagas tus pronósticos para la Jornada 1 de La Quiniela española (temporada 2026-2027).

Para cada partido, elige:
- **1** si crees que gana el equipo local
- **X** si crees que será empate
- **2** si crees que gana el equipo visitante

Para el partido 15 (Pleno al 15), además predice el marcador exacto (ejemplo: "2-1").

Aquí tienes los 15 partidos:

1. Real Oviedo vs Granada (Segunda) - Sáb 15/08 17:00
2. Alavés vs Getafe (Primera) - Sáb 15/08 19:30
3. Mallorca vs Valladolid (Primera) - Sáb 15/08 19:30
4. Sporting Gijón vs Sabadell (Segunda) - Sáb 15/08 19:00
5. Sevilla vs Rayo Vallecano (Primera) - Sáb 15/08 21:30
6. Eibar vs Tenerife (Segunda) - Sáb 15/08 21:30
7. R. Santander vs Villarreal (Primera) - Dom 16/08 17:00
8. Andorra vs Ceuta (Segunda) - Dom 16/08 17:00
9. Burgos vs Córdoba (Segunda) - Dom 16/08 17:00
10. Espanyol vs Levante (Primera) - Dom 16/08 19:00
11. Cádiz vs Celta Fortuna (Segunda) - Dom 16/08 19:00
12. Girona vs Leganés (Segunda) - Dom 16/08 19:00
13. Celta vs Osasuna (Primera) - Dom 16/08 21:30
14. Las Palmas vs Albacete (Segunda) - Dom 16/08 21:00
15. Deportivo vs Elche (Segunda) - Dom 16/08 21:00 [PLENO AL 15]

Responde SOLO con un array JSON de 15 elementos con tus predicciones (1, X, 2, o marcador para el partido 15).

Ejemplo de respuesta:
["1", "X", "1", "2", "1", "X", "1", "2", "1", "1", "X", "1", "2", "1", "2-1"]
```

---

## Instrucciones para usar:

1. Copia el prompt de arriba
2. Pégalo en cada IA (Grok, Claude, ChatGPT, Copilot, Gemini)
3. Copia la respuesta JSON
4. Pega el resultado en `data/predicciones_J1.json` en el campo correspondiente

---

## Formato esperado en predicciones_J1.json:

```json
{
  "jornada": 1,
  "programa": {
    "signos": ["1", "X", "1", "2", "1", "X", "1", "2", "1", "1", "X", "1", "2", "1", "2-1"],
    "nombre": "PROGRAMA",
    "puntos_jornada": 0
  },
  "grok": {
    "signos": [...],
    "nombre": "GROK",
    "puntos_jornada": 0
  }
  // ... etc
}
```
