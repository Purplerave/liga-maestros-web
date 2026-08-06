# Prompt para predicciones Quiniela Jornada 1 - Liga de Maestros 2026-2027

Usa este prompt con cada IA (Grok, Claude, ChatGPT, Copilot, Gemini) para obtener sus predicciones.

---

## Prompt para la IA:

```
Eres un analista de fútbol experto especializado en La Quiniela española. Necesito que hagas tus pronósticos para la Jornada 1 de la temporada 2026-2027.

## Contexto importante:
- La Quiniela mezcla partidos de Primera y Segunda División
- Para cada partido, elige: 1 (gana local), X (empate), 2 (gana visitante)
- El partido 15 es el "Pleno al 15": debes predecir el marcador exacto (ejemplo: "2-1")

## Partidos de la Jornada 1:

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

## Instrucciones:

1. **Analiza cada partido** considerando:
   - Fichajes y bajas de cada equipo
   - Forma en la pretemporada
   - Historial de enfrentamientos directos
   - Factor localía
   - Motivación y objetivos del equipo

2. **Para el Pleno al 15 (partido 15)**, predice el marcador exacto considerando:
   - Goles esperados de cada equipo
   - Tendencia goleadora de ambos equipos
   - Si es un partido abierto o defensivo

3. **Responde en este formato CSV** (una línea por partido):

```
partido,pronostico,confianza,marcador_15,explicacion
1,1,alta,,"Oviedo fuerte en casa, Granada en reconstrucción"
2,X,media,,"Partido igualado, ambos equipos recién ascendidos"
...
15,1,alta,2-0,"Deportivo en casa, Elche en crisis institucional"
```

4. **Explicación breve**: Para cada partido, una frase corta (máximo 10 palabras) que justifique tu pronóstico.

5. **Confianza**: Indica si tu predicción es alta, media o baja.

---

## Ejemplo de respuesta esperada:

```csv
partido,pronostico,confianza,marcador_15,explicacion
1,1,alta,,"Oviedo fuerte en casa, Granada debilitada"
2,1,media,,"Alavés con mejor plantilla, Getafe en transición"
3,X,media,,"Partido equilibrado entre recién ascendidos"
4,2,alta,,"Sabadell con mejor forma, Sporting en crisis"
5,1,alta,,"Sevilla en casa, Rayo con bajas importantes"
6,X,media,,"Eibar y Tenerife, equipos similares"
7,1,media,,"Santander con ilusión, Villarreal en pretemporada"
8,1,media,,"Andorra en casa, Ceuta con problemas económicos"
9,X,media,,"Burgos y Córdoba, equipos de nivel similar"
10,1,alta,,"Espanyol en casa, Levante recién ascendido"
11,2,media,,"Celta Fortuna con cantera, Cádiz en transición"
12,1,media,,"Girona con mejor plantilla, Leganés en reconstrucción"
13,1,alta,,"Celta en casa, Osasuna con bajas"
14,X,media,,"Las Palmas y Albacete, equipos similares"
15,1,alta,2-0,"Deportivo en casa, Elche en crisis"
```

---

## Nota final:
Responde SOLO con el CSV, sin texto adicional. El CSV debe tener exactamente 15 líneas de datos (más la cabecera).
```

---

## Instrucciones para usar:

1. Copia el prompt de arriba
2. Pégalo en cada IA (Grok, Claude, ChatGPT, Copilot, Gemini)
3. Copia la respuesta CSV
4. Convierte el CSV a JSON y pégalo en `data/predicciones_J1.json`

---

## Script para convertir CSV a JSON:

```python
import csv
import json

csv_data = """partido,pronostico,confianza,marcador_15,explicacion
1,1,alta,,"Oviedo fuerte en casa, Granada debilitada"
2,1,media,,"Alavés con mejor plantilla, Getafe en transición"
...
"""

reader = csv.DictReader(csv_data.strip().splitlines())
predictions = []
for row in reader:
    predictions.append({
        "partido": int(row["partido"]),
        "pronostico": row["pronostico"],
        "confianza": row["confianza"],
        "marcador_15": row.get("marcador_15", ""),
        "explicacion": row["explicacion"]
    })

print(json.dumps(predictions, indent=2, ensure_ascii=False))
```
