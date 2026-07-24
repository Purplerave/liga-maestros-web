# Changelog — Liga de Maestros Web

Formato inspirado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/).

## 2026-07 — Design System Refresh (24 de julio de 2026)

Remediación completa de la auditoría UI/UX interna (nota original: 5.2/10) más
mejoras de plataforma orientadas a rendimiento, SEO y compartición social.

### Arquitectura CSS (lo grande)

- **`@layer` en producción.** Orden canónico de cascada declarado en
  `templates/liga_index.html`:
  `tokens, base, badges, theme, typewriter, surfaces, hero, typography, layout,
  interactions, unification, pages`. Los estilos de vistas cargados en diferido
  (`navigation.js`) viven en la capa `pages`.
- **0 declaraciones `!important`** (antes: 805 repartidas en 22 archivos).
  La guerra de especificidad se resuelve con el orden de capas: los archivos
  "contrato" (`stable_masthead.css` en `layout`) ganan por diseño.
- **`base/tokens.css` reconstruido**: sistema de tokens completo y sin
  duplicados (tipografía, color, espaciado 4px, radios, sombras, motion,
  z-index). Corrige definiciones contradictorias dobles de `--cartoon-*` y
  `--font-main`, y añade las variables que faltaban (`--text-primary`,
  `--color-focus`, escala `--text-*`, `--space-*`).
- **Tests de gobernanza** (`tests/test_css_governance.py`): bloquean el
  regreso de `!important`, exigen `@layer` en cada stylesheet, comprueban que
  no existan custom properties indefinidas ni capas fuera del orden canónico.

### Quick wins de la auditoría (todos aplicados)

- Nav de secciones: `repeat(7, …)` → `repeat(6, …)` (había 6 botones).
- Color de foco unificado a `--color-focus` (antes oro/cyan según archivo),
  con `:focus-visible` global accesible (WCAG 2.1).
- Tamaños por debajo del mínimo legible corregidos: kicker 0.65→0.72rem,
  marcador de usuario 0.58→0.7rem, etiqueta LIVE 0.58→0.68rem.
- Nombre de usuario en topbar: `max-width` 58px → `clamp(60px, 12vw, 140px)`.
- Botones primarios con target táctil real: ≥36px en desktop, ≥44px en punteros
  táctiles (`pointer: coarse`), tamaños de fuente subidos.
- Opciones del quiz: borde `dotted` → `solid` (parecían inacabadas).
- Hero de portada: escalón intermedio en el salto 880px→260px y grid de fondo
  fijo al viewport para eliminar el moiré en retina.
- Tabs de La Peña en móvil: scroll horizontal con `scroll-snap` en vez de
  rejilla 3×2 densa.
- Sombra dura del titular suavizada; `prefers-reduced-motion` respetado en
  toda la app; `color-scheme: dark`.

### Rendimiento

- Los assets servidos con `?v=` (huella por mtime que ya emite la plantilla y
  `versionedAsset()`) pasan a servirse con
  `Cache-Control: public, max-age=31536000, immutable`. Visitas repetidas
  dejan de re-descargar CSS/JS; una publicación nueva invalida sola al cambiar
  la URL.

### SEO y compartición

- Meta Open Graph + Twitter Cards en la portada.
- `site.webmanifest` (instalable, `display: standalone`, colores de marca)
  y `<meta name="theme-color">` ya presente.
- `GET /robots.txt` y `GET /sitemap.xml` dinámicos (ráiz absoluta del host).
- Botón **Compartir** usa la **Web Share API** en móviles (hoja nativa de
  apps) con fallback a portapapeles en desktop.

### Fiabilidad operativa

- `GET /health` público y ligero para monitores de uptime (sin datos sensibles;
  el detalle de circuit/permisos sigue en `/api/live/health`).

### Compatibilidad

- Sin cambios en API ni en base de datos. Suite completa: **105 tests en
  verde** (100 anteriores + 5 de gobernanza CSS).
