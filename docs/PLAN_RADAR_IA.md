# 📰🤖 Radar de noticias + IA — sin fundir tokens

> Plan concreto sobre `origin/main` @ `98bfe60`
> Objetivo: enchufar una IA gratuita al radar de noticias que **ya tienes**, gastando lo mínimo posible.

---

## 0. Buenas noticias: ya tienes hecha la mitad difícil

Esto no es empezar de cero. `services/news_radar.py` ya hace:

- ✅ Descarga de **5 feeds RSS** (LALIGA, AS, Mundo Deportivo, Sport, Marca)
- ✅ Parseo seguro con `defusedxml` + `sanitize_xml_payload` (bien hecho: RSS es XML hostil)
- ✅ Validación de esquema/host de cada URL
- ✅ **Deduplicado** por título normalizado
- ✅ **Scoring de relevancia** por keywords (equipo = 4 pts, genérica = 2 pts)
- ✅ Corte a **top 8** con `score > 0`
- ✅ Caché en disco con TTL de 900 s
- ✅ Endpoint `/api/noticias/radar` con `force` restringido a admin

**Lo que falta es solo la última milla: la capa de IA.** Y la buena noticia para tu preocupación
sobre tokens es que ese pipeline **ya es un filtro brutal**: de ~300 noticias que llegan por RSS,
solo 8 sobreviven. La IA nunca ve las otras 292.

> 🔎 **Hallazgo aparte:** el radar **no se consume en ningún sitio del frontend**. Hay un
> `data-radar-match` en `events.js`, pero es otra cosa (el radar de sorpresas de La Peña).
> Estás manteniendo 95 líneas de scraping de noticias que **nadie ve**. O lo enchufas a la UI, o
> deberías borrarlo. Este plan asume lo primero.

---

## 1. La matemática de los tokens (por qué NO vas a fundir nada)

Vamos con números reales, no con intuiciones.

### Presupuesto disponible (tier gratuito, sin tarjeta)

| Proveedor | Req/día | Tokens/min | ¿Entrena con tus datos? |
|---|---:|---:|---|
| **Groq** (Llama 3.3 70B) | ~1.000 | 6.000 TPM | **No** |
| **Gemini 2.5 Flash** | ~1.500 | hasta 1M TPM | Sí (tier gratuito) |
| **Cerebras** | ~30 RPM | ~1M tok/día | No |

El límite que te va a apretar en Groq **no es el diario, es el TPM (6.000 tokens/minuto)**. Diséñalo
en torno a eso.

### Consumo real de este caso de uso

Una noticia del radar ocupa: título (~15 tokens) + `summary` truncado a 220 caracteres (~60 tokens)
+ fuente y fecha (~10). Total: **~85 tokens por noticia**.

| Estrategia | Tokens entrada | Salida | Total/ejecución |
|---|---:|---:|---:|
| ❌ 1 llamada por noticia (8 llamadas) | 8 × (85 + 250 prompt) | 8 × 120 | **~3.640** |
| ✅ **1 llamada con las 8 en lote** | 680 + 300 prompt | ~400 | **~1.380** |

Con la estrategia de lote: **~1.400 tokens por refresco**.

- Refrescando **cada 6 horas** → 4 ejecuciones/día → **5.600 tokens/día, 4 llamadas/día**.
- Sobre 1.000 req/día de Groq, usas el **0,4 % de la cuota**.
- Cabes ~250 veces dentro del tier gratuito.

**Conclusión: es literalmente imposible que fundas los tokens con este diseño.** El riesgo real no
es el volumen, es un bucle accidental (un `force=1` en un `setInterval`, o el collector llamando en
cada tick). Eso se ataja con las salvaguardas del punto 3.

---

## 2. Las 7 reglas de oro para no gastar

Este es el corazón de tu pregunta. Ordenadas por cuánto ahorran.

### Regla 1 — Filtra ANTES de la IA (ya lo haces, ahora explótalo)
Tu `news_relevance_score` es un filtro gratis. Endurécelo antes de llamar a la IA:
```python
# solo van a la IA las noticias que mencionan un equipo (score >= 4)
# y que sean de las últimas 48 h
candidatas = [n for n in selected if n["score"] >= 4 and es_reciente(n, horas=48)][:8]
```
De 300 → 8 → quizá 5. **Cada noticia que descartas con `if` es una noticia gratis.**

### Regla 2 — Una sola llamada en lote, nunca N llamadas
Manda las 8 noticias numeradas en un único prompt y pide un array JSON de vuelta. Ahorro: **62 %**
(el prompt de sistema se paga una vez en lugar de ocho). Es la optimización más grande de todas.

### Regla 3 — Caché por hash de contenido
```python
firma = hashlib.sha256("|".join(sorted(n["link"] for n in candidatas)).encode()).hexdigest()
if cache.get("ia_firma") == firma:
    return cache["ia_resultado"]   # 0 tokens
```
Como los feeds cambian poco entre refrescos, **la mayoría de ejecuciones costarán 0 tokens.** En la
práctica esto te deja en 1-2 llamadas reales al día, no 4.

### Regla 4 — Trunca la entrada con dureza
Ya truncas `summary` a 220 caracteres. Mantenlo. **No mandes nunca el cuerpo del artículo**: no
compensa. Título + 220 caracteres es suficiente para clasificar y resumir.

### Regla 5 — Limita la salida con `max_tokens`
`max_tokens=500` en la llamada de lote. Es un tope duro: aunque el modelo se emocione, no puede
gastar más. Y pide respuestas explícitamente cortas en el prompt ("máximo 20 palabras por noticia").

### Regla 6 — Reutiliza tu contador de cuota
Tienes `services/highlightly_limits.py` (192 líneas) con cuota diaria, reserva y circuit breaker con
cooldown exponencial. **Cópialo tal cual para la IA.** Con `AI_DAILY_CALL_LIMIT=50` tienes un techo
absoluto: aunque haya un bug de bucle infinito, gastas 50 llamadas y se para solo.

### Regla 7 — Cron, no request
La IA se ejecuta **en el collector que ya tienes corriendo** o en un cron, nunca dentro de la
petición de un usuario. Si 30 personas abren la portada a la vez, eso son 0 llamadas nuevas: todas
leen el JSON cacheado.

---

## 3. Qué le pides a la IA (3 funciones, de menos a más ambiciosa)

### 🥇 Función A — Enriquecer el radar: clasificar + resumir + ligar a equipos

Una llamada, las 8 noticias, y por cada una: un resumen de una línea, la categoría, el impacto y
**qué equipos de la jornada afecta**. Esto último es la clave: convierte una lista de titulares
genéricos en **información accionable para rellenar la quiniela**.

```python
SYSTEM = """Eres un analista de fútbol español. Recibes noticias en JSON.
Para cada una devuelves EXACTAMENTE este formato, sin texto adicional:
{"resultados":[{"i":0,"resumen":"...","categoria":"lesion|alineacion|sancion|fichaje|previa|otro",
"impacto":0-3,"equipos":["..."]}]}
Reglas: resumen de MAXIMO 20 palabras. `equipos` solo con nombres que aparezcan literalmente
en la noticia. `impacto` = cuánto afecta al resultado de un partido (0 nada, 3 decisivo).
No inventes datos que no estén en el texto."""
```

Entrada: `[{"i":0,"t":"titular","s":"sumario 220 chars"}, ...]`
Coste: **~1.400 tokens**. Salida: JSON validable.

**Por qué esta primero:** es la que más valor da por token gastado, no tiene riesgo de alucinación
grave (solo resume lo que le das) y el resultado es cacheable durante horas.

### 🥈 Función B — "Alertas de jornada": cruzar noticias con TUS 15 partidos

Aquí está la magia de verdad, y es **casi gratis** porque reutiliza la salida de la Función A:

```
Partido 7: Alavés - Betis
⚠️ El Betis pierde a Isco por lesión (AS, hace 3 h) — impacto alto
```

Y **no necesita IA en absoluto**: una vez que la Función A te ha dado `equipos: ["Betis"]`
normalizado, cruzarlo con los equipos de la jornada es un `set intersection` en Python. **0 tokens.**

Esto es lo que convierte el radar en algo que la gente **usa** en vez de mirar: aparece un aviso
justo al lado del partido, en el momento de decidir el 1X2.

### 🥉 Función C — "El Cronista" lee las noticias
El comentarista IA del que hablábamos, pero **alimentado por el radar**: en lugar de inventar, cita
noticias reales. Una llamada por jornada (~600 tokens). Solo cuando A y B ya funcionen.

---

## 4. Implementación concreta

### Estructura
```
liga_maestros/services/ai/
├── __init__.py
├── client.py      # cliente OpenAI-compatible con fallback (solo `requests`)
├── budget.py      # ← copia adaptada de highlightly_limits.py
└── news_ai.py     # enriquecimiento del radar
```
**Cero dependencias nuevas.** Groq y Gemini exponen API compatible con OpenAI y ya tienes `requests`.

### `services/ai/news_ai.py` (esqueleto real)

```python
import hashlib, json
import config
from ..utils import safe_read_json, safe_write_json
from .budget import can_spend, record_call, record_failure
from .client import chat

AI_CACHE_PATH = os.path.join(config.DATA_DIR, "RADAR_NOTICIAS_IA.json")
MAX_ITEMS = 8

def _firma(items):
    return hashlib.sha256("|".join(sorted(i["link"] for i in items)).encode()).hexdigest()

def enrich_news(items):
    """Devuelve items enriquecidos. Nunca lanza: si la IA falla, devuelve los originales."""
    candidatas = [i for i in items if i.get("score", 0) >= 4][:MAX_ITEMS]
    if not candidatas:
        return items

    cache = safe_read_json(AI_CACHE_PATH, {})
    firma = _firma(candidatas)
    if cache.get("firma") == firma:
        return _merge(items, cache.get("resultados", []))   # 0 tokens

    if not can_spend("news"):        # cuota agotada o circuito abierto
        return items                 # degradación silenciosa

    payload = [{"i": n, "t": c["title"][:120], "s": (c.get("summary") or "")[:220]}
               for n, c in enumerate(candidatas)]
    raw = chat(
        [{"role": "system", "content": SYSTEM},
         {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
        json_mode=True, max_tokens=500, timeout=10,
    )
    if not raw:
        record_failure("news")
        return items                 # fail-open

    try:
        resultados = json.loads(raw)["resultados"]
        assert isinstance(resultados, list)
    except Exception:
        record_failure("news")
        return items                 # JSON inválido: se ignora, no rompe nada

    record_call("news")
    safe_write_json(AI_CACHE_PATH, {"firma": firma, "resultados": resultados})
    return _merge(items, resultados)
```

### Engancharlo en `build_news_radar`

Un solo cambio, al final de la función que ya tienes:
```python
    selected = [item for item in selected if item["score"] > 0][:8]
+   if os.getenv("AI_NEWS_ENABLED", "0") == "1":
+       selected = enrich_news(selected)     # nunca lanza
    payload = {...}
```

Nota: la llamada a la IA añade latencia al refresco. Como `build_news_radar` solo hace trabajo real
cuando expira el TTL de 900 s, y el `force=1` está limitado a admin, el impacto es despreciable.
Si quieres latencia cero garantizada, mueve el enriquecimiento al `web_collector`.

### Cruce con la jornada (Función B, sin IA)

```python
def alertas_por_partido(partidos, noticias_ia):
    from ..utils import normalize_team_key       # ya existe
    alertas = {}
    for n in noticias_ia:
        if n.get("impacto", 0) < 2:
            continue
        for equipo in n.get("equipos", []):
            clave = normalize_team_key(equipo)
            for p in partidos:
                if clave in (normalize_team_key(p["local"]), normalize_team_key(p["visitante"])):
                    alertas.setdefault(p["id"], []).append(n)
    return alertas
```

### Variables de entorno
```bash
GROQ_API_KEY=                  # console.groq.com — gratis, sin tarjeta
GEMINI_API_KEY=                # aistudio.google.com/apikey — fallback
AI_NEWS_ENABLED=0              # apagado por defecto
AI_DAILY_CALL_LIMIT=50         # techo duro anti-bucle
AI_TIMEOUT_SECONDS=10
```

---

## 5. Por qué Groq y no Gemini para esto

Aunque Gemini tiene más cuota, **para noticias da igual**: gastas el 0,4 %. Lo que decide es:

1. **Groq no entrena con tus datos.** Aquí mandas titulares públicos de prensa, así que no hay PII
   y el riesgo es bajo — pero si mañana reutilizas el mismo cliente para moderar comentarios de
   usuarios (que sí es PII), ya lo tendrás bien montado desde el principio.
2. **Velocidad.** Llama 3.3 70B en Groq va a ~500 tokens/s. El refresco no se nota.
3. **JSON mode fiable** y API OpenAI-compatible sin sorpresas.

Deja Gemini como segundo de la cadena de fallback y listo.

---

## 6. Riesgos y cómo los cierras

| Riesgo | Mitigación |
|---|---|
| **Fundir la cuota** | Lote + caché por firma + `AI_DAILY_CALL_LIMIT=50`. Techo duro. |
| **Bucle accidental** | El contador diario lo corta solo. Añade un test que verifique que `enrich_news` con la misma firma NO llama a la API. |
| **Alucinaciones** | Solo resume texto que le das, `temperature=0.2`, y el campo `equipos` se valida contra tu lista real de equipos: lo que no matchea, se descarta. |
| **JSON malformado** | `try/except` → devuelve las noticias sin enriquecer. Nunca rompe la portada. |
| **RSS caído** | Ya está resuelto en tu código (recolecta `errors` por feed). |
| **Prompt injection desde un titular** | Un titular hostil podría intentar dar instrucciones. Va como `user`, nunca como `system`, y validas el JSON de salida contra un esquema. Lo peor que puede pasar es que descartes esa noticia. |
| **Contenido IA sin etiquetar** | Badge "resumen IA" visible en la UI. Exigible por el AI Act, y además es honesto. |

---

## 7. Plan por fases

| Fase | Qué | Esfuerzo | Tokens/día |
|---|---|---|---|
| **1** | `client.py` + `budget.py` (copiando `highlightly_limits.py`) | 2 h | 0 |
| **2** | `news_ai.py` con lote + caché por firma, tras flag | 2 h | ~1.400 |
| **3** | **Widget del radar en la portada** (¡hoy no existe!) | 3 h | 0 |
| **4** | Alertas cruzadas con los 15 partidos de la jornada | 2 h | 0 |
| **5** | El Cronista alimentado por el radar | 3 h | ~600 |

**Total en régimen: unos 2.000 tokens/día y 2-5 llamadas/día.** Sobre 1.000 req/día gratuitas de
Groq, es el **0,5 %**. Podrías multiplicar por 200 el uso y seguirías dentro del tier gratuito.

---

## Resumen en tres frases

1. **Tu radar ya hace el 70 % del trabajo** — el filtrado por keywords que te lleva de 300 noticias
   a 8 es exactamente la optimización de tokens que estabas buscando, y ya la tienes escrita.
2. **La clave para no gastar es: filtrar antes, mandar en lote (una llamada, no ocho), cachear por
   firma de contenido y poner un techo diario duro** — con eso gastas ~1.400 tokens por refresco y
   la mayoría de ejecuciones cuestan literalmente 0.
3. **Lo más valioso ni siquiera consume IA**: una vez que el modelo te devuelve `equipos: ["Betis"]`,
   cruzar eso con tus 15 partidos para mostrar *"⚠️ el Betis pierde a Isco"* justo al lado del
   partido es un `set intersection` gratis — y es lo que convierte el radar en algo que la gente usa
   de verdad para decidir su quiniela.
