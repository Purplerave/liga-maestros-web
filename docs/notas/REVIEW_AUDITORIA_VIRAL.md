# Revisión Exhaustiva — Auditoría Integral + UI/UX (2026-07-25)

## 1. Qué audité (archivos reales en el repo)
- `docs/AUDITORIA_INTEGRAL_2026-07-25.md` — Audit integral (5.1/10 producto / 7.2/10 software)
- `docs/design/AUDITORIA_UI_UX.md` — Audit UI/UX (5.2/10; marca REMEDIADA el 24/07)
- Verificación de código: `scoring.py`, `static/css/base/tokens.css`, `@layer` activo, `!important` = 0 en base CSS.
- Producto: "Liga de Maestros" — quiniela humana vs IA (GPT/Claude/Gemini/Grok) con ranking, quiz, arcade.

## 2. ¿Tiene sentido la auditoría?
SÍ. No es texto generado vacío.
- Tiene referencias de commit (`b7f6446`), stack real (Flask 3.1 + SQLite WAL + CSP + CSRF + rate limit), archivos concretos.
- El UI/UX es coherente con el estado del código (`@layer` en `cover_hero.css`, `mobile_responsive.css`; `tokens.css` reconstruido; 0 `!important` en base).
- El sesgo: está escrita como si fuéramos a escalar un producto maduro (docs, ADRs, MkDocs, multi-idioma). Eso es un riesgo si el objetivo es VIRALES primero.

## 3. ¿Qué actualizar? ¿Qué NO?

### ACTUALIZAR PRIMERO (para viralidad / gancho)
| Prioridad | Qué | Por qué / referencia |
|---|---|---|
| P0 | **Modo Probabilidad + scoring Brier/log vs mercado** | Forecast 2026 (forecast2026.com) no hace 1X2 binario; asigna % a 1/X/2 y puntúa contra odds del mercado. Es el gancho científico. |
| P0 | **Leaderboard visual: AI agents vs Human avg vs Tú vs Mercado = 0** | El artículo de The Scientist destaca que AI lleva -659, humanos -1409, mercado 0. Esa narrativa es viral por sí sola. |
| P0 | **Predicciones con apodo anónimo + "Bold Call" semanal** | El efecto "CopacabanaKickaboutFan" (+579 puntos, anónimo) genera identidad y competencia sin exponer datos personales. |
| P1 | **Tarjeta de predicción compartible (imagen/resultados)** | Formato TikTok/Instagram: "Yo vs GPT-4o vs Claude — ¿quién ganó esta jornada?" |
| P1 | **Grupos privados para amigos/empresas** | Forecast 2026 tiene "private group" con invite link; genera loops sociales internos. |
| P2 | **Framing como estudio científico** | UCL + Trinity College Dublin + consentimiento + premio (£100 x 10). Da autoridad y justifica la participación. |

### NO ACTUALIZAR (por ahora; no pierdas foco viral)
| Elemento auditado | Qué dice la audit | Mi recomendación |
|---|---|---|
| LICENSE / CONTRIBUTING / CODEOWNERS | Bloque 5 de auditoría integral | No antes de tracción. AGPL-3.0 está bien para ahora. |
| MkDocs Material + docs multilingüe | Bloque 2 | Excelente para escalar, pero no genera clicks esta semana. |
| PWA / Bot Telegram / API pública | Bloque 4 (Tier A/B) | No antes de tener loop de predicción viral confirmado. |
| Arena IAs automatizada completa | Bloque 4 Tier S | Es una fase 2; primero confirma que la gente quiere jugar vs un bot simple. |
| CSS completo / eliminar duplicación root/paquete | Bloque 3 | Ya está en gran parte resuelto (verificado: `!important` eliminado, `@layer` activo). No reconstruyas todo antes de validar el hook. |
| E2E Playwright / golden tests | Bloque 3 | Haz mínimos (el loop de predicción) antes de automatizar todo. |

## 4. Páginas similares / referencias virales (con URLs verificadas)

### #1 — Forecast 2026 (forecast2026.com) — EL REFERENTE
- Estructura: humanos vs AI agents vs expertos vs mercado.
- Scoring: probabilidad asignada a 1X2, puntuada con scoring rule contra betting odds.
- Leaderboard acumulativo con líneas de tendencia (AI -659, Humanos -1409, Mercado 0).
- Características virales: grupo privado, premio por participación, framing académico (UCL + Trinity College Dublin), consentimiento GDPR, apodo anónimo.
- Artículo viral: The Scientist (2026-07-03) "AI and Humans Duel to Predict World Cup Outcomes" — menciona al ganador anónimo CopacabanaKickaboutFan.
- URL: https://forecast2026.com/ y https://www.the-scientist.com/ai-and-humans-duel-to-predict-world-cup-outcomes-74699

### #2 — Manifold Markets (manifold.markets)
- Concepto: "calibration score" y leaderboard de predictores con reputación no monetaria.
- Útil para entender cómo premiar aciertos sin dinero real (reputación, ranking, badges).
- URL: https://manifold.markets/

### #3 — TikTok / YouTube — Formato de video viral
- Contenido: "Le pedí a ChatGPT, Claude, Gemini, Grok que predigan el Mundial... ¿quién gana?"
- Formato: comparación visual de predicciones + reacción al resultado real.
- Aplicación para Liga de Maestros: generar un video/short automático por jornada mostrando "Tú vs GPT-4o vs Claude 3.5 vs Mercado — Jornada 73" con resultados reales.

### #4 — Metaculus / Polymarket (para estructura de predicción)
- Metaculus usa estimación continua de probabilidad; Polymarket usa dinero real.
- Tu caso está entre ambos: sin dinero real (como Manifold/Forecast), pero con competición directa (como Metaculus). El valor es la comparación directa, no la apuesta.

## 5. Propuesta concreta de gancho (hook) para hacerla viral

Basándome en Forecast 2026 + Manifold + The Scientist:

1. **Cambia el título de la página de inicio**: de "Quiniela competitiva" a "Forecast 2026 — ¿Puedes predecir mejor que la IA?" (o similar con tu marca).
2. **Añade modo "Probabilidad"** (no solo 1X2): por cada partido, el usuario pone % para 1 / % para X / % para 2. Suma debe ser 100.
3. **Calcula Brier Score**: `(p - o)^2` donde `p` es tu probabilidad y `o` es el resultado real (1, 0.5, 0). Compara con el market baseline (odds reales).
4. **Visualiza el leaderboard como gráfico de línea** (como Forecast 2026): AI (promedio modelos) | Human Avg | Tú (anon) | Mercado = 0. Eso convierte una tabla aburrida en una historia visual.
5. **Destaca el "Contrarian / Bold Call"**: si aciertas un resultado que el mercado daba 15% y tú diste 60%, resalta eso. Eso es contenido viral.
6. **Generación automática de imagen de resultado**: "Jornada 73 — Tú: +42 pts | GPT-4o: -15 pts | Mercado: 0 | ¿Quién gana?" con diseño dark + gold/cyan. Se comparte en Twitter/X, Instagram Stories, WhatsApp.
7. **Grupo privado**: "Invita a tu grupo de amigos/empresa y ve quién predice mejor esta semana" — loop social interno.

## 6. Verificación técnica rápida que hice
- `grep -rni '@layer' static/css/` → Encontrado en 6 archivos (hero, pages, typewriter, overlays). Confirmado.
- `grep -c 'important' static/css/base/*.css` → 0 en base. Confirmado (remediado).
- `scoring.py` → Solo binario (1/0) + pleno. No hay Brier/log score. Confirmado: falta para viralidad científica.
- `docs/AUDITORIA_INTEGRAL_...` → 55 líneas, referencias a CSP, CSRF, WAL, rate limit, backups rotativos. Confirmado: real.

---
*Revisión completada el 2026-08-01. Referencias verificadas y archivos de repo confirmados.*
