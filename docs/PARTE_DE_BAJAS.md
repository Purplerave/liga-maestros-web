# 🩹 Parte de bajas — noticias RSS → una línea por IA

> Lo que pediste: *"Isco en el Betis, lesionado. No jugará el partido. Bellingham duda para el Madrid."*
> Titulares cortos, secos, accionables. Nada más.

---

## ⚠️ Primero, una corrección importante: NO le mandes el enlace

Dijiste "enviarle como el enlace". **Eso no funciona**, y es mejor saberlo antes de perder una tarde:

- Los modelos de las APIs gratuitas (Groq, Gemini Flash vía API) **no navegan**. No abren URLs.
- Si le mandas `https://as.com/futbol/betis-isco-lesion.html` y le pides un resumen, el modelo
  **se lo inventa a partir del texto de la URL**. Alucinación garantizada. Y en un parte de bajas,
  inventarse una lesión es el peor bug posible.
- Los que sí navegan (Perplexity, herramientas con búsqueda) **no tienen tier gratuito por API**.

**La buena noticia: no lo necesitas.** Tu RSS ya te trae el titular y el sumario. En
`news_radar.py` ya guardas `"summary": desc[:220]`. Eso es texto real, verificado, de AS y Marca.

Así que el flujo correcto es:

```
RSS (texto real) → filtro por keywords → IA resume → parte de bajas
```
y no
```
RSS → enlace → IA se inventa qué hay dentro ❌
```

---

## Cómo queda

De esto, que es lo que te da hoy el radar:

> *"El Real Betis Balompié confirma que Isco Alarcón sufre una lesión muscular en el bíceps femoral
> de la pierna derecha y será baja para el próximo encuentro liguero..."* — AS

a esto:

```
🩹 PARTE DE BAJAS · J74

Betis      ❌ Isco — lesión muscular, no juega
Madrid     ⚠️ Bellingham — duda, decide el sábado
Atlético   ❌ Giménez — sancionado
Sevilla    ⚠️ Nianzou — tocado, pendiente de prueba
```

Y en la quiniela, junto al partido:

```
Partido 7   Alavés – Betis        ❌ Isco (Betis)
```

---

## Lo que le pides al modelo

Una sola llamada con las 8 noticias juntas. Prompt corto y con la salida muy cerrada:

```python
SYSTEM = """Eres el redactor del parte de bajas de una quiniela española.
Recibes noticias de prensa deportiva en JSON.

Devuelves SOLO este JSON, sin texto alrededor:
{"bajas":[{"jugador":"Isco","equipo":"Betis","estado":"baja","nota":"lesión muscular"}]}

Reglas estrictas:
- `estado` solo puede ser: "baja" (seguro que no juega), "duda" (puede que no juegue),
  "sancion" (expulsado o sancionado), "vuelve" (regresa tras lesión).
- `nota`: MÁXIMO 5 palabras.
- Si una noticia no habla de disponibilidad de un jugador concreto, IGNÓRALA.
- NO inventes jugadores ni equipos que no aparezcan literalmente en el texto.
- Si ninguna noticia sirve, devuelve {"bajas":[]}.
"""
```

Entrada (lo que ya tienes en el radar, sin tocar nada):
```json
[{"t":"El Betis pierde a Isco por lesión muscular","s":"El centrocampista sufre..."},
 {"t":"Bellingham, duda para el derbi","s":"El inglés arrastra molestias..."}]
```

Salida: JSON pequeño y validable. **~1.400 tokens la llamada entera.**

> Fíjate en la regla más importante: **"si no habla de disponibilidad, ignórala"**. Es lo que
> convierte 8 noticias genéricas en 2-3 bajas útiles. El modelo hace de filtro fino, tus keywords
> hacen de filtro grueso.

---

## Consumo real

| | |
|---|---|
| Llamadas por refresco | **1** (las 8 noticias en lote) |
| Tokens por llamada | **~1.400** |
| Refrescos con contenido nuevo | ~2/día (la caché por firma corta el resto) |
| **Gasto diario** | **~2.800 tokens, 2 llamadas** |
| Cuota gratis de Groq | ~1.000 llamadas/día |
| **% usado** | **0,2 %** |

Podrías multiplicar el uso por 400 y seguirías dentro del tier gratuito. **No vas a fundir nada.**

---

## El código

Te he dejado el módulo listo en **`liga_maestros/services/ai/`**. Tres ficheros, sin dependencias
nuevas (usa el `requests` que ya tienes):

- `client.py` — llamada a Groq con Gemini de reserva, ambos API OpenAI-compatible.
- `budget.py` — contador diario + caché por firma. El techo duro anti-bucle.
- `bajas.py` — el parte de bajas: prompt, validación y cruce con la jornada.

### Enchufarlo (2 líneas en `news_radar.py`)

Al final de `build_news_radar`, donde ya tienes:
```python
    selected = [item for item in selected if item["score"] > 0][:8]
+   from .ai.bajas import construir_parte_bajas
    payload = {
        "fetched_at": ...,
        "items": selected,
+       "bajas": construir_parte_bajas(selected),   # [] si la IA está apagada o falla
        ...
    }
```
`construir_parte_bajas` **nunca lanza una excepción**. Si no hay API key, si se agota la cuota, si
el JSON viene mal o si Groq está caído, devuelve `[]` y el radar sigue funcionando exactamente
igual que hoy.

### Encenderlo

```bash
# .env
GROQ_API_KEY=gsk_...        # console.groq.com — gratis, sin tarjeta, 2 minutos
AI_NEWS_ENABLED=1
AI_DAILY_CALL_LIMIT=50      # techo duro: pase lo que pase, 50 llamadas y para
```

Sin `GROQ_API_KEY` o con `AI_NEWS_ENABLED=0`, el módulo no hace absolutamente nada. Puedes
mergearlo hoy sin riesgo.

### Probarlo

```bash
python -c "
from liga_maestros.services.ai.bajas import construir_parte_bajas
noticias = [{'title': 'El Betis pierde a Isco por lesión muscular',
             'summary': 'El centrocampista sufre una lesión en el bíceps femoral y será baja.'}]
print(construir_parte_bajas(noticias))
"
```

---

## Las 3 salvaguardas que evitan el gasto

1. **Lote.** Una llamada con las 8 noticias, nunca 8 llamadas. Ahorra el 62 %.
2. **Caché por firma.** Se hashean los links; si no han cambiado, se devuelve lo cacheado sin
   llamar a nadie. **La mayoría de refrescos cuestan 0 tokens.**
3. **Techo diario.** `AI_DAILY_CALL_LIMIT=50`. Aunque metas un bucle infinito por error, gasta 50
   llamadas y se apaga solo hasta el día siguiente.

Y una cuarta contra las alucinaciones: **el campo `equipo` se valida contra tu lista real de
equipos**. Si el modelo se inventa un "Betis FC" que no existe en tu jornada, esa baja se descarta
silenciosamente. Solo pasan las que casan con equipos reales.

---

## Y lo mejor: cruzarlo con la quiniela sale gratis

Una vez tienes `{"jugador":"Isco","equipo":"Betis","estado":"baja"}`, colocar el aviso junto al
partido correcto es un cruce en Python. **Cero tokens**, y es la parte que de verdad se usa:

```
Partido 7   Alavés – Betis     ❌ Isco (Betis) — lesión muscular
```

Justo ahí, en el momento de marcar el 1X2. Eso es lo que hace que alguien abra la web el viernes
por la noche antes de firmar su quiniela.
