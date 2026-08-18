# 🎙 Comentarista MiMo — frases breves del directo

El ticker de la portada (la banda fina que va pasando `⚽ EN DIRECTO` con los
marcadores) ahora también puede intercalar **frases cortas de comentarista**
generadas por **Xiaomi MiMo** (token plan, modelo pro): *"Gol de Lewandowski
para el Barcelona"*, *"Le toca remontar al Betis"*, etc. Solo texto, entre los
resultados.

## Cómo funciona

1. En cada carga de la portada, el backend hace una **foto compacta** del
   directo: los partidos en juego (máx. 6) con equipo local, visitante, minuto,
   marcador y estado.
2. Con **una sola llamada** a MiMo se piden 1-3 frases de ≤16 palabras,
   validadas contra esa foto (no puede inventar partidos, jugadores ni
   marcadores).
3. Las frases se cuelgan del payload de `/api/liga/data` (campo
   `comentarista.comentarios`) y el frontend las pinta dentro del ticker con un
   punto dorado y la etiqueta `COMENTARISTA`. **Cero llamadas por visitante**:
   la generación es servidor-side y cacheada.

## Por qué no se comen los créditos

| Protección | Mecanismo |
|------------|-----------|
| Una llamada para todo el directo | Lote único, nunca 1 por partido ni por minuto |
| Disparo por cambio | Caché por firma del contenido (equipos+minuto+marcador). Si no cambió el marcador, 0 tokens |
| Cadencia mínima | `MIMO_COMENTARISTA_MIN_INTERVAL_SECONDS` (10 min por defecto) |
| Tope diario duro | `AI_DAILY_CALL_LIMIT` compartido (12 por defecto). Agotado, sirve lo último cacheado o nada |
| Salida pequeña | `max_tokens=160`, prompt corto, sin multi-turno ni tool-calls (MiMo cobra el contexto a precio completo en cada round-trip) |
| Sin repeticiones | Registro de frases ya emitidas (`MIMO_COMENTARISTA_EMITIDOS.json`) |

Con esto el gasto son unos pocos miles de tokens por jornada, no millones.

## Configuración

En `.env` (plantilla en `.env.example`):

```ini
AI_NEWS_ENABLED=1
MIMO_API_KEY=tu-clave-del-token-plan
MIMO_API_BASE=https://token-plan-ams.xiaomimimo.com/v1
MIMO_MODEL=mimo-v2.5-pro
MIMO_COMENTARISTA_MIN_INTERVAL_SECONDS=600
# Alias alternativo: MIMO_BASE_URL (mismo valor)
```

- `MIMO_API_BASE` / `MIMO_BASE_URL` (alias) admite los espejos `token-plan-ams` (Ámsterdam, recomendado en UE) | `token-plan-sgp` (Singapur) | `token-plan-cn` (China), sin el sufijo `/chat/completions`.
- `MIMO_MODEL`: `mimo-v2.5-pro` (2 créditos/token) o `mimo-v2.5`
  (1 crédito/token) según tu plan.
- Si no hay `MIMO_API_KEY` o se agota la cuota, la web sigue funcionando
  exactamente igual, solo sin frases.

El comentarista **prefiere MiMo** y usa Groq/Gemini solo como fallback. El
boletín de noticias (`boletin.py`) mantiene su orden habitual Groq → Gemini →
MiMo.

## Qué NO es

- No es narración minuto a minuto: el disparador es el **cambio de marcador o
  estado**, no el reloj.
- No sustituye al boletín de noticias: las novedades de prensa previas al
  partido (fichajes, bajas, alineaciones) siguen viniendo del radar RSS +
  `boletin.py`.
- No hay voz (TTS) por ahora; es solo texto, como se acordó.
