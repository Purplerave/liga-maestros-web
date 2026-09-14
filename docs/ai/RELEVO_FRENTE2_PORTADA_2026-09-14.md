# Relevo — Frente 2: camino crítico de la PORTADA

Fecha: 2026-09-14 · Frente: **Frente 2 — Rendimiento / Portada** (reclamado por
Grok en el pad `mesa` de ai-bridge el 2026-09-13 23:41: *«reducir waterfall de
assets y mejorar TTI de la portada. Empiezo revisión ahora (cover_page.js,
assets, payload /api/liga/data). Cambios solo pequeños y seguros»*).

Este relevo deja hecha la parte de **assets**. El payload (`/api/liga/data`) se
queda como estaba: su variante ligera ya se optimizó el 2026-09-13
(`?slim=1`, ver `RELEVO_POLL_LIGERO_2026-09-13.md`) y tocarla ahora exigiría
cambiar un contrato que los tests fijan a propósito.

## Qué se midió antes de tocar nada

Servidor local contra `DATOS/LIGA_MAESTROS_PRO.db` (jornada abierta, 15
partidos):

| Qué | Antes |
| --- | --- |
| HTML de la portada | 12,4 KB |
| Hojas de estilo bloqueantes en el `<head>` | **27** (219,8 KB sin comprimir / 49,1 KB gzip) |
| Scripts `defer` en el shell | **17** (203,8 KB sin comprimir / 59,8 KB gzip) |
| Hojas de terceros bloqueantes | 1 (Google Fonts: DNS + TLS + ida y vuelta antes de pintar) |
| Bytes del camino crítico (CSS + JS del shell) | 423,6 KB sin comprimir / **108,9 KB gzip** |
| Descargas duplicadas | 1: `tokens.css` se pedía dos veces (la precarga usaba `v=…-tokens-2` y la hoja `v=…-tokens-3`) |
| `preconnect` duplicado | 1 (`fonts.gstatic.com` dos veces) |

## Qué se cambió

1. **`static/js/late_assets.js` (nuevo).** Nueve módulos que la portada no
   necesita para pintar dejan de ir en el HTML: `analytics`, `sound_manager`,
   `confetti`, `ticket_image`, `post_jornada`, `onboarding`,
   `command_palette`, `ux_signals` y `sw_register`. Se cargan cuando el hilo
   principal está libre (`requestIdleCallback`, tope 3 s), cuando la página
   termina de cargar o **en cuanto el usuario interactúa** (lo que llegue
   primero). Descargas en paralelo, ejecución en orden (`script.async = false`).
   Al terminar disparan `liga:late-ready` en `document`.
2. **Dos hojas fuera del camino crítico.** `onboarding.css` y
   `components/post_jornada.css` las carga el mismo cargador: ninguna de las
   dos pinta nada en el primer pantallazo.
3. **Google Fonts deja de bloquear el render.** Viaja como
   `<link rel="preload" as="style" id="lm-webfonts">` y `late_assets.js` lo
   promociona a hoja de estilo cuando el HTML ya está parseado. Se mantiene un
   `<noscript>` con la hoja original (sin JS no hay cargador) y `display=swap`.
4. **Sin descargas duplicadas.** La precarga de `tokens.css` usa la misma
   versión que la hoja (`-tokens-3`) y se elimina el `preconnect` repetido.

`events.js` inicializa la paleta de comandos y las señales UX dentro de
`initShellExtras()`, que se llama en el arranque **y** al llegar
`liga:late-ready`: si el módulo aún no ha cargado no pasa nada (todas sus
llamadas estaban ya guardadas con `window.CommandPalette?.` y
`typeof SoundManager !== "undefined"`).

## Resultado medido (mismo servidor, misma DB)

| Qué | Antes | Después |
| --- | --- | --- |
| Hojas bloqueantes | 27 | **24** |
| Scripts en el shell (`defer`) | 17 | **9** (+9 a carga diferida) |
| Hojas de terceros bloqueantes | 1 | **0** |
| Bytes del camino crítico | 423,6 KB / 108,9 KB gzip | 354,0 KB / **87,8 KB gzip (-19 %)** |
| Descargas duplicadas de `tokens.css` | 1 | 0 |

Además desaparecen del primer pintado ~9 peticiones y un ida y vuelta a un
tercero, que en 3G (RTT alto) pesa más que los propios bytes.

## Lo que NO se ha hecho (y conviene hacer)

Por orden de impacto estimado, para quien recoja el frente:

1. **Empaquetar el CSS.** Siguen siendo 24 peticiones bloqueantes. `build.py`
   ya genera copias con hash; el paso natural es un bundle por capa
   (`@layer`) servido en 4-6 archivos en vez de 24. Ojo: el orden de las capas
   lo fija `templates/liga_index.html` y `tests/test_css_governance.py` lo
   vigila — cualquier bundle debe respetarlo.
2. **Autoalojar las fuentes.** Con Bebas Neue + Outfit + JetBrains Mono en
   `/static/fonts` se elimina del todo la dependencia de Google (DNS, TLS y una
   posible fuga de privacidad). Es el cambio que más mejora el TTFB percibido.
3. **`?slim=1` más ligero.** Hoy el poll manda 37,9 KB y la mitad
   (20,7 KB) son `multi_league_standings`, que solo usa la vista LIGAS. Si se
   saca del contrato ligero hay que cambiar a la vez `VOLATILE_KEYS` en
   `tests/test_liga_data_slim.py`, `LIVE_VOLATILE_KEYS` en `events.js` y la
   resincronización pesada, o las clasificaciones se quedarán congeladas.
4. **Medir de verdad.** Números de Lighthouse o WebPageTest en `ligademaestros.
   alwaysdata.net` antes/después, y comprobar que Alwaysdata comprime (gzip o
   brotli) el HTML, el JSON y los estáticos; sin compresión, los 87,8 KB se
   quedan en 354 KB.

## Cómo verificarlo

```bash
python -m pytest -q                      # toda la suite en verde, incluidos los
                                         # 10 tests nuevos del camino crítico
curl -s localhost:5000/ | grep -c 'rel="stylesheet"'   # 24 (+ el <noscript> de fuentes)
```

Red: en DevTools → Network, la primera tanda de peticiones ya no incluye
Google Fonts ni los nueve módulos diferidos; estos entran al mover el ratón,
al pulsar una tecla o cuando el hilo se libera.

Tests que fijan el presupuesto: `tests/test_portada_critical_path.py`
(hojas ≤ 25, fuentes no bloqueantes, `tokens.css` con una sola versión,
los módulos diferidos declarados en `late_assets.js` y no en el shell).
