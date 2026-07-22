/* ==========================================================================
   LIVE — War Room, ticker en directo, live ticker bar.
   Dependencias: utils.js, state.js, navigation.js
   ========================================================================== */


function renderWarRoom() {
    const allMatches = [...(state.data.partidos || []), ...(state.data.all_league_matches || [])];
    const live = allMatches.filter(m => (isLiveStatus(m.status) || isLiveMatch(m)) && !isImplicitlyFinished(m));
    const upcoming = allMatches
        .filter(m => isScheduledStatus(m.status) && !isImplicitlyFinished(m))
        .sort((a, b) => (parseMatchTimestamp(a) || 0) - (parseMatchTimestamp(b) || 0));
    const finished = allMatches.filter(m => isFinishedStatus(m.status) || isImplicitlyFinished(m));

    // Si no hay partidos en vivo ni próximos, mostrar mensaje informativo
    if (!live.length && !upcoming.length) {
        const jornada = state.data?.jornada || "?";
        const nextMatch = allMatches.length > 0 ? allMatches[0] : null;
        const nextDate = nextMatch ? formatSmartDate(nextMatch.added || nextMatch.fecha_raw, nextMatch.scheduled || nextMatch.hora) : "";

        return `<div class="live-empty-state">
            <div class="live-empty-icon">⚽</div>
            <h3 class="live-empty-title">Directo se activa los fines de semana</h3>
            <p class="live-empty-text">Cuando empiece la Jornada ${jornada}, los partidos aparecerán aquí en directo.</p>
            ${nextDate ? `<p class="live-empty-next">Próximo: <strong>${escapeHtml(nextDate)}</strong></p>` : ""}
            <p class="live-empty-hint">Mientras tanto, puedes hacer tu quiniela o ver la clasificación.</p>
        </div>`;
    }

    const renderLiveCard = (match) => {
        const home = match.local || match.home_name || match.home?.name || "Local";
        const away = match.visitante || match.away_name || match.away?.name || "Visitante";
        const score = scoreOnly(match.marcador || match.score || match.scores?.score || "");
        const live = isLiveStatus(match.status) || isLiveMatch(match);
        const minute = matchMinuteValue(match);
        const stage = liveStage(match);
        const league = competitionLabel(match);

        const statusText = live
            ? (stage === "HT" ? "Descanso" : (minute ? `${minute}'` : "En directo"))
            : (score || formatSmartDate(match.added || match.fecha_raw, match.scheduled || match.time || match.hora));

        const cardClass = live ? "is-live" : "";

        return `
            <article class="live-card ${cardClass}">
                <div class="live-card-league">${escapeHtml(league)}</div>
                <div class="live-card-teams">
                    <div class="live-card-team">
                        ${logoBadge(home, teamLogo(match, "home"))}
                        <strong>${escapeHtml(getShortName(home))}</strong>
                    </div>
                    <div class="live-card-score ${live ? "is-live-score" : ""}"${liveScoreAttrs(match, live)}>
                        <span class="live-card-status">${escapeHtml(statusText)}</span>
                        <b>${escapeHtml(score || "vs")}</b>
                    </div>
                    <div class="live-card-team live-card-team-right">
                        ${logoBadge(away, teamLogo(match, "away"))}
                        <strong>${escapeHtml(getShortName(away))}</strong>
                    </div>
                </div>
            </article>`;
    };

    const sections = [];
    if (live.length) {
        sections.push(`
            <section class="live-section">
                <h3 class="live-section-title"><span class="live-dot"></span> En directo (${live.length})</h3>
                <div class="live-card-grid">${live.map(renderLiveCard).join("")}</div>
            </section>`);
    }
    if (upcoming.length) {
        sections.push(`
            <section class="live-section">
                <h3 class="live-section-title">Proximos (${upcoming.length})</h3>
                <div class="live-card-grid">${upcoming.slice(0, 8).map(renderLiveCard).join("")}</div>
            </section>`);
    }
    if (finished.length && !live.length) {
        sections.push(`
            <section class="live-section">
                <h3 class="live-section-title">Finalizados (${finished.length})</h3>
                <div class="live-card-grid">${finished.map(renderLiveCard).join("")}</div>
            </section>`);
    }
    return `<div class="live-warroom">${sections.join("")}</div>`;
}

function renderLiveTicker() {
    const allMatches = getAllLeagueMatches();
    const matches = state.currentFilter === "ALL"
        ? (state.data.partidos || [])
        : state.currentFilter === "LIVE"
            ? getLiveLeagueMatches()
            : state.currentFilter === "WAR_ROOM"
                ? getLiveLeagueMatches()
                : allMatches.filter(m => competitionLabel(m) === state.currentFilter.toUpperCase());
    const live = matches.filter(m => isLiveStatus(m.status) || isLiveMatch(m));
    const nextMatch = getNextLeagueMatch();
    const tickerItems = live.length
        ? live.map(m => {
            const home = m.local || m.home_name || m.home?.name;
            const away = m.visitante || m.away_name || m.away?.name;
            const score = scoreOnly(m.marcador || m.score || m.scores?.score) || m.marcador || m.score || "";
            return `<span><b>${escapeHtml(getShortName(home))}</b> ${escapeHtml(score)} <b>${escapeHtml(getShortName(away))}</b></span>`;
        }).join("")
        : `<span>${nextMatch ? `PrÃ³ximo directo: <b>${escapeHtml(getShortName(nextMatch.local || nextMatch.home_name || nextMatch.home?.name || "-"))}</b> ${escapeHtml(formatKickoffShort(nextMatch.added || nextMatch.fecha_raw, nextMatch.scheduled || nextMatch.time || nextMatch.hora))}` : "Sin partidos en directo ahora mismo"}</span>`;
    return `
        <div class="live-ticker ${live.length ? "has-live" : ""} ${live.length > 1 ? "is-marquee" : "is-static"}">
            <div class="live-ticker-track">
                <div class="live-ticker-items">${live.length > 1 ? tickerItems + tickerItems : tickerItems}</div>
            </div>
        </div>`;
}

function updateTopbarLiveTicker() {
    const slot = qs("topbar-live-slot");
    if (!slot || !state.data) return;
    slot.innerHTML = renderLiveTicker();
}
