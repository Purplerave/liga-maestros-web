# Relevo — cold start de Directo

Fecha: 2026-09-12  ·  Autor: Codex

## Qué se cambió

- `/api/liga/data` devuelve `503` con `status: cold_start`, `code: COLD_START`,
  `Retry-After: 2` y `Cache-Control: no-store` cuando todavía no hay jornada o
  la jornada tiene menos de 15 partidos.
- `static/js/quantum_final.js` reintenta la carga inicial hasta tres veces,
  respetando `Retry-After` y limitando la espera a 5 segundos por intento.
- Se conserva el comportamiento existente de mantener los datos anteriores
  durante fallos de refrescos automáticos.

## Verificación

- `tests/test_cold_start_retry.py`: pasa.
- `tests/test_security_hardening.py`: pasa.
- `node --check static/js/quantum_final.js`: pasa.
- El conjunto frontend/producción ejecutado queda con un fallo preexistente en
  `tests/test_production_readiness.py::test_jornada_75_seed_imports_fixture_and_pronosticos`
  (`pred_count == 0`, esperado `>= 15`), ajeno a este cambio.

## Siguiente paso

Medir en despliegue el tiempo hasta el primer payload válido y confirmar que el
colector termina de poblar los 15 partidos antes del tercer intento.
