# Fixes + rutas listas para pegar

## 1. Manifest — short_name

**Archivo:** `static/manifest.webmanifest`

```json
"short_name": "Maestros",
```

(antes: `"La Maestros"`)

También conviene alinear `name` y `description` con el nuevo mensaje:

```json
{
  "name": "Liga de Maestros — ¿Eres más listo que la IA?",
  "short_name": "Maestros",
  "description": "Predice 15 partidos y enfréntate a GPT, Claude, Gemini y Grok. Humanos vs IA, jornada a jornada."
}
```

---

## 2. Botón NEWS roto

**Problema:** `data-page-action="NEWS"` no existe en el router.

**Opción rápida (panel):** en el handler de navegación, mapear NEWS a un modal:

```js
// navigation.js (o el switch de data-page-action)
case "NEWS":
  openNewsPanel(); // modal con últimas noticias + link "ver todas"
  break;
```

**Opción SEO:** ruta real `/noticias` con HTML server-side.

---

## 3. Fechas hardcodeadas

Sacar de JS:

```js
// MAL
const seasonStart = new Date('2026-08-15T19:30:00');
```

**Bien:** endpoint o payload inicial:

```json
{
  "season": "2026/27",
  "season_start": "2026-08-15T17:30:00Z",
  "jornada_activa": 1,
  "cierre": "2026-08-15T17:30:00Z",
  "partido_destacado": "Alavés vs Getafe"
}
```

Inyectar en plantilla:

```html
<script>
  window.__LM_CONFIG__ = {{ config|tojson }};
</script>
```

---

## 4. Ruta landing + jornada pública (Flask)

```python
# routes/main.py (ejemplo)

@bp.get("/")
def index():
    return render_template("landing.html")

@bp.get("/app")
def app_shell():
    return render_template("liga_index.html", ...)

@bp.get("/jornada/<int:n>")
def jornada_publica(n: int):
    data = services.jornada_summary(n)
    return render_template("jornada_publica.html", j=data, n=n)
```

Sitemap:

```xml
<url><loc>https://TU-DOMINIO/</loc><priority>1.0</priority></url>
<url><loc>https://TU-DOMINIO/jornada/1</loc><priority>0.8</priority></url>
```

---

## 5. Copy hero (sustituir en portada SPA)

```html
<h1>¿Eres más listo que la IA?</h1>
<p>Predice los 15 partidos. Enfréntate a GPT, Claude, Gemini y Grok.</p>
<a class="cta" href="#ticket">Entrar en la quiniela</a>
```

---

## 6. Veredicto automático

```python
def verdict_vs_gpt(human: int, gpt: int) -> str:
    d = human - gpt
    if d >= 3:
        return "🔥 Has destrozado a GPT"
    if d >= 1:
        return "✅ Le has ganado a GPT"
    if d == 0:
        return "🤝 Empate técnico con GPT"
    if d <= -3:
        return "😤 GPT te ha pasado por encima"
    return "🤖 GPT te ha ganado esta vez"
```

---

## Orden de deploy sugerido

1. Manifest + meta + hero copy (30 min)
2. Landing en `/` y app en `/app` (2–4 h)
3. Fix NEWS + fechas desde backend (1–2 h)
4. Pantalla resultado + share nativo (medio día)
5. Tarjeta PNG (html2canvas o endpoint Playwright)
6. Analytics embudo
7. `/jornada/N` pública + sitemap
