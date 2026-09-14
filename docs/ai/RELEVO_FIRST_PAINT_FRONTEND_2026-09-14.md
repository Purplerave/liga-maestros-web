# Relevo — Adoptar `?first=1` en el frontend

Fecha: 2026-09-14 · Grok

## Contexto

Backend listo (PR #128 mergeado): `GET /api/liga/data?first=1` devuelve solo lo necesario para firmar (~4 KB):
`jornada`, `partidos` (15), `is_locked`, `edit_deadline`, `kickoff_at`, `ticket_policy`, `today_madrid`, `max_jornada`, `first: true`.

## Cambio concreto en `static/js/quantum_final.js`

Dentro de `refreshData`:

1. Detectar primera pintura:
```js
const isFirstPaint = !options.auto && !state.data;
```

2. Elegir URL:
```js
const dataUrl = isFirstPaint
  ? `/api/liga/data?first=1&j=${encodeURIComponent(state.jornada)}`
  : `/api/liga/data?j=${encodeURIComponent(state.jornada)}`;
```

3. Tras pintar con el payload `first`, completar en background:
```js
if (isFirstPaint && state.data?.first) {
  window.setTimeout(() => {
    refreshData({ auto: true, afterFirst: true }).catch(err =>
      console.warn("Carga completa post-first fallida", err)
    );
  }, 50);
}
```

## Por qué es seguro

- El payload `first` tiene los 15 partidos → la quiniela se puede firmar.
- El refresh completo (`auto: true`) ya existe y rehidrata rankings/standings.
- No cambia CSS ni layout.
- Si `?first=1` fallara, el retry existente sigue aplicando.

## Verificación

```bash
# Backend
curl -s 'https://ligademaestros.alwaysdata.net/api/liga/data?first=1' | jq 'keys'
# Frontend: Network → primera petición debe ser ?first=1, luego la completa
python -m pytest -q
```

## Nota

Aplicar sobre `main` limpio. No tocar la rama rota `perf/first-paint-frontend`.
