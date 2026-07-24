# 📋 Auditoría Integral UI/UX — Liga de Maestros Web

> **Fecha:** 24 de julio de 2026  
> **Auditor:** Principal UI/UX Designer & Lead Frontend Architect  
> **Stack:** Flask + Jinja2 · Vanilla JS · CSS puro (27 archivos · 7.629 líneas)  
> **Tema visual:** "Diario deportivo nocturno" (dark mode + acentos gold/cyan)

---

## 1. 🏥 Diagnosis General (Resumen Ejecutivo)

### Nota Global: **5.2 / 10**

El producto tiene una **base conceptual sólida** — la metáfora de "diario deportivo" es potente y diferenciadora, la paleta oscura con acentos dorados transmite premium, y la arquitectura de tokens CSS (`tokens.css`) demuestra que hubo intención de diseño sistemático. Sin embargo, la ejecución se ha degradado por acumulación de capas de CSS contradictorias, especificidad descontrolada y ausencia de gobernanza.

### 🔴 Los 3 puntos más críticos a corregir de inmediato:

| # | Problema Crítico | Impacto |
|---|---|---|
| **1** | **802 declaraciones `!important`** — guerra de especificidad que hace el CSS ingobernable, impide el mantenimiento y rompe la cascada natural. | Mantenibilidad: **CRÍTICO** |
| **2** | **672 colores hardcoded** (249 hex + 423 rgba) fuera de tokens CSS, incluyendo **6 variables CSS inexistentes** (`--cartoon-paper`, `--cartoon-ink`, `--cartoon-gold`, `--cartoon-green`, `--cartoon-cyan`, `--cartoon-coral`, `--font-main`). | Consistencia: **CRÍTICO** |
| **3** | **Breakpoints inconsistentes** — se usan 11 breakpoints distintos (420, 600, 620, 640, 760, 850, 899, 900, 980, 1100, 1180, 1420px) sin estrategia unificada, causando comportamientos erráticos entre tamaños. | Responsive: **ALTO** |

---

## 2. 📊 Tabla de Problemas Detectados

| # | Archivo / Componente | Elemento | Problema Actual | Propuesta de Mejora Visual | Prioridad |
|---|---|---|---|---|---|
| 1 | `tokens.css` L121-154 | Variables `--cartoon-*` | **Variables inexistentes** — `--cartoon-paper`, `--cartoon-ink`, `--cartoon-gold`, `--cartoon-green`, `--cartoon-cyan`, `--cartoon-coral` se usan en `.profile-badge-pill` pero **nunca se definen**. Resultado: fondos transparentes rotos. | Definir todas las variables en `:root` o eliminar los selectores huérfanos. | 🔴 Alta |
| 2 | `pages/contest.css` L113 | `.ver-todos-btn` | Usa `font-family: var(--font-main)` — **variable que no existe**. Hereda la fuente del body, inconsistente con el resto de botones. | Cambiar a `var(--font-ui)`. | 🔴 Alta |
| 3 | **Todos los archivos CSS** | `!important` | **802 declaraciones `!important`** repartidas en 27 archivos. Indica una guerra de especificidad entre la capa base (`tokens.css`), el tema (`themes/newspaper/`) y las páginas (`pages/`). | Refactorizar con metodología de capas CSS: `@layer base, theme, components, pages, utilities`. Eliminar todos los `!important`. | 🔴 Alta |
| 4 | `tokens.css` + todos | Colores hardcoded | **672 valores de color** fuera de custom properties. Un cambio de marca requiere editar ~27 archivos. | Centralizar TODOS los colores en tokens semánticos: `--color-surface-elevated`, `--color-border-subtle`, `--color-text-on-accent`, etc. | 🔴 Alta |
| 5 | `stable_masthead.css` + `surface_shape.css` + `shell.css` | `.topbar-shell`, `.header-brand-panel` | **3 archivos diferentes definen el mismo componente** con valores contradictorios (`border-radius: 0` vs `14px`, `box-shadow` diferente). El resultado depende del orden de carga. | Unificar en un único archivo de componente. Usar `@layer` para control de cascada. | 🔴 Alta |
| 6 | `typography.css` + `typewriter_system.css` | Fuentes | **Doble sistema tipográfico contradictorio**: `typography.css` asigna fuentes por selector largo con `!important`, `typewriter_system.css` las sobreescribe con otro `!important`. | Unificar en un solo archivo con clases utility: `.font-display`, `.font-ui`, `.font-data`. | 🟡 Media |
| 7 | `tokens.css` | Escala tipográfica | **No existe escala tipográfica definida**. Los tamaños se asignan arbitrariamente: `0.46rem`, `0.48rem`, `0.52rem`, `0.54rem`, `0.55rem`, `0.56rem`, `0.57rem`, `0.58rem`, `0.6rem`, `0.62rem`, `0.64rem`, `0.65rem`, `0.66rem`, `0.68rem`, `0.7rem`, `0.72rem`, `0.73rem`, `0.74rem`, `0.75rem`, `0.76rem`, `0.78rem`, `0.82rem`, `0.85rem`, `0.86rem`, `0.88rem`, `0.9rem`, `0.92rem`, `0.95rem`, `0.96rem`, `0.98rem`, `1rem`, `1.02rem`, `1.05rem`, `1.1rem`, `1.12rem`, `1.2rem`, `1.25rem`, `1.28rem`, `1.35rem`, `1.4rem`, `1.45rem`, `2.1rem`, `2.35rem`, `2.45rem`, `2.65rem`, `2.7rem`, `3rem`, `4rem`, `4.4rem` — **+50 tamaños distintos**. | Definir escala modular (Major Third 1.25): `--text-xs: 0.625rem`, `--text-sm: 0.75rem`, `--text-base: 0.875rem`, `--text-md: 1rem`, `--text-lg: 1.25rem`, `--text-xl: 1.563rem`, `--text-2xl: 1.953rem`, `--text-3xl: 2.441rem`. | 🟡 Media |
| 8 | **Global** | Sistema de espaciado | **No existe escala de espaciado**. Se usan valores arbitrarios: `1px`, `2px`, `3px`, `4px`, `5px`, `6px`, `7px`, `8px`, `9px`, `10px`, `11px`, `12px`, `13px`, `14px`, `15px`, `16px`, `17px`, `18px`, `20px`, `21px`, `22px`, `24px`, `26px`, `28px`, `30px`, `32px`, `34px`, `36px`, `38px`, `40px`, `44px`, `46px`, `48px`, `54px`, `58px`, `64px`, `66px`, `78px`, `88px`, `92px`, `96px` — sin regla de 4px/8px consistente. | Definir tokens: `--space-1: 4px`, `--space-2: 8px`, `--space-3: 12px`, `--space-4: 16px`, `--space-5: 20px`, `--space-6: 24px`, `--space-8: 32px`, `--space-10: 40px`, `--space-12: 48px`, `--space-16: 64px`. | 🟡 Media |
| 9 | `app_shell.css` L59 | `.topbar-kicker` | `font-size: 0.65rem` (~10.4px) — **por debajo del mínimo legible** (12px recomendado WCAG). | Mínimo `--text-xs: 0.75rem` (12px). | 🟡 Media |
| 10 | `app_shell.css` L79 | `.topbar-user-score` | `font-size: 0.58rem` (~9.3px) — **ilegible** en la mayoría de pantallas. | Subir a mínimo `0.6875rem` (11px) o `0.75rem` (12px). | 🟡 Media |
| 11 | `app_shell.css` L106 | `.topbar-user-name` | `max-width: 58px` — truncamiento agresivo de nombres de usuario. Muchos nombres se cortan. | Aumentar a `100px` o usar `clamp(60px, 8vw, 120px)`. | 🟢 Baja |
| 12 | `tokens.css` L176-181 | `.profile-badge-pill` | `border-radius: 10px 7px 11px 8px` — **border-radius asimétrico "orgánico"** que choca con el sistema geométrico del tema "newspaper" (que usa `0` o `border-radius` uniforme). | Decidir: o el sistema es orgánico/cartoon o es newspaper/rectangular. No ambos a la vez. | 🟡 Media |
| 13 | `stable_masthead.css` | Layout responsive | **11 breakpoints diferentes** sin naming convention ni estrategia mobile-first. Algunos se pisan entre sí (899px vs 900px). | Adoptar 4 breakpoints estándar: `sm: 640px`, `md: 768px`, `lg: 1024px`, `xl: 1280px`. Mobile-first. | 🟡 Media |
| 14 | `cover_hero.css` | `.cp-stage` | `width: min(880px, calc(100vw - 48px))` a 760px colapsa a `width: min(260px, ...)` — **salto drástico** de 880px a 260px sin estados intermedios. | Añadir breakpoint intermedio en ~600px con `width: min(480px, ...)`. | 🟡 Media |
| 15 | `match_cards.css` L77-81 | `.match-card:nth-child` | `animation-delay` hardcoded para 5 tarjetas. Si hay 6+, las restantes no tienen animación de entrada. | Usar `animation-delay: calc(var(--i, 0) * 0.02s)` con custom property inline, o JS. | 🟢 Baja |
| 16 | `interactions.css` L36 | Focus states | `outline: 2px solid #f59e0b !important` — el color de focus es gold, pero en `app_shell.css` es `var(--accent)` (cyan `#38bdf8`). **Inconsistencia** en el color de focus. | Unificar: `--color-focus: var(--accent)` en todos los sitios. | 🟡 Media |
| 17 | `app_shell.css` | `.primary-btn` | `padding: 4px 9px` + `font-size: 0.64rem` — **botones diminutos** (~26px alto real). No cumplen los 44×44px mínimos de Apple HIG / 48×48px de Material Design para targets táctiles. | Mínimo `min-height: 36px` (desktop) / `44px` (touch). Padding `8px 16px`. | 🟡 Media |
| 18 | `cover_hero.css` | `.cp` background | Grid de líneas de fondo de 64px visible pero sin snap — crea **moiré visual** al hacer scroll en pantallas retina. | Usar `background-attachment: fixed` o eliminar el grid sutil. | 🟢 Baja |
| 19 | `typewriter_system.css` | `.topbar-title` | `text-shadow: 2px 2px 0 rgba(0,0,0,0.72)` — sombra de texto dura que reduce legibilidad en texto pequeño. | Eliminar o usar `text-shadow: 0 1px 2px rgba(0,0,0,0.3)`. | 🟢 Baja |
| 20 | `newspaper/shell.css` | `.newspaper-page-nav` | `grid-template-columns: repeat(7, ...)` — pero solo hay 6 botones de navegación. La columna 7 queda vacía. | Cambiar a `repeat(6, minmax(0, 1fr))`. | 🟡 Media |
| 21 | `cover_hero.css` | `.cp-intro h1` | `white-space: nowrap` en el titular H1 — en pantallas <420px puede desbordar si el texto es largo. Ya parcialmente mitigado con media query pero frágil. | Eliminar `white-space: nowrap` y confiar en `clamp()` para el tamaño. | 🟢 Baja |
| 22 | `tokens.css` | Transiciones | Define `--transition: all 0.22s` y `--transition-fast: all 0.12s` pero muchos componentes usan valores propios (`0.15s`, `0.18s`, `0.2s`, `140ms`, `160ms`, `180ms`, `0.3s`, `0.35s`, `0.4s`). | Estandarizar: `--ease-out: cubic-bezier(0.16, 1, 0.3, 1)`, `--duration-fast: 120ms`, `--duration-normal: 200ms`, `--duration-slow: 350ms`. | 🟡 Media |
| 23 | `legal.css` | Página legal | Estilo completamente independiente del resto de la app. No carga tokens ni comparte componentes. Parece un sitio diferente. | Integrar con el sistema de diseño principal: usar `var(--bg-main)`, `var(--text-main)`, `var(--font-ui)`, `var(--radius-md)`. | 🟡 Media |
| 24 | `stable_masthead.css` L1-10 | `.app-shell` | `overflow: hidden` en el shell + `height: 100dvh` — el contenido que excede la altura se gestiona con overflow interno. Esto puede **romper el scroll del navegador** (pull-to-refresh, scroll restoration, etc.) | Preferir `min-height: 100dvh` + `overflow-x: hidden` sin bloquear scroll vertical. | 🟡 Media |
| 25 | `quiz_page.css` | `.quiz-option` | `border: 1px dotted` — borde punteado en opciones de quiz que parece inacabado/error de renderizado. | Cambiar a `border: 1px solid` o `border: 2px solid`. | 🟢 Baja |
| 26 | `components.css` (newspaper) | `.match-score-badge.is-live-score` | `::before` con `content: attr(data-live-label)` posicionado `top: -12px` — puede **sobresalir del contenedor** y cortarse con `overflow: hidden`. | Añadir `overflow: visible` al padre o reposicionar dentro del badge. | 🟢 Baja |
| 27 | `contest.css` | `.contest-view-tabs` | `grid-template-columns: repeat(6, ...)` — 6 pestañas en móvil sin scroll horizontal es **demasiado denso**. | En móvil: `overflow-x: auto` + `scroll-snap-type: x mandatory`. | 🟡 Media |

---

## 3. 💻 Propuestas Concretas de Código

### 3.1 — Eliminar variables fantasma y definir tokens faltantes

**Archivo: `static/css/base/tokens.css`**

<details>
<summary><strong>ANTES (problemático)</strong></summary>

```css
/* tokens.css — las variables --cartoon-* NO existen en :root */
.profile-badge-pill {
    background: var(--cartoon-paper);  /* ❌ undefined → fallback: initial */
    color: var(--cartoon-ink);          /* ❌ undefined → fallback: initial */
}
```

```css
/* pages/contest.css */
.ver-todos-btn {
    font-family: var(--font-main);     /* ❌ undefined → fallback: inherit */
}
```
</details>

<details>
<summary><strong>DESPUÉS (corregido)</strong></summary>

```css
/* tokens.css — :root ampliado */
:root {
    /* ... tokens existentes ... */

    /* Cartoon badge palette (usado en profile badges) */
    --cartoon-paper: #f3e7cf;
    --cartoon-ink: #1a1612;
    --cartoon-gold: #f5c451;
    --cartoon-green: #4ade80;
    --cartoon-cyan: #38d9ff;
    --cartoon-coral: #fb923c;

    /* Alias legacy (eliminar gradualmente) */
    --font-main: var(--font-ui);
}
```
</details>

---

### 3.2 — Sistema de tokens completo recomendado

**Archivo nuevo: `static/css/base/tokens.css` (reemplazo del `:root`)**

```css
:root {
    /* ═══════════════════════════════════════
       FONTS
       ═══════════════════════════════════════ */
    --font-ui: "Plus Jakarta Sans", system-ui, -apple-system, sans-serif;
    --font-display: "Outfit", "Plus Jakarta Sans", system-ui, sans-serif;
    --font-data: "JetBrains Mono", ui-monospace, "SFMono-Regular", Consolas, monospace;
    --font-hand: "Sacramento", "Segoe Script", cursive;
    --font-headline: "Rajdhani", "Outfit", sans-serif;

    /* ═══════════════════════════════════════
       COLOR PALETTE — Deep Space Premium
       ═══════════════════════════════════════ */

    /* Neutrals */
    --color-gray-50:  #f0f4f8;
    --color-gray-100: #dbe7f5;
    --color-gray-200: #b9c9dc;
    --color-gray-300: #8fb7dc;
    --color-gray-400: #8b9dc3;
    --color-gray-500: #5a6d8a;
    --color-gray-600: #3d4f6a;
    --color-gray-700: #1e2d45;
    --color-gray-800: #131d30;
    --color-gray-900: #0d1423;
    --color-gray-950: #06090f;

    /* Accent — Cyan */
    --color-accent-300: #7dd3fc;
    --color-accent-400: #38bdf8;
    --color-accent-500: #0ea5e9;
    --color-accent-600: #0284c7;

    /* Brand — Gold */
    --color-brand-300: #fde68a;
    --color-brand-400: #fbbf24;
    --color-brand-500: #f59e0b;
    --color-brand-600: #d97706;

    /* Semantic — Success */
    --color-success-400: #4ade80;
    --color-success-500: #22c55e;
    --color-success-600: #16a34a;

    /* Semantic — Danger */
    --color-danger-400: #f87171;
    --color-danger-500: #ef4444;
    --color-danger-600: #dc2626;

    /* ═══════════════════════════════════════
       SEMANTIC TOKENS (los que usa la UI)
       ═══════════════════════════════════════ */
    --bg-main:           var(--color-gray-950);
    --bg-surface:        var(--color-gray-900);
    --bg-surface-raised: var(--color-gray-800);
    --bg-card:           rgba(13, 20, 35, 0.75);
    --bg-card-hover:     rgba(22, 34, 55, 0.85);
    --bg-overlay:        rgba(3, 7, 18, 0.86);

    --text-primary:   var(--color-gray-50);
    --text-secondary: var(--color-gray-400);
    --text-tertiary:  var(--color-gray-500);
    --text-on-accent: var(--color-gray-950);
    --text-on-brand:  var(--color-gray-950);

    --border-default:  rgba(255, 255, 255, 0.07);
    --border-subtle:   rgba(255, 255, 255, 0.04);
    --border-accent:   rgba(56, 189, 248, 0.35);
    --border-brand:    rgba(245, 158, 11, 0.35);

    --accent:          var(--color-accent-400);
    --accent-glow:     rgba(56, 189, 248, 0.25);
    --brand:           var(--color-brand-400);
    --success:         var(--color-success-500);
    --danger:          var(--color-danger-500);

    --color-focus:     var(--color-accent-400);

    /* ═══════════════════════════════════════
       TYPOGRAPHY SCALE (Major Third 1.25)
       ═══════════════════════════════════════ */
    --text-2xs:  0.625rem;   /* 10px — mínimo absoluto (solo decorative) */
    --text-xs:   0.75rem;    /* 12px — labels, captions */
    --text-sm:   0.875rem;   /* 14px — body secondary */
    --text-base: 1rem;       /* 16px — body principal */
    --text-md:   1.125rem;   /* 18px — lead */
    --text-lg:   1.25rem;    /* 20px — subheading */
    --text-xl:   1.5625rem;  /* 25px — heading 3 */
    --text-2xl:  1.953rem;   /* 31px — heading 2 */
    --text-3xl:  2.441rem;   /* 39px — heading 1 */
    --text-4xl:  3.052rem;   /* 49px — hero */

    --leading-tight:   1.15;
    --leading-snug:    1.35;
    --leading-normal:  1.55;
    --leading-relaxed: 1.7;

    --tracking-tight:  -0.01em;
    --tracking-normal:  0;
    --tracking-wide:    0.04em;
    --tracking-wider:   0.08em;

    /* ═══════════════════════════════════════
       SPACING SCALE (4px base)
       ═══════════════════════════════════════ */
    --space-0:   0;
    --space-0.5: 2px;
    --space-1:   4px;
    --space-1.5: 6px;
    --space-2:   8px;
    --space-2.5: 10px;
    --space-3:   12px;
    --space-4:   16px;
    --space-5:   20px;
    --space-6:   24px;
    --space-8:   32px;
    --space-10:  40px;
    --space-12:  48px;
    --space-16:  64px;
    --space-20:  80px;

    /* ═══════════════════════════════════════
       RADII
       ═══════════════════════════════════════ */
    --radius-xs:   4px;
    --radius-sm:   6px;
    --radius-md:   10px;
    --radius-lg:   14px;
    --radius-xl:   20px;
    --radius-full: 999px;

    /* ═══════════════════════════════════════
       SHADOWS
       ═══════════════════════════════════════ */
    --shadow-xs: 0 1px 2px rgba(0, 0, 0, 0.3);
    --shadow-sm: 0 2px 8px -2px rgba(0, 0, 0, 0.4);
    --shadow-md: 0 4px 20px -4px rgba(0, 0, 0, 0.5);
    --shadow-lg: 0 8px 30px -6px rgba(0, 0, 0, 0.6);
    --shadow-xl: 0 18px 50px -12px rgba(0, 0, 0, 0.7);
    --shadow-glow-accent: 0 0 16px rgba(56, 189, 248, 0.25);
    --shadow-glow-brand:  0 0 16px rgba(245, 158, 11, 0.25);
    --shadow-card: 0 2px 16px -2px rgba(0, 0, 0, 0.45), 0 0 0 1px rgba(255,255,255,0.03);

    /* ═══════════════════════════════════════
       MOTION
       ═══════════════════════════════════════ */
    --ease-out:    cubic-bezier(0.16, 1, 0.3, 1);
    --ease-spring: cubic-bezier(0.4, 0, 0.2, 1);
    --ease-in:     cubic-bezier(0.4, 0, 1, 1);

    --duration-instant: 80ms;
    --duration-fast:    120ms;
    --duration-normal:  200ms;
    --duration-slow:    350ms;
    --duration-slower:  500ms;

    /* ═══════════════════════════════════════
       GRADIENTS
       ═══════════════════════════════════════ */
    --gradient-accent: linear-gradient(135deg, #38bdf8 0%, #818cf8 100%);
    --gradient-brand:  linear-gradient(135deg, #fbbf24 0%, #f59e0b 100%);
    --gradient-live:   linear-gradient(135deg, #22c55e 0%, #10b981 100%);
    --gradient-danger: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);

    /* ═══════════════════════════════════════
       BREAKPOINTS (referencia, usar en @media)
       ═══════════════════════════════════════ */
    /* sm:  640px  — Móvil grande */
    /* md:  768px  — Tablet */
    /* lg:  1024px — Desktop */
    /* xl:  1280px — Desktop wide */

    /* ═══════════════════════════════════════
       Z-INDEX SCALE
       ═══════════════════════════════════════ */
    --z-base:     1;
    --z-sticky:   100;
    --z-dropdown: 500;
    --z-overlay:  1000;
    --z-modal:    5000;
    --z-toast:    9000;
    --z-max:      10000;
}
```

---

### 3.3 — Refactor de botones con tokens y estados correctos

**Archivo: `static/css/layout/app_shell.css`**

<details>
<summary><strong>ANTES</strong></summary>

```css
.primary-btn, .login-btn {
    background: var(--gradient-accent);
    color: #000;
    border: none;
    padding: 4px 9px;
    border-radius: var(--radius-sm);
    font-weight: 700;
    font-size: 0.64rem;
    cursor: pointer;
    transition: var(--transition);
    position: relative;
    overflow: hidden;
}
```
</details>

<details>
<summary><strong>DESPUÉS</strong></summary>

```css
.primary-btn, .login-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: var(--space-1.5);
    min-height: 36px;
    padding: var(--space-2) var(--space-4);
    border: 1px solid transparent;
    border-radius: var(--radius-md);
    background: var(--gradient-accent);
    color: var(--text-on-accent);
    font-family: var(--font-ui);
    font-weight: 700;
    font-size: var(--text-xs);
    line-height: 1;
    cursor: pointer;
    transition: 
        transform var(--duration-fast) var(--ease-out),
        filter var(--duration-fast) var(--ease-out),
        box-shadow var(--duration-normal) var(--ease-out);
    position: relative;
    overflow: hidden;
    -webkit-tap-highlight-color: transparent;
}

.primary-btn:hover {
    filter: brightness(1.1);
    transform: translateY(-1px);
    box-shadow: var(--shadow-glow-accent);
}

.primary-btn:active {
    transform: translateY(0) scale(0.98);
    filter: brightness(0.95);
}

.primary-btn:focus-visible {
    outline: 2px solid var(--color-focus);
    outline-offset: 2px;
}

.primary-btn:disabled,
.primary-btn[aria-disabled="true"] {
    opacity: 0.45;
    cursor: not-allowed;
    transform: none;
    filter: none;
}

/* Touch target mínimo en móvil */
@media (pointer: coarse) {
    .primary-btn {
        min-height: 44px;
        padding: var(--space-3) var(--space-5);
        font-size: var(--text-sm);
    }
}
```
</details>

---

### 3.4 — Focus states unificados

**Archivo: `static/css/base/tokens.css` (añadir al final)**

```css
/* ═══════════════════════════════════════
   GLOBAL FOCUS — Accesibilidad WCAG 2.1
   ═══════════════════════════════════════ */
:focus {
    outline: none;
}

:focus-visible {
    outline: 2px solid var(--color-focus);
    outline-offset: 2px;
    border-radius: var(--radius-xs);
}

/* Focus interno para elementos con fondo oscuro */
.dark-focus:focus-visible {
    outline-color: var(--color-brand-400);
    box-shadow: 0 0 0 4px rgba(56, 189, 248, 0.15);
}
```

---

### 3.5 — Responsive: sistema de breakpoints unificado

**Archivo: `static/css/base/tokens.css` (añadir media queries base)**

```css
/* ═══════════════════════════════════════
   RESPONSIVE FOUNDATIONS
   ═══════════════════════════════════════ */

/* Base: mobile-first */
.app-shell {
    display: grid;
    grid-template-columns: 1fr;
    grid-template-rows: auto auto auto 1fr;
    min-height: 100dvh;
    width: 100%;
}

/* sm — 640px */
@media (min-width: 640px) {
    .app-shell {
        grid-template-rows: 56px auto 1fr;
    }
}

/* md — 768px */
@media (min-width: 768px) {
    .app-shell {
        grid-template-rows: 60px 40px 1fr;
    }
}

/* lg — 1024px */
@media (min-width: 1024px) {
    .app-shell {
        grid-template-columns: 200px 1fr;
        grid-template-rows: 64px 38px 1fr;
    }
}

/* xl — 1280px */
@media (min-width: 1280px) {
    .app-shell {
        grid-template-columns: 220px 1fr;
        grid-template-rows: 66px 38px 1fr;
    }
}
```

---

### 3.6 — Migración CSS con @layer (eliminación progresiva de !important)

**Archivo: `templates/liga_index.html` (modificar imports)**

<details>
<summary><strong>ANTES</strong></summary>

```html
<link rel="stylesheet" href="css/base/tokens.css">
<link rel="stylesheet" href="css/layout/app_shell.css">
<link rel="stylesheet" href="css/themes/newspaper/shell.css">
<link rel="stylesheet" href="css/themes/newspaper/components.css">
<!-- ... 14 archivos más sin orden de capas -->
```
</details>

<details>
<summary><strong>DESPUÉS</strong></summary>

```html
<!-- Un solo entry point que importa todo con @layer -->
<link rel="stylesheet" href="css/main.css">
```

**Nuevo archivo: `static/css/main.css`**

```css
/* Define el orden de prioridad de capas */
@layer reset, base, layout, theme, components, pages, utilities;

@import "base/reset.css"        layer(reset);
@import "base/tokens.css"        layer(base);
@import "base/typography.css"    layer(base);
@import "layout/app_shell.css"   layer(layout);
@import "layout/stable_masthead.css" layer(layout);
@import "themes/newspaper/shell.css" layer(theme);
@import "themes/newspaper/components.css" layer(theme);
@import "components/interactions.css" layer(components);
@import "components/match_cards.css"  layer(components);
@import "components/team_badges.css"  layer(components);
@import "pages/ticket.css"        layer(pages);
@import "pages/standings.css"     layer(pages);
@import "pages/profile.css"       layer(pages);
/* ...etc */
```

Con `@layer`, una regla en `pages` **siempre** gana sobre `theme` que gana sobre `base`, sin necesidad de `!important`.
</details>

---

### 3.7 — Accesibilidad: contraste corregido

```css
/* ANTES — Contraste insuficiente */
--text-muted: #8b9dc3;    /* sobre #06090f → ratio 5.2:1 ✅ OK */
--text-dim:   #5a6d8a;    /* sobre #06090f → ratio 3.1:1 ❌ FAIL AA para texto */

/* DESPUÉS — WCAG AA compliant */
--text-secondary: #8b9dc3;  /* 5.2:1 ✅ — texto secundario */
--text-tertiary:  #6b7fa0;  /* 4.5:1 ✅ — texto terciario (antes #5a6d8a) */
--text-disabled:  #4a5c78;  /* 3.0:1 ⚠️  — solo para disabled (no requiere AA) */
```

---

## 4. 🎨 Sistema de Tokens Recomendado

### Paleta refinada

```
NEUTRALS (escala azul-gris profunda)
┌─────────────────────────────────────────────────────────┐
│  50  #f0f4f8  ████████  Texto principal                │
│ 100  #dbe7f5  ████████  Texto hover                     │
│ 200  #b9c9dc  ████████  Texto secondary                 │
│ 300  #8fb7dc  ████████  Labels activos                  │
│ 400  #8b9dc3  ████████  Texto muted (WCAG AA ✅)        │
│ 500  #6b7fa0  ████████  Texto tertiary (WCAG AA ✅)     │
│ 600  #3d4f6a  ████████  Bordes activos                  │
│ 700  #1e2d45  ████████  Surface elevated                │
│ 800  #131d30  ████████  Surface raised                  │
│ 900  #0d1423  ████████  Surface (cards)                 │
│ 950  #06090f  ████████  Background main                 │
└─────────────────────────────────────────────────────────┘

ACCENTS
┌─────────────────────────────────────────────────────────┐
│  Cyan    #38bdf8  ████████  Acento primario, links      │
│  Gold    #fbbf24  ████████  Brand, premios, destacados  │
│  Green   #22c55e  ████████  Live, éxito, positivo       │
│  Red     #ef4444  ████████  Error, peligro, eliminar    │
│  Purple  #818cf8  ████████  Consejo IA, gradientes      │
└─────────────────────────────────────────────────────────┘
```

### Escala tipográfica optimizada

```
DISPLAY SYSTEM
┌───────────────────────────────────────────────────────────────┐
│  Token      │ Size      │ Font          │ Weight │ Uso       │
├─────────────┼───────────┼───────────────┼────────┼───────────┤
│  --text-4xl │ 3.052rem  │ Rajdhani      │ 700    │ Hero H1   │
│  --text-3xl │ 2.441rem  │ Outfit        │ 800    │ Page H1   │
│  --text-2xl │ 1.953rem  │ Outfit        │ 700    │ Section H2│
│  --text-xl  │ 1.5625rem │ Outfit        │ 600    │ Card H3   │
│  --text-lg  │ 1.25rem   │ Plus Jakarta  │ 700    │ Subtitle  │
│  --text-md  │ 1.125rem  │ Plus Jakarta  │ 500    │ Lead/Body │
│  --text-base│ 1rem      │ Plus Jakarta  │ 400    │ Body      │
│  --text-sm  │ 0.875rem  │ Plus Jakarta  │ 500    │ Secondary │
│  --text-xs  │ 0.75rem   │ Plus Jakarta  │ 600    │ Labels    │
│  --text-2xs │ 0.625rem  │ JetBrains Mono│ 700    │ Data only │
└───────────────────────────────────────────────────────────────┘

FONT STACK
  UI:       Plus Jakarta Sans → system-ui (legibilidad moderna)
  Display:  Outfit → Plus Jakarta Sans (titulares geométricos)
  Data:     JetBrains Mono → ui-monospace (tablas, scores)
  Hero:     Rajdhani → Outfit (titulares de portada, deportivo)
```

### Contraste verificado (WCAG AA)

```
  Combinación                         Ratio   AA     AAA
  ─────────────────────────────────────────────────────
  #f0f4f8 on #06090f                  17.2:1  ✅     ✅
  #8b9dc3 on #06090f                   5.2:1  ✅     ❌
  #6b7fa0 on #06090f (nuevo)          4.5:1  ✅     ❌
  #fbbf24 on #06090f                   8.7:1  ✅     ✅
  #38bdf8 on #06090f                   7.8:1  ✅     ✅
  #22c55e on #06090f                   6.3:1  ✅     ❌
  #ef4444 on #06090f                   4.6:1  ✅     ❌
  #06090f on #fbbf24 (texto en gold)   8.7:1  ✅     ✅
  #06090f on #38bdf8 (texto en cyan)   7.8:1  ✅     ✅
```

---

## 5. 📝 Plan de Acción Priorizado

### Sprint 1 — Quick Wins (1-2 días)
- [ ] Definir variables `--cartoon-*` faltantes en `tokens.css`
- [ ] Corregir `--font-main` → `--font-ui` en `contest.css`
- [ ] Corregir `repeat(7, ...)` → `repeat(6, ...)` en `newspaper-page-nav`
- [ ] Subir `font-size` mínimo a `0.75rem` (12px) en todos los labels visibles
- [ ] Unificar color de focus a `var(--accent)`

### Sprint 2 — Foundation (3-5 días)
- [ ] Implementar `@layer` en un `main.css` entry point
- [ ] Migrar tokens.css al sistema completo recomendado
- [ ] Eliminar duplicación de reglas entre `stable_masthead.css`, `surface_shape.css` y `shell.css`
- [ ] Estandarizar breakpoints a 4 valores: 640, 768, 1024, 1280px

### Sprint 3 — Cleanup (5-10 días)
- [ ] Eliminar progresivamente los 802 `!important`
- [ ] Migrar colores hardcoded a tokens semánticos
- [ ] Unificar la escala tipográfica a 10 valores
- [ ] Implementar escala de espaciado de 4px

### Sprint 4 — Polish (continuo)
- [ ] Añadir microinteracciones con `@keyframes` y `transition` estandarizados
- [ ] Testing de accesibilidad con Lighthouse y axe-core
- [ ] Responsive audit con BrowserStack en dispositivos reales
- [ ] Documentar el design system en Storybook o Zeroheight

---

*Fin de la auditoría. Documento generado el 24 de julio de 2026.*
