/* ==========================================================================
   QUANTUM FINAL — Init, refreshData, y funciones unicas.
   Todos los modulos (utils, state, logos, navigation, live, standings,
   contest, quiz, arena, events) se cargan ANTES que este archivo.
   ========================================================================== */

// --- refreshData: orquestacion principal de datos y render ---
let initialLoadAttempts = 0;
const INITIAL_LOAD_MAX_RETRIES = 4;

/* Reintentos de la carga inicial. Dos fallos del servidor son distintos y los
   dos se reintentan:
   - 503 cold_start: la jornada todavía se está poblando (backend).
   - 504 network_error: el service worker se rindió esperando (red/cuelgue).
   Antes solo se reintentaba el cold_start, así que cualquier respuesta lenta
   dejaba la página clavada en «No se pudo cargar la Arena» hasta recargar a
   mano, justo lo que se veía cuando el DIRECTO "no funcionaba" con partidos en
   juego. */
function ligaDataRetryDelay(response, attempt) {
    let retryAfter = NaN;
    if (response) {
        try {
            retryAfter = Number.parseInt(response.headers.get("Retry-After") || "", 10);
        } catch {
            retryAfter = NaN;
        }
    }
    if (Number.isFinite(retryAfter) && retryAfter > 0) {
        return Math.min(5000, Math.max(250, retryAfter * 1000));
    }
    return Math.min(5000, 600 * attempt);
}

function isRetryableLigaDataFailure(response, payload) {
    if (!response) return true;
    if (response.status !== 503 && response.status !== 504) return false;
    if (payload === null || payload === undefined) return true;
    return payload?.status === "cold_start"
        || payload?.code === "COLD_START"
        || payload?.status === "network_error"
        || payload?.retryable === true;
}

async function fetchLigaDataWithRetry(url) {
    const maxAttempts = 3;
    let lastResponse = null;
    for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
        let response;
        try {
            response = await fetch(url, { cache: "no-store" });
        } catch (networkError) {
            if (attempt === maxAttempts) throw networkError;
            await new Promise(resolve => window.setTimeout(resolve, ligaDataRetryDelay(null, attempt)));
            continue;
        }
        lastResponse = response;
        if (response.status !== 503 && response.status !== 504) return response;

        let payload = null;
        try {
            payload = await response.clone().json();
        } catch {
            // Keep the original response available to the caller below.
        }
        if (!isRetryableLigaDataFailure(response, payload) || attempt === maxAttempts) return response;
        await new Promise(resolve => window.setTimeout(resolve, ligaDataRetryDelay(response, attempt)));
    }
    return lastResponse || fetch(url, { cache: "no-store" });
}

async function refreshData(options = {}) {
    if (options.auto && Date.now() - state.lastUserEdit < 12000) return;
    const preserveLocalTicket = Boolean(options.auto && (state.editMode || state.draftDirty));
    const scrollState = options.auto ? {
        x: window.scrollX,
        y: window.scrollY,
        tableX: qs("matches-body")?.querySelector(".arena-table-wrap")?.scrollLeft || 0
    } : null;
    try {
        const isFirstPaint = !options.auto && !state.data;
        const userRequest = options.auto
            ? Promise.resolve(null)
            : fetch("/api/user/status");
        // Primera pintura: ?first=1 (~4 KB) solo con lo necesario para firmar.
        // Luego se completa en segundo plano con el payload completo.
        const dataUrl = isFirstPaint
            ? `/api/liga/data?first=1&j=${encodeURIComponent(state.jornada)}`
            : `/api/liga/data?j=${encodeURIComponent(state.jornada)}`;
        const [userRes, dataRes] = await Promise.all([
            userRequest,
            fetchLigaDataWithRetry(dataUrl)
        ]);
        if (userRes) {
            if (!userRes.ok) throw new Error(`User API ${userRes.status}`);
            const userPayload = await userRes.json();
            state.user = userPayload.user;
            state.csrfToken = userPayload.csrf_token || "";
        }
        if (!dataRes.ok) throw new Error(`Data API ${dataRes.status}`);
        state.data = await dataRes.json();
        initialLoadAttempts = 0;
        logoAliasIndex = null;
        logoCache.clear();
        state.jornada = String(state.data.jornada || state.jornada);
        if (typeof startLiveUpdates === "function") startLiveUpdates();
        // Completar payload en background tras la primera pintura.
        if (isFirstPaint && state.data?.first) {
            window.setTimeout(() => {
                refreshData({ auto: true, afterFirst: true }).catch(err =>
                    console.warn("Carga completa post-first fallida", err)
                );
            }, 50);
        }

        // 🎊 Welcome-back celebration for returning users
        if (!options.auto && state.user && hasSavedTicket() && state.draftDirty === false) {
            const done = state.my_signs.filter(s => s !== "-").length;
            if (done === 15 && typeof window.launchConfetti === "function") {
                setTimeout(() => {
                    window.launchConfetti({ count: 30, speed: 50, duration: 2000, origin: { x: 0.5, y: 0.15 } });
                }, 400);
            }
        }

        await ensureViewAssets(currentMainView());
        const patchedLiveView = Boolean(options.auto && state.currentFilter === "LIVE" && patchLiveArena());
        const patchedTicketView = Boolean(
            options.auto
            && state.currentFilter === "TICKET"
            && typeof patchTicketArena === "function"
            && patchTicketArena()
        );
        if (patchedLiveView || patchedTicketView) return;

        hydrateJornadaNav();
        hydrateUserSigns({ preserveLocalTicket });
        hydrateHero();
        updateAuthUI();
        renderArena();
        if (scrollState) {
            window.scrollTo(scrollState.x, scrollState.y);
            const table = qs("matches-body")?.querySelector(".arena-table-wrap");
            if (table) table.scrollLeft = scrollState.tableX;
        }
    } catch (error) {
        console.error(error);
        if (options.auto && state.data) {
            const now = Date.now();
            if (now - state.refreshErrorNotifiedAt > 60000) {
                showToast("No se pudo actualizar en segundo plano. Mantengo la ultima version cargada.", "error");
                state.refreshErrorNotifiedAt = now;
            }
            return;
        }
        const body = qs("matches-body");
        initialLoadAttempts += 1;
        if (!state.data && initialLoadAttempts <= INITIAL_LOAD_MAX_RETRIES) {
            if (body) {
                body.innerHTML = `<div class="empty-state">Cargando el directo&#8230; Reintentando (${initialLoadAttempts}/${INITIAL_LOAD_MAX_RETRIES}).</div>`;
            }
            window.setTimeout(() => {
                refreshData(options).catch(retryError => console.warn("Reintento de carga fallido", retryError));
            }, 2000 * initialLoadAttempts);
            return;
        }
        if (body) {
            const status = error?.status || error?.response?.status;
            const message = error?.message || error?.statusText || "Error desconocido";
            body.innerHTML = `<div class="empty-state">No se pudo cargar el directo (HTTP ${status || "?"}). ${escapeHtml(message)}. <button class="direct-empty-action" type="button" data-reload-arena="1">Reintentar ahora</button></div>`;
            body.querySelector("[data-reload-arena]")?.addEventListener("click", () => {
                initialLoadAttempts = 0;
                refreshData(options).catch(retryError => console.warn("Reintento manual fallido", retryError));
            });
        }
    }
}
