# ROADMAP — POST-CHISPA (lo que sigue)

Estado actual:
- Chispa aplicada: countdown vivo, VS animado, hero Opción A, logo pequeño, push hecho (branch arena/...) ✅
- Auditas revisadas: integral (5.1/10) + UI/UX remediada + chispa (portada viva) ✅
- Referencia viral verificada: Forecast 2026 + Manifold + The Scientist (2026-07-03) ✅

=== FASE 1 — ENTREGA DE HOY (ya hecho) ===
- [x] Countdown vivo (JS + CSS)
- [x] VS que pelea (animación)
- [x] Hero con datos reales (Opción A)
- [x] Logo jerarquía corregida
- [x] Push a branch

=== FASE 2 — GANCHO VIRAL (próximo sprint, 1-2 semanas) ===
Objetivo: que un usuario se quede, compare su resultado con la IA, y comparta.

P0 (impacto máximo, esfuerzo medio):
- [ ] Modo Probabilidad: usuario asigna % a 1/X/2 por partido (no solo 1X2 binario)
- [ ] Scoring Brier / log-score vs odds del mercado (como Forecast 2026)
- [ ] Leaderboard visual por jornada: AI vs Human Avg vs Tú vs Mercado = 0 (líneas, no tabla)
- [ ] Sección "Bold Call" / Contrarian: destacar el acierto arriesgado que nadie esperaba (ej: Qatar-Suiza en Forecast 2026)
- [ ] Apodo anónimo + grupo privado (como Forecast 2026 "private group")

P1 (refuerzo):
- [ ] Tarjeta de resultado compartible (imagen auto-generada: "Tú vs GPT-4o vs Claude")
- [ ] Framing de estudio (UCL/Trinity) con consentimiento y premio por participación (no dinero real)
- [ ] Botón "Ver cómo van las máquinas" con gráfico acumulativo

=== FASE 3 — ARQUITECTURA / LIMPIEZA (mes 2-3, no antes) ===
- [ ] Scoring por probabilidades integrado en DB (actualmente scoring.py es binario 1/0)
- [ ] Data validation / JSON Schema en data/ (audit integral QW-9)
- [ ] Health check + robots.txt + sitemap (ya parcial)
- [ ] MkDocs / docs multilingüe / LICENSE / CONTRIBUTING (cuando haya comunidad)
- [ ] PWA / Telegram bot / API pública (solo si la fase 2 tiene tracción)
- [ ] Arena IAs automatizada (Tier S) — solo cuando haya datos de usuarios

=== NO TOCAR (sin tracción) ===
- ❌ No rebuild CSS completo (ya remediado: @layer, 0 !important)
- ❌ No API pública sin usuarios
- ❌ No bot Telegram sin loop de predicción confirmada
- ❌ No multi-idioma sin comunidad internacional
- ❌ No MKDocs o ADRs antes de producto-mercado

=== REFERENCIA DEFINITIVA ===
Forecast 2026 (forecast2026.com / The Scientist 2026-07-03):
- Human avg: -1409 | AI: -659 | Market: 0
- Probabilidad asignada a 1X2 con scoring rule vs betting odds
- Líder anónimo (CopacabanaKickaboutFan) como narrativa
- Grupo privado + premio £100 x 10
- Framing académico (UCL + Trinity College Dublin)

=== PRÓXIMO MOVIMIENTO CONCRETO ===
1. Confirmar que el countdown/V funcionan en producción (despliegue / reinicio local)
2. Definir modo probabilidad: ¿por partido o global? (recomendado: por partido, suma 100%)
3. Calcular Brier score inicial con datos de jornada 75 (ya tienes rankings y predicciones)
4. Generar 1 imagen de resultado tipo "Jornada 75 — Tú 42pts vs GPT-4o -15 vs Claude -8" como prueba de concepto viral
5. Si funciona la imagen + el score, implementar grupo privado y bold call
