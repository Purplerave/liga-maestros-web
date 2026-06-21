# Revision por IA

## Contexto

Liga de Maestros es una app Flask de quinielas con:
- predicciones de usuarios y maestros IA;
- rankings;
- directo de partidos;
- consumo de Highlightly;
- login Google OAuth.

## Archivos principales

- `app.py`: backend Flask, endpoints, rankings, OAuth, live refresh.
- `config.py`: rutas, ligas, variables de entorno.
- `utils.py`: normalizacion, helpers de equipos, JSON, horarios.
- `LIVE_COLLECTOR.py`: refresco live fuera de peticiones web.
- `SCRAPE_QUINIELA15_DIRECTO.py`: scraper de resultados Quiniela15.
- `templates/liga_index.html`: layout principal.
- `static/js/quantum_final.js`: frontend principal.
- `static/css/quantum_pro.css`: estilos.
- `DATOS/LIGA_MAESTROS_PRO.db`: SQLite beta.

## Tareas de revision recomendadas

1. Seguridad antes de deploy.
2. Riesgos de SQLite online.
3. Bugs de ranking y puntuacion.
4. OAuth Google y registro de usuarios.
5. Consumo de API Highlightly.
6. UX mobile/desktop.
7. Limpieza de mojibake/UTF-8.

## No pedir ni exponer

No pedir claves reales. Las claves van en variables de entorno privadas del hosting.
