# CHISPA — CÓDIGO PARA HOY (elige A, copia y pega)

> No importa si luego quieres B o C. Este código funciona con cualquier texto del hero. Solo cambias el texto del H1 si cambias de opinión.

---

## 1) COUNTDOWN VIVO (30 min) — cover_page.js

Busca donde se renderiza `coverCloseLabel()` o `#cp-deadline`. Reemplaza el span estático por:

```js
// Al cargar (o donde inicialices el cover)
setInterval(() => {
  const node = document.querySelector("#cp-deadline");
  if (!node) return;
  const raw = String(state?.data?.edit_deadline || state?.data?.close_deadline || "");
  if (!raw) return;
  const target = new Date(raw.replace(" ", "T"));
  const diff = target - Date.now();
  if (diff <= 0) {
    node.textContent = "CERRADA";
    node.classList.add("is-urgent");
    return;
  }
  const s = Math.max(0, Math.floor(diff / 1000));
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60;
  node.textContent = `${h}h ${String(m).padStart(2,"0")}m ${String(sec).padStart(2,"0")}s`;
  node.classList.toggle("is-urgent", diff < 3_600_000); // <1h: rojo + pulso
}, 1000);
```

Y en CSS (`cover_hero.css`):

```css
#cp-deadline { font-variant-numeric: tabular-nums; letter-spacing: 0.02em; }
#cp-deadline.is-urgent { color: #f87171; animation: urgentPulse 1s ease-in-out infinite; }
@keyframes urgentPulse { 0%,100%{opacity:1} 50%{opacity:.55} }
@media (prefers-reduced-motion: reduce) { #cp-deadline.is-urgent { animation: none; } }
```

**Nota:** si el deadline ya pasó, cambia `CERRADA` por `PRÓXIMA JORNADA EN ...` para que el reloj nunca se apague.

---

## 2) VS QUE PELEA (25 min) — cover_hero.css

```css
/* Esquinas entrando */
.cp-side { animation: cornerIn .55s cubic-bezier(.16,1,.3,1) both; }
.cp-side.is-ai { animation-name: cornerInR; animation-delay: .15s; }

/* VS latiendo */
.cp-vs { animation: vsBeat 2.2s ease-in-out infinite; }

/* Al pasar el ratón, los bandos se empujan */
.cp-duel:hover .cp-side.is-pena { transform: translateX(6px); }
.cp-duel:hover .cp-side.is-ai  { transform: translateX(-6px); }
.cp-side { transition: transform 200ms cubic-bezier(.16,1,.3,1); }

@keyframes cornerIn  { from { transform: translateX(-36px); opacity: 0; } to { opacity: 1; } }
@keyframes cornerInR { from { transform: translateX(36px);  opacity: 0; } to { opacity: 1; } }
@keyframes vsBeat    { 0%,100% { transform: scale(1);    box-shadow: 0 0 0 rgba(239,68,68,.45); } 50% { transform: scale(1.08); box-shadow: 0 0 22px rgba(239,68,68,.65); } }
```

Si quieres sonido de campana al guardar, reutiliza `SoundManager.playSave` o crea `SoundManager.playBell` (200ms, ya tienes la infra).

---

## 3) HERO — ELIGE UNO (solo cambia el texto del H1)

### Opción A (la más segura, sin ideología, datos puros)
```html
<div class="cp-deadline" id="cp-deadline">CIERRE EN ...</div>
<h1>Grok 144. Claude 141. ChatGPT 139.</h1>
<p>75 jornadas. Tres semanas ganando. Una para meterla.</p>
<a href="#" class="primary-btn">Dar mi quiniela</a>
```

### Opción B (periodismo / newspaper)
```html
<h1>Las máquinas ganan. La Peña no ha dejado.</h1>
<p>El ranking real: los 5 maestros IA arriba. 2 puntos de media. El cierre es hoy.</p>
<a href="#" class="primary-btn">Ver mi bando</a>
```

### Opción C (solo si hoy tienes prueba social real: nombres o número)
```html
<h1>Grok 144. Claude 141. ChatGPT 139.</h1>
<p>Faucher, @paco y 142 más ya pasaron por aquí esta jornada.</p>
<a href="#" class="primary-btn">Unirme con mi pronóstico</a>
```

---

## 4) JERARQUÍA (15 min) — HTML del hero

- Logo (`.app-shell` o `.masthead`) a **60px max**, no 132px.
- `H1` a `clamp(2.2rem, 6vw, 4rem)` con `font-weight: 800`.
- Small texto de fecha/kicker (`SÁBADO 1 AGO · JORNADA 75`) encima del H1.
- El countdown llama a `#cp-deadline` y va junto al kicker o justo debajo del H1.

---

## RESUMEN PARA NO PERDERTE

Paso 1: Copia el countdown (JS + CSS).
Paso 2: Copia el VS (CSS).
Paso 3: Escribe el H1 que quieras (A, B o C) — el código funciona igual.
Paso 4: Haz el logo pequeño (HTML/CSS, 2 líneas).

**No hay que pensar en el copy antes del código.** El código es independiente. Elige A si no tienes prueba social hoy.
