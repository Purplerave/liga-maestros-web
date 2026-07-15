/* ==========================================================================
   EVENTS — Bindings de eventos y inicializacion DOMContentLoaded.
   Dependencias: todos los modulos anteriores.
   ========================================================================== */


function bindEvents() {
    qs("warroom-btn")?.addEventListener("click", () => {
        filterLeague(state.currentFilter === "WAR_ROOM" ? "ALL" : "WAR_ROOM");
    });
    qs("refresh-btn")?.addEventListener("click", refreshData);
    qs("save-quiniela-btn")?.addEventListener("click", savePredictions);
    qs("share-ticket-btn")?.addEventListener("click", shareTicket);
    document.querySelectorAll("[data-page-action]").forEach(button => {
        button.addEventListener("click", () => openNewspaperPage(button.dataset.pageAction));
    });
    qs("porra-body")?.addEventListener("submit", event => {
        if (event.target.id === "porra-form") submitPorra(event);
    });
    qs("comment-form")?.addEventListener("submit", submitComment);
    document.querySelector(".comments-panel-side .panel-head")?.addEventListener("click", () => {
        setCommentsOpen(!state.commentsOpen);
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
        const btn = event.target.closest(".clickable");
        if (!btn) return;
        if (!state.user) return showToast("Entra con Google para jugar.", "error");
        if (!state.data || String(state.data.jornada) !== String(state.data.max_jornada) || state.data.is_locked) {
            return showToast("Jornada bloqueada.", "error");
        }
        const idx = Number.parseInt(btn.dataset.matchIdx || btn.closest("[data-match-idx]").dataset.matchIdx, 10);
        if (Number.isNaN(idx)) return;
        if (btn.dataset.pleno) {
            const value = window.prompt("Resultado del pleno al 15", state.my_signs[idx] === "-" ? "0-0" : state.my_signs[idx]);
            if (value) state.my_signs[idx] = value.trim();
        } else {
            state.my_signs[idx] = state.my_signs[idx] === btn.dataset.sign ? "-" : btn.dataset.sign;
        }
        state.lastUserEdit = Date.now();
        state.draftDirty = true;
        persistDraft();
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
    document.addEventListener("click", event => {
        const tab = event.target.closest("[data-league-tab]");
        if (!tab) return;
        const targetId = tab.dataset.leagueTab;
        document.querySelectorAll("[data-league-tab]").forEach(btn => btn.classList.remove("active"));
        document.querySelectorAll(".league-standings-pane").forEach(p => p.classList.remove("active"));
        tab.classList.add("active");
        const pane = qs("league-standings-" + targetId);
        if (pane) pane.classList.add("active");
    });
}


document.addEventListener("DOMContentLoaded", () => {
    hydrateCommentsPanel();
    bindEvents();
    refreshData();
    let autoRefreshId = setInterval(() => {
        refreshData({ auto: true });
    }, 120000);
    document.addEventListener("visibilitychange", () => {
        if (document.hidden) {
            clearInterval(autoRefreshId);
            autoRefreshId = null;
        } else if (!autoRefreshId) {
            autoRefreshId = setInterval(() => {
                refreshData({ auto: true });
            }, 120000);
        }
    });
});
