# Operacion semanal Liga de Maestros

Objetivo: que cada jornada salga igual de limpia sin revisar todo a mano.

## 1. Cargar jornada

- Importar o scrapear la jornada oficial.
- Confirmar que hay 15 partidos en `resultados`.
- Confirmar horas y fechas antes de generar predicciones.

Comando de control:

```powershell
python AUDITAR_JORNADA_LIGA_MAESTROS.py --jornada 67
```

## 2. Generar predicciones

Capas separadas:

- `programa`: motor propio.
- `consejo_ias`: consenso final de modelos.
- `gemini`, `grok`, `claude`, `copilot`, `chatgpt`: maestros individuales cuando existan.
- Usuario: quiniela personal autenticada.
- La Pena: grupo social y aliases, nunca usuario unico.

Regla: Programa, Consejo IA y usuario deben tener 15/15 antes de dar la jornada por lista.

## 3. Revisar antes de sellar

Comprobar:

- Programa 15/15.
- Consejo IA 15/15.
- Usuario 15/15 si ya se ha guardado.
- Pleno al 15 en formato Quiniela: `0`, `1`, `2`, `M` por cada equipo. Ejemplo: `M-0`, no `3-0`.
- Escudos/banderas resuelven desde `utils.load_team_logos()`.

## 4. Durante la jornada

- La web puede refrescar datos internos sin gastar API.
- Las llamadas externas tienen que venir del colector/controlador, no del refresco del navegador.
- Si hay partido suspendido, bloquear el resultado oficial LAE manualmente y auditar.

## 5. Despues de la jornada

- Ejecutar auditoria.
- Revisar ranking de jornada.
- Revisar ranking general.
- Guardar ganador de jornada y, si toca, ganador mensual.
- No borrar predicciones historicas; ocultar IDs obsoletos desde configuracion.

## Comandos rapidos

```powershell
python AUDITAR_JORNADA_LIGA_MAESTROS.py --jornada 67
python -m py_compile app.py LIVE_COLLECTOR.py AUDITAR_JORNADA_LIGA_MAESTROS.py
node --check static/js/quantum_final.js
```
