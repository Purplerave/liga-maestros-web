# Roadmap Liga de Maestros

Actualizado: 2026-07-17

## Objetivo

Llegar al inicio de la temporada 2026/27 con una beta publica estable, facil de
actualizar cada semana y capaz de conservar todo el historico de la competicion.
La prioridad es fiabilidad primero, claridad visual despues y nuevas funciones
solo cuando aporten una razon real para volver.

## Estado actual

### Arquitectura y seguridad

- [x] Backend Flask organizado con Blueprints y servicios independientes.
- [x] JavaScript principal dividido en modulos: estado, navegacion, arena,
  directo, clasificaciones, concurso, logos, eventos y utilidades.
- [x] `quantum_final.js` reducido a inicializacion y flujos compartidos.
- [x] Claves y configuracion sensible fuera del codigo.
- [x] Cookies endurecidas y endpoints administrativos protegidos.
- [x] Rate limiting en guardado de quinielas, juegos y acciones sensibles.
- [x] SQLite configurado con WAL, `busy_timeout` y transacciones explicitas.
- [x] CI con tests, compilacion y auditoria de dependencias bloqueante.
- [x] Despliegue beta en Alwaysdata con datos persistentes separados de releases.
- [x] Arranque sobre disco vacio con esquema completo y semilla publica sin datos privados.
- [x] Backups SQLite automaticos, rotativos y verificados con `integrity_check`.
- [x] Privacidad, cookies, aviso legal y eliminacion transaccional de cuenta.
- [x] Auditoria de seguridad: CSP, CSRF, hosts confiables, limites de peticion,
  minimizacion de datos, IDs publicos opacos y telemetria administrativa privada.
- [x] Dependencias sin vulnerabilidades conocidas segun `pip-audit`.
- [x] Historial Git saneado para retirar la antigua base SQLite versionada.
- [x] Procedimiento de respuesta a incidentes documentado en `SECURITY.md`.

### Producto

- [x] Portada competitiva con estado del usuario y pulso de la jornada.
- [x] Vista Quiniela compacta con partidos, Maestros, Pena y usuario.
- [x] Quiniela de escritorio reducida de 64 a 48 px por fila: 12 partidos
  visibles en 1280x720 sin eliminar informacion.
- [x] Perfil personal, clasificaciones general/mensual y palmares.
- [x] Clasificaciones de Primera y Segunda.
- [x] Vista de directo multiliga y estado de salud del collector.
- [x] Contrato canonico inicial para equipos, alias y escudos.
- [x] Juegos integrados con rankings: Snake Gol, Arkanoid y Maestros Invaders.
- [x] J73 detectada y preparada para importacion.

## Prioridad 0: beta fiable

Estas tareas deben quedar terminadas antes de considerar la web lista para la
temporada.

### Directo y datos

- [ ] Crear tests de integracion para el collector live y sus cambios de estado:
  programado, directo, descanso, suspendido y finalizado.
- [ ] Crear fixtures de proveedores para probar resultados sin gastar API.
- [ ] Probar scrapers de Quiniela15 y calendarios ante cambios de HTML.
- [ ] Evitar duplicados de partidos entre proveedores mediante el contrato
  canonico de equipos y competiciones.
- [ ] Registrar errores estructurados del collector y mostrar una alerta
  administrativa cuando deje de actualizar.
- [ ] Mantener las llamadas API completamente separadas de las visitas y
  recargas de usuarios.

### Historico reproducible

- [ ] Guardar un snapshot cerrado de cada jornada con partidos, horarios,
  pronosticos, quinielas, resultados y clasificaciones.
- [ ] Poder recalcular puntuaciones y rankings desde snapshots sin depender del
  estado actual de la base de datos.
- [x] Crear copia automatica y rotativa de SQLite cada seis horas.
- [ ] Marcar automaticamente backups de apertura y cierre de cada jornada.
- [ ] Anadir una comprobacion semanal unica que valide los 15 partidos, horarios,
  participantes, logos, cierre y presupuesto API.

### J73 y operacion semanal

- [ ] Importar J73 cuando sus equipos y horarios sean definitivos.
- [ ] Cargar Programa, Maestros, Pena y quiniela del usuario sin mezclar roles.
- [ ] Documentar un unico comando de preparacion y otro de auditoria final.
- [ ] Confirmar el procedimiento de importacion en Render sin subir SQLite a Git.

## Prioridad 1: experiencia terminada

### Interfaz

- [ ] Revisar visualmente todas las vistas a 1280x720, 1920x1080 y movil.
- [ ] Eliminar los `min-width` heredados que impidan un responsive real.
- [ ] Mantener estable la cabecera al cambiar de seccion.
- [ ] Completar la separacion del CSS grande por componentes y paginas sin
  acumular nuevas capas de overrides.
- [ ] Revisar accesibilidad: foco visible, contraste, teclado y tamanos minimos.

### Perfil y retorno semanal

- [ ] Completar la evolucion por jornadas del usuario y la comparacion contra
  cada Maestro.
- [ ] Mostrar rachas que tengan significado: victorias de jornada, top 3 y
  mejores marcas; no medallas arbitrarias.
- [ ] Crear resumen post-jornada compartible con aciertos, posicion, Maestros
  superados y cambio respecto a la jornada anterior.
- [ ] Anadir historial navegable por jornada y mes sin listas interminables.
- [ ] Crear rankings semanales de los juegos y reinicio controlado por temporada.

## Prioridad 2: temporada 2026/27

- [ ] Crear ficha historica semanal por equipo: posicion, GF, GC, forma, local y
  visitante.
- [ ] Incorporar contexto confirmado de pretemporada: entrenador, altas, bajas,
  lesiones y minutos; separar siempre hechos de rumores.
- [ ] Guardar las probabilidades originales antes del partido para permitir
  backtests honestos sin fuga de informacion.
- [ ] Comparar Programa, mercado, Maestros y Pena con metricas acumuladas.
- [ ] Mejorar el modelo solo cuando un backtest reproducible demuestre ganancia.

## Funciones posteriores a la beta

- [ ] Duelos usuario contra Maestro o contra otro usuario.
- [ ] Ligas privadas de amigos.
- [ ] Nuevos juegos solo si tienen ranking, reglas claras y buena rejugabilidad.
- [ ] Notificaciones opcionales de incidencias o goles para administracion.

## Decisiones aplazadas

No se abordaran antes de estabilizar la beta:

- Migracion de SQLite a SQLAlchemy/Alembic.
- Celery y Redis para el collector.
- Sentry y servicios externos adicionales.
- Docker como requisito del desarrollo local.
- Noticias automaticas o contenido de relleno.
- Monetizacion, premium o apertura publica del repositorio.

Estas opciones se reevaluaran cuando la web tenga usuarios reales o la escala
demuestre que la solucion actual se queda corta.

## Criterio de beta lista

La beta se considera lista cuando:

1. Una jornada completa se importa, cierra, actualiza y puntua sin correcciones
   manuales.
2. Los resultados pueden recalcularse desde snapshots.
3. Existe backup restaurable de la base de datos.
4. Collector y scrapers tienen pruebas con datos simulados.
5. No hay errores de consola ni solapamientos en las vistas principales.
6. La actualizacion semanal se ejecuta con dos comandos documentados.
