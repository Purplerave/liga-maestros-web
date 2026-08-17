# Prompt para predicciones Jornada 2 - Liga de Maestros 2026-2027

Usa este prompt con cada IA (Grok, Claude, ChatGPT, Copilot, Gemini) vía lmarena.ai
para obtener sus predicciones. Cierre: **sábado 22/08/2026, 17:00**.

Partidos verificados contra Quiniela15 (J2).

---

## Prompt para la IA:

```
Eres un analista de fútbol experto especializado en La Quiniela española. Necesito tus pronósticos para la Jornada 2 de La Liga y Segunda División, temporada 2026-2027.

Para cada partido, responde: 1 (gana local), X (empate), 2 (gana visitante).
Para el partido 15 (Pleno al 15), predice también el marcador exacto.

Partidos (cierre: sábado 22/08/2026, 17:00):

1. Athletic Club vs Sevilla
2. Valencia vs Celta
3. Espanyol vs Real Madrid
4. Getafe vs Racing Santander
5. Elche vs Barcelona
6. Osasuna vs Levante
7. Málaga vs Deportivo
8. Real Oviedo vs Leganés
9. Ceuta vs Las Palmas
10. Eldense vs Cádiz
11. Eibar vs Valladolid
12. Castellón vs Sabadell
13. Sporting Gijón vs Burgos
14. Tenerife vs Almería
15. Atlético Madrid vs Villarreal [PLENO AL 15]

Responde SOLO con un array JSON de 15 elementos (1, X, 2, o "M-M" para el partido 15).
Ejemplo: ["1","X","2","1","2","1","X","1","2","2","1","1","2","1","2-1"]
```

---

## Instrucciones para usar:

1. Copia el prompt de arriba.
2. Pégalo en cada IA (Grok, Claude, ChatGPT, Copilot, Gemini) vía lmarena.ai.
3. Copia la respuesta JSON de cada modelo.
4. Vuelca los arrays en `data/inbox/JORNADA_2_LM_ARENA.json` siguiendo el mismo
   esquema que `data/inbox/JORNADA_1_LM_ARENA.json` (`schema_version`, `jornada`,
   `temporada`, `fuente`, `partidos`, `pronosticos`, `incidencias`).

## Formato esperado de cada pronóstico en el inbox:

```json
{
  "participante_id": "claude",
  "nombre_publico": "Claude",
  "ia_origen": "Claude",
  "grupo": "maestro",
  "signos": ["1", "X", "2", "1", "2", "1", "X", "1", "2", "2", "1", "1", "1", "1", "2-1"]
}
```

Notas:

- Signos válidos: `1`, `X`, `2` (y dobles canónicos `1X`, `X2`, `12` si el
  modelo se cubre). Normaliza variantes tipo `1/X` → `1X` y registra el ajuste
  en `incidencias`, igual que se hizo en J1.
- El partido 15 lleva marcador exacto (`"2-1"`), no signo.
- El pronóstico de `programa` sale del motor propio, no de LM Arena.
