/* Portada mecanografiada del diario. Mantener aqui todo lo propio de Pag. 1. */

function coverCloseLabel() {
    const raw = state.data.edit_deadline || state.data.kickoff_at || "";
    if (!raw) return state.data.is_locked ? "cerrada" : "abierta";
    const date = new Date(String(raw).replace(" ", "T"));
    if (Number.isNaN(date.getTime())) return state.data.is_locked ? "cerrada" : "abierta";
    const diff = date.getTime() - Date.now();
    if (diff <= 0 || state.data.is_locked) return "cerrada";
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(minutes / 60);
    const mins = minutes % 60;
    if (hours >= 24) return `${Math.floor(hours / 24)}d ${hours % 24}h`;
    if (hours > 0) return `${hours}h ${String(mins).padStart(2, "0")}m`;
    return `${Math.max(1, mins)}m`;
}

function coverMasterMajority(idx, matches = state.data.partidos || []) {
    const preds = state.data.predicciones_actuales || {};
    const counts = { "1": 0, "X": 0, "2": 0 };
    getVisibleAIColumns(matches)
        .filter(([id]) => id !== "programa")
        .forEach(([id, fallback]) => {
            const sign = normalizeSign(getSign(preds, idx, id, fallback));
            if (counts[sign] !== undefined) counts[sign] += 1;
        });
    const sorted = Object.entries(counts).sort((a, b) => b[1] - a[1]);
    return { sign: sorted[0]?.[1] ? sorted[0][0] : "-", votes: counts };
}

function coverDiscrepancyMatches(limit = 3) {
    const matches = state.data.partidos || [];
    const preds = state.data.predicciones_actuales || {};
    const pena = state.data.consenso_pena || [];
    return matches.slice(0, 14).map((match, idx) => {
        const p = pena[idx] || {};
        const penaSign = normalizeSign(p.ganador || "-");
        const programSign = normalizeSign(getSign(preds, idx, "programa", "v260_omnisciente"));
        const master = coverMasterMajority(idx, matches);
        const maxPct = Math.max(Number(p.p1 || 0), Number(p.px || 0), Number(p.p2 || 0));
        let score = 100 - maxPct;
        if (programSign !== "-" && penaSign !== "-" && programSign !== penaSign) score += 34;
        if (master.sign !== "-" && penaSign !== "-" && master.sign !== penaSign) score += 28;
        if (programSign !== "-" && master.sign !== "-" && programSign !== master.sign) score += 18;
        return { match, idx, pena: p, penaSign, programSign, masterSign: master.sign, score };
    })
        .sort((a, b) => b.score - a.score)
        .slice(0, limit);
}

function coverSpotlightActionHtml(match) {
    if (isLiveStatus(match.status) || isLiveMatch(match)) {
        return `<button type="button" data-page-action="LIVE">Ver directo</button>`;
    }
    if (isFinishedStatus(match.status) || scoreOnly(match.marcador || match.score || match.scores?.score || "")) {
        return `<button type="button" data-page-action="LIVE">Ver resultado</button>`;
    }
    return "";
}

function coverSpotlightHtml() {
    const items = coverDiscrepancyMatches(3);
    const item = items[0];
    if (!item?.match) {
        return `
            <div class="type-hot-card">
                <div class="type-kicker">La jornada en juego</div>
                <h3>Liga de Maestros</h3>
                <p>La Pe&ntilde;a, El Programa y los Maestros IA pronostican la jornada. Directo, ranking y discrepancias en una sola portada.</p>
                <button type="button" data-page-action="TICKET">Ver quiniela</button>
            </div>`;
    }
    const { match, idx, penaSign, programSign, masterSign } = item;
    const home = match.local || match.home_name || match.home?.name || "Local";
    const away = match.visitante || match.away_name || match.away?.name || "Visitante";
    const score = scoreOnly(match.marcador || match.score || match.scores?.score || "");
    return `
        <div class="type-hot-card is-compact">
            <div class="type-kicker">#${idx + 1} &middot; mayor discrepancia</div>
            <h3>${escapeHtml(getShortName(home))} vs ${escapeHtml(getShortName(away))}</h3>
            <div class="type-matchup">
                <div class="type-team">
                    ${logoBadge(home, teamLogo(match, "home"))}
                    <strong>${escapeHtml(getShortName(home))}</strong>
                </div>
                <div class="type-vs-block">
                    <b>${escapeHtml(score || "VS")}</b>
                    <span>mayor discrepancia</span>
                </div>
                <div class="type-team">
                    ${logoBadge(away, teamLogo(match, "away"))}
                    <strong>${escapeHtml(getShortName(away))}</strong>
                </div>
            </div>
            <div class="type-picks">
                <span>El Programa <b>${escapeHtml(programSign || "-")}</b></span>
                <span>Maestros <b>${escapeHtml(masterSign || "-")}</b></span>
                <span>La Pe&ntilde;a <b>${escapeHtml(penaSign || "-")}</b></span>
            </div>
            <div class="type-actions">
                ${coverSpotlightActionHtml(match)}
                <button type="button" data-page-action="TICKET">Ver quiniela</button>
            </div>
            <div class="type-discrepancy-list">
                ${items.map(row => {
                    const rowHome = row.match.local || row.match.home_name || row.match.home?.name || "Local";
                    const rowAway = row.match.visitante || row.match.away_name || row.match.away?.name || "Visitante";
                    return `
                        <button type="button" data-page-action="TICKET">
                            <span>#${row.idx + 1}</span>
                            <b>${escapeHtml(getShortName(rowHome))} - ${escapeHtml(getShortName(rowAway))}</b>
                            <small>El Programa ${escapeHtml(row.programSign || "-")} &middot; Maestros ${escapeHtml(row.masterSign || "-")} &middot; Pe&ntilde;a ${escapeHtml(row.penaSign || "-")}</small>
                        </button>`;
                }).join("")}
            </div>
        </div>`;
}

function coverMissionHtml() {
    return `
        <section class="type-mission">
            <div class="type-kicker">Tres rivales. Una clasificaci&oacute;n.</div>
            <p>
                No es una quiniela suelta: es una liga de aciertos. Cada jornada suma,
                cada fallo pesa y el ranking pone a cada uno en su sitio.
            </p>
            <div class="type-contender-grid">
                <article>
                    <span>T&uacute; / La Pe&ntilde;a</span>
                    <b>Tu pron&oacute;stico entra en la pelea.</b>
                </article>
                <article>
                    <span>Maestros IA</span>
                    <b>Cinco IAs. Cinco pron&oacute;sticos. Cero excusas.</b>
                </article>
                <article>
                    <span>El Programa</span>
                    <b>Nuestro modelo juega con datos y probabilidades.</b>
                </article>
            </div>
        </section>`;
}

function coverIsClosed() {
    return Boolean(state.data.is_locked) || coverCloseLabel() === "cerrada";
}

function coverStatusLineHtml({ liveCount, finished, saved, jornada, closed }) {
    const matchStatus = liveCount ? coverLiveCountText(liveCount) : `${finished}/15 resultados cerrados`;
    const ticketStatus = saved
        ? "Tu quiniela esta guardada"
        : closed ? "No hiciste quiniela en esta jornada" : "Tu quiniela esta pendiente";
    const parts = closed
        ? [`Jornada ${jornada || "-"}: quiniela cerrada`, matchStatus, ticketStatus]
        : [`Jornada ${jornada || "-"}: puedes participar`, ticketStatus, `Cierre en ${coverCloseLabel()}`];
    return `<div class="type-status-line ${closed ? "is-locked" : "is-open"}">${parts.map(part => `<span>${escapeHtml(String(part))}</span>`).join("")}</div>`;
}

function coverHeroActionsHtml({ saved, closed, liveCount }) {
    const primary = closed
        ? saved ? "Ver mi quiniela" : "Ver quiniela"
        : saved ? "Ver o modificar mi quiniela" : "Hacer mi quiniela";
    return `
        <div class="type-hero-actions">
            <button type="button" class="type-primary-action ${closed ? "is-closed" : ""}" data-page-action="TICKET">${escapeHtml(primary)}</button>
            <button type="button" class="type-secondary-action" onclick="document.querySelector('.type-hot-card')?.scrollIntoView({ behavior: 'smooth', block: 'center' })">Ver discrepancias</button>
        </div>`;
}

function coverLiveCountText(liveCount) {
    return liveCount === 1
        ? "1 partido de la quiniela en directo"
        : `${liveCount} partidos de la quiniela en directo`;
}

function coverNowHtml({ liveCount, finished, saved }) {
    const nextMatch = (state.data.partidos || []).find(match => !isFinishedStatus(match.status));
    const home = nextMatch ? getShortName(nextMatch.local || nextMatch.home_name || nextMatch.home?.name || "Local") : "-";
    const away = nextMatch ? getShortName(nextMatch.visitante || nextMatch.away_name || nextMatch.away?.name || "Visitante") : "-";
    const time = nextMatch ? (nextMatch.hora || nextMatch.kickoff || nextMatch.fecha || "") : "";
    return `
        <section class="type-now">
            <div class="type-now-item">
                <span>Ahora</span>
                <b>${liveCount ? coverLiveCountText(liveCount) : `${finished}/15 cerrados`}</b>
            </div>
            <div class="type-now-item">
                <span>Tu quiniela</span>
                <b>${saved ? "guardado" : "pendiente"}</b>
            </div>
            <div class="type-now-item is-wide">
                <span>Siguiente foco</span>
                <b>${escapeHtml(home)}${away !== "-" ? ` - ${escapeHtml(away)}` : ""}${time ? ` - ${escapeHtml(String(time))}` : ""}</b>
            </div>
        </section>`;
}

function hydrateCoverTypewriter() {
    const title = document.getElementById("cover-type-title");
    if (!title) return;
    const text = title.dataset.text || title.textContent || "";
    title.textContent = text;
}

function renderNewspaperCoverPageV3() {
    const matches = state.data.partidos || [];
    const liveCount = matches.filter(match => isLiveStatus(match.status) || isLiveMatch(match)).length;
    const finished = matches.filter(match => isFinishedStatus(match.status)).length;
    const saved = hasSavedTicket();
    const jornada = state.data.jornada || state.jornada || "";
    const headline = "Humano vs. M\u00e1quina";
    const closed = coverIsClosed();
    return `
        <section class="typewriter-cover">
            <article class="typewriter-sheet">
                <b class="typewriter-stamp">J.${escapeHtml(String(jornada || "-"))}<br>${closed ? "Cerrada" : "En juego"}</b>
                <div class="typewriter-main">
                    <section class="typewriter-lead">
                        <p class="typewriter-kicker">Portada &middot; Jornada ${escapeHtml(String(jornada || "-"))}</p>
                        <div class="type-cover-intro">
                            <strong>Compite por ser el mejor</strong>
                            <span>Reta a La Pe&ntilde;a, El Programa y los Maestros IA. Jornada tras jornada, el ranking pone a cada uno en su sitio.</span>
                        </div>
                        <h2 id="cover-type-title" data-text="${escapeHtml(headline)}">${escapeHtml(headline)}</h2>
                        <p>Entra en la jornada, reta a las IAs y pelea por ser el mejor en la clasificaci&oacute;n.</p>
                        ${coverHeroActionsHtml({ saved, closed, liveCount })}
                        ${coverStatusLineHtml({ liveCount, finished, saved, jornada, closed })}
                        ${coverMissionHtml()}
                    </section>
                    <section class="typewriter-hot">
                        ${coverSpotlightHtml()}
                        ${coverNowHtml({ liveCount, finished, saved })}
                    </section>
                </div>
            </article>
        </section>`;
}
