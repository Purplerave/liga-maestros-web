# Informe de Revisión y Propuestas de Mejora - Liga de Maestros

Este documento presenta una revisión técnica exhaustiva del proyecto **Liga de Maestros**, analizando tanto el backend (Flask, SQLite WAL, arquitectura) como el frontend (sistema de capas CSS, carga modular de JS, UX/UI, accesibilidad y rendimiento).

En términos generales, el proyecto cuenta con una **arquitectura extremadamente robusta, limpia y moderna**. El cumplimiento de directrices avanzadas de seguridad, gobernanza CSS estricta (sin `!important`, uso de `@layer`) y una suite de pruebas con excelente cobertura (130 tests pasando con éxito en ~3 segundos) sitúan a esta aplicación muy por encima de la media en calidad de software.

A continuación, se detallan los hallazgos y se proponen mejoras específicas organizadas por áreas.

---

## 1. Backend y Rendimiento de la Base de Datos

### Hallazgo: Invalidación Agresiva de la Caché de Assets
En `liga_maestros/routes/main.py`, la función `_get_assets_version` calcula el máximo `mtime` de cualquier archivo estático bajo `static/`:
```python
@lru_cache(maxsize=1)
def _get_assets_version():
    # ... busca recursivamente todos los archivos .css, .js, .png, etc.
    return str(max(mtimes) if mtimes else int(time.time()))
```
* **Impacto:** Si se edita un solo logo o un archivo JS secundario, la versión global de assets cambia y se invalida la caché del navegador de **todos** los archivos estáticos cargados por la aplicación.
* **Propuesta de Mejora:** Implementar un sistema de hash individual por archivo o por módulo. Por ejemplo, mapear cada recurso en un manifiesto (`manifest.json`) generado en tiempo de compilación o inicio, de modo que cada archivo mantenga su propia firma única. Esto optimizaría drásticamente el consumo de ancho de banda y la velocidad de carga de usuarios recurrentes.

### Hallazgo: Activación Tardía del Modo WAL de SQLite
En `liga_maestros/db/connection.py`, la base de datos se configura en modo WAL (`PRAGMA journal_mode = WAL`) en la primera llamada a `get_db` durante el ciclo de vida del proceso de Flask, mediante un bloqueo con exclusión mutua:
```python
if not _sqlite_wal_ready:
    lock = _get_pragma_lock()
    with lock:
        # ... conn.execute("PRAGMA journal_mode = WAL")
```
* **Impacto:** Cualquier script offline, comando de consola o worker que acceda a la base de datos de manera directa antes de que Flask atienda la primera petición HTTP podría interactuar con el archivo de base de datos sin que este haya sido inicializado de forma segura en modo WAL, limitando la concurrencia en ese instante.
* **Propuesta de Mejora:** Mover la activación del modo WAL directamente al inicio de las migraciones de base de datos (`run_startup_migrations` en `liga_maestros/db/migrations.py`) para asegurar que el archivo se configure en modo WAL desde su creación o inicialización, independientemente del punto de entrada (Flask o scripts CLI).

### Hallazgo: Indexación de Consultas Frecuentes
La base de datos cuenta con buenos índices sobre `predicciones` y `resultados`. Sin embargo, considerando que se ejecutan agregaciones complejas sobre jornadas específicas (por ejemplo, en el cálculo de puntuaciones mensuales y semanales del concurso en `liga_maestros/services/contest.py`), es recomendable monitorizar el rendimiento de:
```sql
SELECT rowid AS pred_rowid, user_id, jornada, partido_id, signo
FROM predicciones WHERE jornada >= ?
```
* **Propuesta de Mejora:** Asegurar que el índice único `ux_predicciones_user_jornada_partido` o los índices individuales cubran de forma óptima estas consultas de rango sobre `jornada`. Un índice compuesto `(jornada, user_id, partido_id, signo)` podría permitir que SQLite resuelva la consulta mediante un *index-only scan*, evitando consultar las páginas del montón (*heap*).

---

## 2. Seguridad y Hardening

### Hallazgo: Configuración Estática de la Content Security Policy (CSP)
El middleware en `liga_maestros/__init__.py` define una CSP muy restrictiva y segura, lo cual es excelente:
```python
response.headers["Content-Security-Policy"] = (
    "default-src 'self'; script-src 'self'; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com; img-src 'self' data: https:; "
    "connect-src 'self'; object-src 'none'; base-uri 'self'; "
    "form-action 'self'; frame-ancestors 'none'"
)
```
* **Propuesta de Mejora:**
  1. **Evitar `'unsafe-inline'` en `style-src`:** Aunque se use para simplificar la inyección de fuentes de Google o estilos rápidos, expone al sitio a ataques CSS injection que podrían exfiltrar datos. Se recomienda usar un hash de estilo o un `nonce` dinámico generado en cada petición para los estilos en línea que sean estrictamente necesarios.
  2. **Imágenes externas específicas:** El uso de `img-src 'self' data: https:` es permisivo al permitir cualquier origen HTTPS. Se aconseja restringir a los dominios específicos requeridos, como `https://highlightly.net` y otros proveedores de logos/imágenes que use la aplicación.

### Hallazgo: Implementación Prototipo de CSRF
La aplicación valida peticiones autenticadas de escritura frente a un sistema CSRF propio:
```python
@app.before_request
def protect_authenticated_writes():
    if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
        return None
    if not session.get("user"):
        return None
    if valid_csrf_request():
        return None
    return jsonify({"status": "error", "error": "Solicitud de seguridad caducada."}), 403
```
* **Propuesta de Mejora:** Aunque el mecanismo es correcto y seguro, delegar la protección CSRF en librerías estándar consolidadas como **Flask-WTF (SeaSurf)** proporciona mitigaciones automáticas contra ataques de temporización, rotación de tokens y una gestión óptima de tokens de un solo uso por formulario.

---

## 3. Rendimiento Frontend y UX/UI

### Hallazgo: Gobernanza de Capas CSS Sobresaliente
El uso del sistema de capas CSS (`@layer`) con un orden canónico estricto es **brillante**. Garantiza que no haya colisiones de especificidad y elimina por completo el uso indeseado de `!important` (validado mediante tests automatizados en `test_css_governance.py`).
* **Propuesta de Mejora:** Continuar con esta práctica. Como única optimización, el uso de `@layer` puede ralentizar ligeramente la renderización en navegadores antiguos si las capas son excesivamente complejas. Mantener las capas limpias y agrupadas como está actualmente es la mejor opción.

### Hallazgo: Precarga de Hojas de Estilo Críticas
La carga asíncrona de recursos a través de `navigation.js` ayuda a mantener un JS y CSS inicial ligeros. Sin embargo, cambiar de vista (por ejemplo, a la sección de Quiniela o Directo) provoca una breve transición visual sin estilos (*FOUC - Flash of Unstyled Content*) mientras se descarga la hoja de estilo correspondiente en segundo plano.
* **Propuesta de Mejora:** Precomentar o precargar (`<link rel="preload" as="style">`) en la cabecera HTML las hojas de estilo de las 2-3 vistas más frecuentadas (como la Quiniela y la Clasificación) para que estén disponibles instantáneamente en el navegador del usuario al cambiar de pestaña.

### Hallazgo: Accesibilidad (a11y) y Semántica HTML
En `static/js/contest.js` y `templates/liga_index.html`, algunos elementos interactivos carecen de la semántica o los roles de accesibilidad adecuados:
* **Propuesta de Mejora:**
  1. Asegurar que todos los botones de filtro y pestañas tengan descripciones claras en lectores de pantalla (por ejemplo, los botones mensuales en La Peña).
  2. Agregar `aria-expanded` dinámico en todos los elementos colapsables (por ejemplo, el botón de "Ver todos" en la clasificación de La Peña ya cuenta con él, lo cual es excelente; replicar este patrón en los detalles de partidos desplegables).
  3. Comprobar que los contrastes de texto sobre fondos oscuros sigan el estándar WCAG AA (especialmente para textos pequeños como `ccr-rank` o descripciones secundarias).

---

## 4. Calidad de Código y Pruebas

### Hallazgo: Suite de Pruebas Excelente
La suite de pruebas (con 130 tests que verifican seguridad, dominio, payload de partidos y UX) proporciona una red de seguridad inmejorable.
* **Propuesta de Mejora:**
  1. **Pruebas de Límites en Concurrencia de SQLite:** Añadir tests unitarios o de integración que simulen escrituras concurrentes agresivas para verificar que el manejo del `busy_timeout` y las transacciones previene los errores de `database is locked` bajo estrés extremo.
  2. **Automatización en Pre-Commit:** Integrar `ruff` y `pytest` dentro de un hook de pre-commit local para evitar subir código que falle las políticas del sistema de gobernanza de capas o la auditoría de seguridad.

---

## Conclusión

El proyecto **Liga de Maestros** es un ejemplo excepcional de desarrollo web moderno utilizando Flask y Vanilla Javascript con un alto grado de rigor arquitectónico.

Las mejoras propuestas representan pasos de optimización hacia la escala de producción y excelencia en la experiencia de usuario, sin requerir reestructuraciones drásticas del código existente.
