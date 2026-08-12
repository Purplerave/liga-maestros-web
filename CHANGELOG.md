# Changelog — Liga de Maestros Web

Formato inspirado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/).

## 2026-08-12 — Ligas 2026-27: planteles oficiales y extranjeras a cero

### Corregido

- 🔴 **Primera y Segunda seguían con los equipos de 2025-26.** Mallorca, Girona y Oviedo ya no están en Primera; Racing de Santander, Deportivo y Málaga ascienden. En Segunda entran Mallorca, Girona, Oviedo, Tenerife, Eldense, Sabadell y Celta Fortuna, y salen Racing, Deportivo, Málaga, Mirandés, Huesca, Cultural Leonesa y Zaragoza. La migración de arranque sustituye `clasificacion` si el plantel no coincide, sin borrar puntos de una temporada ya empezada.
- 🔴 **Las ligas extranjeras de la pestaña Ligas seguían con la clasificación cerrada de 2025-26.** Premier, Bundesliga y Ligue 1 se reinician a 0 puntos con los planteles 2026-27 (Coventry/Ipswich/Hull, Schalke/Elversberg/Paderborn, Troyes/Le Mans). El deploy copia también `MULTI_STANDINGS.json` al runtime para que producción no conserve el cache viejo.

## 2026-08-03 — Quiniela J75 autoreparable

### Corregido

- 🔴 **Dos partidos de la J75 se quedaron sin resultado (VPS y TPS).** En
  produccion los partidos 1 (VPS Vaasa–Inter Turku) y 2 (TPS Turku–IFK
  Mariehamn) quedaron como `NS` tras acabar la jornada. La migracion
  `ensure_jornada_75()` aplica ahora los resultados oficiales verificados de
  `data/quiniela15_J75_resultados.json` **solo en filas que sigan sin
  marcador** (nunca pisa un resultado existente): al desplegar/arrancar, la
  jornada queda completa de forma determinista aunque el directo no cubra algo.
- 🔴 **La pestaña Quiniela mostraba la última jornada a medias.** La migración
  `ensure_jornada_75()` se saltaba todo el trabajo si existía **cualquier** fila
  de la jornada en `resultados`. Si una importación quedó a medias (partidos
  ausentes, filas vacías `-/-` o duplicadas), la jornada se quedaba rota para
  siempre y el boleto renderizaba `Pendiente / -` en los huecos.
  - Nueva `ensure_jornada_completa()` (en `liga_maestros/db/migrations.py`)
    lee el boleto oficial `data/quiniela15_J{N}_scrape.json` (ya va en el repo)
    e **inserta los partidos que falten, rellena filas vacías y elimina
    duplicados** quedándose con la fila más completa. Nunca toca goles,
    estados ni minutos de partidos jugados o en directo, así que es segura a
    mitad de jornada. Corre sola en cada arranque de la app.
  - `build_jornada_matches()` autocompleta desde el scrape los huecos antes
    de responder: aunque una BD esté incompleta, la pestaña siempre muestra el
    boleto de 15 partidos.

### Añadido

- **`tools/ops/REPARAR_JORNADA_QUINIELA.py`** — reparación manual en un comando:
  `python tools/ops/REPARAR_JORNADA_QUINIELA.py --jornada 75` (con `--check` solo
  diagnostica: ausentes, vacíos y duplicados). Hace backup de la BD antes de
  escribir y es standalone (no depende del resto del código).
- Tests de regresión: jornada parcial se completa, filas vacías se rellenan,
  duplicados se eliminan, resultados en directo no se tocan, payload siempre
  devuelve 15 partidos.

## 2026-07 — Frontend from the future (26 de julio de 2026)

Capa de producto sobre el design system: navegación por teclado, señales de
sistema honestas y arreglo de dos regresiones que se colaron en la entrega
anterior. Todo es **mejora progresiva**: si un módulo falla, la app sigue igual.

### Corregido (regresiones reales)

- 🔴 **El Service Worker nunca se registraba.** El registro vivía en un
  `<script>` inline dentro de `liga_index.html`, pero la CSP del sitio es
  `script-src 'self'` sin `'unsafe-inline'`: el navegador lo descartaba en
  silencio, así que el modo offline y el precacheo no funcionaban en
  producción. Extraído a `static/js/sw_register.js` (con la URL en un
  `data-sw-url`). Nuevo test bloquea cualquier `<script>` inline en templates.
- 🔴 **`animations.css` rompía los tests de gobernanza CSS**: llegó sin bloque
  `@layer`, con 4 `!important` y usando `--drift-x` sin definir. Ahora está en
  la capa `animations`, con la variable declarada en `.confetti-piece` y cero
  `!important`. La suite vuelve a estar verde.
- Cachés del Service Worker bumpeadas a `v2` (las tres a la vez) para que los
  clientes existentes recojan el shell nuevo.

### Añadido

- **Paleta de comandos (`⌘K` / `Ctrl+K`)** — `static/js/command_palette.js`.
  Buscador difuso sobre vistas, jornadas recientes y acciones (guardar,
  compartir, actualizar, perfil, sonido). Navegación completa con teclado
  (flechas, Home/End, Enter, Esc), roles ARIA `combobox`/`listbox`/`option`,
  devolución de foco al cerrar y resaltado del término buscado. Disparador
  visible en la topbar para que sea descubrible, no solo un atajo oculto.
- **Atajos globales**: `P` portada, `Q` quiniela, `D` directo, `L` ligas,
  `J` juegos, `N` La Peña, `R` actualizar, `S` guardar, `?` abre la paleta.
  Se ignoran mientras se escribe en un campo de texto.
- **Señales de sistema (`static/js/ux_signals.js`)**:
  - *Skip link* «Saltar al contenido» para navegación por teclado.
  - Barra de progreso al cargar vistas en diferido (ya no hay saltos mudos).
  - Píldora de estado de red: avisa al perder conexión, confirma al
    recuperarla y relanza la carga de datos.
  - Aviso «hay una versión nueva» con botón de recarga cuando el Service
    Worker instala una actualización.
- **View Transitions API** en los cambios de sección, con degradación limpia
  en navegadores que no la soportan y desactivada bajo `prefers-reduced-motion`.
- **Prefetch por intención**: al pasar el ratón o tabular a un botón de
  sección se precarga su CSS (idempotente, sin ejecutar lógica de vista).
- `aria-current="page"` en la navegación principal: hasta ahora el estado
  activo era solo visual y los lectores de pantalla no lo anunciaban.
- `content-visibility: auto` en los bloques de la arena: el navegador se
  ahorra pintar lo que está fuera de pantalla.
- Tokens de movimiento que la auditoría pedía y faltaban: `--duration-fast`,
  `--duration-normal`, `--duration-slow`, `--ease-spring`.

### Tests

- `tests/test_frontend_ux.py`: sin scripts inline, assets nuevos existentes y
  referenciados en el shell, precacheo del SW, versiones de caché alineadas y
  arranque de los módulos protegido con `try/catch`.

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
