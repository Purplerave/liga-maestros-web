/* ==========================================================================
   NAVIGATION — Cambio de vistas, filtros, URL state, navegación secondary.
   Dependencias: utils.js, logos.js, state.js
   ========================================================================== */

function versionedAsset(path, tag) {
    const version = document.body.dataset.assetsV || "dev";
    return `${path}?v=${encodeURIComponent(version)}-${tag}`;
}

const VIEW_STYLES = {
    CONTEST: [
        ["view-contest-styles", versionedAsset("/static/css/pages/contest.css", "contest-3")],
        ["view-profile-styles", versionedAsset("/static/css/pages/profile.css", "profile-3")],
    ],
    STANDINGS: [["view-standings-styles", versionedAsset("/static/css/pages/standings.css", "standings-2")]],
    LIVE: [
        ["view-match-card-styles", versionedAsset("/static/css/components/match_cards.css", "matches-3")],
        ["view-direct-styles", versionedAsset("/static/css/pages/direct.css", "direct-2")],
    ],
    LEAGUES: [
        ["view-match-card-styles", versionedAsset("/static/css/components/match_cards.css", "matches-3")],
        ["view-direct-styles", versionedAsset("/static/css/pages/direct.css", "direct-2")],
    ],
    SNAKE: [["view-games-styles", versionedAsset("/static/css/pages/games.css", "games-5")]],
    QUIZ: [["view-quiz-styles", versionedAsset("/static/css/pages/quiz_page.css", "quiz-page-2")]],
    TICKET: [
        ["view-ticket-styles", versionedAsset("/static/css/pages/ticket.css", "ticket-2")],
        ["view-ticket-compact-styles", versionedAsset("/static/css/pages/ticket_compact.css", "ticket-compact-4")],
        ["view-pleno-modal-styles", versionedAsset("/static/css/components/pleno_modal.css", "pleno-modal-1")],
    ],
};

const VIEW_SCRIPTS = {
    ALL: [["view-cover-script", versionedAsset("/static/js/pages/cover_page.js", "cover-page-21")]],
    CONTEST: [["view-contest-script", versionedAsset("/static/js/contest.js", "contest-4")]],
    STANDINGS: [["view-standings-script", versionedAsset("/static/js/standings.js", "standings-2")]],
    SNAKE: [["view-games-script", versionedAsset("/static/js/pages/games_hub.js", "games-hub-10")]],
    QUIZ: [["view-quiz-script", versionedAsset("/static/js/quiz.js", "quiz-2")]],
    TICKET: [
        ["view-ticket-script", versionedAsset("/static/js/pages/ticket_page.js", "ticket-page-3")],
        ["view-pleno-modal-script", versionedAsset("/static/js/components/pleno_modal.js", "pleno-modal-1")],
    ],
};

function loadStylesheetOnce(id, href) {
    return new Promise((resolve, reject) => {
        const existing = document.getElementById(id);
        if (existing) {
            if (existing.dataset.loaded === "true") resolve();
            else {
                existing.addEventListener("load", resolve, { once: true });
                existing.addEventListener("error", reject, { once: true });
            }
            return;
        }
        const link = document.createElement("link");
        link.id = id;
        link.rel = "stylesheet";
        link.href = href;
        link.addEventListener("load", () => {
            link.dataset.loaded = "true";
            resolve();
        }, { once: true });
        link.addEventListener("error", reject, { once: true });
        document.head.appendChild(link);
    });
}

function loadScriptOnce(id, src) {
    return new Promise((resolve, reject) => {
        const existing = document.getElementById(id);
        if (existing) {
            if (existing.dataset.loaded === "true") resolve();
            else {
                existing.addEventListener("load", resolve, { once: true });
                existing.addEventListener("error", reject, { once: true });
            }
            return;
        }
        const script = document.createElement("script");
        script.id = id;
        script.src = src;
        script.async = true;
        script.addEventListener("load", () => {
            script.dataset.loaded = "true";
            resolve();
        }, { once: true });
        script.addEventListener("error", reject, { once: true });
        document.body.appendChild(script);
    });
}

function ensureViewStyles(view = currentMainView()) {
    return Promise.all((VIEW_STYLES[view] || []).map(([id, href]) => loadStylesheetOnce(id, href)));
}

function ensureViewScripts(view = currentMainView()) {
    return Promise.all((VIEW_SCRIPTS[view] || []).map(([id, src]) => loadScriptOnce(id, src)));
}

function ensureViewAssets(view = currentMainView()) {
    return Promise.all([ensureViewStyles(view), ensureViewScripts(view)]);
}

function changeJornada(jornada) {
    persistDraft();
    state.jornada = jornada;
    state.contest = null;
    state.contestJornada = "";
    state.q15Directo = {};
    state.q15DirectoJornada = "";
    syncUrlState();
    refreshData();
}

function currentMainView() {
    if (state.contestView !== "MATCHES") return "CONTEST";
    if (String(state.currentFilter || "").startsWith("STANDINGS_")) return "STANDINGS";
    if (state.currentFilter === "LIVE") return "LIVE";
    if (state.currentFilter === "SNAKE_PAGE") return "SNAKE";
    if (state.currentFilter === "QUIZ_PAGE") return "QUIZ";
    if (state.currentFilter === "TICKET") return "TICKET";
    if (state.currentFilter && state.currentFilter !== "ALL") return "LEAGUES";
    return "ALL";
}

async function changeMainView(view) {
    const target = view || "ALL";
    await ensureViewAssets(target);
    state.newspaperPage = target;
    hydrateNewspaperPageNav(target);
    if (target === "CONTEST") {
        state.currentFilter = "ALL";
        state.contestView = "CONTEST_GENERAL";
    } else if (target === "STANDINGS") {
        state.currentFilter = "STANDINGS_PRIMERA";
        state.contestView = "MATCHES";
    } else if (target === "LIVE") {
        state.currentFilter = "LIVE";
        state.contestView = "MATCHES";
    } else if (target === "TICKET") {
        state.currentFilter = "TICKET";
        state.contestView = "MATCHES";
    } else if (target === "LEAGUES") {
        const leagues = getAvailableLeagueOptions();
        state.currentFilter = leagues[0]?.[0] || "LIVE";
        state.contestView = "MATCHES";
    } else {
        state.currentFilter = "ALL";
        state.contestView = "MATCHES";
    }
    syncUrlState();
    renderArena();
    hydrateHero();
}

function hydrateNewspaperPageNav(activePage = state.newspaperPage) {
    document.querySelectorAll("[data-page-action]").forEach(button => {
        button.classList.toggle("active", button.dataset.pageAction === activePage);
    });
}

async function openNewspaperPage(page) {
    const target = page || "ALL";
    await ensureViewAssets(target);
    state.newspaperPage = target;
    hydrateNewspaperPageNav(target);
    if (target === "SNAKE") {
        state.currentFilter = "SNAKE_PAGE";
        state.contestView = "MATCHES";
        syncUrlState();
        renderArena();
        return;
    }
    if (target === "QUIZ") {
        state.currentFilter = "QUIZ_PAGE";
        state.contestView = "MATCHES";
        syncUrlState();
        renderArena();
        return;
    }
    await changeMainView(target);
}

async function openProfileView() {
    await ensureViewAssets("CONTEST");
    state.contestView = "CONTEST_PROFILE";
    state.newspaperPage = "CONTEST";
    syncUrlState();
    renderArena();
    hydrateHero();
}

function changeAwardJornada(value) {
    state.selectedAwardJornada = value || "";
    renderArena();
}

function changeAwardMonth(value) {
    state.selectedAwardMonth = value || "";
    renderArena();
}

function syncUrlState() {
    try {
        const url = new URL(window.location.href);
        if (state.jornada) url.searchParams.set("j", state.jornada);
        if (state.currentFilter && state.currentFilter !== "ALL") url.searchParams.set("view", state.currentFilter);
        else url.searchParams.delete("view");
        if (state.contestView && state.contestView !== "MATCHES") url.searchParams.set("contest", state.contestView);
        else url.searchParams.delete("contest");
        window.history.replaceState({}, "", url.toString());
    } catch {}
}

function getAvailableLeagueOptions() {
    const allMatches = getBrowsableLeagueMatches();
    const counts = allMatches.reduce((acc, match) => {
        const key = competitionLabel(match);
        acc[key] = (acc[key] || 0) + 1;
        return acc;
    }, {});
    return Object.keys(counts)
        .sort((a, b) => a.localeCompare(b))
        .map(key => [key, `${key.replaceAll("_", " ")} (${counts[key]})`]);
}
