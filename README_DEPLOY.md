# Liga de Maestros - despliegue beta

## Que se sube a GitHub

Sube este directorio `LIGA_MAESTROS` a un repositorio privado.

El repo debe incluir:
- codigo Python;
- `templates/`;
- `static/`;
- `data/` con JSON necesarios;
- `data/bootstrap/production_seed.json` como semilla publica regenerable;
- `requirements.txt`;
- `render.yaml`;
- `.env.example`.

No debe incluir:
- `.env`;
- claves API;
- secretos OAuth;
- logs;
- backups;
- capturas temporales;
- copias antiguas.

Eso ya queda cubierto por `.gitignore`.

## GitHub

```powershell
cd "C:\Users\Mortadelo\Desktop\QUINIELAs\LIGA_MAESTROS"
git init
git add .
git commit -m "Preparar Liga de Maestros para deploy beta"
git branch -M main
git remote add origin https://github.com/TU_USUARIO/liga-maestros.git
git push -u origin main
```

## Render

1. Crear cuenta en https://render.com.
2. New > Web Service.
3. Conectar el repo privado `liga-maestros`.
4. Render detectara `render.yaml`.
5. En Environment Variables rellenar como minimo:

```env
SECRET_KEY=<cadena larga aleatoria>
GOOGLE_CLIENT_ID=<cliente OAuth de Google>
GOOGLE_CLIENT_SECRET=<secreto OAuth de Google>
HIGHLIGHTLY_API_KEY=<clave Highlightly/RapidAPI>
ADMIN_EMAILS=<tu correo si quieres permisos admin>
LEGAL_OWNER_NAME=<responsable de la web>
LEGAL_OWNER_ID=<identificacion legal>
LEGAL_OWNER_ADDRESS=<direccion de contacto>
LEGAL_CONTACT_EMAIL=<correo publico de privacidad>
```

El `render.yaml` actual esta preparado como **beta de un solo servicio**:

- 1 web service con disco persistente en `/var/data`;
- SQLite en `/var/data/LIGA_MAESTROS_PRO.db`;
- inicializacion automatica desde una semilla sin cuentas ni datos privados;
- backup SQLite verificado cada 6 horas, con 14 copias de retencion;
- collector live interno activado con `WEB_COLLECTOR_ENABLED=1`;
- Gunicorn con `--workers 1 --threads 8` para evitar dos collectors simultaneos.

El disco persistente de Render requiere un servicio de pago. No publiques esta
configuracion sobre una instancia efimera: los usuarios y quinielas se perderian.

## Alternativa gratuita: Alwaysdata

La beta tambien puede ejecutarse en el plan gratuito de Alwaysdata con un unico
worker y SQLite persistente. La disposicion preparada es:

```text
/home/ligademaestros/current -> version activa
/home/ligademaestros/releases/ -> versiones inmutables
/home/ligademaestros/runtime/ -> base, datos, secretos y backups persistentes
/home/ligademaestros/venv/ -> entorno Python compartido
```

El sitio debe configurarse como `User program`:

```text
Working directory: /home/ligademaestros/current
Command: /home/ligademaestros/venv/bin/gunicorn --workers 1 --threads 4 --timeout 120 --bind $IP:$PORT app:app
Address: ligademaestros.alwaysdata.net
Idle time: 0
```

El workflow `.github/workflows/deploy-alwaysdata.yml` publica automaticamente
cada `push` a `main`, crea un backup antes de activar la nueva version y comprueba
la salud publica. Requiere estos secretos de GitHub:

```text
ALWAYSDATA_SSH_KEY
ALWAYSDATA_KNOWN_HOSTS
ALWAYSDATA_API_TOKEN
ALWAYSDATA_SITE_ID
```

El plan gratuito queda limitado al subdominio de Alwaysdata, 256 MB de RAM y uso
no comercial. No se deben ejecutar varios workers ni duplicar el collector.

## Google OAuth

En Google Cloud Console, en el cliente OAuth de la app, anadir:

```text
https://TU-DOMINIO-DE-RENDER.onrender.com/authorize
```

Tambien puedes anadir para pruebas locales:

```text
http://localhost:5000/authorize
```

## Base de datos

La base privada nunca se sube a Git. En el primer despliegue,
`INICIALIZAR_PRODUCCION.py` crea el esquema completo e importa
`data/bootstrap/production_seed.json`. La semilla conserva competicion e
historico publico, pero excluye usuarios, correos, comentarios y actividad privada.

Para regenerarla despues de actualizar el historico local:

```powershell
python EXPORTAR_SEMILLA_PRODUCCION.py
```

La app tambien inicializa la base al arrancar, por lo que el `initialDeployHook`
es una comprobacion adicional y no un punto unico de fallo.

Nota Render importante: un Persistent Disk solo es accesible por la instancia del servicio al que se adjunta. Por eso la beta no usa un worker separado. Si mas adelante se separa `LIVE_COLLECTOR.py` como worker, antes hay que mover el estado compartido a Postgres/Redis o hacer que el worker actualice la web por API HTTP autenticada.

## Directo / Highlightly

El refresco live no depende de que los usuarios recarguen la web. En Render lo ejecuta el collector interno:

- `WEB_COLLECTOR_ENABLED=1`
- `WEB_COLLECTOR_INTERVAL_SECONDS=60`
- `WEB_COLLECTOR_HIGHLIGHTLY_INTERVAL_SECONDS=60`

El collector respeta la ventana de jornada, el limite diario y el circuit breaker. El estado se consulta en:

```text
/api/live/health
/api/sync/status
```

Para un directo fuerte con varios procesos o servicios, el siguiente paso sera PostgreSQL/Redis.

## Backups

Render guarda las copias en `/var/data/backups`. Operaciones manuales:

```bash
python GESTIONAR_BACKUPS.py create --reason antes-jornada
python GESTIONAR_BACKUPS.py list
python GESTIONAR_BACKUPS.py verify /var/data/backups/NOMBRE.db
```

Una copia solo se conserva si supera `PRAGMA integrity_check`. Para restaurar,
deten el servicio, conserva primero la base actual y sustituye `DB_PATH` por una
copia verificada.

## Antes de abrir al publico

- rellenar todas las variables `LEGAL_*`;
- comprobar `/privacidad`, `/cookies`, `/aviso-legal` y `/cuenta`;
- probar login, guardado y eliminacion de una cuenta de prueba;
- reiniciar el servicio y confirmar que los datos permanecen;
- crear y verificar un backup manual;
- ejecutar una jornada completa en staging.

## Revisiones con otra IA

Pidele que revise:

```text
Lee README_DEPLOY.md, app.py, config.py, utils.py, LIVE_COLLECTOR.py,
SCRAPE_QUINIELA15_DIRECTO.py, templates/liga_index.html,
static/js/quantum_final.js y static/css/quantum_pro.css.
Busca bugs de produccion, seguridad, despliegue y UX.
```
