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
            <div class="type-kicker">Tres formas de leer el f&uacute;tbol. Un solo ganador.</div>
            <p>
                Aqu\u00ed no vienes solamente a rellenar una quiniela. Vienes a demostrar
                que puedes acertar m\u00e1s que ChatGPT, Claude, Gemini, Grok, Copilot...
                y que nuestro propio modelo.
            </p>
            <ul>
                <li>La Pe\u00f1a juega con la intuici\u00f3n colectiva.</li>
                <li>El Programa analiza datos, probabilidades y valor.</li>
                <li>Los Maestros IA hacen sus propios pron\u00f3sticos.</li>
                <li>Cada jornada suma. El ranking decide qui\u00e9n acierta m\u00e1s cuando pasa el tiempo.</li>
            </ul>
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
            <button type="button" class="type-secondary-action" onclick="document.querySelector('.type-hot-card')?.scrollIntoView({ behavior: 'smooth', block: 'center' })">Ver el duelo</button>
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
    const headline = "\u00bfQui\u00e9n sabe m\u00e1s de f\u00fatbol?";
    const closed = coverIsClosed();
    return `
        <section class="typewriter-cover">
            <article class="typewriter-sheet">
                <b class="typewriter-stamp">J.${escapeHtml(String(jornada || "-"))}<br>${closed ? "Cerrada" : "En juego"}</b>
                <div class="typewriter-main">
                    <section class="typewriter-lead">
                        <p class="typewriter-kicker">Portada &middot; Jornada ${escapeHtml(String(jornada || "-"))}</p>
                        <div class="type-cover-intro">
                            <strong>La batalla de la jornada</strong>
                            <span>La Pe&ntilde;a, El Programa y cinco grandes IAs compiten jornada tras jornada por el ranking de aciertos.</span>
                        </div>
                        <h2 id="cover-type-title" data-text="${escapeHtml(headline)}">${escapeHtml(headline)}</h2>
                        <p>Haz tu pron&oacute;stico, descubre d&oacute;nde no se ponen de acuerdo y sigue qui&eacute;n domina hoy... y qui&eacute;n manda a la larga.</p>
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
