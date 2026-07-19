/* ==========================================================================
   EVENTS — Bindings de eventos y inicializacion DOMContentLoaded.
   Dependencias: todos los modulos anteriores.
   ========================================================================== */


function bindEvents() {
    qs("jornada-nav")?.addEventListener("change", event => changeJornada(event.target.value));
    qs("warroom-btn")?.addEventListener("click", () => {
        filterLeague(state.currentFilter === "WAR_ROOM" ? "ALL" : "WAR_ROOM");
    });
    qs("refresh-btn")?.addEventListener("click", refreshData);
    qs("save-quiniela-btn")?.addEventListener("click", savePredictions);
    qs("share-ticket-btn")?.addEventListener("click", shareTicket);
    document.querySelectorAll("[data-page-action]").forEach(button => {
        button.addEventListener("click", () => openNewspaperPage(button.dataset.pageAction));
    });
    document.addEventListener("submit", event => {
        if (event.target.matches("[data-porra-form]")) submitPorra(event);
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
            openPlenoModal(idx);
            return;
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
        const liveSignature = data => [...(data?.partidos || []), ...(data?.all_league_matches || [])]
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
        logoDataIndex = null;
        logoCache.clear();
        const hasLive = hasLiveLeagueMatches();
        if (!hadLive && !hasLive) return;
        if (previousSignature === nextSignature) return;
        if (state.currentFilter === "LIVE" && patchLiveArena()) return;
        if (state.currentFilter === "TICKET" && patchTicketArena()) return;
        const pageX = window.scrollX;
        const pageY = window.scrollY;
        const tableScroll = qs("matches-body")?.querySelector(".arena-table-wrap")?.scrollLeft || 0;
        updateWarRoomButton();
        hydrateHero();
        renderArena();
        window.scrollTo(pageX, pageY);
        const nextTable = qs("matches-body")?.querySelector(".arena-table-wrap");
        if (nextTable) nextTable.scrollLeft = tableScroll;
        if (shouldRefreshSideModules()) renderLiveStandings();
        loadPorra();
    } catch (error) {
        console.warn("No se pudo refrescar el directo", error);
    }
}


document.addEventListener("DOMContentLoaded", () => {
    hydrateCommentsPanel();
    bindEvents();
    refreshData();
    let autoRefreshId = setInterval(() => {
        refreshData({ auto: true });
    }, 60000);
    let liveRefreshId = setInterval(refreshLiveSnapshot, 30000);
    document.addEventListener("visibilitychange", () => {
        if (document.hidden) {
            clearInterval(autoRefreshId);
            clearInterval(liveRefreshId);
            autoRefreshId = null;
            liveRefreshId = null;
        } else if (!autoRefreshId) {
            refreshLiveSnapshot();
            autoRefreshId = setInterval(() => {
                refreshData({ auto: true });
            }, 60000);
            liveRefreshId = setInterval(refreshLiveSnapshot, 30000);
        }
    });
});
