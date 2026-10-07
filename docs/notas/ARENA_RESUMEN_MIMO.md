# 📋 Resumen para la próxima sesión Arena — MIMO Ámsterdam + Ticker

> Guarda este fichero. En una **sesión nueva de Arena en este mismo repo** (`Purplerave/liga-maestros-web`) solo tienes que decir:
>
> **"Revisa el commit `e2e6935` de la rama `arena/01a01551-liga-maestros-web` y ábrelo como PR"**
> — o — **"Reaplica las 4 líneas de `liga_maestros/services/ai/client.py` de abajo (MIMO_API_BASE + mirror ams)"**

Con eso queda todo: clave leída de `MIMO_API_KEY`, mirror `token-plan-ams` (Ámsterdam), modelo `mimo-v2.5-pro` y el ticker pintando frases.

---

## 1) Estado actual (2026-08-18 UTC)

| Item | Valor |
|------|-------|
| **PR #75 — Comentarista MiMo: frases breves del directo en el ticker** | **MERGED** `2026-08-18 15:01 UTC` |
| Rama origen | `arena/01a01551-liga-maestros-web` |
| Rama destino | `main` |
| Merge commit | `51c8afcec26ac88a0924f90eb364f30e28d4e391` |
| Commit de feature dentro del PR | `e2e693596f2ec0bb161aedec6d77c6834f651f16` — `feat(comentarista): frases breves de MiMo en el ticker del directo` |
| Rama **actual de esta sesión** | `arena/01a0156f-liga-maestros-web` (branched from `51c8afc`, ya tiene todo el ticker) |
| Nota sobre `4b4b477` | No existe en remoto (shallow/rebase local de la sesión anterior). **El commit real es `e2e6935`**. Si ves `4b4b477` en notas antiguas, es alias de `e2e6935` + el parche ams. |

### Qué ya está en `main` (vía PR #75) — no hace falta rehacer

- `liga_maestros/services/ai/comentarista.py` (nuevo) — foto compacta del directo (máx. 6 partidos) → 1 llamada MiMo → 1-3 frases ≤16 palabras validadas contra marcador real.
- `liga_maestros/services/ai/client.py` — proveedor `mimo` con `prefer="mimo"`, fallback Groq/Gemini, retry sin `response_format`.
- `liga_maestros/schemas.py` + `liga_maestros/routes/liga_data.py` — campo `comentarista: {comentarios, generated}` en `GET /api/liga/data`.
- `static/js/pages/cover_page.js` + `static/css/cover_hero.css` + `templates/liga_index.html` — ticker `⚽ EN DIRECTO` intercala `COMENTARISTA` con punto dorado. Cache-bust `66→67`.
- `docs/COMENTARISTA_MIMO.md`, `.env.example`, `docs/operations/VARIABLES_ENTORNO.md`, `tests/test_comentarista.py`.

### Qué falta para producción (Ámsterdam)

El default actual apunta a **Singapur** (`token-plan-sgp`). En Alwaysdata conviene **Ámsterdam** (`token-plan-ams`) por latencia UE. Además, en algunos `.env` la variable viene como `MIMO_API_BASE` en vez de `MIMO_BASE_URL` — hay que aceptar ambas.

---

## 2) Parche de 4 líneas — `liga_maestros/services/ai/client.py`

Copia/pega exactamente. Es el único cambio de código necesario:

```diff
--- a/liga_maestros/services/ai/client.py
+++ b/liga_maestros/services/ai/client.py
-# Base del token plan de Xiaomi MiMo (sin /chat/completions). Mirrors:
-#   token-plan-sgp (Singapur) y token-plan-cn (China). Override con MIMO_BASE_URL.
-_MIMO_BASE_URL = os.getenv("MIMO_BASE_URL", "https://token-plan-sgp.xiaomimimo.com/v1").rstrip("/")
+# Base del token plan de Xiaomi MiMo (sin /chat/completions). Mirrors:
+#   token-plan-ams (Ámsterdam) | token-plan-sgp (Singapur) | token-plan-cn (China).
+#   Override con MIMO_API_BASE o MIMO_BASE_URL (alias).
+_MIMO_BASE_URL = os.getenv("MIMO_API_BASE", os.getenv("MIMO_BASE_URL", "https://token-plan-ams.xiaomimimo.com/v1")).rstrip("/")
```

Claves del parche:
- **Lee `MIMO_API_KEY`** (ya lo hacía) — no cambia `key_env`.
- **Acepta `MIMO_API_BASE` como alias principal**, con fallback a `MIMO_BASE_URL` para compatibilidad.
- **Default `https://token-plan-ams.xiaomimimo.com/v1`** (Ámsterdam).
- **Modelo** sigue siendo `mimo-v2.5-pro` (2 créditos/token) vía `MIMO_MODEL` — no tocar.

Después de aplicar, actualiza también la doc (3 ficheros, solo comentarios/ejemplos):

```ini
# .env.example y docs/COMENTARISTA_MIMO.md y docs/operations/VARIABLES_ENTORNO.md
# cambiar ejemplo/default de token-plan-sgp -> token-plan-ams
# y documentar que MIMO_API_BASE y MIMO_BASE_URL son alias
```

Si prefieres reaplicar todo sin editar a mano, en la próxima sesión di:

> "Aplica el parche ams a client.py: alias MIMO_API_BASE→MIMO_BASE_URL y default a https://token-plan-ams.xiaomimimo.com/v1, y actualiza la doc"

---

## 3) Los 2 puntos a revisar en `app.env` (Alwaysdata `.env`)

En Alwaysdata el fichero se llama `.env` (subido como `ENV_ALWAYSDATA.txt` renombrado). Añade/verifica **exactamente estas 2 líneas** (el resto ya está en la plantilla):

```ini
# 1) Activa IA + clave MiMo (token plan)
AI_NEWS_ENABLED=1
MIMO_API_KEY=tu_clave_real_del_token_plan   # <-- RELLENA, sin comillas

# 2) Espejo Ámsterdam (usa el alias que tengas; ambos valen)
MIMO_API_BASE=https://token-plan-ams.xiaomimimo.com/v1
# o alternativo:
MIMO_BASE_URL=https://token-plan-ams.xiaomimimo.com/v1
MIMO_MODEL=mimo-v2.5-pro
MIMO_COMENTARISTA_MIN_INTERVAL_SECONDS=600
```

Notas:
- Sin `MIMO_API_KEY` la web **funciona igual**, solo sin frases (best-effort).
- `MIMO_MODEL=mimo-v2.5-pro` (pro) o `mimo-v2.5` (1 crédito/token) según tu plan.
- `AI_DAILY_CALL_LIMIT=12` (tope duro compartido) y `MIMO_COMENTARISTA_MIN_INTERVAL_SECONDS=600` ya están en `.env.example`.
- Reinicia la app tras guardar `.env` (Alwaysdata → Web → Restart).

---

## 4) Cómo abrir el PR en la próxima sesión Arena (copia/pega)

**Opción A — Reabrir PR desde commit existente (más rápido):**
```
Revisa el commit e2e6935 de la rama arena/01a01551-liga-maestros-web y ábrelo como PR contra main.
Si el commit no está en shallow, haz git fetch --unshallow y búscalo como 51c8afc^2.
Aplica además el parche ams de 4 líneas de client.py (alias MIMO_API_BASE + default token-plan-ams) y actualiza la doc.
```

**Opción B — Parche directo (si no quieres buscar commits):**
```
En liga_maestros/services/ai/client.py cambia las 4 líneas del header MiMo:
- comentario mirrors a "token-plan-ams | token-plan-sgp | token-plan-cn"
- código a: _MIMO_BASE_URL = os.getenv("MIMO_API_BASE", os.getenv("MIMO_BASE_URL", "https://token-plan-ams.xiaomimimo.com/v1")).rstrip("/")
Actualiza .env.example, docs/COMENTARISTA_MIMO.md y docs/operations/VARIABLES_ENTORNO.md al espejo ams.
Commit y abre PR a main como "fix(mimo): espejo Ámsterdam + alias MIMO_API_BASE".
```

**Verificación tras deploy:**
```bash
# 1) Log debe mostrar "IA: respuesta obtenida de mimo" al haber LIVE
# 2) GET /api/liga/data debe traer {"comentarista":{"comentarios":[...],"generated":bool}}
# 3) Portada: banda "⚽ EN DIRECTO" debe intercalar "COMENTARISTA" con punto dorado
```

---

## 5) Referencias

- PR #75 body: `docs/COMENTARISTA_MIMO.md` + `COMENTARISTA_MIMO.md` + tests en `tests/test_comentarista.py`
- Ficheros tocados por PR #75: `client.py`, `comentarista.py`, `liga_data.py`, `schemas.py`, `cover_page.js`, `cover_hero.css`, `liga_index.html`, `navigation.js`
- Budget: `liga_maestros/services/ai/budget.py` (tope diario + cache por firma + cadencia 10min)

¿Siguiente paso? Si quieres, en esta misma sesión aplico el parche ams y lo dejo commiteado en `arena/01a0156f-liga-maestros-web` para que solo tengas que revisar `.env` en Alwaysdata.
