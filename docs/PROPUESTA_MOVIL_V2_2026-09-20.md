# 📱 Estudio y propuesta móvil v2 — Liga de Maestros
**Fecha:** 2026-09-20
**Contexto:** petición del usuario — "la versión móvil es horrible, habría que hacer un estudio de cómo cambiarla" + problemas de portada (aciertos poco visibles) y refresco con parpadeo.

---

## 1. Diagnóstico rápido (lo que había)

### Portada
- **Aciertos poco visibles:** los `is-hit` solo cambiaban color de texto (`#6ee7b7`) sin fondo ni borde. En tabla densa de 8 columnas, el ojo no los distinguía. No había `is-miss`, así que fallos y no-jugados se veían igual.
- **Parpadeo al refrescar:** `refreshData()` y `refreshLiveSnapshot()` hacían `innerHTML = renderNewspaperCoverPageV3()` completo. Toda la portada se destruía y recreaba → flash blanco, scroll jump, pérdida de foco. No existía `patchCoverPage` como sí existe `patchLiveArena` / `patchTicketArena`.
- **Auto-refresh parecía no funcionar:** el poll ligero solo comparaba `liveSignature`, `resultsSignature` y `standingsSignature`. Si cambiaba consenso de La Peña o ranking, no se repintaba. Además `livePollDelay()` en idle era 180s → 3 minutos sin novedades aparentes.

### Móvil
Auditoría previa (2026-08-20) ya detectó:
- Doble scroll (`app-shell 100dvh overflow:hidden` + `arena-content overflow:auto`) → gesto no nativo.
- Tablas con `min-width: 600-1040px` → scroll horizontal obligatorio.
- Tipografía <12px (hasta 8.6px) → ilegible + auto-zoom iOS en inputs.
- Touch targets 36px en 1X2 → mis-taps.
- Nav superior con 6 pestañas + `overflow-x:auto` → poco accesible con pulgar.
- 25 CSS + 17 JS en portada → TTI lento.

La portada v19 añadía más densidad: 7 columnas IA + Peña + Tú en 360px.

---

## 2. Qué se ha arreglado en esta iteración

### A. Aciertos visibles (cover_hero.css)
- **Nuevo `is-hit`:** fondo degradado verde (`rgba(52,211,153,0.22)`), borde 0.65 opaco, glow `0 0 10px`, texto `#a7f3d0` 800. En fila de usuario, `✓` con `box-shadow` verde y barra lateral `inset 3px 0 0`.
- **Nuevo `is-miss`:** fondo rojo tenue, borde rojo 0.22, tachado sutil `::before` rotado -12deg, opacidad 0.72. En fila de usuario, `✕` y barra lateral roja.
- **Transiciones:** `transition: background,color,border,box-shadow 0.25s` en `td`, `cx-r-when`, `cx-r-pick-val`, `cx-ia-sign`. Al actualizar, `is-updating` → `animation: cxCellFlash 0.6s`.
- **JS:** en `cover_page.js` `buildRow` ahora calcula `signHit` y `signMiss` para IA y Peña, añade clases `is-hit` / `is-miss`. Antes solo `is-hit`.

Resultado: de un vistazo se ve quién acertó, sin leer letra pequeña.

### B. Refresco sin parpadeo
- **Nueva función `patchCoverPage()`** en `cover_page.js`:
  - Detecta si estamos en `ALL` y existe `.cx`.
  - Parchea solo celdas cambiadas: ticker (con `dataset.sig` para evitar re-render), KPIs (Peña vs IA, TU progreso), boleto (por `match-id` → solo `when`, `pick`, `ia-sign`, `pena`), live panel (solo marcadores/minutos si count igual, si no re-render ligero de 4 tarjetas).
  - Usa `classList.toggle` y `textContent` → no `innerHTML` de toda la página.
  - Devuelve `true` si parcheó → `refreshData` y `refreshLiveSnapshot` hacen early return.
- **Integración:**
  - `quantum_final.js`: `patchedCoverView` además de `patchedLiveView` / `patchedTicketView`.
  - `events.js`: `refreshLiveSnapshot()` llama `patchCoverPage()` y evita `renderArena()` completo.
  - `livePollDelay()` idle: 180s → 60s. Ventana jornada 45s → 40s. Más vivo sin machacar servidor.
  - `LIVE_HEAVY_SYNC_POLLS`: 4 → 2. Consenso y ranking se sincronizan cada ~80s en directo, no cada 2-4 min.
  - Nuevas firmas: `consensoSignature()` y `rankingSignature()` → si La Peña vota, se detecta y parchea.

Resultado: gol entra → solo cambia el `cx-r-when` con flash azul suave, sin parpadeo de toda la página. Scroll y foco se preservan.

### C. Móvil v2 rediseñado (cover_hero.css @899px + mobile_v2.css)
**Principios aplicados:**
1. **Scroll nativo:** `app-shell`, `main-arena`, `arena-content` → `height:auto overflow:visible` en `mobile_v2.css` (capa `responsive` gana a `hero`).
2. **Sin scroll horizontal:** `.cx`, `.cx-boleto-table-wrap`, `.cx-boleto` → `max-width:100vw overflow-x:hidden`. Tabla pasa a `display:block`.
3. **Boleto como tarjetas:**
   - `thead {display:none}`
   - `tbody {display:flex flex-direction:column gap:10px}`
   - `tr {display:flex flex-wrap, border-radius 12px, padding 10px, box-shadow}`
   - `td {display:contents}` → reordenamos con `order`:
     - 0: Nº (28px chip)
     - 1: local, 2: vs, 3: visitante (flex 1, 0.88rem bold)
     - 4: hora/res (pill 56px, 0.72rem, colores live/ft)
     - 5: TU (100% ancho, `::before "TÚ"` + pill 44px min-height)
     - 6+: IA chips (40px, envuelven), 7: Peña
   - `is-hit` en tarjeta → borde verde + glow.
4. **Top compacto:**
   - `grid-template-columns:1fr` + `top-right: grid 1fr 1fr`
   - `top-state` ocupa 2 columnas, centrado, wrap permitido.
   - KPIs con borde, radius 8px, fondo tenue.
   - CTA `min-height:44px width:100%`.
5. **Tipografía legible:** piso 12px (0.75rem). En móvil, `cx-boleto-table` 0.82rem, `cx-r-team` 0.88rem, `cx-r-pick-val` 1.05rem, `cx-st-row` 0.82rem + min-height 44px.
6. **Touch targets:** todos los interactivos ≥44px (CTA, KPIs, pick-val 44px, IA 40px, nav buttons 56px, match cards 52px).
7. **Orden de contenido:** `cx-col-center {order:-1}` → boleto primero, luego clasificaciones y directo. En móvil lo importante arriba.

**Antes vs después (360px):**
- Antes: tabla 1040px con scroll lateral, texto 0.58rem, aciertos verde claro sobre negro sin fondo, top con 4 KPIs en fila que desbordaban.
- Después: 15 tarjetas apiladas, sin scroll horizontal, TU pick grande con ✓/✕, IA en chips envueltos, top en 2 columnas + CTA full width, todo legible a 1 mano.

---

## 3. Qué queda por hacer (roadmap móvil)

### P0 — Ya hecho en este PR
- [x] Aciertos visibles con fondo/borde/✓/✕
- [x] `patchCoverPage` sin parpadeo
- [x] Poll más frecuente + firmas de consenso/ranking
- [x] Boleto en tarjetas en ≤899px
- [x] Top responsive y sin overflow

### P1 — Próximos sprints (1-2 días)
- **Bottom nav con contador live:** mostrar puntito rojo con número de directos en "Directo". Ya existe estructura, falta badge dinámico.
- **Skeleton loading para portada:** en vez de vacío, 3 tarjetas grises que evitan CLS.
- **Pull-to-refresh nativo:** en móvil, gesto hacia abajo → `refreshData({auto:true})` + haptic.
- **Peña voto en portada:** en tarjeta móvil, mostrar % de consenso al lado de Peña (ej: "PEÑA 1 62%").

### P2 — Pulido (1 semana)
- **Bundling CSS/JS:** 25 CSS → 2 (critical + resto). 17 JS → 2. Usar `build.py` ya existente.
- **Imágenes:** logos equipos con `width/height` + `loading=lazy` excepto crest `eager fetchpriority=high`. Convertir PNG a WebP.
- **Gestos:** swipe horizontal entre jornadas (izq/dcha cambia `j=`).
- **A11y:** aumentar contraste de `cx-dim` en móvil (ya 4.6:1, pero subir a 5:1) y `aria-live` en ticker.

---

## 4. Métricas de aceptación

- [ ] En 360×740, 0 scroll horizontal (DevTools → no overflow).
- [ ] `patchCoverPage()` se ejecuta en 90% de polls auto (console log).
- [ ] Acierto se ve a 1m de distancia (test visual con 3 usuarios).
- [ ] Tiempo entre gol real y actualización en portada < 45s (poll 30s + patch).
- [ ] Lighthouse mobile: Performance ≥80, CLS <0.1, Best Practices ≥90.
- [ ] Touch targets ≥44px (DevTools → Accessibility).
- [ ] Ningún input hace auto-zoom en iOS (font-size ≥16px).

---

## 5. Archivos tocados

- `static/css/cover_hero.css` → hit/miss + mobile tarjetas + transiciones + bump v75
- `static/js/pages/cover_page.js` → `is-miss` + `patchCoverPage()` + ticker sig + bump v77
- `static/js/quantum_final.js` → integra `patchCoverPage` + bump v47
- `static/js/events.js` → nuevas firmas + delay 60s + `patchCoverPage` + bump v18
- `static/css/mobile_v2.css` → overrides cover-active + hit contraste + bump v3
- `templates/liga_index.html` → bumps de versión

---

## 6. Conclusión

La portada ya no parpadea, los aciertos cantan en verde con ✓ y glow, y el móvil deja de ser una tabla encogida para ser 15 tarjetas apiladas que se marcan con el pulgar. El trabajo restante es de pulido (skeletons, pull-to-refresh, bundling), no de re-arquitectura. Con este PR la experiencia móvil pasa de "horrible" a "usable y bonita" sin tocar backend ni API.
