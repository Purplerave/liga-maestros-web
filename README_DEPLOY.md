# Liga de Maestros - despliegue beta

## Que se sube a GitHub

Sube este directorio `LIGA_MAESTROS` a un repositorio privado.

El repo debe incluir:
- codigo Python;
- `templates/`;
- `static/`;
- `data/` con JSON necesarios;
- `DATOS/LIGA_MAESTROS_PRO.db` como base inicial beta;
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
```

Opcional si contratas/configuras disco persistente en Render:

```env
DB_PATH=/var/data/LIGA_MAESTROS_PRO.db
```

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

Para beta rapida se sube `DATOS/LIGA_MAESTROS_PRO.db`.

Advertencia: en Render sin disco persistente, los cambios hechos en SQLite pueden perderse al redeploy/recrear instancia. Vale para probar online. Para produccion real, el siguiente paso sera migrar a PostgreSQL o configurar persistencia.

Si defines `DB_PATH` apuntando a un disco persistente y la DB no existe ahi, la app copia automaticamente la DB inicial incluida en `DATOS/LIGA_MAESTROS_PRO.db`.

## Directo / Highlightly

La web puede lanzar refrescos live desde endpoints internos ya existentes cuando hay uso. Para un directo fuerte 24/7, el siguiente paso sera montar un worker/cron con almacenamiento persistente compartido o migrar la DB a PostgreSQL.

## Revisiones con otra IA

Pidele que revise:

```text
Lee README_DEPLOY.md, app.py, config.py, utils.py, LIVE_COLLECTOR.py,
SCRAPE_QUINIELA15_DIRECTO.py, templates/liga_index.html,
static/js/quantum_final.js y static/css/quantum_pro.css.
Busca bugs de produccion, seguridad, despliegue y UX.
```
