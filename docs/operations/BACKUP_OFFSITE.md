# Backup off-site (copia de seguridad fuera del servidor)

## Por qué

La app guarda todo en un fichero SQLite en el disco del hosting. El scheduler
ya crea copias verificadas cada 6 horas, pero si solo viven en el mismo disco
no protegen contra pérdida de la cuenta, borrado accidental o fallo de disco.
Este documento explica cómo activar la subida automática a un almacenamiento
externo (Backblaze B2, Cloudflare R2 o cualquier S3 compatible).

Coste esperado: 0 €. La BD ocupa pocos MB y B2/R2 regalan 10 GB.

## Regla de oro

Las credenciales NUNCA se suben a GitHub. El fichero `.env` está en
`.gitignore` a propósito. En GitHub solo vive la plantilla `.env.example`
con los nombres de las variables, sin valores.

## Paso 1 — Crear cuenta y bucket en Backblaze B2 (~10 min)

1. Registrarse gratis en https://www.backblaze.com/sign-up/cloud-storage
   (no pide tarjeta).
2. Panel → **B2 Cloud Storage → Buckets → Create a Bucket**.
   - Nombre: único a nivel global, p. ej. `liga-maestros-backups-XXXX`.
   - Files are: **Private**.
3. Apuntar el **Endpoint** que muestra el bucket
   (p. ej. `s3.eu-central-003.backblazeb2.com`). La región es la parte
   central (`eu-central-003`).
4. Panel → **Application Keys → Add a New Application Key**.
   - Acceso: solo a ese bucket, Read & Write.
   - Copiar **keyID** y **applicationKey** inmediatamente
     (el applicationKey solo se muestra una vez).

## Paso 2 — Configurar las variables en el hosting

Variables a definir (los valores salen del Paso 1):

```bash
DB_BACKUP_ENABLED=1
BACKUP_S3_BUCKET=liga-maestros-backups-XXXX
BACKUP_S3_ENDPOINT=https://s3.eu-central-003.backblazeb2.com
BACKUP_S3_KEY_ID=<keyID>
BACKUP_S3_SECRET=<applicationKey>
BACKUP_S3_REGION=eu-central-003
# Opcional (tiene valores por defecto razonables):
# BACKUP_S3_PREFIX=liga-maestros-backups
# DB_BACKUP_INTERVAL_SECONDS=21600   # cada 6 h
# DB_BACKUP_RETENTION=14             # conserva las 14 últimas
```

### Si el deploy es Render

Dashboard → servicio **liga-maestros** → **Environment** →
**Add Environment Variable** → añadir las de arriba → **Save Changes**
(Render redespliega solo).

### Si el deploy es Alwaysdata (u otro hosting con ficheros)

1. Por SSH o gestor de ficheros, en el directorio del código (junto a
   `app.py`), copiar `.env.example` a `.env` si aún no existe.
2. Rellenar las variables de arriba en ese `.env`.
3. Reiniciar el sitio desde el panel.

## Paso 3 — Verificar que funciona

En una consola SSH del servidor:

```bash
python tools/ops/GESTIONAR_BACKUPS.py create --reason prueba --upload
```

Salida esperada: la ruta del backup y `UPLOADED`. Después, comprobar en el
panel de Backblaze que el fichero `liga_maestros_<fecha>_prueba.db` aparece
dentro del bucket.

A partir de ahí el scheduler sube una copia cada 6 horas de forma automática
y borra en remoto las que exceden la retención.

## Comandos útiles

```bash
# Crear backup local verificado
python tools/ops/GESTIONAR_BACKUPS.py create --reason manual

# Crear y subir en un solo paso
python tools/ops/GESTIONAR_BACKUPS.py create --reason manual --upload

# Subir el backup local más reciente
python tools/ops/GESTIONAR_BACKUPS.py upload

# Listar backups locales retenidos
python tools/ops/GESTIONAR_BACKUPS.py list

# Verificar la integridad de una copia
python tools/ops/GESTIONAR_BACKUPS.py verify /ruta/al/backup.db
```

## Recuperación ante desastre

1. Descargar el `.db` más reciente desde el panel de Backblaze.
2. Verificarlo: `python tools/ops/GESTIONAR_BACKUPS.py verify <fichero>`.
3. Colocarlo en la ruta de `DB_PATH` del servidor nuevo.
4. Reiniciar la app.
