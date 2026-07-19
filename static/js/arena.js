/* ==========================================================================
   ARENA — Dispatcher principal renderArena, match cards, agrupacion por ligas.
   Dependencias: todos los modulos anteriores.
   ========================================================================== */


function renderArena() {
    const container = qs("matches-body");
    if (!container || !state.data) return;
    if (state.currentFilter !== "SNAKE_PAGE") {
        if (typeof leaveGamesHub === "function") leaveGamesHub();
        else document.body.classList.remove("games-snake-open", "games-arkanoid-open");
    }
    standingContextCache = new Map();
    document.body.classList.add("quiniela-focus");
    document.body.classList.toggle("newspaper-cover-active", isCoverPage());
    document.body.classList.toggle("newspaper-ticket-active", isTicketPage());
    document.body.classList.toggle("newspaper-standings-active", isStandingsPage());
    document.body.classList.toggle("newspaper-snake-active", isSnakePage());
    document.body.classList.toggle("newspaper-quiz-active", isQuizPage());
    document.body.classList.toggle("newspaper-contest-active", isContestPage() && !isProfilePage());
    document.body.classList.toggle("newspaper-live-active", isLiveOrLeaguePage());
    document.body.classList.toggle("newspaper-profile-active", isProfilePage());
    relocateSnakeHud();
    hydrateHero();
    updateTopbarLiveTicker();
    if (shouldRefreshSideModules()) renderSidebarRadar();
    hydrateNewspaperPageNav(currentMainView());
    fixMojibakeLabels();
    document.body.classList.remove("standings-focus");

    if (state.currentFilter === "WAR_ROOM") {
        container.className = "arena-content warroom-content";
        container.innerHTML = renderWarRoom();
        return;
    }

    if (state.contestView !== "MATCHES") {
        container.className = "arena-content contest-page-mode";
        container.innerHTML = renderContestPage(state.contestView);
        return;
    }

    if (state.currentFilter === "STANDINGS_FULL" || state.currentFilter === "STANDINGS_PRIMERA" || state.currentFilter === "STANDINGS_SEGUNDA") {
        container.className = "arena-content standings-full-mode";
        container.innerHTML = renderFullStandingsPage();
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
        return;
    }

    if (state.currentFilter === "TICKET") {
        const matches = state.data.partidos || [];
        container.className = "arena-content table-mode";
        container.innerHTML = `
            <section class="ticket-porra-strip" aria-labelledby="ticket-porra-title">
                <div class="ticket-porra-heading">
                    <span data-porra-label>PORRA</span>
                    <strong id="ticket-porra-title">Marcador exacto</strong>
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
            </div>`;
        renderArenaTensionBody(matches);
        loadPorra();
        return;
    }

    const allMatches = state.data.all_league_matches || [];
    const matches = state.currentFilter === "LIVE"
        ? getLiveLeagueMatches()
        : allMatches.filter(m => competitionLabel(m) === state.currentFilter.toUpperCase());

    container.className = "arena-content arena-grid live-grouped-grid";
    if (matches.length === 0) {
        container.innerHTML = `<div class="empty-state">No hay partidos para ${escapeHtml(state.currentFilter)}.</div>`;
        return;
    }
    container.innerHTML = renderGroupedMatchCards(matches, state.currentFilter !== "LIVE");
}

function renderGroupedMatchCards(matches, singleCompetition = false) {
    if (!Array.isArray(matches) || !matches.length) return "";
    if (singleCompetition) {
        return `<div class="match-card-container">${matches.map(match => renderMatchCard(match, { showCompetition: false })).join("")}</div>`;
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
        <section class="league-match-group">
            <header class="league-group-header">
                <strong>${escapeHtml(group.label)}</strong>
                <span>${group.matches.length} partido${group.matches.length === 1 ? "" : "s"}</span>
            </header>
            <div class="match-card-container">
                ${group.matches.map(match => renderMatchCard(match, { showCompetition: false })).join("")}
            </div>
        </section>
    `).join("");
}

function liveMatchDomKey(match) {
    return encodeURIComponent(matchPairKey(match) || String(match.id || ""));
}

function patchLiveArena() {
    if (state.currentFilter !== "LIVE") return false;
    const container = qs("matches-body");
    if (!container) return false;

    const matches = getLiveLeagueMatches();
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
        card.classList.add("is-live");
        card.classList.remove("is-finished");
    }
    return true;
}

function renderMatchCard(match, options = {}) {
    const home = match.local || match.home_name || match.home?.name || "Local";
    const away = match.visitante || match.away_name || match.away?.name || "Visitante";
    const preds = state.data.predicciones_actuales || {};
    const consenso = state.data.consenso_pena || [];
    const canEdit = Boolean(state.user) && String(state.data.jornada) === String(state.data.max_jornada) && !state.data.is_locked;

    const finished = isFinishedStatus(match.status) || isImplicitlyFinished(match);
    const live = (isLiveMatch(match) || isLiveStatus(match.status)) && !finished;
    const scheduled = isScheduledStatus(match.status) && !live && !finished;
    const score = scheduled
        ? formatSmartDate(match.added || match.fecha_raw, match.scheduled || match.time || match.hora)
        : live
            ? liveScoreDisplay(match, "-")
            : (match.marcador || match.score || match.scores?.score || "-");

    const matchIdx = (state.data.partidos || []).findIndex(m => Number(m.id) === Number(match.id));
    const idx = matchIdx >= 0 ? matchIdx : -1;
    const predsForMatch = idx >= 0 ? preds : {};

    const aiCells = AI_COLUMNS.map(([primary, fallback, label]) => {
        const sign = idx >= 0 ? getSign(predsForMatch, idx, primary, fallback) : "-";
        return `<span class="ia-signo" title="${escapeHtml(label)}">${escapeHtml(sign)}</span>`;
    }).join(" ");

    const cardClass = live ? "is-live" : (finished ? "is-finished" : "");

    return `
        <article class="match-card ${cardClass}" data-match-id="${match.id || ""}"${live ? ` data-live-key="${escapeHtml(liveMatchDomKey(match))}"` : ""}>
            <div class="card-teams">
                ${teamCell(home, "left", teamLogo(match, "home"))}
                <div class="card-score-area">
                    <div class="match-score-badge ${live ? "is-live-score" : (scheduled ? "is-scheduled-time" : "")}"${live ? " data-live-score" : ""}${liveScoreAttrs(match, live)}>${escapeHtml(score)}</div>
                </div>
                ${teamCell(away, "right", teamLogo(match, "away"))}
            </div>
            ${options.showCompetition !== false ? `<div class="card-competition">${escapeHtml(competitionLabel(match))}</div>` : ""}
        </article>`;
}

function renderArenaCards(matches) {
    const preds = state.data.predicciones_actuales || {};
    const consenso = state.data.consenso_pena || [];
    const canEdit = Boolean(state.user) && String(state.data.jornada) === String(state.data.max_jornada) && !state.data.is_locked;

    return matches.map((m, idx) => {
        const isPleno = idx === 14;
        const real = m.signo_actual || "-";
        const realScore = scoreOnly(m.marcador);
        const realCell = isPleno
            ? (isFinishedStatus(m.status) && realScore
                ? `<span class="pleno-real-score">${escapeHtml(realScore)}</span>`
                : `<span class="pleno-res-muted">-</span>`)
            : `<span class="ia-signo active">${escapeHtml(real)}</span>`;
        const mySign = state.my_signs[idx] || "-";
        const c = consenso.find(item => Number(item.id) === Number(m.id)) || { p1: 0, px: 0, p2: 0, ganador: "-" };
        const consensoPleno = getPenaPlenoSummary(idx);
        const consensus = isPleno
            ? renderPenaPleno(consensoPleno, m.marcador, m.status)
            : renderConsensus(c, real, m.status);
        const finishedMatch = isFinishedStatus(m.status) || isImplicitlyFinished(m);
        const liveMatch = (isLiveMatch(m) || isLiveStatus(m.status)) && !finishedMatch;
        const scheduledMatch = isScheduledStatus(m.status) && !liveMatch && !finishedMatch;
        const score = scheduledMatch
            ? formatSmartDate(m.added || m.fecha_raw, m.scheduled || m.time || m.hora)
            : (m.marcador || m.score || m.scores?.score || "-");

        const aiCells = AI_COLUMNS.map(([primary, fallback, label]) => {
            const sign = getSign(preds, idx, primary, fallback);
            return `<span class="ia-signo ${hitClass(sign, isPleno ? m.marcador : real, m.status, isPleno)}" title="${escapeHtml(label)}">${escapeHtml(sign)}</span>`;
        }).join(" ");

        const mine = renderMyCell(idx, mySign, isPleno ? m.marcador : real, m.status, canEdit, isPleno);
        const isFinished = finishedMatch;

        const isFav = ["REAL MADRID", "BARCELONA", "ATLETICO MADRID"].includes(normalizeName(m.local)) || ["REAL MADRID", "BARCELONA", "ATLETICO MADRID"].includes(normalizeName(m.visitante));
        const isSurprise = liveMatch && isFav && (m.goles_local === m.goles_visitante || (normalizeName(m.local) === "REAL MADRID" && m.goles_local < m.goles_visitante) || (normalizeName(m.visitante) === "REAL MADRID" && m.goles_visitante < m.goles_local));
        const values = [Number(c.p1 || 0), Number(c.px || 0), Number(c.p2 || 0)].sort((a, b) => b - a);
        const splitMatch = idx !== 14 && !isFinished && values[0] > 0 && values[0] - values[1] <= 12;

        const cardClass = [
            liveMatch ? "is-live" : (isFinished ? "is-finished" : ""),
            isSurprise ? "match-trap" : "",
            splitMatch ? "is-split" : ""
        ].filter(Boolean).join(" ");

        const statusBadge = liveMatch ? `<span class="badge badge-live">LIVE</span>` : "";
        const surpriseBadge = isSurprise ? `<span class="badge badge-surprise">SORPRESA</span>` : "";

        return `
            <div class="match-card-container">
                <article class="match-card ${cardClass}" data-match-idx="${idx}">
                    <div class="card-teams">
                        ${teamCell(m.local, "left", teamLogo(m, "home"))}
                        <div class="card-score-area">
                            <div class="match-score-badge ${liveMatch ? "is-live-score" : (scheduledMatch ? "is-scheduled-time" : "")}"${liveScoreAttrs(m, liveMatch)}>${escapeHtml(score)}</div>
                            <div class="card-status">${statusBadge}${surpriseBadge}</div>
                        </div>
                        ${teamCell(m.visitante, "right", teamLogo(m, "away"))}
                    </div>
                    <div class="match-controls">
                        <div class="user-pick-area">${mine}</div>
                        <div class="ai-picks-area">${aiCells}</div>
                        <div class="pena-cell">${consensus}</div>
                    </div>
                </article>
                ${state.expandedMatch === idx ? renderMatchDetail(m, c) : ""}
                <div class="match-detail-toggle-container" style="text-align:center; margin-top:-8px; margin-bottom:8px;">
                    <button class="match-detail-toggle" data-detail-toggle="1" data-match-idx="${idx}">INFO</button>
                </div>
            </div>`;
    }).join("");
}
