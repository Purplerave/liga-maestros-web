# Revisión de La Peña — Jornada 2

Fecha de revisión: 19/08/2026 (Sonia y Sonia2 añadidas el 22/08/2026).

## Resumen

Se recibieron doce boletos de La Peña: Chipi (DeepSeek), Geli (Z.AI/GLM),
Pepe (Perplexity), Profe (Meta), Fortu (Mistral), Oráculo (Qwen), Sesudo
(Kimi), Luzia, ErnieBot (Baidu), Jimmy (ChatJimmy) y las dos columnas de
Sonia (`sonia` y `sonia2`).

- Los doce contienen exactamente 15 partidos.
- El orden coincide con el boleto J2 del repositorio.
- Los signos 1–14 quedan en `1`, `X` o `2` tras normalizar a Jimmy.
- Los doce Plenos al 15 son válidos (`0`, `1`, `2` o `M` por equipo).
- Los datos quedaron en `data/predicciones_J2.json` junto a los Maestros.
- `ensure_jornada_2()` los importa al arrancar.

No se inventaron boletos ausentes.

## Pendientes

| Participante | Motivo |
|---|---|
| Luna | No se recibió boleto. |
| Fistro | No se recibió boleto. |
| MrPurple | Usuario humano; rellena su quiniela en la web. |

## Signos normalizados

| Peña | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | Pleno |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Chipi | 1 | X | 2 | 1 | 2 | 1 | X | 1 | 2 | X | 1 | 1 | 1 | 2 | 2-1 |
| Geli | 1 | 1 | 2 | X | 2 | 1 | X | X | 2 | X | 1 | 1 | X | 1 | 1-1 |
| Pepe | 1 | 1 | X | 1 | 2 | 1 | X | X | 2 | 2 | 1 | 1 | X | X | 2-1 |
| Profe | 1 | X | 2 | X | 2 | 1 | 2 | 1 | 2 | 2 | 1 | 1 | 1 | X | 2-1 |
| Fortu | 1 | 1 | 2 | 2 | 2 | 1 | X | X | 2 | 2 | 1 | 1 | 2 | 2 | 2-0 |
| Oráculo | 1 | X | 2 | 1 | 2 | 1 | X | 1 | 2 | X | 1 | 1 | 1 | 2 | 2-1 |
| Sesudo | 1 | X | 2 | X | 2 | 1 | X | 1 | 2 | X | 1 | 1 | X | 2 | 2-1 |
| Luzia | 1 | 1 | 2 | X | 2 | 1 | 1 | X | 2 | 2 | 1 | 1 | X | 2 | 2-1 |
| ErnieBot | 1 | X | 2 | 1 | 2 | 1 | X | 1 | 2 | X | 1 | 1 | X | 2 | 2-1 |
| Jimmy | 2 | X | 1 | 2 | 2 | 2 | 1 | X | 1 | 1 | X | 1 | X | 2 | M-0 |
| Sonia | 1 | 2 | 1 | 1 | 2 | X | 2 | X | 2 | X | 1 | X | 1 | 1 | 2-1 |
| Sonia2 | 1 | 2 | 1 | 1 | 2 | 1 | 2 | 2 | 2 | X | 1 | 1 | 1 | 1 | 2-1 |

## Incidencias de Jimmy

Misma política que en J1: se guarda el boleto y se normalizan los signos
inválidos para que el importador no lo descarte.

1. Partidos 8, 11 y 13 llegaron como `0`. En quiniela eso no es `1`, `X` ni
   `2`. Se pasaron a `X`.
2. El Pleno llegó como `M`. Faltaba el marcador visitante. Se guardó `M-0`
   (Atlético 3 o más; no se inventó un gol del Villarreal).
3. Varios nombres de rival no coinciden con el boleto oficial (Osasuna–Leganés,
   Eibar–Villarreal, «El curso»). Se respetó el orden 1–15.
4. Varias explicaciones contradicen el signo. Se conservó el signo aportado.

## Consenso provisional (12 votos)

Coincidencia total:

- 5: Barcelona gana.
- 12: Castellón gana (11 de 12, con Sonia marcando X).

Mayorías claras:

- 1: `1` por 11–1.
- 2: `X` por 6–4–2.
- 3: `2` por 8–3–1.
- 4: `1` por 6–4–2.
- 6: `1` por 10–1–1.
- 7: `X` por 7–3–2.
- 8: `X` por 6–5–1.
- 9: `2` por 11–1.
- 10: `X` por 7–4–1.
- 11: `1` por 11–1.
- 13: `X` por 6–5–1.
- 14: `2` por 7–3–2.
- Pleno: `2-1` por 9 votos; Geli `1-1`, Fortu `2-0` y Jimmy `M-0`.

Columna de consenso simple:

`1, X, 2, 1, 2, 1, X, X, 2, X, 1, 1, X, 2, 2-1`

## Privacidad

Los boletos individuales de La Peña no se publican hasta el cierre
(sábado 22/08/2026 17:00). El consenso sí aparece en la portada.
