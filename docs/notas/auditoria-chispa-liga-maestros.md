# 🔥 AUDITORÍA DE CHISPA — Liga de Maestros
**Auditado en vivo el 1 de agosto de 2026** · `ligademaestros.alwaysdata.net` · Jornada 75 · commit `857e548`
**Comité:** 1 diseñador de producto obsesivo · 1 copywriter que odia lo aburrido · 1 growth hacker

> Método: no es opinión, es evidencia. Extraje el DOM real de la demo (estilos computados, animaciones, jerarquía tipográfica) y leí el código fuente (`cover_page.js`, `cover_hero.css`, `quantum_final.js`, `confetti.js`). Todo lo que digo aquí está anclado a líneas concretas de TU código.

---

## 1. DIAGNÓSTICO BRUTAL (3 frases)

1. **Tienes el mejor gancho del fútbol-fantasy del mundo — humanos contra máquinas en una quiniela real — y lo estás contando como un comunicado de prensa:** "Suma aciertos, escala en el ranking y conquista la jornada" es copy de LinkedIn, no de un derbi; la pregunta más emocionante de tu producto ("¿Quién sabe más de fútbol?") está renderizada a 16px, el mismo tamaño que el párrafo que la rodea.

2. **Tu dato más dramático — las máquinas van GANANDO (Grok 144, Claude 141, ChatGPT 139) — está enterrado al fondo del primer pliego como una tarjeta de datos más,** mientras arriba del todo un logo de 132px de alto ocupa el espacio que debería tener el titular.

3. **La portada está técnicamente muerta:** verifiqué que el único elemento animado en todo el DOM es un fade de entrada de 0.35s (`animation: page-enter`), y tu countdown "CIERRE EN 3H 06M" — la palanca de conversión #1 — es un texto congelado que se calcula UNA vez al render (`coverCloseLabel()`) y jamás vuelve a actualizarse. No hay tic-tac, no hay pulso, no hay nada que respire.

**En una frase:** un concepto de 10/10 envuelto en una página de 4/10 — la gente se va sin saber que acaba de ver el partido más interesante de la jornada.

---

## 2 + 3. LAS 10 CHISPAS

| # | Categoría | Chispa | Esfuerzo |
|---|-----------|--------|----------|
| 1 | Micro-interacción | El countdown que late | Bajo |
| 2 | Micro-interacción | El VS que pelea (pesaje) | Bajo |
| 3 | Micro-interacción | La quiniela que se completa | Bajo |
| 4 | Copy | "Las máquinas nos están ganando" | Mínimo |
| 5 | Copy | CTA de reclutamiento, no de tarea | Mínimo |
| 6 | Copy | La porra que te hace mojarte | Bajo |
| 7 | Prueba social | Robots con cara y lengua | Medio |
| 8 | Prueba social | El marcador humano-máquina sticky | Medio |
| 9 | Efecto WOW | Portada de periódico de verdad | Medio |
| 10 | Efecto WOW | El partido bajo lupa que se enciende | Bajo |

---

### 🔹 A) MICRO-INTERACCIONES

---

#### CHISPA 1 — El countdown que late

**Qué es.** Tu "CIERRE EN 3H 06M" se calcula una vez al render (`coverCloseLabel()` en `cover_page.js`) y se queda congelado hasta el próximo refresh. La chispa: convertirlo en un reloj vivo con segundos que hace tic-tac delante de los ojos del usuario, y que cambia de estado según la urgencia.

**Por qué engancha (psicología).** Escasez real + aversión a la pérdida. Un reloj que se agota en tiempo real es la forma *honesta* de urgencia (no es un countdown falso de Booking: es tu deadline real de cierre de quiniela). El segundero en movimiento activa el mismo circuito que el "Time's Up" de un examen: el cerebro sabe que la puerta se cierra y decide mojarse. Además, un reloj que **cambia de color cuando quedan <60 min** (oro → rojo pulsante) comunica urgencia sin una sola palabra.

**Cómo lo implementas (30 líneas, los datos ya existen).**
```js
// cover_page.js — sustituir el span estático del kicker por:
setInterval(() => {
  const node = document.querySelector("#cp-deadline");
  if (!node) return;
  const diff = new Date(String(state.data.edit_deadline).replace(" ", "T")) - Date.now();
  if (diff <= 0) { node.textContent = "CERRADA"; node.classList.add("is-urgent"); return; }
  const s = Math.max(0, Math.floor(diff / 1000));
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60;
  node.textContent = `${h}h ${String(m).padStart(2, "0")}m ${String(sec).padStart(2, "0")}s`;
  node.classList.toggle("is-urgent", diff < 3_600_000); // <1h: rojo + pulso
}, 1000);
```
```css
/* cover_hero.css */
#cp-deadline { font-variant-numeric: tabular-nums; } /* no tiembla al contar */
#cp-deadline.is-urgent { color: #f87171; animation: urgentPulse 1s ease-in-out infinite; }
@keyframes urgentPulse { 0%,100% { opacity: 1; } 50% { opacity: .55; } }
```
*(Respetad `prefers-reduced-motion`, como ya hacéis en `confetti.js`.)*

**Ejemplo textual:** `JORNADA 75 · CIERRE EN 2H 58M 41S` → a <1h: `CIERRE EN 43M 12S` en rojo latiendo.

**Bonus retención:** cuando la jornada cierra, el mismo reloj se reinvierte: `PRÓXIMA JORNADA EN 6D 04H 12M`. Ahí tienes tu máquina de "ganas de volver" — la gente vuelve porque el reloj nunca se apaga.

---

#### CHISPA 2 — El VS que pelea

**Qué es.** El "VS" de EL DUELO DE LA JORNADA es una letra estática entre dos bloques de texto. La chispa: convertir la sección en un **pesaje de boxeo** — los dos bandos entran deslizando desde sus esquinas, el VS late como un corazón de combate, y al pasar el ratón por un bando, éste empuja al rival (que retrocede 4px).

**Por qué engancha (psicología).** El cerebro humano detecta movimiento antes que texto (los fotorreceptores periféricos están cableados para eso), y los pares en conflicto capturan atención selectiva: dos cosas enfrentadas = micro-drama = el ojo vuelve. Es la misma razón por la que un "HUMANOS vs MÁQUINAS" en movimiento se recuerda y un "HUMANOS vs MÁQUINAS" estático no.

**Cómo lo implementas (25 líneas de CSS puro).**
```css
/* cover_hero.css */
.cp-side { animation: cornerIn .5s cubic-bezier(.16,1,.3,1) backwards; }
.cp-side.is-ai { animation-name: cornerInR; animation-delay: .15s; }
.cp-vs { animation: vsBeat 2.2s ease-in-out infinite; }
.cp-duel:hover .cp-side.is-pena { transform: translateX(6px); }
.cp-duel:hover .cp-side.is-ai  { transform: translateX(-6px); }
.cp-side { transition: transform 200ms cubic-bezier(.16,1,.3,1); } /* la curva que ya usas */
@keyframes cornerIn  { from { transform: translateX(-36px); opacity: 0; } }
@keyframes cornerInR { from { transform: translateX(36px);  opacity: 0; } }
@keyframes vsBeat    { 0%,100% { transform: scale(1);    box-shadow: 0 0 0 rgba(239,68,68,.4); }
                       50%     { transform: scale(1.07); box-shadow: 0 0 24px rgba(239,68,68,.55); } }
```

**Ejemplo visual:** los bandos entran en escena al cargar (izquierda/derecha), el "VS" late en rojo con glow, y al hover el bando ganador psicológico "empuja". Con sonido opcional de campana (`SoundManager.playSave` reutilizado o un `playBell` de 200ms) tienes el round 1 de cada visita.

---

#### CHISPA 3 — La quiniela que se completa

**Qué es.** Ya celebráis el final: confeti grande a 15/15, confeti mediano a ≥10, sonido al guardar (`quantum_final.js` — bien jugado). Pero entre el clic 1 y el clic 15 no pasa nada visible. La chispa: un contador de progreso **en el propio botón** ("7/15") que hace `pop` con cada acierto marcado, y un mini-estado "¡Quiniela completa!" con bounce al llegar a 15.

**Por qué engancha (psicología).** Efecto gradiente de meta (goal-gradient effect): las personas aceleran su esfuerzo cuanto más cerca están del objetivo. Cada clic que acerca el contador a 15/15 es una micro-recompensa que engacha el bucle (el mismo mecanismo de las rachas de Duolingo). El progreso visible convierte "rellenar un formulario" en "completar un reto".

**Cómo lo implementas.** Tenéis el keyframe `count-pop` en `themes/newspaper/animations.css` **sin usar en portada**. En el handler de clic de signos:
```js
const done = state.my_signs.filter(s => s !== "-").length;
const btn = qs("#save-quiniela-btn");
btn.innerHTML = done === 15
  ? "¡Quiniela completa! 🏆"
  : `Guardar quiniela <b class="count-badge">${done}/15</b>`;
btn.querySelector(".count-badge")?.animate?.(
  [{ transform: "scale(1)" }, { transform: "scale(1.35)" }, { transform: "scale(1)" }],
  { duration: 250, easing: "cubic-bezier(.34,1.56,.64,1)" });
```
**Ejemplo textual:** `Guardar quiniela [7/15]` → clic → `[8/15]` con pop → al 15: el botón hace un bounce y lanza el confeti que ya tenéis.

---

### 🔹 B) COPY QUE ENGANCHA

---

#### CHISPA 4 — "Las máquinas nos están ganando"

**Qué es.** Tu ranking real: **Grok 144 · Claude 141 · ChatGPT 139**. Los tres primeros son máquinas. Y el hero dice "La competición de la quiniela" + "¿Quién sabe más de fútbol?" — un titular de periódico local en el día del derbi. La chispa: declarar la verdad incómoda como titular de portada.

**Por qué engancha (psicología).** Aversión a la pérdida × tribalismo: el cerebro reacciona con mucha más fuerza a una amenaza que a una oportunidad, y si la amenaza es "a *nosotros*" (tu tribu humana), la activación se duplica. "¿Quién sabe más de fútbol?" es una pregunta retórica que no exige respuesta; "Las máquinas nos están ganando" es una herida que pide revancha. Y la revancha se llama CTA.

**Cómo lo implementas (3 strings en `cover_page.js`, 15 minutos, cero CSS):**
```
Kicker:  "JORNADA 75 · EL MARCADOR: MÁQUINAS 3 · HUMANOS 0"   (calculado de datos reales)
H1:      "Las máquinas nos están ganando."
Lead:    "75 jornadas llevan Grok, Claude y ChatGPT demostrando que el fútbol se calcula.
          La Peña lleva 75 jornadas demostrando que no. Tú decides en qué bando juegas."
```
La vieja pregunta "¿Quién sabe más de fútbol?" no se tira: se convierte en el **cierre** del lead, justo antes del CTA. La pregunta funciona cuando ya hay tensión construida, no como titular.

**Ejemplo textual completo del hero nuevo:**
> **JORNADA 75 · LAS MÁQUINAS NOS ESTÁN GANANDO**
> 75 jornadas llevan Grok, Claude y ChatGPT demostrando que el fútbol se calcula. La Peña lleva 75 jornadas demostrando que no. ¿Quién sabe más de fútbol?
> **[Firmar por la humanidad →]**

---

#### CHISPA 5 — CTA de reclutamiento, no de tarea

**Qué es.** "Hacer mi quiniela" es un verbo de gestión de tareas (lo mismo diría una app de impuestos). Cuando tu rival es una máquina, el CTA debe ser de **bando**, no de acción.

**Por qué engancha (psicología).** Motivación basada en identidad (identity-based motivation): la gente actúa para ser coherente con un "yo" deseado. "Firmar por la humanidad" convierte un clic en una declaración de principios; "Hacer mi quiniela" convierte el clic en papeleo. Bonus: funciona como prueba social invertida — firmar por la humanidad implica que otros ya lo han hecho.

**Cómo lo implementas (2 strings en `renderNewspaperCoverPageV3()`):**
```
Nuevo visitante:  "Firmar por la humanidad"        (primary)
Ya ha guardado:   "Revisar mi bando"               (en vez de "Revisar mi quiniela")
Secondary:        "Ver cómo van las máquinas"      (en vez de "Ver clasificación")
```
Y si queréis el turbo: el countdown dentro del botón — `Firmar por la humanidad · quedan 2h 58m` — el CTA y la urgencia fusionados en un solo elemento (el usuario no puede hacer scroll sin ver la hora).

---

#### CHISPA 6 — La porra que te hace mojarte

**Qué es.** Tenéis la mejor línea de todo el código muerta de risa en un estado vacío: **"Sé el primero en mojarte"** (`cover_page.js`, porra sin pronósticos). La chispa: subir la porra a la zona visible y usar el idioma español como arma — "mojarse" es el verbo perfecto para comprometerse con un marcador.

**Por qué engancha (psicología).** FOMO social + compromiso público: mojarse = exponerse = compromiso que luego se quiere cumplir. Y el copy de contexto lo hace todo: si no has mojado → "Los 5 maestros ya han mojado. **Tú no.**" (comparación social + vergüenza amable); si has mojado → "Tu porra: 2-1 · La Peña va con 4-1" (pertenencia).

**Cómo lo implementas.** Reordenar el grid del `cp-dashboard` (la porra es de los pocos elementos donde el usuario puede *opinar* — es engagement puro, no debe vivir al fondo) y cambiar el estado vacío:
```
Antes:  "Haz tu porra · 4-1 pronóstico único"
Ahora:  "Los 5 maestros ya han mojado. Tú no."  [Mojarme]
```
**Ejemplo textual del estado con compromiso:**
> **PORRA DE LA JORNADA · Marcador exacto**
> FREDRIKSTAD vs SANDEFJORD — La Peña va con 4-1 (12 mojados)
> [Mojarme con 2-1] · [Ver los pronósticos]

---

### 🔹 C) PRUEBA SOCIAL INTELIGENTE

---

#### CHISPA 7 — Robots con cara y lengua

**Qué es.** Los Maestros IA son 5 columnas anónimas en una tabla. La chispa: darles **identidad y voz** — avatar, personalidad y una frase de la jornada que se genere tras cada cierre. Y al mejor humano de la Peña, derecho a réplica.

**Por qué engancha (psicología).** Personificación = rivalidad = apego. Nadie vuelve una semana tras otra por un leaderboard; la gente vuelve por ver **si Claude vuelve a meterse con la Peña** y si @paco le responde. Las rivalidades con nombre propio son el motor de retención más barato que existe (es el "villano" de toda buena serie).

**Cómo lo implementas.** Ya tenéis los nombres y el ranking; añadid un campo `trash_talk` por jornada en los datos (plantilla con variantes para que no se repita):
```
Grok (144 pts):   "El fútbol es una ecuación. 75 jornadas y la Peña sigue sin despejarla."
Claude (141):     "Respeto a La Peña. Pero respeto más a los datos."
ChatGPT (139):    "Predije este mensaje antes de escribirlo."
→ Réplica del mejor humano (@paco, 4º): "Grok, el VAR existe porque las máquinas no veis nada."
```
Se renderiza en la tarjeta CLASIFICACIÓN GENERAL (que hoy solo dice "La pelea por el liderato"): ahora dice quién es cada quién y qué dice. El módulo CONTEST ya tiene rachas, rivales directos y galardones — **ese oro está a un clic de la portada**.

---

#### CHISPA 8 — El marcador humano-máquina siempre encendido

**Qué es.** Una franja fina sticky bajo el topbar: `HUMANOS 2 — 3 MÁQUINAS · J75` con una barra de progreso dorada vs cian. Calculada de verdad (puntos agregados del bando humano vs bando máquina), nunca inventada.

**Por qué engancha (psicología).** Feedback ambiental continuo + comparación social en tiempo real. El marcador de un partido nunca se apaga porque la incertidumbre del resultado es el gancho: si "vamos perdiendo", la tensión te hace volver; si "vamos ganando", el orgullo te hace volver. Es el "ganas de volver" que pediste, mecanizado.

**Cómo lo implementas.** Los datos ya existen (`rankingRows` en `cover_page.js`); solo falta agregarlos por bando. La franja se puebla en `state.js` (que ya actualiza `topbar-kicker`/`topbar-title`):
```html
<div class="cp-scorebar" aria-label="Marcador global">
  <span class="human">HUMANOS <b>2</b></span>
  <i class="bar"><em style="width:40%"></em></i>
  <span class="machine">MÁQUINAS <b>3</b></span>
</div>
```
Con una micro-animación `width` al refrescar (la barra "se mueve" cuando hay novedades — estáis a un paso: ya tenéis `livePulse` y SSE).

---

### 🔹 D) EFECTO WOW VISUAL

---

#### CHISPA 9 — Portada de periódico de verdad

**Qué es.** Ya tenéis el tema "newspaper" activo (`body.newspaper-ui`) y un `typewriter_system.css` construido y **sin usar en portada**. La chispa: dejar de poner un logo gigante y convertir la portada en una **primera plana** — masthead, fecha de edición, titular en tipografía de prensa que se escribe a sí misma (typewriter), y el duelo VS como foto de portada del pesaje.

**Por qué engancha (psicología).** Efecto framing: el formato "noticia de hoy" presta autoridad y urgencia — un periódico solo publica en portada lo que importa *hoy*. Además, novelty: nadie en el mundo de las quinielas usa el formato prensa; es una firma visual que se recuerda ("la web que es un periódico donde las máquinas ganan a los humanos").

**Cómo lo implementas.** Jerarquía tipográfica nueva (hoy el titular es más pequeño que el logo):
```
Kicker:  "SÁBADO 1 DE AGOSTO · JORNADA 75 · CIERRE EN 2H 58M"   ← fecha de edición + countdown vivo
H1:      "LAS MÁQUINAS NOS ESTÁN GANANDO"  (clamp(2.2rem, 6vw, 4rem), 800, reveal typewriter)
Lead:    (el de la Chispa 4)
Logo:    reducido a masthead de cabecera (60px máx) — hoy ocupa 132px del hero
```
El typewriter ya está implementado: enlazad el H1 al sistema (`typewriter_system.css` respeta `prefers-reduced-motion`).

---

#### CHISPA 10 — El partido bajo lupa que se enciende

**Qué es.** PARTIDO BAJO LUPA es vuestro dato más curioso: **4-5 inteligencias mirando el mismo partido y eligiendo distinto**. Hoy son 5 etiquetas planas. La chispa: convertirlo en un **jurado** — las fichas entran en cascada con rebote, el contador "4 posturas" cuenta 0→4 en 400ms, y al pasar el ratón sobre un equipo, las fichas de quienes eligieron su resultado se iluminan en oro.

**Por qué engancha (psicología).** La divergencia dispara curiosidad ("¿cómo pueden no ponerse de acuerdo?") y el recuento animado crea microsuspense (contar hacia arriba = expectativa). El hover con "votos iluminados" convierte datos abstractos en una escena: el jurado deliberando en directo.

**Cómo lo implementas (CSS de por medio, ya tenéis el keyframe `count-pop`):**
```html
<div class="cp-picks">
  <span class="is-pena" style="animation-delay:0ms">  <small>La Peña</small> <b>2</b> <em>45%</em></span>
  <span style="animation-delay:60ms">                 <small>Claude</small> <b>X</b></span>
  <span style="animation-delay:120ms">                <small>Grok</small>   <b>X</b></span>
  <span style="animation-delay:180ms">                <small>Copilot</small><b>1</b></span>
</div>
```
```css
.cp-picks span { animation: count-pop .4s cubic-bezier(.34,1.56,.64,1) backwards; }
.cp-fixture:hover .cp-picks span[data-sign="2"] { background: rgba(245,158,11,.25); box-shadow: 0 0 14px rgba(245,158,11,.4); }
```

---

## 4. TOP 3 — MAYOR IMPACTO / MENOR ESFUERZO PARA HOY

| # | Chispa | Esfuerzo | Impacto | Por qué |
|---|--------|----------|---------|---------|
| 🥇 | **Hero reescrito** (Chispa 4 + 5: "Las máquinas nos están ganando" + "Firmar por la humanidad") | **15 min** — 3 strings en `cover_page.js` | 🔥🔥🔥 | Cambia la primera impresión de TODO visitante y el recuerdo de la web. Cero riesgo, cero CSS, dato real ya disponible. |
| 🥈 | **Countdown vivo** (Chispa 1) | **30 min** — `setInterval` + 2 reglas CSS | 🔥🔥🔥 | Tu palanca de conversión #1 (cierre de quiniela) está congelada. Un reloj que corre convierte la urgencia en acción y, al cerrarse, en "ganas de volver". |
| 🥉 | **El VS que pelea** (Chispa 2) | **25 min** — keyframes CSS puros | 🔥🔥 | Es lo primero que ve el ojo tras el hero; 3 animaciones baratas hacen que la portada "respire" y refuerzan la metáfora del combate, que es tu marca. |

**Orden sugerido del día:** copy (15 min) → countdown (30 min) → VS (25 min). **Menos de 2 horas y la portada deja de estar muerta.**

---

## 5. MODO BESTIA — 3 CONCEPTOS COMPLETAMENTE DISTINTOS

### 🎮 CONCEPTO 1 — GAMIFICADO: "LA ARENA"

La página es un **coliseo**. La quiniela es el combate de la semana; cada jornada es un round.

**Titular hero:** `JORNADA 75 — SUENA LA CAMPANA.`

**Micro-copy:**
> En la esquina azul: 24 humanos que se juegan la cena.
> En la esquina roja: 5 máquinas que no duermen.
> El árbitro ya está en el campo. Falta un humano en la esquina azul.

**Animación/interacción:** los bandos entran desde sus esquinas con spring al cargar; el VS late; al guardar la quiniela suena la campana (la tenéis en `SoundManager`); el countdown es un **reloj de round de boxeo**: `ROUND 75 · 2:58:41` en rojo de combate.

**Detalle visual que brilla:** los avatares de los Maestros IA con su "récord" tipo boxeador — `GROK · 144 PTS · RACHA: 3` — y el mejor humano como "retador" de la esquina azul.

---

### 📰 CONCEPTO 2 — MINIMAL BRUTALISTA: "EL MARCADOR" (GANADOR 🏆)

Se acabó el ruido. Una primera plana brutalista: fondo negro, una cifra gigante, la verdad. Reutiliza TODO lo que ya construiste (tema newspaper, typewriter, ranking real).

**Titular hero:** `LAS MÁQUINAS NOS ESTÁN GANANDO.` (revelado con typewriter — `typewriter_system.css` ya existe y no lo usas)

**Micro-copy:**
> Grok 144 · Claude 141 · ChatGPT 139.
> 75 jornadas demostrando que el fútbol no se calcula: se siente.
> Falta tu firma.

**Animación/interacción:** el titular se escribe a sí mismo; los puntos de los maestros **tic-tac como un ticker de bolsa** cuando hay novedad (SSE ya lo permite); el countdown en la fecha de edición del periódico.

**Detalle visual que brilla:** la franja sticky `HUMANOS 2 — 3 MÁQUINAS` como la "cinta de resultados" de un periódico de la mañana — y la portada cambia según el bando que lidera: si lideran las máquinas, el acento es cian (frío, calculador); si lideran los humanos, el acento es oro (calor de la Peña).

---

### ✍️ CONCEPTO 3 — STORYTELLING PERSONAL: "LA CARTA"

La portada es una **carta manuscrita** del mejor humano de La Peña al visitante. Primera persona, vulnerabilidad, reclutamiento.

**Titular hero:** `Llevo 75 jornadas perdiendo contra un robot. Necesito ayuda.`

**Micro-copy:**
> Soy @paco, 4º de La Peña. Grok me saca 12 puntos.
> Cada semana 5 máquinas hacen su quiniela sin sudar, mientras nosotros nos jugamos la cena.
> La Peña te cubre las espaldas. Firma aquí abajo.

**Animación/interacción:** la carta se escribe sola (typewriter), la firma de @paco aparece con un trazo, y al unirte **tu nombre se añade a la lista de firmantes** con un mini confeti (la infraestructura ya existe).

**Detalle visual que brilla:** tu quiniela guardada lleva tu nombre **escrito a mano** sobre la tarjeta — compromiso público de verdad.

---

### 🏆 EL GANADOR: CONCEPTO 2 — "EL MARCADOR"

**Por qué gana:**
1. **Es el único que convierte tu verdad en identidad.** La gamificación (1) es divertida pero genérica — cualquier fantasy puede ser una arena. El storytelling (3) es entrañable pero depende de un personaje. El marcador brutalista es la única apuesta que **ninguna otra quiniela del mundo se atrevería a hacer**: admitir en portada que las máquinas ganan. Eso ES tu diferenciación.
2. **Cuesta casi nada.** Tema newspaper ✓ · typewriter ✓ · ranking real ✓ · SSE ✓. Es 80% copy + jerarquía, 20% código nuevo.
3. **Corta el ruido.** Hoy la portada compite: logo gigante + 8 secciones + 2 CTAs. Brutalista = un solo mensaje, una sola emoción, un solo botón. El minimalismo es la forma más rápida de que algo se sienta *brillante*.

### QUÉ CAMBIAR EXACTAMENTE ABOVE THE FOLD (en orden de impacto)

1. **El kicker** → `SÁBADO 1 DE AGOSTO · JORNADA 75 · CIERRE EN 2H 58M 41S` (con segundos vivos, Chispa 1).
2. **El H1** → "Las máquinas nos están ganando." en `clamp(2.2rem, 6vw, 4rem)` / 800 / blanco, con reveal typewriter. El logo pasa a masthead de 60px máximo (hoy 132px — el titular manda).
3. **El lead** → "Grok 144 · Claude 141 · ChatGPT 139. 75 jornadas demostrando que el fútbol no se calcula: se siente. Falta tu firma." Los tres nombres en cian frío, "se siente" en oro.
4. **El CTA primario** → `Firmar por la humanidad` con el countdown dentro; secundario → `Ver cómo van las máquinas`.
5. **El duelo** → se queda (es tu mejor metáfora) pero vivo: esquinas entrando, VS latiendo (Chispa 2).
6. **La franja sticky** `HUMANOS 2 — 3 MÁQUINAS` bajo el topbar, con la barra dorada/cian (Chispa 8).

**Regla de oro para todo el documento:** el marcador, el 3-0, los puntos — **siempre de datos reales, jamás inventados**. La credibilidad es el único activo que una web de quinielas no puede permitirse perder, y "las máquinas ganan" solo funciona si es verdad.

---

## ANEXO — EVIDENCIA TÉCNICA (lo que verifiqué en vivo, 1 ago 2026)

| Verificación | Resultado |
|---|---|
| Animaciones en portada (escaneo de estilos computados del DOM completo) | **1 sola:** `page-enter` 0.35s en el contenedor `.cp` |
| Countdown "CIERRE EN 3H 06M" | **Congelado**: `coverCloseLabel()` calcula una vez al render; sin `setInterval` |
| Clasificación general | Grok 144 · Claude 141 · ChatGPT 139 — **3 máquinas arriba**, enterrada a y≈676 |
| Jerarquía hero | Logo 132px > titular; "¿Quién sabe más de fútbol?" a 16px (mismo tamaño que el lead) |
| Copy hero actual | "Compite contra nuestro Programa, los Maestros IA y toda La Peña. Suma aciertos, escala en el ranking y conquista la jornada." |
| Joyas infrautilizadas | `confetti.js` (grande a 15/15 ✓), `SoundManager` ✓, `count-pop` keyframe sin usar, `typewriter_system.css` sin usar en portada, "Sé el primero en mojarte" muerto en un estado vacío |
| Micro-interacciones ya existentes | Confeti al guardar, sparkles en hover, paleta ⌘K, PWA, SSE — **la base es sólida, solo falta llevarla a la portada** |
