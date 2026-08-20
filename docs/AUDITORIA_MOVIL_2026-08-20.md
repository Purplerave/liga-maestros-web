# 📱 Auditoría completa de experiencia móvil — Liga de Maestros

**Fecha:** 20 de agosto de 2026
**Rama:** `arena/01a01f9c-liga-maestros-web` (base `main` @ `0ba0224`)
**Alcance:** factibilidad + belleza visual en móvil (teléfonos, no tablet)
**Método:** inspección del código fuente real (`templates/`, `static/css/`, `static/js/`), inventario de assets y mapeo de breakpoints. No es opinión: cada hallazgo apunta a archivo y línea.

---

## 1. Veredicto en 3 frases

1. **El producto ya "funciona" en móvil, pero funciona como una app de escritorio encogida.** El layout es un *app shell* de `height: 100dvh; overflow: hidden` con scroll interno anidado (`static/css/layout/app_shell.css` y `stable_masthead.css`) — un patrón de dashboard de escritorio, no una web móvil. El teléfono queda atrapado en un doble scroll.

2. **El 80 % del contenido de datos se sirve en tablas con `min-width` fijo (600–1040 px) que obligan a scroll horizontal** en Portada, Directo y Ligas. Solo la vista Quiniela tiene una transformación a tarjetas en móvil (`ticket_compact.css` ≤700px). El resto depende del gesto de "arrastrar la tabla", que es el anti-patrón clásico de móvil.

3. **La tipografía está sistemáticamente por debajo del umbral de legibilidad:** 138 reglas usan fuentes < 0.65rem y hay tamaños de **0.54rem (8.6px)**, 0.55rem, 0.58rem (9.3px) y 0.62rem (9.9px). En un teléfono eso es ilegible y además dispara el auto-zoom de Safari en los inputs (< 16px).

**Conclusión:** no hay que rehacer el backend ni el concepto (que es 10/10). Hay que **reescribir la capa de presentación móvil** con una estrategia *mobile-first* de verdad: contenedor de scroll nativo, tarjetas en lugar de tablas, escala tipográfica legible y *touch targets* de 44px. El trabajo es acotado (todo es CSS + algo de HTML/JS de render), no requiere migrar de stack.

---

## 2. Qué se inspeccionó

| Área | Evidencia revisada |
|---|---|
| Layout base | `templates/liga_index.html`, `static/css/layout/app_shell.css`, `static/css/layout/stable_masthead.css` |
| Breakpoints | `static/css/mobile_responsive.css`, `themes/newspaper/ticket_compact.css`, `themes/newspaper/shell.css` |
| Tipografía | `static/css/base/tokens.css`, `base/typography.css`, `themes/newspaper/page_foundations.css` |
| Render JS | `static/js/arena.js` (tabla de tensión + match cards), `static/js/quantum_final.js` |
| Assets / perf | inventario de `static/img/team_logos` (179 PNG, 2.5 MB), `static/sw.js`, `static/manifest.webmanifest` |
| Carga | 25 `<link rel=stylesheet>` + 17 `<script defer>` solo en la portada |

---

## 3. Diagnóstico por capas (con evidencia)

### A. Arquitectura de layout — DOBLE SCROLL (P0, crítico)

**Evidencia:**
- `static/css/layout/app_shell.css`: `.app-shell { height: 100vh; overflow: hidden }`, `.main-arena { overflow: hidden }`, `.arena-content { overflow: hidden }`.
- `static/css/layout/stable_masthead.css`: `body.newspaper-ui.quiniela-focus .app-shell { height: 100dvh; max-height: 100dvh; overflow: hidden }` y `.arena-content { overflow: auto }`.
- En `@media (max-width: 899px)` se mantiene el mismo esquema de grid fijo (filas 56px/52px/42px/1fr), solo se reordena en columna.

**Problema:** el `body` no hace scroll; el scroll vive dentro de `.arena-content`. Resultado en móvil:
- Dos barras de scroll posibles (la interna de `.arena-content` + la que introduce Safari con `100dvh` cuando aparece/desaparece la barra de URL).
- El gesto de "swipe hacia abajo" no refresca ni se siente nativo.
- El `scroll-behavior: smooth` de `html` no aplica al contenedor interno → los anclajes (`#matches-body`, el *skip-link*) no saltan bien.

**Solución:** en móvil, desactivar el *frame* fijo:
```css
@media (max-width: 899px) {
  body.newspaper-ui.quiniela-focus .app-shell {
    height: auto; max-height: none; overflow: visible;
    display: flex; flex-direction: column;
  }
  body.newspaper-ui.quiniela-focus .main-arena,
  body.newspaper-ui.quiniela-focus .arena-content {
    height: auto; overflow: visible;
  }
}
```
Dejar que el `body` sea el único scroller. Header y nav pasan a `position: sticky`.

---

### B. Tablas con scroll horizontal (P0, crítico)

**Evidencia:**
- `static/css/mobile_responsive.css`: `.arena-table { min-width: 600px }` (≤768px) y `min-width: 500px` (≤480px), dentro de `.arena-table-wrap { overflow-x: auto }`.
- `static/css/themes/newspaper/ticket_compact.css`: `@media (max-width: 1100px) { .arena-table.is-tension-table { min-width: 1040px } }`. La vista de tarjetas solo se activa **≤700px**.
- La tabla de quiniela la renderiza `static/js/arena.js` (`<table class="arena-table is-tension-table">`) con 8 columnas (número + fixture + consenso de 7 maestros + Peña + TU).

**Problema:**
- Portada / Directo / Ligas / Quiz / La Peña dependen de arrastrar una tabla de 500–600px de ancho en un viewport de 360–430px.
- Hay una **franja huérfana entre 700px y 1100px** donde la quiniela sigue siendo tabla de 1040px con scroll lateral, en lugar de tarjetas.
- El scroll horizontal dentro de un contenedor vertical (problema A) es especialmente torpe con el pulgar.

**Solución:** generalizar el patrón de tarjetas que ya existe para Quiniela a **todas** las vistas tabulares:
- Portada/Directo → ya usan `match-card` (bien); el problema es solo la tabla de tensión y las tablas de standings.
- Standings/Ligas → tarjeta por equipo (pos + escudo + nombre + PTS + racha) en 1 columna.
- Quiz/La Peña → lista apilada.
- Cerrar la franja 700–1100px subiendo el *breakpoint* de tarjetas de `700px` a `1100px` (o directamente hacer la tarjeta el diseño base y la tabla el *enhancement* desktop).

---

### C. Tipografía minúscula (P0, crítico — el mayor problema de "bonito")

**Evidencia (inventario `static/css/`):**

| Tamaño | Px | Ocurrencias | Uso típico |
|---|---|---|---|
| 0.54rem | 8.6px | 6 | chips de maestros (`.tension-chip > span`) |
| 0.55rem | 8.8px | 10 | labels de consenso |
| 0.58rem | 9.3px | 16 | estados, horas, breakdowns |
| 0.60rem | 9.6px | 11 | labels |
| 0.62rem | 9.9px | 24 | kickers, captions |
| 0.64rem | 10.2px | 6 | selectores, sub-labels |
| 0.65rem | 10.4px | 17 | botones |

138 reglas usan fuentes por debajo de 0.65rem (10.4px).

**Problema:**
- Por debajo de **12px** el texto deja de ser legible con comodidad en pantallas de alta densidad; por debajo de **10px** es ilegible para la mayoría.
- **Safari iOS auto-zoomea** cualquier `<input>`/`<select>`/`<textarea>` cuyo `font-size` sea < 16px, rompiendo el layout al enfocar (afecta a `.field-group select` en `app_shell.css` que está a 0.64–0.68rem).
- Falla WCAG 2.1 (criterio de tamaño mínimo legible) y el espíritu de AA, anulando el buen contraste que sí está declarado en tokens (`--text-muted` 5.2:1).

**Solución:** una escala tipográfica móvil con **mínimos absolutos**:
- Base: `font-size: 16px` en `<html>`/`body`.
- Labels/captions: **nunca < 12px** (`0.75rem`).
- Cuerpo: 14–16px.
- Datos en mono (marcadores): ≥ 14px.
- Inputs/selects: **16px obligatorio** (evita auto-zoom iOS).

Regla práctica para el refactor: reemplazar todas las fuentes `0.54–0.65rem` por tokens nuevos (`--text-xs: 0.75rem` como piso) y ajustar los contenedores (los chips de 32px de alto no caben con 12px de fuente → rediseñar los chips a 2 columnas o con abreviaturas).

---

### D. Touch targets por debajo del estándar (P0 en la quiniela)

**Evidencia:**
- Solo `.primary-btn`/`.login-btn` reciben `min-height: 44px` vía `@media (pointer: coarse)` (`app_shell.css:335`).
- Los botones 1X2 de la tarjeta móvil: `.match-card .match-signs button { min-width: 36px; min-height: 36px }` (`mobile_responsive.css`).
- En la tarjeta compacta de quiniela, los chips quedan en `height: 32px` y los signos en `18px` (`ticket_compact.css`).
- Nav: botones de `min-height: 30–40px` (`stable_masthead.css` y `shell.css`).

**Problema:** la acción core (marcar 1X2) se hace sobre targets de 36px (y chips de 18–32px), muy por debajo de Apple HIG (44pt) y Material (48dp). Riesgo alto de *mis-tap* justo en el flujo de conversión.

**Solución:** asegurar `min-width/min-height: 44px` en **todos** los controles interactivos en `@media (pointer: coarse)`, no solo en los botones primarios. En la tarjeta de quiniela, rediseñar el picker 1/X/2 como 3 botones grandes de ≥44px en fila, no como chips densos.

---

### E. Navegación (P1)

**Evidencia:**
- `.newspaper-page-nav` con 6 pestañas (Portada, Quiniela, Directo, Ligas, Juegos, La Peña) es una **barra superior** que en móvil se vuelve `overflow-x: auto` (`stable_masthead.css` media 899px).
- Existe CSS huérfano de menú hamburguesa: `.mobile-menu-btn`, `.sidebar-panel.mobile-open` (`mobile_responsive.css`) pero **ningún template/JS lo renderiza** (grep `mobile-menu-btn` = 0 resultados en `templates/` y `static/js/`).

**Problema:**
- Una barra de pestañas **arriba** es poco accesible con el pulgar; el estándar móvil es una **bottom navigation**.
- 6 secciones + scroll horizontal sin indicador = el usuario no sabe que hay más opciones.
- Código muerto de menú lateral.

**Solución:**
- Bottom nav fija (4–5 destinos: Portada, Quiniela, Directo, Ligas, Más) con `padding-bottom: env(safe-area-inset-bottom)`.
- "Juegos" y "La Peña" pueden ir dentro de un menú "Más" o mantenerse como tabs secundarias.
- Eliminar el CSS huérfano o implementar el menú, no dejarlo a medias.

---

### F. Rendimiento y assets (P1)

**Evidencia:**
- La portada carga **25 hojas CSS** y **17 scripts JS** (42 peticiones bloqueantes/`defer`), más 3 familias de Google Fonts.
- `static/img/team_logos/`: **179 archivos PNG, 2.5 MB** sin `srcset`/`sizes`; se sirven a tamaño natural.
- `static/img/ligademaestroslogo_trans.png` = **232 KB** y está marcado `loading="lazy"` en `liga_index.html` pese a ser la imagen *above the fold* (el logo de cabecera). Es el caso inverso al correcto.
- `Rajdhani` se referencia en `typography.css` (`.cp-intro h1 { font-family: "Rajdhani"… }`) pero **no se carga** → FOUT/fallback a Outfit.
- Cache-busting manual con sufijos (`-tokens-3`, `-ticket-mobile-cards-6`, `-cover-hero-68`) → riesgo de desincronización y sin bundling.

**Problema:** en redes móviles (latencia alta, 4G), 42 peticiones + 2.5 MB de logos + 3 fuentes ⇒ TTI lento y CLS alto (logos sin `width`/`height`).

**Solución:**
- **Bundling + minificación** de CSS (35→1-2) y JS (31→1-2) vía build (el proyecto ya usa Makefile; añadir `flask-assets`/`webassets` o un paso simple de concatenación con hash).
- **Imágenes responsivas:** `width`/`height` + `loading="lazy"` en todos los logos de equipos; `loading="eager"` + `fetchpriority="high"` en el logo de cabecera; considerar un sprite o WebP/AVIF.
- Reducir fuentes a **2 familias** (Outfit + JetBrains Mono) y cargar solo pesos usados, con `font-display: swap`.
- Quitar la referencia muerta a Rajdhani o cargarla.

---

### G. PWA / safe area / meta (P2)

**Evidencia:**
- `viewport-fit=cover` y `env(safe-area-inset-*)` presentes en `stable_masthead.css` (top/bottom), pero aplicados de forma incompleta (la nav y los botones no compensan el *home indicator* de iPhone).
- `manifest.webmanifest` correcto (`display: standalone`, icons, maskable), `sw.js` con estrategia cache-first para estáticos.
- `theme-color` = `#06090f` (correcto para la piel oscura).

**Problema:** con *standalone* PWA, si no se compensa el *safe area* inferior, los botones quedan pegados/ocultos tras el *home indicator*.

**Solución:** aplicar `padding-bottom: env(safe-area-inset-bottom)` a la bottom nav y `padding-top: env(safe-area-inset-top)` al header; verificar iconos maskable (ya hay 512 maskable — OK).

---

### H. Interacciones y micro-UX (P2, "bonito")

- **Indicadores de scroll:** donde quede scroll horizontal (p. ej. la propia nav mientras se migra), añadir *fade*/flechas para señalar que hay más contenido.
- **Estados de carga:** hoy se renderiza `<div class="empty-state">Cargando porra...` como texto; en móvil convienen *skeletons* para evitar saltos.
- **Pull-to-refresh** y **swipe entre jornadas** son los gestos nativos esperados en una quiniela móvil (el refresh actual es un botón `↻` en la topbar).
- **Reducir el peso del "periódico":** la piel *newspaper* (doble línea, texturas repetidas, sombras de 10px) es densa en una pantalla de 360px; en móvil conviene una variante más limpia (menos ruido de fondo, radios mayores, sombras suaves).

---

## 4. Plan de acción priorizado

### P0 — Bloqueantes (factibilidad): 1–2 días
1. Eliminar el doble scroll (sección A): `body` como único scroller + header/nav sticky.
2. Tipografía mínima 12px y base 16px; inputs a 16px (sección C).
3. Convertir todas las tablas a tarjetas en móvil; cerrar la franja 700–1100px (sección B).
4. Touch targets 44px en el picker 1X2 y la nav (sección D).

**Resultado:** la web deja de sentirse "rota/encogida" y pasa a ser *usable* con el pulgar en cualquier teléfono.

### P1 — Alto impacto visual: 3–5 días
5. Bottom navigation fija con safe-area (sección E).
6. Bundling de CSS/JS + fuentes a 2 familias (sección F).
7. Imágenes responsivas y CLS (logos con dimensiones, lazy correcto).
8. Skin móvil más limpia (reducir ruido del "periódico").

### P2 — Pulido y encanto: 1 semana
9. Skeletons, indicadores de scroll, pull-to-refresh.
10. Gestos (swipe entre jornadas).
11. Auditar el resto de vistas (Quiz, Juegos, La Peña) con la misma lente.

---

## 5. Sistema de diseño móvil propuesto (tokens)

Añadir a `tokens.css` una sección móvil (o un `@media`):

```css
:root {
  /* Escala tipográfica móvil (pisos absolutos) */
  --text-2xs: 0.75rem;   /* 12px — piso para labels/captions */
  --text-xs:  0.8125rem; /* 13px */
  --text-sm:  0.875rem;  /* 14px */
  --text-base: 1rem;     /* 16px — cuerpo e inputs */
  --text-md:  1.125rem;
  --text-lg:  1.25rem;

  /* Touch targets */
  --tap-min: 44px;
  --tap-lg:  48px;

  /* Espaciado móvil */
  --space-page: 16px;    /* gutter lateral */
  --space-card: 12px;

  /* Radios móviles (más suaves) */
  --radius-md: 12px;
  --radius-lg: 16px;
}
```

Breakpoints recomendados (explicitar en una sola constante de referencia):
- `≤ 359px` (SE/pequeños)
- `360–480px` (móvil)
- `481–700px` (phablet)
- `701–1100px` (tablet / desktop pequeño)
- `> 1100px` (desktop)

Hoy el código usa `768px`, `700px`, `899px`, `1100px` de forma inconsistente; unificar a esta escala elimina la franja huérfana de la sección B.

---

## 6. Checklist de aceptación (Definición de "hecho")

- [ ] En un viewport 360×740 no existe **ningún** scroll horizontal (grep `overflow-x: auto`/`min-width` en tablas de datos = 0).
- [ ] El body hace scroll nativo; header y nav quedan sticky y no "saltan" en iOS.
- [ ] Ningún texto renderiza por debajo de 12px (auditar con DevTools → "computed font-size").
- [ ] Ningún input/select auto-zoomea al enfocar (font-size ≥ 16px).
- [ ] Todos los controles interactivos miden ≥ 44×44px en `pointer: coarse`.
- [ ] Bottom nav visible con *safe area* inferior correcto en iPhone con notch.
- [ ] Portada carga en ≤ 3s en 4G throttling (Lighthouse mobile: Performance ≥ 80, CLS < 0.1).
- [ ] La quiniela se marca con el pulgar sin mis-taps (test manual en 2-3 teléfonos reales).
- [ ] Los logos no causan layout shift (todos con `width`/`height`).

---

## 7. Nota final

El backend, la seguridad y el concepto están resueltos y por encima de la media (según `README.md` y auditorías previas). **Todo el trabajo pendiente es de presentación móvil** y vive en `static/css/` + un puñado de strings en `static/js/arena.js` / `quantum_final.js`. Es un esfuerzo acotado y de alto retorno: pasar de "app de escritorio encogida" a "web móvil bonita y nativa" sin tocar datos ni API.
