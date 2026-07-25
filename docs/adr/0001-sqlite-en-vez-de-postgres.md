# ADR-0001: SQLite en vez de PostgreSQL

## Estado: Aceptado

## Contexto

Liga de Maestros necesita persistencia para predicciones, resultados, rankings y usuarios.
El despliegue actual es un solo worker en Alwaysdata/Render con plan gratuito/barato.

## Decisión

Usar SQLite con WAL mode, busy_timeout y backups rotativos verificados.

## Consecuencias

- **Positivo**: Sin dependencia externa, cero configuración, backups simples (copia de archivo), rendimiento suficiente para <1000 usuarios concurrentes.
- **Negativo**: Escalabilidad limitada a 1 worker (write lock), sin conexión concurrente de múltiples procesos.
- **Mitigación**: Si se necesitan 2+ workers, migrar a Postgres abstracto tras un repositorio de datos (`repositories/`). Actualmente documentado como restricción explícita.
