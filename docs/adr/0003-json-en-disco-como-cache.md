# ADR-0003: JSON en disco como cache de live

## Estado: Aceptado

## Contexto

El directo necesita datos frescos de Highlightly API. El collector interno actualiza periódicamente.

## Decisión

Usar JSON en disco (`DATA_DIR/`) como cache entre el collector y la API pública. Escritura con lock de archivo (`write_json_locked`), lectura con `safe_read_json`.

## Consecuencias

- **Positivo**: Sin dependencia de Redis/Memcached, persiste entre reinicios, debugging trivial (JSON legible).
- **Negativo**: I/O síncrono en hot path, write lock a nivel de archivo (no funciona con 2+ workers), potencial stale data si el collector falla.
- **Mitigación**: Cache en memoria con invalidación por `mtime` para requests frecuentes. Si se escalan workers, mover estado live a SQLite o Redis.
