/* ==========================================================================
   EVENTS — Bindings de eventos y inicializacion DOMContentLoaded.
   Dependencias: todos los modulos anteriores.
   ========================================================================== */


/* ──────────────────────────────────────────
   MICRO-INTERACCIONES GLOBALES
   ────────────────────────────────────────── */

function rippleHandler(event) {
    const btn = event.currentTarget;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    if (btn.dataset.noRipple === 'true') return;
    const rect = btn.getBoundingClientRect();
    const size = Math.max(rect.width, rect.height) * 1.2;
    const x = event.clientX - rect.left - size / 2;
    const y = event.clientY - rect.top - size / 2;
    const ripple = document.createElement('span');
    ripple.className = 'ripple-effect';
    ripple.style.cssText = `
        width: ${size}px;
        height: ${size}px;
        left: ${x}px;
        top: ${y}px;
    `;
    btn.style.position = 'relative';
    btn.style.overflow = 'hidden';
    btn.appendChild(ripple);
    ripple.addEventListener('animationend', () => ripple.remove());
}

function addRippleToButtons() {
    document.querySelectorAll('.primary-btn, .icon-btn, .cp-primary, .cp-secondary, .tab-btn, [data-page-action]').forEach(btn => {
        if (!btn.dataset.rippleAdded) {
            btn.addEventListener('mousedown', rippleHandler);
            btn.dataset.rippleAdded = 'true';
        }
    });
}

function sparkleHoverHandler(event) {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    if (typeof window.sparkleAt !== 'function') return;
    const target = event.currentTarget;
    if (target.dataset.sparkleDisabled) return;
    const rect = target.getBoundingClientRect();
    window.sparkleAt(
        rect.left + rect.width * 0.8,
        rect.top + rect.height * 0.3,
        target.dataset.sparkleColor || '#fbbf24'
    );
}

function addSparkleToElements() {
    document.querySelectorAll('.cp-primary, .cp-secondary, .primary-btn#save-quiniela-btn, .tension-row .clickable').forEach(el => {
        if (!el.dataset.sparkleAdded) {
            el.addEventListener('mouseenter', sparkleHoverHandler);
            el.dataset.sparkleAdded = 'true';
        }
    });
}

function initMicroInteractions() {
    addRippleToButtons();
    addSparkleToElements();
    // Re-aplicar cuando cambie el contenido del DOM
    const observer = new MutationObserver(() => {
        addRippleToButtons();
        addSparkleToElements();
    });
    observer.observe(document.getElementById('matches-body') || document.body, {
        childList: true,
        subtree: true
    });
}

function bindEvents() {
    qs("jornada-nav")?.addEventListener("change", event => changeJornada(event.target.value));
qs("refresh-btn")?.addEventListener("click", refreshData);
    qs("save-quiniela-btn")?.addEventListener("click", savePredictions);
    qs("cmdk-trigger")?.addEventListener("click", () => window.CommandPalette?.open());
    qs("share-ticket-btn")?.addEventListener("click", shareTicket);
    qs("share-sheet")?.addEventListener("click", event => {
        if (event.target.closest("[data-share-close]")) {
            closeShareSheet();
            return;
        }
        const action = event.target.closest("[data-share-action]");
        if (action) runShareAction(action.dataset.shareAction);
    });
    document.addEventListener("keydown", event => {
        if (event.key === "Escape") closeShareSheet();
    });
    // Las pestañas fijas están fuera de matches-body; las acciones que se
    // pintan dentro de las vistas se resuelven con el listener delegado.
    document.querySelectorAll("[data-page-action]").forEach(button => {
        if (!button.closest("#matches-body")) {
            button.addEventListener("click", event => {
                event.preventDefault();
                openNewspaperPage(button.dataset.pageAction);
            });
        }
    });
    document.addEventListener("submit", event => {
        if (event.target.matches("[data-porra-form]")) submitPorra(event);
    });
    qs("matches-body")?.addEventListener("click", event => {
        const pageBtn = event.target.closest("[data-page-action]");
        if (pageBtn) {
            openNewspaperPage(pageBtn.dataset.pageAction);
            return;
        }
        const radarBtn = event.target.closest("[data-radar-match]");
        if (radarBtn) {
            const idx = Number.parseInt(radarBtn.dataset.radarMatch, 10);
            if (Number.isNaN(idx)) return;
            state.expandedMatch = state.expandedMatch === idx ? null : idx;
            renderArena();
            return;
        }
        const detailBtn = event.target.closest("[data-detail-toggle]");
        if (detailBtn) {
            const idx = Number.parseInt(detailBtn.dataset.matchIdx, 10);
            if (Number.isNaN(idx)) return;
            state.expandedMatch = state.expandedMatch === idx ? null : idx;
            renderArena();
            return;
        }
        const contestView = event.target.closest("[data-contest-view]");
        if (contestView) {
            state.contestView = contestView.dataset.contestView;
            state.currentFilter = "ALL";
            state.newspaperPage = "CONTEST";
            syncUrlState();
            renderArena();
            return;
        }
        const monthBtn = event.target.closest("[data-month]");
        if (monthBtn) {
            changeContestMonth(monthBtn.dataset.month);
            return;
        }
        const jornadaBtn = event.target.closest("[data-contest-jornada]");
        if (jornadaBtn) {
            changeContestJornada(jornadaBtn.dataset.contestJornada);
            return;
        }
        const btn = event.target.closest(".clickable");
        if (!btn) return;
        if (!state.user) return showToast("Entra con Google para jugar.", "error");
        if (!state.data || String(state.data.jornada) !== String(state.data.max_jornada) || state.data.is_locked) {
            return showToast("Jornada bloqueada.", "error");
        }
        const idx = Number.parseInt(btn.dataset.matchIdx || btn.closest("[data-match-idx]")?.dataset.matchIdx, 10);
        if (Number.isNaN(idx)) return;
        if (btn.dataset.pleno) {
            openPlenoModal(idx);
            return;
        } else {
            state.my_signs[idx] = state.my_signs[idx] === btn.dataset.sign ? "-" : btn.dataset.sign;
        }
        state.lastUserEdit = Date.now();
        state.draftDirty = true;
        persistDraft();
        if (typeof checkQuinielaCompletion === "function") checkQuinielaCompletion();
        hydrateHero();
        renderArena();
    });
    document.querySelectorAll(".tab-btn[data-standings]").forEach(button => {
        button.addEventListener("click", () => {
            document.querySelectorAll(".tab-btn[data-standings]").forEach(btn => btn.classList.remove("active"));
            document.querySelectorAll(".standings-pane").forEach(pane => pane.classList.remove("active"));
            button.classList.add("active");
            qs(button.dataset.standings).classList.add("active");
        });
    });
    document.addEventListener("change", event => {
        const selector = event.target.closest("[data-porra-match]");
        if (!selector || typeof loadPorra !== "function") return;
        loadPorra(selector.value);
    });
    document.addEventListener("click", event => {
        const porraSubmit = event.target.closest("[data-porra-submit]");
        if (porraSubmit) {
            submitPorra(event);
            return;
        }
        if (event.target.closest("[data-open-profile]")) {
            openProfileView();
            return;
        }
        if (event.target.closest("[data-close-game]")) {
            closeActiveGame();
            return;
        }
        const expandContest = event.target.closest("[data-contest-expand]");
        if (expandContest) {
            const target = qs(expandContest.dataset.contestExpand);
            if (!target) return;
            const expanded = target.classList.toggle("is-visible");
            expandContest.setAttribute("aria-expanded", String(expanded));
            expandContest.textContent = expanded ? "Ocultar" : "Ver todos";
            return;
        }
        const tab = event.target.closest("[data-league-tab]");
        if (!tab) return;
        const targetId = tab.dataset.leagueTab;
        document.querySelectorAll("[data-league-tab]").forEach(btn => btn.classList.remove("active"));
        document.querySelectorAll(".league-standings-pane").forEach(p => p.classList.remove("active"));
        tab.classList.add("active");
        const pane = qs("league-standings-" + targetId);
        if (pane) pane.classList.add("active");
    });
    document.addEventListener("change", event => {
        if (event.target.matches("[data-award-jornada]")) changeAwardJornada(event.target.value);
        if (event.target.matches("[data-award-month]")) changeAwardMonth(event.target.value);
    });
    document.addEventListener("keydown", event => {
        if ((event.key === "Enter" || event.key === " ") && event.target.matches("[data-open-profile][role='button']")) {
            event.preventDefault();
            openProfileView();
        }
    });
}

async function refreshLiveSnapshot() {
    if (!state.data || document.hidden) return;
    try {
        const liveSignature = data => [
            ...(data?.partidos || []),
            ...(data?.all_league_matches || []),
            ...(data?.live_matches || [])
        ]
            .filter(match => isLiveStatus(match.status) || isLiveMatch(match))
            .map(match => [
                matchPairKey(match),
                String(match.status || ""),
                String(match.minuto || match.time || ""),
                scoreOnly(match.marcador || match.score || match.scores?.score || "")
            ].join(":"))
            .sort()
            .join("|");
        const previousSignature = liveSignature(state.data);
        const response = await fetch(`/api/liga/data?j=${encodeURIComponent(state.jornada)}`, { cache: "no-store" });
        if (!response.ok) return;
        const freshData = await response.json();
        if (String(freshData.jornada || "") !== String(state.jornada || "")) return;
        const hadLive = hasLiveLeagueMatches();
        const nextSignature = liveSignature(freshData);
        state.data = freshData;
        logoAliasIndex = null;
        logoCache.clear();
        const hasLive = hasLiveLeagueMatches();
        if (!hadLive && !hasLive) return;
        if (previousSignature === nextSignature) return;
        if (state.currentFilter === "LIVE" && patchLiveArena()) return;
        if (state.currentFilter === "TICKET" && patchTicketArena()) return;
        const pageX = window.scrollX;
        const pageY = window.scrollY;
        const tableScroll = qs("matches-body")?.querySelector(".arena-table-wrap")?.scrollLeft || 0;
        hydrateHero();
        renderArena();
        window.scrollTo(pageX, pageY);
        const nextTable = qs("matches-body")?.querySelector(".arena-table-wrap");
        if (nextTable) nextTable.scrollLeft = tableScroll;
        loadPorra();
    } catch (error) {
        console.warn("No se pudo refrescar el directo", error);
    }
}


document.addEventListener("DOMContentLoaded", async () => {
    bindEvents();
    initMicroInteractions();
    try { window.CommandPalette?.init(); } catch (error) { console.warn("[cmdk] init fallido", error); }
    try { window.UXSignals?.init(); } catch (error) { console.warn("[ux] init fallido", error); }
    await refreshData();
    startLiveUpdates();
    showWelcomeOnboarding();
    document.addEventListener("visibilitychange", () => {
        if (document.hidden) {
            stopLiveUpdates();
        } else {
            startLiveUpdates();
        }
    });
});

let liveSSE = null;
let liveRefreshTimer = null;
let liveTransportKey = "";

function livePollDelay() {
    return hasLiveLeagueMatches() ? 30000 : 120000;
}

function scheduleLivePoll(delay = livePollDelay()) {
    if (liveRefreshTimer) window.clearTimeout(liveRefreshTimer);
    if (document.hidden) {
        liveRefreshTimer = null;
        return;
    }
    liveRefreshTimer = window.setTimeout(async () => {
        liveRefreshTimer = null;
        await refreshLiveSnapshot();
        scheduleLivePoll();
    }, delay);
}

function startLivePolling() {
    stopLiveSSE();
    scheduleLivePoll();
}

function startLiveUpdates() {
    const jornada = String(state.data?.jornada || "");
    if (!jornada || document.hidden) return;
    const useSSE = Boolean(state.data?.live_stream_enabled && "EventSource" in window);
    const nextKey = `${jornada}:${useSSE ? "sse" : "poll"}`;
    if (liveTransportKey === nextKey && (liveSSE || liveRefreshTimer)) return;

    stopLiveUpdates();
    liveTransportKey = nextKey;
    if (useSSE) {
        startLiveSSE(jornada);
    } else {
        startLivePolling();
    }
}

function startLiveSSE(jornada) {
    const url = `/api/live/stream?j=${encodeURIComponent(jornada)}`;
    try {
        liveSSE = new EventSource(url);
        liveSSE.addEventListener("message", (event) => {
            try {
                const data = JSON.parse(event.data);
                if (data.type === "live_update" && data.matches) {
                    const hadLive = hasLiveLeagueMatches();
                    state.data = { ...state.data, partidos: mergeLiveData(state.data.partidos, data.matches) };
                    logoAliasIndex = null;
                    logoCache.clear();
                    const hasLive = hasLiveLeagueMatches();
                    if (!hadLive && !hasLive) return;
                    if (state.currentFilter === "LIVE" && patchLiveArena()) return;
                    if (state.currentFilter === "TICKET" && patchTicketArena()) return;
                    hydrateHero();
                    renderArena();
                    loadPorra();
                }
            } catch {
                // A malformed event must not stop future live updates.
            }
        });
        liveSSE.onerror = () => {
            // Degrade once to bounded polling instead of reconnecting forever.
            startLivePolling();
            liveTransportKey = `${jornada}:poll`;
        };
    } catch {
        startLivePolling();
        liveTransportKey = `${jornada}:poll`;
    }
}

function stopLiveSSE() {
    if (liveSSE) {
        liveSSE.close();
        liveSSE = null;
    }
}

function stopLiveUpdates() {
    stopLiveSSE();
    if (liveRefreshTimer) {
        window.clearTimeout(liveRefreshTimer);
        liveRefreshTimer = null;
    }
    liveTransportKey = "";
}

function mergeLiveData(partidos, liveMatches) {
    if (!partidos || !liveMatches) return partidos || [];
    const liveMap = new Map();
    liveMatches.forEach((m) => {
        const key = `${m.local}|${m.visitante}`;
        liveMap.set(key, m);
    });
    return partidos.map((p) => {
        const key = `${p.local || ""}|${p.visitante || ""}`;
        const live = liveMap.get(key);
        if (live) {
            return { ...p, status: live.status, minuto: live.minuto };
        }
        return p;
    });
}
