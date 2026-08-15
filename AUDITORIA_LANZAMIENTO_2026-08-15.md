# Auditoría de lanzamiento — Liga de Maestros

**Fecha:** 15 de agosto de 2026
**Commit base:** `531de89`
**Método:** ejecución real del proyecto (no lectura de código). Se levantó la app con Gunicorn en modo producción, se probaron las 59 rutas, se ejecutaron los tests, el linter, el type checker, la auditoría de dependencias, una prueba de carga y sondas de seguridad.

---

> ## ✅ ACTUALIZACIÓN — arreglos aplicados el mismo día
>
> Tras la auditoría se corrigieron los hallazgos que no dependen de datos
> personales ni de claves privadas. **Estado actual: 93 % lista.**
>
> | # | Hallazgo | Estado |
> |---|---|---|
> | 1 | Jornada incoherente (J1 vs J76) | ✅ **Resuelto** — `resolve_jornada()` delega en `resolve_active_jornada()`. Verificado: los 3 endpoints dicen J1 y el collector ya solo refresca `2026-08-15`. + 4 tests de regresión. |
> | 2 | Privacidad con "No configurado" | ✅ **Blindado** — en producción la app **se niega a arrancar** sin `LEGAL_OWNER_NAME` y `LEGAL_CONTACT_EMAIL`. Faltan los valores reales (solo los sabe el responsable). |
> | 3 | Secretos sin poner | ⏳ **Tuyo** — requiere claves privadas. |
> | 4 | J1 sin quiz | ⏳ **Tuyo** — requiere redactar preguntas. La UI ya degrada bien ("Reto 10 no disponible"). |
> | 5 | Motor fantasma | ✅ **Resuelto** — nuevo `motor_available()`; `/api/ai/status` informa `available:false, reason:"motor_no_instalado"` y desaparece el WARNING por petición. |
> | 6 | Predicciones IA visibles | ⏳ **Decisión de producto** — documentado; ahora hay test que fija el comportamiento en ambos estados. |
> | 7 | Escudos hotlinkeados | ✅ **De 25 a 3** — 21 reapuntados a ficheros que ya estaban en disco, 5 huecos rellenados, 2 alias nuevos. Script `tools/ops/DESCARGAR_ESCUDOS_EXTERNOS.py` + 4 tests. |
> | 8 | JSON versionados que mutan | ⚠️ **Documentado** — solo un `updated_at`. Separar semilla de caché toca dónde viven BD y cachés en producción; no se hace en caliente. |
> | 11 | Sin `<noscript>` ni skip-link | ✅ **Resuelto** — ambos añadidos respetando la gobernanza `@layer` (0 `!important`). |
>
> **Bug extra encontrado al arreglar:** `test_j1_boletos.py` fallaba desde las
> 16:45 de cada día — dependía de la hora real, y tras el cierre `reveal_all`
> destapa todas las columnas. Ahora congela el reloj y prueba **los dos**
> estados (abierto y cerrado), más una comprobación nueva de que jamás se filtra
> un ID de cuenta de Google.
>
> **Verificación:** 225 tests en verde (antes 216 + 1 roto), ruff/format/mypy
> limpios, 0 vulnerabilidades, 200 peticiones concurrentes sin fallos y algo más
> rápido que antes (p50 670 → 480 ms).
>
> **Lo único que queda para abrir es tuyo:** rellenar el `.env` (datos legales,
> `SECRET_KEY`, OAuth de Google, clave de Highlightly, `ADMIN_EMAILS`).

---

## VEREDICTO ORIGINAL: **82 % lista**

La aplicación es sólida y está muy por encima de la media de un proyecto personal: arranca limpia, no tiene un solo test rojo, cero vulnerabilidades en dependencias, cabeceras de seguridad bien puestas y un rendimiento excelente. **Pero hay 3 cosas que hay que arreglar sí o sí antes de abrir la puerta a la gente**, y una de ellas rompe el directo el día del estreno.

| Bloque | % listo | Estado |
|---|---|---|
| Infraestructura y arranque | 95 % | Excelente |
| Seguridad | 92 % | Excelente |
| Rendimiento | 90 % | Excelente |
| Calidad de código y tests | 88 % | Muy bueno |
| Datos y lógica de negocio | **55 %** | **Bloqueante** |
| Legal (RGPD) | **40 %** | **Bloqueante** |
| SEO / compartir | 80 % | Bueno |
| Contenido de lanzamiento | 60 % | Mejorable |
| Observabilidad y operación | 85 % | Muy bueno |
| Accesibilidad | 75 % | Mejorable |

---

## 🔴 BLOQUEANTES — sin esto no se abre

### 1. La web dice J1, pero el directo persigue la J76 *(el más grave)*

Hay **dos funciones distintas** que deciden "cuál es la jornada actual", y devuelven cosas diferentes:

```
resolve_active_jornada()  → 1    ← lo que ve el usuario, el guardado, el ranking
resolve_jornada()         → 76   ← el directo, el collector, /health, /sync/status
```

Comprobado en caliente:

```
/api/liga/data    → "jornada": 1
/api/live/health  → "jornada_activa": 76
/api/sync/status  → "jornada": 76, "pending_matches": 2
```

`resolve_jornada()` (en `services/highlightly.py:57`) hace simplemente `SELECT MAX(jornada) FROM resultados`, y la BD todavía guarda la J76 del periodo de pruebas.

**Qué pasa el sábado a las 19:30:** el usuario firma su quiniela de la J1, empiezan los partidos… y los marcadores no se mueven. El collector estará gastando las llamadas de la API de Highlightly refrescando las fechas de la J76 (`['2026-08-10', '2026-08-15']`, verificado) en vez de los 15 partidos de la J1. El directo, el ticker y el ranking en vivo quedan muertos justo en el momento de máxima audiencia.

**Arreglo:** que `resolve_jornada()` delegue en `resolve_active_jornada()` cuando no le pasan una jornada explícita. Es un cambio de pocas líneas en un único sitio, y arregla de golpe los 6 puntos que la usan (`live.py` ×3, `highlightly.py` ×3).

**Alternativa complementaria:** borrar/archivar las jornadas 51-76 de la tabla `resultados`. Hoy hay 18 jornadas de pruebas conviviendo con la J1 real, y toda la lógica está llena de parches para esquivarlas (`current_season_sql()`, listas negras `not in (75, 76)`…). Limpiar la BD elimina la clase entera de bugs.

### 2. La política de privacidad publica "No configurado"

Página `/privacidad` en vivo ahora mismo:

> Responsable: **No configurado**. Contacto: **No configurado**.
> Puedes solicitar acceso, rectificación o eliminación escribiendo a **No configurado**.

Las variables `LEGAL_OWNER_NAME`, `LEGAL_OWNER_ID`, `LEGAL_OWNER_ADDRESS` y `LEGAL_CONTACT_EMAIL` están vacías. Con login de Google y datos personales de por medio, esto **incumple el RGPD y la LSSI** y deja al responsable expuesto. Es rellenar 4 variables en el `.env`, pero no es opcional.

**Extra recomendado:** que la app se niegue a arrancar en producción (o muestre un aviso grande en el log) si falta `LEGAL_CONTACT_EMAIL`. Ahora falla en silencio, que es la peor forma de fallar.

### 3. Secretos de producción sin poner

En `ENV_ALWAYSDATA.txt` siguen marcados `<-- RELLENA`: `SECRET_KEY`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `HIGHLIGHTLY_API_KEY`, `ADMIN_EMAILS`.

Sin OAuth, `/login/google` devuelve **503** y `auth_enabled` viaja en `false`: **nadie puede registrarse ni guardar una quiniela**. La web sería solo de lectura. Verificado en local.

---

## 🟠 IMPORTANTE — arreglar en la primera semana

### 4. La J1 no tiene quiz
`quiz_preguntas` solo tiene datos de las jornadas 71 y 72 (las de pruebas). `/api/quiz/preguntas?j=1` responde `"disponible": false`. La pestaña Quiz aparecerá vacía en el estreno. Hay que importar el banco con `tools/importers/IMPORTAR_QUIZ_JORNADA.py`.

### 5. El motor de predicción propio no existe en el repositorio

En los logs de producción, al pedir `/api/ai/predictions?j=1`:

```
WARNING [liga_maestros.services.ai.predictor] AI predictor: failed for jornada 1
        (No module named 'MOTOR_QUINIELA_MAESTRO')
```

`services/ai/predictor.py` importa `MOTOR_QUINIELA_MAESTRO` en tres sitios, pero **ese fichero no está en el repositorio** (`find` no encuentra nada). El endpoint devuelve `200` con `"count": 0, "predictions": []`, así que falla en silencio: parece que funciona pero nunca genera nada.

O el motor está fuera de Git y hay que subirlo/documentarlo, o esa funcionalidad está muerta y conviene quitarla. Tal y como está, la columna "Programa" solo se llena a mano.

### 6. Las predicciones de las IA se ven antes del cierre
`/api/liga/data` expone los 15 signos de ChatGPT, Claude, Gemini, Grok, Copilot y Programa **con `is_locked: false`**, es decir, antes del cierre. Cualquiera puede copiar la columna de Gemini y firmarla como suya.

Es una decisión de producto legítima (parte de la gracia es ver qué dicen las IA), pero **rompe la competición** si La Peña compite contra ellas por un ranking. Decide: o se ocultan hasta el cierre, o se asume y se comunica claramente. Hoy no está comunicado en ninguna parte.

### 7. Escudos servidos desde un dominio ajeno
4 de los 15 partidos de la J1 tiran el logo desde `quiniela15.com`:

```
Cádiz–Celta Fortuna    → https://www.quiniela15.com/media/.../celta.png
Eibar–Tenerife         → https://www.quiniela15.com/media/.../tenerife.png
Sporting–Sabadell      → https://www.quiniela15.com/media/.../9593.png
```

Es hotlinking a un tercero: si cambian la ruta o bloquean el referer, aparecen huecos en la quiniela. Además filtra a los usuarios hacia otro dominio. Hay que descargarlos a `static/img/team_logos/`.

### 8. Ficheros de datos versionados que la app reescribe en caliente
Durante la auditoría, con solo arrancar la app, `data/MULTI_STANDINGS.json` quedó modificado en Git. Hay 32 JSON versionados en `data/` que son a la vez semilla y caché de runtime. En producción esto ensucia el árbol de trabajo y puede provocar conflictos en cada deploy. Conviene separar semilla (en Git, solo lectura) de caché (en `DATA_DIR`, fuera de Git).

### 9. Ficheros de desarrollo en la raíz del repo
`fix-j75-quiniela.patch` (32 KB), `fix-j75-resultados.patch`, `debug_results.py`, `debug_results_v2.py`, `rellenar_resultados (2).py` (duplicado literal con espacio y paréntesis en el nombre), `nombre.py`. Ruido que confunde y que en algunos casos son scripts ejecutables contra la BD de producción.

---

## 🟡 MEJORAS — cuando haya tiempo

10. **Cobertura de tests: 60 %.** Muy buena en lo crítico (`payloads/predictions.py` 93 %, `contest.py` 86 %, `privacy.py` 93 %), pero los puntos flojos son justo donde está el bug nº 1: `highlightly.py` **14 %**, `web_collector.py` **14 %**, `standings_calculator.py` **0 %**, `quiz.py` 38 %.

11. **Falta enlace "saltar al contenido"** y el HTML no trae `<noscript>`: sin JS la página se queda en blanco. 16 atributos `aria-` es escaso para una tabla de 15 partidos con controles interactivos.

12. **`X-Frame-Options: ALLOWALL`** viene de `ALLOW_IFRAME_EMBED`, que en la auditoría estaba activo. Verifica que en producción esté a `0`, o cualquiera podrá embeber la web en un iframe (riesgo de clickjacking sobre el login).

13. **Sin analítica conectada.** `analytics.js` está preparado para Plausible/Umami/PostHog pero no hay ninguno configurado: el día del lanzamiento no sabrás cuánta gente entró ni dónde abandonó.

14. **Sin Sentry.** `SENTRY_DSN` vacío. Los errores de producción se perderán en un log del servidor.

15. **Backup off-site desactivado.** `DB_BACKUP_ENABLED=1` en local, pero `BACKUP_S3_*` vacío: las copias viven en el mismo disco que la BD. Si Alwaysdata pierde el disco, se pierde todo.

16. **Sitemap y canonical dependen del Host.** Con la cabecera correcta funcionan bien (`https://ligademaestros.alwaysdata.net/sitemap.xml`), pero requiere `TRUST_PROXY_HEADERS=1` en producción. Está documentado en `ENV_ALWAYSDATA.txt`; solo hay que no olvidarlo.

17. **La landing es muy pobre** comparada con la app: HTML plano con estilos inline, sin capturas, sin prueba social, sin explicar el juego. Es la página que verá quien llegue desde redes.

---

## ✅ LO QUE ESTÁ MUY BIEN

Conviene decirlo, porque es mucho:

- **Tests:** 216 pasando, 0 fallos, en 7 segundos.
- **Linter:** `ruff check` limpio. **Formato:** 138 ficheros conformes. **Tipos:** `mypy` sin un solo error en 63 ficheros.
- **Dependencias:** `pip-audit` → *No known vulnerabilities found*.
- **Rendimiento:** 200 peticiones concurrentes a `/api/liga/data` (el endpoint gordo, 51 KB): **100 % en 200**, p50 670 ms, p95 862 ms, sin un solo error. La home responde en **3 ms**.
- **Seguridad verificada en caliente:** `/api/admin/*` devuelve 403 sin credenciales; escrituras sin sesión → 401; CSRF con `compare_digest`; path traversal (`/static/../config.py`, `/juegos/../config.py`) → 404; body de 200 KB rechazado; CSP real sin `unsafe-inline` en scripts; HSTS, `nosniff`, `Referrer-Policy`, `Permissions-Policy` presentes.
- **Las 20 alertas S608 de "SQL injection" son falsos positivos**: revisadas una a una, todas son fragmentos constantes (`current_season_sql()` con un `int` literal) o placeholders `?` generados por conteo. No hay concatenación de entrada de usuario.
- **RGPD por diseño:** el email de Google se guarda como `NULL` a propósito, borrado transaccional de cuenta, IDs públicos ofuscados.
- **Los 48 assets estáticos** referenciados en la home devuelven 200. Cero enlaces rotos.
- **Detalles de oficio:** `X-Request-ID` y `Server-Timing` en cada respuesta, log automático de peticiones lentas, circuit breaker y cuota diaria en la API externa, rate limiter atómico en SQLite con fallback en memoria, SHAs de GitHub Actions pineados.

---

## PLAN DE ACCIÓN

**Antes de abrir (2-4 horas):**
1. Unificar `resolve_jornada()` con `resolve_active_jornada()` → arregla el directo.
2. Rellenar los 4 datos legales.
3. Rellenar `SECRET_KEY`, OAuth de Google, clave de Highlightly y `ADMIN_EMAILS`.
4. Verificar `ALLOW_IFRAME_EMBED=0` y `TRUST_PROXY_HEADERS=1`.
5. **Ensayo general:** entrar con una cuenta real, firmar una quiniela y comprobar que un marcador se mueve de verdad.

**Primera semana:**
6. Importar el quiz de la J1. 7. Resolver el motor `MOTOR_QUINIELA_MAESTRO` (subirlo o retirar el código). 8. Decidir qué hacer con las predicciones IA visibles. 9. Descargar los 4 escudos externos. 10. Conectar Sentry y analítica. 11. Activar backup off-site.

**Después:** limpiar las jornadas de pruebas de la BD, separar semilla de caché, subir cobertura en `highlightly.py` y `web_collector.py`, limpiar la raíz del repo.

---

### En una frase

La ingeniería está a nivel profesional; lo que falla es la **configuración de lanzamiento y el estado de los datos**. Con la jornada unificada y las variables rellenas, esto se pone en **95 % en una tarde**.
