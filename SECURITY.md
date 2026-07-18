# Seguridad de Liga de Maestros

Ultima revision: 2026-07-17

## Datos protegidos

La aplicacion conserva el identificador interno de Google, el nombre visible,
quinielas, comentarios y puntuaciones de juegos. El correo recibido durante el
login se usa solo para decidir permisos administrativos y no se almacena. Las
claves OAuth y de proveedores deportivos viven exclusivamente en variables de
entorno del servidor.

## Modelo de amenazas

La revision cubre:

- visitante anonimo que intenta leer datos privados o usar endpoints de escritura;
- usuario autenticado que intenta modificar datos de otra cuenta;
- paginas externas que intentan enviar peticiones con la sesion del usuario;
- contenido remoto malicioso en feeds de noticias;
- abuso de endpoints, cuerpos excesivos y consumo del presupuesto de APIs;
- filtracion accidental de bases, `.env`, claves o identificadores mediante Git;
- robo o reutilizacion de cookies y cache compartida;
- perdida o corrupcion de SQLite y sus copias de seguridad.

No existe una promesa realista de riesgo cero. Una cuenta comprometida de
Alwaysdata, GitHub, Google o del propio usuario queda fuera del aislamiento que
puede ofrecer Flask y exige rotar credenciales.

## Controles activos

- OAuth de Google con `state` gestionado por Authlib y sesion regenerada al entrar.
- Cookies `HttpOnly`, `Secure` en produccion, `SameSite=Lax` y caducidad de 12 horas.
- Token CSRF ligado a sesion para escrituras autenticadas.
- Autorizacion por propietario en quinielas, comentarios, porra, quiz y juegos.
- Endpoints administrativos separados y comprobados en servidor.
- Identificadores de proveedor sustituidos por codigos publicos opacos estables.
- Correo eliminado de la base activa y de las copias retenidas.
- CSP, bloqueo de framing, `nosniff`, politica de permisos, HSTS y respuestas
  autenticadas con `Cache-Control: no-store`.
- Limite global de 64 KiB por peticion y limites especificos de frecuencia.
- Hosts aceptados restringidos a produccion y desarrollo local.
- XML remoto procesado con `defusedxml` y enlaces limitados a HTTP(S).
- SQLite fuera de las versiones inmutables, permisos `0600`, WAL, backups
  rotativos y `integrity_check`.
- CI bloqueante para tests, dependencias vulnerables y material sensible rastreado.
- Repositorio privado, permisos de Actions en solo lectura, acciones permitidas
  restringidas y cada dependencia de CI fijada a un commit oficial verificado.
- Alertas y correcciones automaticas de Dependabot activadas.

## Hallazgos corregidos en julio de 2026

1. Se actualizaron Flask, Authlib, Requests y python-dotenv para eliminar las
   vulnerabilidades conocidas detectadas por `pip-audit`.
2. Se retiraron de respuestas publicas los IDs largos de Google y la telemetria
   interna de cuotas/circuitos de proveedores.
3. Se dejo de almacenar el correo y se limpiaron base activa y backups.
4. Se incorporaron CSP, limites de peticion, hosts confiables y cache privada.
5. Se sustituyo el parser XML estandar en feeds externos.
6. Se anadieron pruebas de regresion sobre IDOR, CSRF, headers, limites,
   minimizacion de datos y exposicion de endpoints.
7. Se elimino del historial publico de Git la base que habia sido versionada.
8. Se reescribieron las ramas, se fijaron las Actions por SHA y se restringio la
   cadena de suministro del despliegue. El 18 de julio de 2026 se solicito a
   GitHub Support la purga de referencias internas de la PR #1 mediante el
   ticket #4581722; permanece pendiente hasta que GitHub confirme el borrado.

## Operacion segura

- No copiar nunca secretos en codigo, incidencias, capturas, chats o commits.
- Rotar cualquier clave que se haya compartido fuera del gestor de secretos.
- Mantener activado 2FA en Google, GitHub y Alwaysdata.
- Revisar `pip-audit -r requirements.txt` y `python -m pytest -q` antes de publicar.
- Conservar una copia verificada antes de cada migracion o jornada importante.
- No servir SQLite, `.env`, logs ni backups desde la carpeta publica.

## Respuesta ante incidentes

1. Pausar collector y escrituras si hay actividad anomala.
2. Rotar `SECRET_KEY` para invalidar todas las sesiones.
3. Rotar secreto OAuth, tokens de APIs y credencial de despliegue afectada.
4. Guardar logs y una copia de la base para investigar sin modificar evidencia.
5. Restaurar el ultimo backup con `integrity_check` correcto si hubo corrupcion.
6. Informar a usuarios afectados si se confirma acceso no autorizado.

## Riesgos residuales

- El rate limiting de aplicacion reduce abuso, pero no sustituye proteccion DDoS
  del proveedor.
- Nombre visible y actividad competitiva son publicos por diseno; correo e ID del
  proveedor no lo son.
- Los juegos aplican validacion heuristica, no un sistema anti-trampas infalible.
- Las paginas legales requieren los datos reales del responsable antes del
  lanzamiento oficial; no deben quedar campos `Pendiente de configurar`.
- GitHub puede conservar temporalmente objetos antiguos tras reescribir el
  historial. La base retirada no esta en ramas ni tags y el repositorio es
  privado. El objeto antiguo continua accesible por SHA mientras GitHub procesa
  el ticket #4581722 para retirar la referencia interna y sus vistas en cache.
- GitHub no permite activar reglas de proteccion de rama en este repositorio
  privado personal sin un plan compatible; CI y despliegue siguen siendo
  obligatorios, pero el propietario conserva capacidad de `force-push`.
