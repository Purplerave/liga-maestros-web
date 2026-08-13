# Kit Viral — Liga de Maestros

Entregables listos para integrar en el producto.

## Archivos

| Archivo | Qué es |
|---------|--------|
| `landing-liga-maestros.html` | Landing de conversión SEO-ready |
| `kit-viral-liga-maestros.html` | Prototipo interactivo de todos los componentes P0/P1 |
| `jornada-publica.html` | Página pública SEO `/jornada/N` |
| `README-KIT.md` | Esta guía |
| `FIXES-Y-RUTAS.md` | Bugs + rutas Flask + analytics |

## Prioridad de integración

### Esta semana (P0)

1. **Landing** → servir como `/` o pre-app HTML real (contenido indexable).
2. **Tarjeta viral** → tras guardar/resultado de jornada, generar imagen compartible.
3. **Pantalla de resultado** → ranking Tú vs GPT/Claude/Gemini/Grok vs Peña + botón compartir.
4. **Mensaje hero** → «¿Eres más listo que la IA?» en portada de la app.

### Siguiente sprint (P1)

5. Flujo móvil partido-a-partido (una decisión por pantalla).
6. Bold Call al cerrar quiniela.
7. Medallas en perfil.
8. Objetivos semanales post-login.
9. Parte de guerra automatizado (texto + imagen + `/jornada/N`).

## Cómo generar la tarjeta PNG en producción

### Opción A — Cliente (rápida)
- Librería: `html2canvas` o el canvas nativo del kit.
- Pros: sin servidor.
- Contras: fuentes/calidad variables en iOS Safari.

### Opción B — Servidor (recomendada)
```
POST /api/share-card
{ user, jornada, scores: { human, gpt, claude, gemini, grok, pena }, verdict }

→ PNG 1080×1920 (Stories) + 1200×630 (OG)
```
- Playwright / Puppeteer renderiza plantilla HTML.
- Cache por `user_id + jornada`.

### Textos de veredicto (ejemplos)

| Condición | Copy |
|-----------|------|
| human > gpt + 2 | 🔥 Has destrozado a GPT |
| human > gpt | ✅ Le has ganado a GPT |
| human == gpt | 🤝 Empate técnico con GPT |
| human < gpt - 2 | 😤 GPT te ha pasado por encima |
| human < gpt | 🤖 GPT te ha ganado esta vez |
| human > all AIs | 🧠 Cerebro de silicio |

## Analytics mínimos (eventos)

```
landing_view
cta_click
play_start
pick_made          { match_index }
quiniela_complete
quiniela_save
result_view
share_click        { channel }
share_success
return_visit
```

Plausible / Umami / PostHog valen. Sin embudo medido, no optimizas.

## Bugs a cerrar en el repo (del audit)

- [ ] `data-page-action="NEWS"` sin vista → panel modal o `/noticias`
- [ ] Manifest `short_name`: «La Maestros» → «Maestros» o «Liga Maestros»
- [ ] Fechas hardcodeadas en JS → config/backend
- [ ] Onboarding duplicado (`onboarding.js` + `quantum_final.js`) → un solo sistema

## URLs canónicas sugeridas

```
/                     → landing HTML
/app                  → SPA actual
/jornada/:n           → resultados públicos (SEO)
/maestro/gpt          → ficha del modelo
/ranking              → clasificación
/como-funciona
```

## Dominio

Unificar:
- Canonical + OG + README + Search Console → un solo host
- Redirect de `alwaysdata` / Render preview al definitivo

## Copy de portada (sustituir)

**Antes:** «Temporada oficial. 15 partidos por jornada…»

**Después:**
```
¿Eres más listo que la IA?
Predice los 15 partidos. Enfréntate a GPT, Claude, Gemini y Grok.
[ Entrar en la quiniela ]
```
