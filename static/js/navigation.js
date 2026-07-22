/* ==========================================================================
   NAVIGATION — Cambio de vistas, filtros, URL state, navegación secondary.
   Dependencias: utils.js, logos.js, state.js
   ========================================================================== */

function changeJornada(jornada) {
    persistDraft();
    state.jornada = jornada;
    syncUrlState();
    refreshData();
}

function filterLeague(league) {
    state.currentFilter = !league || league === "MATCHES" ? "ALL" : league;
    state.contestView = "MATCHES";
    state.newspaperPage = state.currentFilter === "LIVE" ? "LIVE" : state.currentFilter === "ALL" ? "ALL" : "LEAGUES";
    syncUrlState();
    renderArena();
    loadLeagueNav();
    hydrateContestNav();
    hydrateStandingsNav();
    updateWarRoomButton();
}

function currentMainView() {
    if (state.contestView !== "MATCHES") return "CONTEST";
    if (String(state.currentFilter || "").startsWith("STANDINGS_")) return "STANDINGS";
    if (state.currentFilter === "LIVE" || state.currentFilter === "WAR_ROOM") return "LIVE";
    if (state.currentFilter === "SNAKE_PAGE") return "SNAKE";
    if (state.currentFilter === "QUIZ_PAGE") return "QUIZ";
    if (state.currentFilter === "TICKET") return "TICKET";
    if (state.currentFilter && state.currentFilter !== "ALL") return "LEAGUES";
    return "ALL";
}

function changeMainView(view) {
    const target = view || "ALL";
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
    loadLeagueNav();
    updateWarRoomButton();
}

function hydrateNewspaperPageNav(activePage = state.newspaperPage) {
    document.querySelectorAll("[data-page-action]").forEach(button => {
        button.classList.toggle("active", button.dataset.pageAction === activePage);
    });
}

function focusNewspaperPanel(selector) {
    const panel = document.querySelector(selector);
    if (!panel) return;
    panel.classList.add("paper-focus");
    panel.scrollIntoView({ behavior: "smooth", block: "center", inline: "nearest" });
    window.setTimeout(() => panel.classList.remove("paper-focus"), 1800);
}

function openNewspaperPage(page) {
    const target = page || "ALL";
    state.newspaperPage = target;
    hydrateNewspaperPageNav(target);
    if (target === "SNAKE") {
        state.currentFilter = "SNAKE_PAGE";
        state.contestView = "MATCHES";
        syncUrlState();
        renderArena();
        loadLeagueNav();
        return;
    }
    if (target === "QUIZ") {
        state.currentFilter = "QUIZ_PAGE";
        state.contestView = "MATCHES";
        syncUrlState();
        renderArena();
        loadLeagueNav();
        updateWarRoomButton();
        return;
    }
    changeMainView(target);
}

function changeSecondaryView(value) {
    if (!value) return;
    if (String(value).startsWith("CONTEST_")) {
        changeContestView(value);
        return;
    }
    if (String(value).startsWith("STANDINGS_")) {
        changeStandingsView(value);
        return;
    }
    filterLeague(value);
}

function goHome() {
    state.currentFilter = "ALL";
    state.contestView = "MATCHES";
    state.newspaperPage = "ALL";
    syncUrlState();
    renderArena();
    hydrateHero();
    loadLeagueNav();
    hydrateContestNav();
    hydrateStandingsNav();
    updateWarRoomButton();
}

function changeContestView(view) {
    state.contestView = view || "MATCHES";
    if (state.contestView !== "MATCHES") {
        state.currentFilter = "ALL";
        state.newspaperPage = "CONTEST";
    }
    syncUrlState();
    renderArena();
    hydrateHero();
    loadLeagueNav();
    hydrateContestNav();
    hydrateStandingsNav();
    updateWarRoomButton();
}

function changeStandingsView(view) {
    if (!view || view === "MATCHES") {
        goHome();
        return;
    }
    state.currentFilter = view || "ALL";
    state.contestView = "MATCHES";
    state.newspaperPage = "STANDINGS";
    syncUrlState();
    renderArena();
    loadLeagueNav();
    hydrateContestNav();
    hydrateStandingsNav();
    updateWarRoomButton();
}

function openProfileView() {
    state.contestView = "CONTEST_PROFILE";
    state.newspaperPage = "CONTEST";
    if (state.currentFilter === "WAR_ROOM") state.currentFilter = "ALL";
    syncUrlState();
    renderArena();
    hydrateHero();
    loadLeagueNav();
    hydrateContestNav();
    updateWarRoomButton();
}

function openAwardsView() {
    state.contestView = "CONTEST_AWARDS";
    state.newspaperPage = "CONTEST";
    if (state.currentFilter === "WAR_ROOM") state.currentFilter = "ALL";
    syncUrlState();
    renderArena();
    hydrateHero();
    loadLeagueNav();
    hydrateContestNav();
    updateWarRoomButton();
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

function hydrateMainViewNav() {
    const nav = qs("league-nav");
    if (!nav) return;
    const options = [
        ["ALL", "Portada"],
        ["TICKET", "La Quiniela"],
        ["LIVE", `Directo (${getLiveLeagueMatches().length})`],
        ["LEAGUES", "Ligas"],
        ["CONTEST", "La Peña"],
        ["STANDINGS", "Primera / Segunda"]
    ];
    const selected = currentMainView();
    nav.innerHTML = options.map(([value, label]) =>
        `<option value="${escapeHtml(value)}" ${selected === value ? "selected" : ""}>${escapeHtml(label)}</option>`
    ).join("");
}

function getAvailableLeagueOptions() {
    const allMatches = state.data?.all_league_matches || [];
    const counts = allMatches.reduce((acc, match) => {
        const key = competitionLabel(match);
        acc[key] = (acc[key] || 0) + 1;
        return acc;
    }, {});
    return Object.keys(counts)
        .sort((a, b) => a.localeCompare(b))
        .map(key => [key, `${key.replaceAll("_", " ")} (${counts[key]})`]);
}

function hydrateSecondaryNav() {
    const nav = qs("contest-nav");
    if (!nav) return;
    const group = nav.closest(".field-group");
    const leagueNav = qs("league-nav");
    const filters = leagueNav?.closest(".topbar-filters");
    if (!group || !filters) return;
    const main = currentMainView();
    let options = [];
    let selected = "";
    let placeholder = "Detalle";

    if (main === "CONTEST") {
        placeholder = "La Peña";
        selected = state.contestView;
        options = [
            ["CONTEST_PROFILE", "👤 Mi perfil"],
            ["CONTEST_GENERAL", "🏆 General"],
            ["CONTEST_MONTHLY", "📅 Mensual"],
            ["CONTEST_JORNADA", "⚡ Jornada"],
            ["CONTEST_HISTORY", "📊 Histórico"],
            ["CONTEST_AWARDS", "🎖️ Galardones"]
        ];
    } else if (main === "STANDINGS") {
        placeholder = "Clasificación";
        selected = state.currentFilter;
        options = [
            ["STANDINGS_PRIMERA", "Primera"],
            ["STANDINGS_SEGUNDA", "Segunda"]
        ];
    } else if (main === "LEAGUES") {
        placeholder = "Liga";
        selected = state.currentFilter;
        options = getAvailableLeagueOptions();
    }

    const hasOptions = options.length > 0;
    group.classList.toggle("is-hidden", !hasOptions);
    filters.classList.toggle("has-secondary", hasOptions);
    if (!hasOptions) {
        nav.innerHTML = "";
        return;
    }
    nav.innerHTML = [
        `<option value="" disabled hidden>${escapeHtml(placeholder)}</option>`,
        ...options.map(([value, label]) =>
            `<option value="${escapeHtml(value)}" ${selected === value ? "selected" : ""}>${escapeHtml(label)}</option>`
        )
    ].join("");
    if (options.some(([value]) => value === selected)) {
        nav.value = selected;
    }
}

function hydrateContestNav() {
    hydrateSecondaryNav();
}

function hydrateStandingsNav() {
    hydrateSecondaryNav();
}

async function loadLeagueNav() {
    const nav = qs("league-nav");
    if (!nav) return;
    hydrateMainViewNav();
    hydrateSecondaryNav();
}
