# Roadmap de ejecucion - Liga de Maestros

Regla de trabajo: implementar una sola etapa por PR. No mezclar etapas, no
reescribir modulos fuera de alcance y no fusionar PRs. Cada entrega debe incluir
pruebas ejecutadas, verificacion manual y los archivos modificados.

## Etapa 1 - Quiniela guardada y clara

- Corregir cualquier caso en que una quiniela guardada siga mostrando los tres
  controles de eleccion en lugar del signo guardado.
- Mantener sincronizados estado local, respuesta del servidor y renderizado.
- Mostrar error util si el guardado falla; no dejar estado visual ambiguo.
- Verificar guardado, recarga y cambio de pestaña.

## Etapa 2 - Cierre correcto de jornada

- Probar y corregir el cierre al inicio del primer partido con zona
  `Europe/Madrid`.
- Impedir cambios cuando el partido correspondiente ya haya comenzado.
- Definir e implementar el tratamiento de partido aplazado, suspendido o
  anulado antes de calcular puntuaciones.
- Añadir tests para los tres estados y para el limite de hora.

## Etapa 3 - Directo fiable y cuota API controlada

- Garantizar que abrir, recargar o navegar por la web no dispare llamadas extra
  al proveedor live.
- Crear fixtures para los estados programado, directo, descanso, finalizado y
  suspendido.
- Incorporar un control administrativo para pausar el collector sin romper la
  vista de Directo; mostrar un estado claro al usuario.
- Registrar errores operativos del collector para diagnostico administrativo.

## Etapa 4 - Estados vacios y lenguaje humano

- Crear estados utiles para: sin jornada activa, jornada cerrada, sin resultados,
  sin quiniela guardada y directo temporalmente pausado.
- Mostrar "Directo" solo en partidos que realmente se esten jugando; usar
  "Resultado" cuando hayan terminado y no mostrar accion de directo antes.
- Retirar tecnicismos, mensajes duplicados y datos sin contexto visible.

## Etapa 5 - Quiniela: discrepancia y motivos

- Pintar por partido una barra compacta 1/X/2 del consenso de La Pena usando el
  payload existente.
- Pintar una segunda barra compacta del consenso de Maestros IA si cabe sin
  saturar la fila.
- Anadir un control accesible para ver el motivo real de cada pronostico IA.
- No crear endpoints, llamadas API ni modificaciones de backend o base de datos.
- Verificar 100% de zoom, 1280x720, 1920x1080 y movil.

## Etapa 6 - Diseno estable y responsive

- Mantener la misma cabecera y dimensiones base en todas las secciones.
- Eliminar overflow horizontal, `min-width` heredados y botones cortados.
- Revisar Portada, Quiniela, Directo, Ligas, Snake, La Pena, Quiz y Perfil a
  1280x720, 1920x1080 y movil.
- Corregir foco, contraste, teclado y tamano minimo de controles interactivos.

## Etapa 7 - Portada que explica el reto

- Explicar de forma breve que La Pena, Mi Programa y los Maestros IA compiten
  jornada a jornada por el ranking de aciertos.
- Dar prioridad al acceso a Quiniela y al estado de la jornada.
- Eliminar enlaces, tarjetas y textos que repitan la navegacion principal.
- Mostrar solo datos reales: partido destacado, discrepancias y proximo partido
  cuando correspondan.

## Etapa 8 - Perfil, clasificacion y retorno

- Crear historico navegable por jornada y mes sin listas interminables.
- Comparar al usuario contra cada Maestro mediante aciertos por jornada y total.
- Mostrar rachas comprensibles: victorias de jornada, top 3 y mejor marca.
- No anadir medallas arbitrarias ni gamificacion sin significado.

## Etapa 9 - Cierre de jornada y contenido compartible

- Generar resumen post-jornada con aciertos, posicion, Maestros superados y
  variacion de ranking.
- Permitir compartirlo usando la integracion de comparticion ya existente.
- Crear una imagen compartible solo si se puede generar con datos reales y sin
  bloquear la pagina.

## Etapa 10 - Operacion semanal reproducible

- Guardar snapshot cerrado de cada jornada: partidos, horarios, pronosticos,
  resultados y clasificaciones.
- Poder recalcular puntuaciones desde snapshots.
- Marcar backups de apertura y cierre de jornada.
- Documentar un comando de preparacion y otro de auditoria final.
- Crear comprobacion unica de los 15 partidos, horarios, participantes, logos,
  cierre y presupuesto API antes de publicar la jornada.

## Fuera de alcance hasta nueva orden

- Migrar a PostgreSQL, SQLAlchemy/Alembic, Redis, Celery, Docker, Vite o
  TypeScript.
- Anadir juegos, ampliar Snake o Quiz, noticias automaticas o contenido de
  relleno.
- Crear ligas privadas, duelos avanzados, premium o monetizacion.
