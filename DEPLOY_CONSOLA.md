# Deploy y actualizacion desde consola

## 1. Donde se sube

No subas la carpeta `QUINIELAs` entera ni un ZIP manual.

El proyecto que se despliega es solo:

```text
C:\Users\Mortadelo\Desktop\QUINIELAs\LIGA_MAESTROS
```

Ese directorio ya tiene remoto configurado:

```text
https://github.com/Purplerave/liga-maestros-web.git
```

Render debe conectarse a ese repositorio privado de GitHub y leer el `render.yaml`.

## 2. Primera subida a Render

En Render:

1. `New +`
2. `Blueprint` o `Web Service` conectado al repo `Purplerave/liga-maestros-web`
3. Usar la rama `main`
4. Confirmar que detecta `render.yaml`
5. Rellenar variables secretas:

```env
SECRET_KEY=<cadena larga>
GOOGLE_CLIENT_ID=<id de Google>
GOOGLE_CLIENT_SECRET=<secret de Google>
HIGHLIGHTLY_API_KEY=<clave>
ADMIN_EMAILS=<tu email>
```

El `render.yaml` ya crea un servicio web con disco persistente `/var/data` y collector interno.

## 3. Subir cambios de codigo

Desde PowerShell:

```powershell
cd "C:\Users\Mortadelo\Desktop\QUINIELAs\LIGA_MAESTROS"
git status
git add render.yaml .env.example README_DEPLOY.md OPERACION_SEMANAL.md ROADMAP.md DEPLOY_CONSOLA.md
git add liga_maestros static templates data
git commit -m "Describe el cambio"
git push origin main
```

Render redepliega automaticamente al recibir el push.

No hagas `git add .` sin mirar `git status`: este proyecto genera caches, salidas y pruebas locales.

## 4. Actualizar una nueva jornada localmente

Primero extraer la proxima quiniela desde Quiniela15:

```powershell
python SCRAPE_QUINIELA15_PROXIMA.py --dry-run
python SCRAPE_QUINIELA15_PROXIMA.py
```

Despues probar la importacion:

```powershell
python IMPORTAR_PROGRAMA_JORNADA.py --jornada N --dry-run --usar-q15-base
```

Si esta bien:

```powershell
python IMPORTAR_PROGRAMA_JORNADA.py --jornada N --usar-q15-base
python AUDITAR_JORNADA_LIGA_MAESTROS.py --jornada N
```

## 5. Actualizar una jornada en Render

Como la beta usa SQLite en disco persistente, la base de datos viva esta en Render, no en GitHub.

La forma correcta es ejecutar los mismos comandos desde la shell del servicio en Render:

```bash
python SCRAPE_QUINIELA15_PROXIMA.py --dry-run
python SCRAPE_QUINIELA15_PROXIMA.py
python IMPORTAR_PROGRAMA_JORNADA.py --jornada N --dry-run --usar-q15-base
python IMPORTAR_PROGRAMA_JORNADA.py --jornada N --usar-q15-base
python AUDITAR_JORNADA_LIGA_MAESTROS.py --jornada N
```

Si Render no permite shell en el plan usado, el siguiente paso tecnico sera crear un endpoint admin de importacion de jornada. Hasta entonces, no conviene confiar en subir la DB por Git, porque pisaria comentarios, usuarios y puntuaciones vivas.

## 6. Directo y gasto de API

El navegador no llama a Highlightly por refrescar la pagina.

En produccion el collector interno corre con:

```env
WEB_COLLECTOR_ENABLED=1
WEB_COLLECTOR_INTERVAL_SECONDS=60
WEB_COLLECTOR_HIGHLIGHTLY_INTERVAL_SECONDS=60
```

Estado:

```text
/api/live/health
/api/sync/status
```

Prueba manual local:

```powershell
python LIVE_COLLECTOR.py --once --jornada N
python LIVE_COLLECTOR.py --once --force --jornada N
```
