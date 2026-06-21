# Roadmap Liga Maestros

## Auditorias externas 2026-06-20

Objetivo: aplicar solo lo que mejora fiabilidad o producto real, sin meter mas ruido visual.

Aplicado:
- [x] Quitar API key de Highlightly incrustada en `app.py`; ahora solo se lee desde `.env`.
- [x] Quitar fallback publico de `SECRET_KEY`; si falta, la app no arranca.
- [x] Endurecer cookies de sesion: `HttpOnly`, `SameSite=Lax` y `Secure` configurable.
- [x] Blindar `/api/live/refresh` y `/api/live/probe` para uso local/admin.
- [x] Crear `/api/live/health` para leer el estado del collector sin lanzar scrapers ni API.
- [x] Evitar que Highlightly arranque si no hay key o si esta desactivado.
- [x] Activar SQLite con `busy_timeout`, `foreign_keys`, `journal_mode=WAL` y `synchronous=NORMAL` para reducir bloqueos durante directos.
- [x] Reservar llamadas Highlightly antes de hacer la peticion, con bloqueo interno, para respetar mejor el limite diario.
- [x] Hacer que el collector no muera en silencio: captura errores del bucle principal y escribe `data/LIVE_COLLECTOR_HEALTH.json`.
- [x] Cerrar la quiniela antes del primer partido con margen configurable: `PREDICTION_CLOSE_MINUTES_BEFORE_KICKOFF` (por defecto 15).
- [x] Quitar fallback silencioso a Jornada 61 si no hay datos.
- [x] Hacer mas robusto el JSON de guardado de quiniela y comentarios.
- [x] Validar en servidor que cada quiniela tenga 15 signos y que el Pleno al 15 tenga formato Quiniela valido.
- [x] Hacer configurable el acceso admin por localhost con `ALLOW_LOCAL_ADMIN` para despliegues futuros.
- [x] La auditoria de la Pena ya valida dobles contra Programa/Consenso actual.
- [x] Resolver banderas locales de Austria e Iraq para J68.
- [x] Crear contrato canonico `/api/teams/canonical` y enviarlo tambien en `/api/liga/data`.
- [x] Empezar a consumir el contrato canonico de logos desde `quantum_final.js` antes de los mapas locales.
- [x] Anadir Radar de Sorpresas compacto en la vista Quiniela: senala 2-3 partidos con consenso debil, desacuerdo Programa/Consejo/usuario o mercado dividido.
- [x] Anadir reintentos con espera progresiva al scraper de Quiniela15 directo.
- [x] Hacer que `with get_db()` cierre realmente SQLite mediante `ClosingConnection`.
- [x] Guardar quiniela con transaccion explicita `BEGIN IMMEDIATE` + rollback si falla entre DELETE e INSERT.
- [x] Usar `team_contract.aliases` en el lookup frontend de escudos antes de los alias hardcodeados.
- [x] Anadir circuit breaker de Highlightly con cooldown configurable y exponerlo en `/api/live/health`.
- [x] Compactar la vista principal de Quiniela: 15 partidos visibles en 1920x860, Radar fuera de la home, comentarios colapsados, filas/chips mas finos y partido+marcador mas agrupados.
- [x] Simplificar navegacion superior: selector principal de vista + selector secundario contextual solo para Ligas, La Pena o Clasificaciones.
- [x] Quitar el boton Directo duplicado de la cabecera; Directo queda como vista principal y el probe manual no ocupa espacio visual.

No aplicado ahora:
- [ ] Reescribir `LIVE_COLLECTOR.py` como APScheduler/systemd: importante para despliegue real, no urgente en local.
- [ ] Pasar el presupuesto API de JSON + lock de proceso a lock/lease persistente en SQLite si se despliega con varios procesos.
- [ ] Eliminar definitivamente los mapas/alias duplicados de JS cuando el contrato canonico cubra todos los equipos historicos.
- [ ] Limpiar contrato DOM-JS-CSS: quitar referencias a nodos inexistentes y caminos de render muertos.
- [ ] Cache/materializacion de `build_contest_payload`: conviene hacerlo, pero requiere invalidacion clara para no mostrar rankings viejos.
- [ ] Render parcial de `renderArena`: mejora real, pero tocarlo ahora tiene riesgo alto de romper interaccion/foco.
- [ ] Revisar ranking historico para eliminar supuestos tipo "no se solapan" y hacerlo recalculable.
- [ ] Modularizar `static/js/quantum_final.js`: necesario a medio plazo, demasiado grande para tocar de golpe.
- [ ] Eliminar `min-width: 1116px` y rehacer responsive: pendiente, pero requiere mirar capturas y no romper la vista escritorio.
- [ ] Mover comentarios fuera del lateral fijo: buena idea, decidir con pantalla delante.
- [ ] Rematar UX de menus con pruebas de usuario real: ya hay base principal/secundaria, falta decidir nombres finales y si Directo merece vista propia o solo ticker.
- [ ] Resumen post-jornada compartible: idea fuerte de retencion.
- [ ] Duelo usuario vs IA/humano: idea fuerte, requiere persistencia.
- [ ] Rachas/logros reales: solo los que tengan sentido, no medallas tontas.

## Bloque de saneamiento 2026-06-10

Objetivo: reducir el caos semanal y separar bien Programa, Consejo IA, Maestros, La Pena y usuario.

Hecho:
- [x] Crear `data/ECOSISTEMA_PARTICIPANTES.json` como fuente de verdad de roles.
- [x] Corregir `data/PARTICIPANTES_MAESTROS.json`: Gemini vuelve a Maestros y Consejo IA queda separado.
- [x] Anadir columna visible para `consejo_ias`/`consenso` en la tabla.
- [x] Corregir puntuacion del Pleno al 15 para comparar por formato Quiniela (`M-0` equivale a `3-0`, `4-0`, etc.).
- [x] Corregir J67: Consejo IA y usuario tenian 14/15; faltaba el partido 14 y se completo con `X` segun consenso cargado.
- [x] Crear `AUDITAR_JORNADA_LIGA_MAESTROS.py`.
- [x] Crear `OPERACION_SEMANAL.md`.
- [x] Crear `COMPROBAR_JORNADA.bat`.
- [x] Generar auditorias `data/auditorias/J67_estado.md` y `data/auditorias/J66_estado.md`.

Estado actual:
- J67 queda sin bloqueos.
- J67 avisa que faltan quinielas individuales de Claude, Grok, ChatGPT, Copilot y Gemini. Esto es correcto si la jornada se juega como Programa + Consejo IA.
- J66 queda cerrada sin bloqueos; aparece un ID historico obsoleto (`manu`) que no debe mostrarse como maestro.

## Intervencion actual: Vista Quiniela con tension

Fecha: 2026-06-06

Backup antes de tocar:
`C:\Users\Mortadelo\Desktop\QUINIELAs\LIGA_MAESTROS\BACKUP_PRE_REDISENO_TENSION_20260606_133904`

Objetivo:
Convertir la vista principal de Quiniela en una pantalla compacta de lectura competitiva, no en una parrilla administrativa de columnas.

Direccion acordada:
- Mantener los 15 partidos visibles como prioridad.
- Cambiar la fila principal hacia el modelo:
  `# | Partido | Consenso + signos | Resultado`
- Mostrar el partido de carrerilla: local - visitante, con hora o marcador.
- Anadir barra compacta de consenso 1/X/2 cuando existan porcentajes.
- Mostrar chips compactos para Programa, Maestro destacado, Pena y Tu.
- Reducir o esconder la parrilla completa de Maestros en la home; el detalle debe ir al desplegable/fila expandida.
- Marcar solo los focos importantes de la jornada:
  - Fijo
  - Partido abierto
  - Empate oculto
  - Golpe del programa
  - Trampa del consenso
  - Pleno caliente
- Evitar nuevas llamadas API. Esto es solo presentacion usando datos ya cargados.

No hacer en este bloque:
- No reescribir backend.
- No tocar scheduler/API live.
- No crear menus nuevos grandes.
- No meter noticias ni texto editorial largo.
- No mezclar Pena con Maestros ni simular usuarios sin marcarlo.

Plan tecnico:
- Revisar `templates/liga_index.html`, `static/js/quantum_final.js` y `static/css/quantum_pro.css`.
- Localizar `renderArena`, `renderMatchCard`/render de filas y datos de consenso.
- Implementar una primera version reversible de fila compacta.
- Probar que no rompe:
  - cambio de jornada
  - vista Quiniela
  - Directo basico
  - tabs/botones laterales
  - guardado de boleto si aplica
- Hacer captura final antes de darlo por bueno.

Estado: vivo  
Última actualización: 2026-05-26

## Ya resuelto

- Web principal operativa con jornada 64 y 65
- Refresco Highlightly estabilizado
- Modo `Directo` básico
- Peña separada de Maestros visibles
- Escudos con mapa fijo + fallback
- Jornada 65 cargada con partidos y horarios

## Prioridad alta

### 1. Identidad visual
- [x] Crear logo base de Liga Maestros
- [ ] Ajustar branding superior para que tenga más presencia
- [ ] Unificar icono/logo en topbar, capturas y posibles vistas futuras

### 2. Producto competitivo
- [ ] Clasificación mensual
- [ ] Ranking de jornada
- [ ] Perfil personal
  - [ ] posición actual
  - [ ] puntos totales
  - [ ] jornadas jugadas
  - [ ] aciertos
  - [ ] media por jornada
  - [ ] mejor posición
  - [ ] mejor jornada
- [ ] Evolución personal por jornadas

### 3. Palmarés
- [ ] Ganadores por jornada
- [ ] Ganadores por mes
- [ ] Veces líder
- [ ] Veces top 3
- [ ] Mejor racha top 3

### 4. Quiniela / motor
- [ ] Ejecutar `Programa` para J65
- [ ] Volcar columna del programa en la web
- [ ] Definir rutina híbrida para próxima temporada:
  - [ ] IAs visibles
  - [ ] peña oculta
  - [ ] programa
  - [ ] compendio final
- [ ] Crear capa de contexto 2026/27 para alimentar programa e IAs:
  - [ ] Altas y bajas confirmadas por equipo
  - [ ] Entrenador nuevo o continuidad
  - [ ] Salidas clave y lesionados de larga duracion
  - [ ] Minutos y resultados de pretemporada
  - [ ] Senales manuales: equipo salvado, rotaciones, plantilla en construccion
  - [ ] Fuentes candidatas: Marca mercado de fichajes, webs oficiales, LaLiga, prensa local
  - [ ] Rumores separados de confirmados, con baja confianza
  - [ ] Ficha compacta por equipo para prompts y motor

## Prioridad media

### 5. Vista Directo / War Room
- [ ] Solo visible cuando haya directos reales
- [ ] Lista limpia de partidos live multiliga
- [ ] Detectar mejor estados inconsistentes del proveedor
- [ ] Mostrar resultado final aunque el proveedor deje `SCHEDULED`

### 6. Arena principal
- [ ] Compactar más la topbar
- [ ] Afilar tabla principal
- [ ] Mejorar jerarquía de clasificación derecha
- [ ] Revisar espaciado de columnas en vistas de ligas

### 7. Datos estables
- [ ] Consolidar base fija de escudos
- [ ] Consolidar alias de equipos
- [ ] Separar mejor datos de competición, jornada y snapshots históricos

## Prioridad baja

### 8. Comunidad
- [ ] Menú/área de Peña aparte
- [ ] Historial de comentarios por jornada
- [ ] Foro ligero si de verdad aporta

### 9. Próxima temporada
- [ ] Guardado sistemático por jornada:
  - [ ] predicción de cada IA
  - [ ] predicción del programa
  - [ ] boleto final jugado
  - [ ] resultado real
  - [ ] ganador de jornada
  - [ ] ganador de mes
- [ ] Preparar soporte para jornadas mixtas con Mundial, amistosos o torneos cortos
- [ ] Preparar dossier de pretemporada antes de la J1:
  - [ ] Snapshot por equipo: plantilla, fichajes, bajas, entrenador, objetivo probable
  - [ ] Peso manual de contexto: muy positivo / positivo / neutro / alerta / riesgo
  - [ ] Archivo historico para comparar lo previsto con lo que realmente pasa

## Decisiones ya tomadas

- No meter medallas raras tipo `rey del empate`
- Sí apostar por prestigio simple:
  - ganador de jornada
  - líder mensual
  - top 3
  - rachas reales
  - récords personales
- No llenar la home de bloques con texto inútil
- Si algo no aporta de un vistazo, fuera
