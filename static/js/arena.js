/* ==========================================================================
   ARENA — Dispatcher principal renderArena, match cards, agrupacion por ligas.
   Dependencias: todos los modulos anteriores.
   ========================================================================== */

let _matchIntersectionObserver = null;

function initLazyMatchRendering() {
    if (_matchIntersectionObserver) return;
    _matchIntersectionObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const el = entry.target;
                const matchData = el.dataset.matchJson;
                if (matchData) {
                    try {
                        const match = JSON.parse(matchData);
                        el.innerHTML = renderMatchCard(match);
                        el.classList.add("match-loaded");
                    } catch {}
                }
                _matchIntersectionObserver.unobserve(el);
            }
        });
    }, { rootMargin: "200px" });
}

function lazyMatchPlaceholder(match) {
    const div = document.createElement("div");
    div.className = "match-card match-lazy";
    div.dataset.matchJson = JSON.stringify(match);
    div.style.minHeight = "120px";
    return div;
}


function renderSkeletonLoading() {
    return `
        <div class="arena-content newspaper-cover-mode" style="padding: 20px; max-width: 880px; margin: 0 auto;">
            <div class="skeleton skeleton-heading" style="width: 180px; margin-bottom: 20px;">&nbsp;</div>
            <div class="skeleton skeleton-text" style="width: 70%; margin-bottom: 30px;">&nbsp;</div>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 20px;">
                <div class="skeleton skeleton-card" style="height: 160px;">&nbsp;</div>
                <div class="skeleton skeleton-card" style="height: 160px;">&nbsp;</div>
            </div>
            <div class="skeleton skeleton-card" style="height: 100px; margin-bottom: 10px;">&nbsp;</div>
            <div class="skeleton skeleton-card" style="height: 100px; margin-bottom: 10px;">&nbsp;</div>
            <div class="skeleton skeleton-card" style="height: 100px;">&nbsp;</div>
        </div>`;
}

function renderArena() {
    const container = qs("matches-body");
    if (!container) return;
    if (!state.data) {
        container.innerHTML = renderSkeletonLoading();
        return;
    }
    if (state.currentFilter !== "TICKET" && typeof stopTicketComments === "function") {
        stopTicketComments();
    }
    if (state.currentFilter !== "SNAKE_PAGE") {
        if (typeof leaveGamesHub === "function") leaveGamesHub();
        else document.body.classList.remove("games-snake-open", "games-arkanoid-open");
    }
    standingContextCache = new Map();
    document.body.classList.add("quiniela-focus");
    document.body.classList.toggle("newspaper-cover-active", isCoverPage());
    if (isCoverPage()) loadSacramentoFont();
    document.body.classList.toggle("newspaper-ticket-active", isTicketPage());
    document.body.classList.toggle("newspaper-standings-active", isStandingsPage());
    document.body.classList.toggle("newspaper-snake-active", isSnakePage());
    document.body.classList.toggle("newspaper-quiz-active", isQuizPage());
    document.body.classList.toggle("newspaper-news-active", isNewsPage());
    document.body.classList.toggle("newspaper-contest-active", isContestPage() && !isProfilePage());
    document.body.classList.toggle("newspaper-live-active", isLiveOrLeaguePage());
    document.body.classList.toggle("newspaper-profile-active", isProfilePage());
    hydrateHero();
    hydrateNewspaperPageNav(currentMainView());
    document.body.classList.remove("standings-focus");
    if (state.contestView !== "MATCHES") {
        container.className = "arena-content contest-page-mode";
        if (!state.contest || state.contestJornada !== String(state.data.jornada || "")) {
            container.innerHTML = `<div class="empty-state">Cargando La Pe&ntilde;a...</div>`;
            ensureContestData()
                .then(() => {
                    if (state.contestView !== "MATCHES") renderArena();
                    updateAuthUI();
                })
                .catch(error => {
                    console.error(error);
                    if (state.contestView !== "MATCHES") {
                        container.innerHTML = `<div class="empty-state">No se pudo cargar La Pe&ntilde;a.</div>`;
                    }
                });
            return;
        }
        container.innerHTML = renderContestPage(state.contestView);
        return;
    }

    if (state.currentFilter === "STANDINGS_FULL" || state.currentFilter === "STANDINGS_PRIMERA" || state.currentFilter === "STANDINGS_SEGUNDA") {
        container.className = "arena-content standings-full-mode";
        container.innerHTML = renderFullStandingsPage();
        return;
    }

    if (state.currentFilter === "NEWS_PAGE") {
        container.className = "arena-content newspaper-feature-page newspaper-news-mode";
        container.innerHTML = typeof renderNewsPage === "function"
            ? renderNewsPage()
            : `<div class="empty-state">Cargando noticias...</div>`;
        loadNewsBriefing();
        return;
    }

    if (state.currentFilter === "QUIZ_PAGE") {
        container.className = "arena-content newspaper-feature-page";
        container.innerHTML = renderQuizNewspaperPage();
        setTimeout(initQuiz, 50);
        return;
    }

    if (state.currentFilter === "SNAKE_PAGE") {
        container.className = "arena-content newspaper-feature-page games-hub";
        container.innerHTML = renderGamesHub();
        if (typeof initGamesHub === "function") initGamesHub();
        return;
    }

    if (state.currentFilter === "ALL") {
        container.className = "arena-content newspaper-cover-mode";
        container.innerHTML = renderNewspaperCoverPageV3();
        requestAnimationFrame(hydrateCoverTypewriter);
        if (typeof startCoverCountdown === "function") startCoverCountdown();
        if (typeof startSeasonCountdown === "function") startSeasonCountdown();
        if (typeof loadSeasonSummary === "function") loadSeasonSummary();
        if (typeof startCoverScorebar === "function") startCoverScorebar();
        loadPorra();
        loadNewsBriefing();
        return;
    }

    if (state.currentFilter === "TICKET") {
        const matches = state.data.partidos || [];
        container.className = "arena-content table-mode";
        container.innerHTML = `
            <div class="ticket-workspace">
                <div class="ticket-main-column">
                    <div class="ticket-progress-strip" aria-live="polite">
                        <span>Tu quiniela</span>
                        <strong id="ticket-picks-done">0/15</strong>
                        <div class="picks-track" aria-hidden="true"><i id="ticket-picks-bar"></i></div>
                    </div>
                    <section class="ticket-porra-strip" aria-labelledby="ticket-porra-title">
                        <div class="ticket-porra-heading">
                            <span data-porra-label>PORRA</span>
                            <strong id="ticket-porra-title">+2 puntos por marcador exacto</strong>
                        </div>
                        <div id="ticket-porra-body" class="porra-body">
                            <div class="empty-state">Cargando porra...</div>
                        </div>
                    </section>
                    ${renderLiveScrutinyBadge(matches)}
                    <div class="arena-table-wrap">
                        <table class="arena-table is-tension-table">
                            <thead id="arena-thead"></thead>
                            <tbody id="arena-body"></tbody>
                        </table>
                    </div>
                </div>
                ${renderTicketCommentsPanel()}
            </div>`;
        renderArenaTensionBody(matches);
        if (typeof updatePicksProgress === "function") updatePicksProgress();
        initTicketComments();
        loadPorra();
        ensureQ15Directo().then(loadedNow => {
            if (loadedNow && state.currentFilter === "TICKET" && state.expandedMatch !== null) renderArena();
        });
        return;
    }

    if (state.currentFilter === "LIVE") {
        const subFilter = state.liveSubFilter || "live";
        let matches;
        if (subFilter === "live") {
            matches = getLiveLeagueMatches();
        } else if (subFilter === "primera") {
            matches = getTodayLeagueMatches().filter(m => competitionLabel(m) === "LA LIGA");
        } else if (subFilter === "segunda") {
            matches = getTodayLeagueMatches().filter(m => competitionLabel(m) === "SEGUNDA DIVISION");
        } else {
            matches = getAllTodayLeagueMatches();
        }

        container.className = "arena-content arena-grid live-grouped-grid";
        if (matches.length === 0) {
            container.className = "arena-content direct-empty-page";
            container.innerHTML = renderDirectEmptyState();
            return;
        }
        const subnavHtml = `
            <div class="live-subnav" id="live-subnav" aria-label="Filtrar directo">
                <button type="button" class="${subFilter === 'live' ? 'active' : ''}" data-live-sub="live">En Juego</button>
                <button type="button" class="${subFilter === 'primera' ? 'active' : ''}" data-live-sub="primera">Primera</button>
                <button type="button" class="${subFilter === 'segunda' ? 'active' : ''}" data-live-sub="segunda">Segunda</button>
                <button type="button" class="${subFilter === 'all' ? 'active' : ''}" data-live-sub="all">Todos</button>
            </div>`;
        const comentaristaHtml = typeof directComentaristaHtml === "function" ? directComentaristaHtml() : "";
        container.innerHTML = subnavHtml + comentaristaHtml + renderGroupedMatchCards(matches, false);
        container.querySelectorAll("[data-live-sub]").forEach(btn => {
            btn.addEventListener("click", () => {
                state.liveSubFilter = btn.dataset.liveSub;
                syncUrlState();
                renderArena();
            });
        });
        return;
    }

    const allMatches = getBrowsableLeagueMatches();
    const matches = allMatches.filter(m => competitionLabel(m) === state.currentFilter.toUpperCase());

    container.className = "arena-content arena-grid live-grouped-grid";
    if (matches.length === 0) {
        container.className = "arena-content arena-grid";
        container.innerHTML = `<div class="empty-state">No hay partidos disponibles en esta competicion.</div>`;
        return;
    }
    const comentaristaHtml = typeof directComentaristaHtml === "function" ? directComentaristaHtml() : "";
    container.innerHTML = comentaristaHtml + renderGroupedMatchCards(matches, state.currentFilter !== "LIVE");
}
function renderGroupedMatchCards(matches, singleCompetition = false) {
    if (!Array.isArray(matches) || !matches.length) return "";
    if (singleCompetition) {
        return `<div class="match-card-container">${matches.map(renderMatchCard).join("")}</div>`;
    }
    const groups = [];
    const indexByKey = new Map();
    for (const match of matches) {
        const key = competitionLabel(match);
        if (!indexByKey.has(key)) {
            indexByKey.set(key, groups.length);
            groups.push({ key, label: matchCompetitionMeta(match), matches: [] });
        }
        groups[indexByKey.get(key)].matches.push(match);
    }
    groups.sort((a, b) => {
        const liveDiff = b.matches.filter(isLiveMatch).length - a.matches.filter(isLiveMatch).length;
        if (liveDiff) return liveDiff;
        return a.label.localeCompare(b.label, "es");
    });
    return groups.map(group => `
        <section class="league-match-group" data-competition="${escapeHtml(group.key)}">
            <header class="league-group-header">
                <strong>${escapeHtml(group.label)}</strong>
                <span>${group.matches.length} partido${group.matches.length === 1 ? "" : "s"}</span>
            </header>
            <div class="match-card-container">
                ${group.matches.map(renderMatchCard).join("")}
            </div>
        </section>
    `).join("");
}
function liveMatchDomKey(match) {
    return encodeURIComponent(matchPairKey(match) || String(match.id || ""));
}

function patchLiveArena() {
    if (state.currentFilter !== "LIVE") return false;
    if ((state.liveSubFilter || "live") !== "live") return false; // solo parchea en vista "En Juego"
    const container = qs("matches-body");
    if (!container) return false;

    // Los comentarios del directo se parchean aparte: pueden llegar en un
    // refresco en el que las tarjetas no han cambiado.
    if (typeof patchDirectComentarista === "function") patchDirectComentarista();

    const matches = getLiveLeagueMatches();
    const expectedCompetitions = new Set(matches.map(competitionLabel));
    const renderedCompetitions = new Set(
        [...container.querySelectorAll(".league-match-group[data-competition]")].map(group => group.dataset.competition)
    );
    if (
        expectedCompetitions.size !== renderedCompetitions.size
        || [...expectedCompetitions].some(competition => !renderedCompetitions.has(competition))
    ) return false;

    const cards = [...container.querySelectorAll(".match-card[data-live-key]")];
    if (!cards.length || cards.length !== matches.length) return false;

    const cardsByKey = new Map(cards.map(card => [card.dataset.liveKey, card]));
    if (new Set(matches.map(liveMatchDomKey)).size !== matches.length) return false;
    if (matches.some(match => !cardsByKey.has(liveMatchDomKey(match)))) return false;

    for (const match of matches) {
        const card = cardsByKey.get(liveMatchDomKey(match));
        const scoreNode = card.querySelector("[data-live-score]");
        if (!scoreNode) return false;

        const nextScore = liveScoreDisplay(match, "-");
        if (scoreNode.textContent !== nextScore) scoreNode.textContent = nextScore;
        scoreNode.dataset.liveMatch = String(match.id || "");
        scoreNode.dataset.liveMinute = String(matchMinuteValue(match) || "");
        scoreNode.dataset.liveStage = liveStage(match) || "LIVE";
        // El chip del minuto se actualiza igual que el marcador, sin repintar la vista.
        const minuteNode = card.querySelector("[data-live-minute-label]");
        const nextMinute = liveMinuteLabel(match) || "EN DIRECTO";
        if (minuteNode && minuteNode.textContent !== nextMinute) minuteNode.textContent = nextMinute;
        card.classList.add("is-live");
        card.classList.remove("is-finished");
    }
    return true;
}

function renderMatchCard(match) {
    const home = match.local || match.home_name || match.home?.name || "Local";
    const away = match.visitante || match.away_name || match.away?.name || "Visitante";

    const scheduled = needsFixtureSchedule(match);
    const finished = isFinishedStatus(match.status) || isImplicitlyFinished(match) || isExpiredLiveMatch(match);
    const live = (isLiveMatch(match) || isLiveStatus(match.status)) && !finished && !scheduled;
    const score = scheduled
        ? fixtureScheduleDisplay(match)
        : live
            ? liveScoreDisplay(match, "-")
            : (match.marcador || match.score || match.scores?.score || "-");
    // El minuto ("63'", "Descanso") va en su chip bajo el marcador: en directo
    // es el dato que dice si el partido esta empezando o muriendo.
    const minute = live ? (liveMinuteLabel(match) || "EN DIRECTO") : "";

    const cardClass = live ? "is-live" : (finished ? "is-finished" : "");

    return `
        <article class="match-card ${cardClass}" data-match-id="${match.id || ""}"${live ? ` data-live-key="${escapeHtml(liveMatchDomKey(match))}"` : ""}>
            <div class="card-teams">
                ${teamCell(home, "left", teamLogo(match, "home"))}
                <div class="card-score-area">
                    <div class="match-score-badge ${live ? "is-live-score" : (scheduled ? "is-scheduled-time" : "")}"${live ? " data-live-score" : ""}${liveScoreAttrs(match, live)}>${escapeHtml(score)}</div>
                    ${minute ? `<span class="card-live-minute" data-live-minute-label>${escapeHtml(minute)}</span>` : ""}
                </div>
                ${teamCell(away, "right", teamLogo(match, "away"))}
            </div>
        </article>`;
}


