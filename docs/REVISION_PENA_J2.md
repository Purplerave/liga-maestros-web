# Revisión de La Peña — Jornada 2

Fecha de revisión: 19/08/2026.

## Resumen

Se recibieron nueve boletos de La Peña: Chipi (DeepSeek), Geli (Z.AI/GLM),
Pepe (Perplexity), Profe (Meta), Fortu (Mistral), Oráculo (Qwen), Sesudo
(Kimi), Luzia y ErnieBot (Baidu).

- Los nueve contienen exactamente 15 partidos.
- El orden coincide con el boleto J2 del repositorio.
- Todos los signos 1–14 son válidos (`1`, `X` o `2`).
- Los nueve Plenos al 15 son válidos (`0`, `1`, `2` o `M` por equipo).
- Los datos quedaron en `data/predicciones_J2.json` junto a los Maestros.
- `ensure_jornada_2()` los importa al arrancar.

No se inventaron boletos ausentes.

## Pendientes

| Participante | Motivo |
|---|---|
| Jimmy | No se recibió boleto. |
| Luna | No se recibió boleto. |
| Fistro | No se recibió boleto. |
| Sonia | Participante humana; rellena en la web o se añade cuando lo envíe. |
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

## Consenso provisional (9 votos)

Coincidencia total:

- 1: Athletic gana.
- 5: Barcelona gana.
- 6: Osasuna gana.
- 9: Las Palmas gana.
- 11: Eibar gana.
- 12: Castellón gana.

Mayorías claras:

- 2: `X` por 5–4.
- 3: `2` por 8–1.
- 7: `X` por 7–1–1.
- 8: `1` por 5–4.
- 10: `X` por 5–4.
- 13: `X` por 5–3–1.
- 14: `2` por 6–2–1.
- Pleno: `2-1` por 7 votos; Geli `1-1` y Fortu `2-0`.

Empate:

- 4, Getafe–Racing: `1` = 4, `X` = 4, `2` = 1.

Columna de consenso simple, deshaciendo el empate 4 a favor del local:

`1, X, 2, 1, 2, 1, X, 1, 2, X, 1, 1, X, 2, 2-1`

## Privacidad

Los boletos individuales de La Peña no se publican hasta el cierre
(sábado 22/08/2026 17:00). El consenso sí aparece en la portada.
