# 🔍 Segunda ronda de auditoría + Plan de IA gratuita

> Revisión sobre `origin/main` @ `98bfe60` · 2026-07-26
> Comparativa contra el estado auditado en `b7f6446` (108 ficheros cambiados, +2.604 / −1.452)

---

## Parte A — Qué ha mejorado (y qué se ha roto por el camino)

### ✅ Lo conseguido desde la primera auditoría

Muy buen trabajo. Se han cerrado **8 de los 10 Quick Wins**:

| Quick Win | Estado |
|---|---|
| QW-1 `LICENSE` | ✅ AGPL-3.0-only |
| QW-2 Limpieza de raíz | ✅ **39 → 19 entradas**. `tools/{ops,scrapers,importers,audit}` + `docs/{operations,design,ai,adr}` |
| QW-4 Duplicación root/paquete | 🟡 Parcial — ver A.3 |
| QW-5 README con badges | ✅ Hero, badges, tabla de módulos, Mermaid |
| QW-6 `pyproject.toml` + ruff | ✅ Con `E,F,W,I,B,UP,S` y `per-file-ignores` |
| QW-8 `.github/` completo | ✅ 3 plantillas de issue (incl. `jornada_error.yml`), PR template, CODEOWNERS, dependabot |
| Docs | ✅ 3 ADRs + `GLOSARIO.md` + `CONTRIBUTING.md` + `CODE_OF_CONDUCT.md` |
| Dev deps | ✅ `requirements-dev.txt` |
| Formato | ✅ `ruff format` aplicado — **107 ficheros ya formateados** |

Los **222 tests pasan** en verde. El código está objetivamente más sano.

---

### 🔴 A.1 — CRÍTICO: el deploy a producción lleva 3 días roto

```
30195928469  Deploy Alwaysdata  main  failure  ← hace 2 min
30167311682  Deploy Alwaysdata  main  failure  ← hace 15 h
30166576812  Deploy Alwaysdata  main  failure  ← hace 16 h
```

**Causa raíz:** la reorganización a `tools/` movió los scripts, pero
`.github/workflows/deploy-alwaysdata.yml` sigue invocándolos desde la raíz:

```bash
# línea 74 y 84 — estas rutas ya no existen
"$HOME_DIR/venv/bin/python" GESTIONAR_BACKUPS.py create --reason pre-deploy
"$HOME_DIR/venv/bin/python" INICIALIZAR_PRODUCCION.py
```
Los ficheros están ahora en `tools/ops/`. El step *"Activate release"* sale con exit code 2.
`render.yaml:6` tiene el mismo problema (`initialDeployHook: python INICIALIZAR_PRODUCCION.py`).

**Fix inmediato** (3 líneas):
```bash
"$HOME_DIR/venv/bin/python" tools/ops/GESTIONAR_BACKUPS.py create --reason pre-deploy
"$HOME_DIR/venv/bin/python" tools/ops/INICIALIZAR_PRODUCCION.py
```
Y en `render.yaml`: `initialDeployHook: python tools/ops/INICIALIZAR_PRODUCCION.py`.

> ⚠️ **Ojo con el backup pre-deploy.** El step que falla es justo el que crea el backup antes de
> activar la release. Llevas 3 días desplegando sin red de seguridad… salvo que, como el step
> muere, tampoco se activa la release: **producción está congelada en un commit antiguo**. Verifica
> con `curl https://ligademaestros.alwaysdata.net/api/live/health` qué `build_sha` sirve realmente.

**Además:** elimina las referencias a `IMPORTAR_J74_COMPLETO.py` y `ACTUALIZAR_COMPLETO_J74.py`
(líneas 85-92). Son de una jornada concreta, ya están en `scripts/archive/j74/`, y no pintan nada en
un pipeline de deploy. Un despliegue **nunca** debe importar datos de negocio.

---

### 🔴 A.2 — CI en rojo: `ruff check .` encuentra 39 errores

Ampliaste ruff a todo el repo (correcto) pero el código no está limpio, así que el CI falla en el
step de lint desde entonces. Desglose:

| Regla | Nº | Veredicto |
|---|---|---|
| `S110` try-except-pass | 16 | **Deuda real.** Errores silenciados. Arreglar de verdad, no silenciar. |
| `S608` SQL por f-string | 6 | **Falso positivo.** Los nombres de tabla/columna vienen de listas internas. `# noqa: S608` con comentario justificativo. |
| `S112` try-except-continue | 5 | Igual que S110. |
| `F601` clave de dict repetida | 6 | 🐛 **BUG REAL — ver abajo.** |
| `B007` variable de bucle sin usar | 2 | Trivial: renombrar a `_jornada`, `_signs`. |
| `S105` password hardcodeada | 2 | Falso positivo en tests. Añade `"tests/*" = [..., "S105"]`. |
| `B904` `raise ... from` | 1 | Trivial, y mejora el traceback. |
| `S311` `random` no criptográfico | 1 | Falso positivo: es un shuffle determinista con seed para el quiz. `# noqa: S311`. |

#### 🐛 El bug escondido: `tools/scrapers/SCRAPE_QUINIELA15_ESCUDOS.py`

```python
repl = {
    "?": "A", "?": "E", "?": "I", "?": "O", "?": "U", "?": "U", "?": "N",
}
```
Eso **eran** `Á É Í Ó Ú Ü Ñ` y se han convertido en `?` — corrupción de encoding en algún guardado
con codificación equivocada. En Python un dict con claves repetidas se queda con la última: el
diccionario real es `{"?": "N"}`. **La normalización de acentos en los escudos de equipos está
rota**, así que "ALAVÉS" o "LOGROÑÉS" no matchean su logo.

Fix correcto (y a prueba de encoding, sin tabla manual):
```python
import unicodedata

def normalize_key(text: str) -> str:
    text = (text or "").upper()
    text = "".join(c for c in unicodedata.normalize("NFD", text)
                   if unicodedata.category(c) != "Mn")
    text = re.sub(r"[^A-Z0-9 ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()
```
Ya tienes `unicodedata` importado en `utils.py` haciendo exactamente esto. **Reutilízalo** en vez de
mantener una tabla paralela.

> **Lección de proceso:** este bug lo habría cazado un `pre-commit` local. Sigue sin haberlo. Es
> ahora la pieza de DX que más falta te hace, precisamente porque ruff ya está bien configurado.

---

### 🟠 A.3 — La duplicación root/paquete sigue viva

`config.py`, `utils.py` y `scoring.py` continúan existiendo en la raíz **y** en `liga_maestros/`.
Y `utils.py` conserva el patrón más frágil del repo:

```python
try:
    from .config import BASE_DIR, DATA_DIR, ...
except ImportError:
    from config import BASE_DIR, DATA_DIR, ...
```

Un `try/except ImportError` para resolver imports significa que **el módulo se comporta distinto
según cómo lo importes**. Sigue siendo la bomba de relojería nº 1 del proyecto. Termina la
migración: contenido real dentro de `liga_maestros/`, y en la raíz o nada, o un shim de una línea.

---

### 🟡 A.4 — Lo que sigue pendiente de la primera auditoría

Sin tocar (y siguen siendo válidos):
- **Sin banner, GIF, capturas ni social preview.** El README tiene estructura de élite pero
  **cero píxeles**. Es el 60 % del impacto visual que aún no has cobrado.
- **Sin `Makefile`, sin pre-commit, sin devcontainer, sin Dockerfile.**
- **Sin CLI unificado** (QW-3): siguen siendo 12 scripts sueltos, ahora mejor ordenados.
- **Sin CodeQL, sin coverage, sin E2E, sin Lighthouse.**
- **`/api/liga/data` sigue siendo el god-endpoint**, con I/O de JSON síncrona en el hot path.
- **Cache-busting manual** con los 20 sufijos `'-cover-hero-15'` en la plantilla.
- **Frontend sin ES modules ni `package.json`**; `node --check` cubre 2 de ~20 ficheros JS.
- **`/metrics` y health enriquecido**: `live.py` creció +203 líneas, buena señal — verifica si ya
  cubre parte de esto.

### 📋 Orden de ataque recomendado

1. **Hoy:** arreglar rutas del deploy (A.1) → producción vuelve a desplegar.
2. **Hoy:** arreglar los 39 de ruff, empezando por el bug de encoding (A.2) → CI en verde.
3. **Esta semana:** pre-commit + terminar la desduplicación (A.3).
4. **Después:** los píxeles del README (banner, GIF, capturas) — máximo impacto restante.

---

## Parte B — Comentarios con IA, gratis

Ya tienes una base sólida: `routes/comments.py` con CSRF, rate limit (4 s), límite de 240 caracteres,
`escapeHtml` en cliente y la UI en `ticket_page.js`. Lo que falta es **la capa de IA**. Y sí, se
puede hacer con coste **0 €**.

### B.1 — Qué proveedor gratuito elegir

Panorama real de tiers gratuitos permanentes (sin tarjeta) a día de hoy:

| Proveedor | Cuota gratis | Modelos | Notas |
|---|---|---|---|
| **Groq** | 30 RPM · ~1.000 req/día · sin tarjeta | Llama 3.3 70B, Qwen, GPT-OSS | **Ultrarrápido (LPU)** y explícitamente **no entrena con tus datos** [1](https://tokenmix.ai/blog/groq-free-tier-limits-2026) |
| **Google AI Studio** | ~1.500 req/día · 15 RPM · 1M TPM | Gemini 2.5 Flash / Flash-Lite | La cuota más generosa, pero **Google puede entrenar con datos del tier gratuito** [2](https://tokenmix.ai/blog/gemini-api-free-tier-limits) |
| **Cerebras** | ~1M tokens/día · 30 RPM | Llama 3.3 70B, Qwen3 | Muy buena cuota de tokens [3](https://awesomeagents.ai/tools/free-ai-inference-providers-2026/) |
| **OpenRouter** | 50 req/día (`:free`) | 20+ modelos, una sola key | Ideal para **rotar modelos** sin cambiar código [4](https://openrouter.ai/blog/tutorials/free-llm-apis-compared/) |
| **Cloudflare Workers AI** | ~10.000 neuronas/día | Llama 3.2, Mistral | Sin cold start, en el edge |
| **Ollama (local)** | ∞ | Gemma 3, Llama, Phi-4 | Coste 0 y privacidad total, pero Alwaysdata no te dará esa RAM |

**Mi recomendación para tu caso concreto:**

> 🥇 **Groq como primario + Gemini Flash como fallback.**
>
> Por qué Groq primero: **no entrena con los datos de usuario**, y tú vas a enviarle comentarios de
> personas reales identificadas por Google Login. Eso te ahorra un dolor de cabeza de RGPD que, con
> tu `SECURITY.md` y tu página de privacidad ya escritas, sería incoherente ignorar. Además la
> latencia baja importa: un comentario debe moderarse en < 1 s o rompes la conversación.
>
> Por qué Gemini de fallback: 1.500 req/día es mucho margen si Groq se agota.
>
> Ambos hablan **API compatible con OpenAI**, así que un solo cliente HTTP te sirve para los dos.
> **Y no añades ninguna dependencia**: ya tienes `requests` en `requirements.txt`.

Tu volumen real: una peña de ~20 personas, 15 partidos, una jornada por semana. Estás hablando de
**decenas de llamadas al día**. Cabes 20 veces dentro del tier gratuito.

### B.2 — Las cinco funciones de IA que de verdad valen aquí

Ordenadas por (valor para el usuario) ÷ (esfuerzo).

#### 1. 🛡️ Moderación automática de comentarios — *empieza por aquí*
El problema que **vas a tener** en cuanto abras la web: insultos entre colegas que se pasan de
frenada. Hoy no tienes ninguna moderación.

- Antes de insertar en `comentarios_jornada`, una llamada que devuelva JSON estricto:
  `{"ok": true|false, "motivo": "insulto|spam|ok", "severidad": 0-3}`.
- Si `severidad >= 2` → 400 con mensaje amable. Si es 1 → se guarda con flag para revisión.
- **Fail-open**: si la API falla o tarda > 2 s, el comentario **se publica igual**. Nunca dejes que
  un tier gratuito caído tumbe tu funcionalidad. Encolas para revisar después.
- Coste: ~1 llamada por comentario. Con 20 usuarios, imposible agotar la cuota.

#### 2. 🎙️ "El Cronista" — comentarista IA de la jornada — *la joya*
Un participante más en el chat, que **comenta solo**:
- Al abrirse la jornada: *"15 partidos. La Peña ve claro el Betis-Sevilla con un 87% de 1. Claude
  es el único que se atreve con el 2. Veremos."*
- Cuando cae un gol (ya tienes el collector con el ticker): *"¡Gol del Alavés! Tres de los cuatro
  Maestros IA acaban de quedarse sin su 1. Marta sube a la primera plaza."*
- Al cierre: crónica de 200 palabras en tono periodístico.

**Encaja perfectamente con tu identidad visual "newspaper"** — llevas todo un tema de CSS imitando
un periódico. Dale un **columnista de verdad**. Es la feature más "wow" del proyecto y la que hará
que la gente deje la pestaña abierta.

Implementación: `services/cronista.py` + una tabla `comentarios_ia`, o mejor aún, insertar en
`comentarios_jornada` con `etiqueta='Cronista'` y `user_id='__ia_cronista__'` — **tu esquema ya lo
soporta** gracias al campo `etiqueta`, y el frontend solo necesita un estilo distinto. Cero
migraciones.

Coste: ~5-10 llamadas por jornada. Ridículo.

#### 3. 🧠 Resumen del debate
Con 40 comentarios en la jornada, un botón *"Resumir la conversación"* que devuelva 3 bullets:
el consenso, la discrepancia y la predicción más polémica. Una llamada, cacheada 10 minutos.

#### 4. ❓ Generación del quiz semanal
Ya tienes el pipeline montado (`data/quiz/` con `sources → generated → approved/rejected` y
`quiz_schema.json`) y `scripts/quiz/validate_quiz_bank.py`. **Falta solo el generador.** Un script
que lea las noticias del radar, pida 20 preguntas en JSON conforme a tu schema, valide con el
validador que ya existe, y deje el resultado en `generated/` para tu aprobación manual.
Esto ya estaba diseñado para IA — solo hay que enchufarla.

#### 5. 💬 Razonamientos de los Maestros IA
Tienes `PREDICTION_REASONS.json` relleno a mano. Automatízalo: al pedir la predicción a cada modelo,
pide también su razonamiento en la misma respuesta. Cero llamadas extra. Y **es contenido
diferencial**: la gente entrará solo para leer por qué Grok se equivocó.

### B.3 — Diseño técnico (encaja con tu arquitectura actual)

```
liga_maestros/services/ai/
├── __init__.py
├── client.py        # cliente OpenAI-compatible, solo `requests`
├── budget.py        # cuota diaria + circuit breaker  ← COPIA highlightly_limits.py
├── moderation.py
└── cronista.py
```

**El truco clave: no inventes nada.** Ya tienes resuelto exactamente este problema con
`services/highlightly_limits.py` (192 líneas: cuota diaria, reserva, circuit breaker con cooldown
exponencial). **Es el mismo patrón.** Cópialo para la IA y tendrás desde el día uno lo que la
mayoría de proyectos no consigue: control de gasto y degradación elegante.

```python
# services/ai/client.py — sin dependencias nuevas
PROVIDERS = [
    {"name": "groq",   "url": "https://api.groq.com/openai/v1/chat/completions",
     "key_env": "GROQ_API_KEY",   "model": "llama-3.3-70b-versatile"},
    {"name": "gemini", "url": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
     "key_env": "GEMINI_API_KEY", "model": "gemini-2.5-flash"},
]

def chat(messages, *, json_mode=True, timeout=8, max_tokens=400):
    """Intenta cada proveedor en orden. Devuelve None si todos fallan (fail-open)."""
    for provider in PROVIDERS:
        key = os.getenv(provider["key_env"], "").strip()
        if not key or ai_budget_exhausted(provider["name"]) or circuit_open(provider["name"]):
            continue
        try:
            body = {"model": provider["model"], "messages": messages,
                    "max_tokens": max_tokens, "temperature": 0.4}
            if json_mode:
                body["response_format"] = {"type": "json_object"}
            r = requests.post(provider["url"], json=body, timeout=timeout,
                              headers={"Authorization": f"Bearer {key}"})
            r.raise_for_status()
            record_ai_call(provider["name"])
            return r.json()["choices"][0]["message"]["content"]
        except Exception as exc:
            record_ai_failure(provider["name"], exc)
    return None   # fail-open: quien llama decide el comportamiento degradado
```

**Reglas de oro no negociables:**
1. **Fail-open siempre.** IA caída ⇒ la web funciona igual, sin IA. Nunca un 500 por esto.
2. **Timeout corto (8 s) y llamada fuera del request** cuando puedas (el cronista va en el
   collector que ya tienes corriendo, no en la petición del usuario).
3. **Nunca envíes PII.** Manda el texto del comentario, jamás el email ni el `user_id` real.
   Tu `services/privacy.py` ya marca la línea; respétala.
4. **Cachea agresivamente** por hash del prompt. El mismo resumen no se pide dos veces.
5. **Etiqueta visiblemente** todo lo generado: badge "IA" en la UI. Es honestidad, y además es lo
   que exige el AI Act europeo para contenido sintético.
6. **Cuota diaria configurable** (`AI_DAILY_CALL_LIMIT`) igual que hiciste con Highlightly.

### B.4 — Variables de entorno a añadir

```bash
GROQ_API_KEY=                      # groq.com/keys — gratis, sin tarjeta
GEMINI_API_KEY=                    # aistudio.google.com/apikey — fallback
AI_ENABLED=1
AI_DAILY_CALL_LIMIT=400
AI_MODERATION_ENABLED=1
AI_MODERATION_THRESHOLD=2
AI_CRONISTA_ENABLED=1
AI_TIMEOUT_SECONDS=8
```
Documéntalas en `.env.example` y en `docs/operations/VARIABLES_ENTORNO.md`, que ya tienes.

### B.5 — Riesgos honestos

| Riesgo | Mitigación |
|---|---|
| **Datos de usuarios a un tercero** | Groq no entrena con ellos. Actualiza igualmente tu política de privacidad: es un nuevo encargado del tratamiento y estás obligado a declararlo. |
| **Cuota agotada / servicio caído** | Fail-open + fallback en cadena + circuit breaker (ya sabes hacerlo). |
| **Alucinaciones del cronista** | Dale **solo datos que le pases tú** en el prompt (marcador, ranking, predicciones) y prohíbele inventar cifras. Temperatura ≤ 0,4. |
| **Prompt injection** desde un comentario | El comentario va como `user`, nunca como `system`. Y valida siempre el JSON de salida contra un esquema antes de usarlo. |
| **Coste sorpresa** | Ninguna key con tarjeta asociada. Si el tier gratuito se acaba, la llamada falla y ya está. |
| **Tono ofensivo generado por tu propia IA** | Prompt del cronista explícito: nunca ridiculizar a personas concretas, solo a los modelos. |

### B.6 — Plan de implementación por fases

- **Fase 1 (1 tarde):** `services/ai/client.py` + `budget.py` + moderación en el POST de comentarios.
  Con feature flag `AI_ENABLED=0` por defecto.
- **Fase 2 (1 día):** El Cronista con 3 disparadores (apertura, gol, cierre), publicando en
  `comentarios_jornada` con `etiqueta='Cronista'`.
- **Fase 3:** Resumen del debate + generador de quiz enchufado al pipeline existente.
- **Fase 4:** Razonamientos automáticos de los Maestros IA → y de ahí, directo al benchmark público
  que comentaba en la primera auditoría.

---

## Resumen en tres frases

1. Has hecho **muy buen trabajo de fondo** (raíz limpia, licencia, ruff, docs, ADRs, 222 tests en
   verde), pero **has roto el deploy y el CI en el proceso** — y eso hay que arreglarlo hoy, antes
   que nada.
2. Escondido entre los errores de ruff hay un **bug real de encoding** que rompe la normalización de
   escudos: la mejor prueba de que ampliar el linter valió la pena, y de que te falta pre-commit.
3. Para la IA: **Groq gratis + Gemini de fallback, sin dependencias nuevas**, copiando el patrón de
   cuota y circuit breaker que ya dominas de Highlightly. Empieza por la moderación (te hace falta
   sí o sí) y sigue con **El Cronista**, que es la feature que convierte tu tema de periódico en una
   promesa cumplida.
