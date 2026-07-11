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

function coverDiscrepancyMatch() {
    const matches = state.data.partidos || [];
    const preds = state.data.predicciones_actuales || {};
    const pena = state.data.consenso_pena || [];
    let best = null;
    matches.slice(0, 14).forEach((match, idx) => {
        const p = pena[idx] || {};
        const penaSign = normalizeSign(p.ganador || "-");
        const programSign = normalizeSign(getSign(preds, idx, "programa", "v260_omnisciente"));
        const master = coverMasterMajority(idx, matches);
        const maxPct = Math.max(Number(p.p1 || 0), Number(p.px || 0), Number(p.p2 || 0));
        let score = 100 - maxPct;
        if (programSign !== "-" && penaSign !== "-" && programSign !== penaSign) score += 34;
        if (master.sign !== "-" && penaSign !== "-" && master.sign !== penaSign) score += 28;
        if (programSign !== "-" && master.sign !== "-" && programSign !== master.sign) score += 18;
        if (!best || score > best.score) {
            best = { match, idx, pena: p, penaSign, programSign, masterSign: master.sign, score };
        }
    });
    return best;
}

function coverSpotlightHtml() {
    const item = coverDiscrepancyMatch();
    if (!item?.match) {
        return `
            <div class="type-hot-card">
                <div class="type-kicker">La jornada en juego</div>
                <h3>Liga de Maestros</h3>
                <p>La Pe&ntilde;a y los Maestros IA juegan el mismo boleto. Quiniela, directo y ranking en una sola jornada.</p>
                <button type="button" data-page-action="TICKET">Ver boleto</button>
            </div>`;
    }
    const { match, idx, penaSign, programSign, masterSign } = item;
    const home = match.local || match.home_name || match.home?.name || "Local";
    const away = match.visitante || match.away_name || match.away?.name || "Visitante";
    const score = scoreOnly(match.marcador || match.score || match.scores?.score || "");
    const status = isLiveStatus(match.status) || isLiveMatch(match) ? "En directo" : (score ? "Marcador" : "Partido caliente");
    return `
        <div class="type-hot-card">
            <div class="type-kicker">#${idx + 1} &middot; ${escapeHtml(status)}</div>
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
                <span>Programa <b>${escapeHtml(programSign || "-")}</b></span>
                <span>Maestros <b>${escapeHtml(masterSign || "-")}</b></span>
                <span>La Pe&ntilde;a <b>${escapeHtml(penaSign || "-")}</b></span>
            </div>
            <div class="type-actions">
                <button type="button" data-page-action="LIVE">Ver directo</button>
                <button type="button" data-page-action="TICKET">Ver boleto</button>
            </div>
        </div>`;
}

function coverSectionsHtml() {
    const sections = [
        ["TICKET", "Pag. 2", "Quiniela", "Boleto completo y signos"],
        ["LIVE", "Pag. 3", "Directo", "Marcadores de la jornada"],
        ["STANDINGS", "Pag. 4", "Ligas", "Primera y Segunda"],
        ["SNAKE", "Pag. 5", "Snake", "Arcade y ranking"],
        ["CONTEST", "Pag. 6", "La Pe\u00f1a", "Perfil y galardones"],
        ["QUIZ", "Pag. 7", "Quiz", "Reto de preguntas"]
    ];
    return `
        <section class="type-summary">
            <div class="type-kicker">Sumario</div>
            <div class="type-summary-grid">
                ${sections.map(([action, page, title, text]) => `
                    <button type="button" data-page-action="${escapeHtml(action)}">
                        <span>${escapeHtml(page)}</span>
                        <b>${escapeHtml(title)}</b>
                        <small>${escapeHtml(text)}</small>
                    </button>
                `).join("")}
            </div>
        </section>`;
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
                <b>${liveCount ? `${liveCount} en juego` : `${finished}/15 resueltos`}</b>
            </div>
            <div class="type-now-item">
                <span>Tu boleto</span>
                <b>${saved ? "guardado" : "pendiente"}</b>
            </div>
            <div class="type-now-item is-wide">
                <span>Siguiente foco</span>
                <b>${escapeHtml(home)}${away !== "-" ? ` - ${escapeHtml(away)}` : ""}${time ? ` · ${escapeHtml(String(time))}` : ""}</b>
            </div>
        </section>`;
}

function coverProgramTicketHtml() {
    const preds = state.data.predicciones_actuales || {};
    const matches = state.data.partidos || [];
    const signs = Array.from({ length: 15 }, (_, idx) => getSign(preds, idx, "programa", "v260_omnisciente") || "-");
    const doubles = signs
        .map((sign, idx) => String(sign).length > 1 && idx < 14 ? idx + 1 : null)
        .filter(Boolean);
    const visible = [0, 1, 2, 3, 14];
    const labelFor = (idx) => {
        const match = matches[idx] || {};
        const home = getShortName(match.local || match.home_name || match.home?.name || (idx === 14 ? "Pleno al 15" : "Local"));
        const away = getShortName(match.visitante || match.away_name || match.away?.name || (idx === 14 ? "" : "Visitante"));
        return idx === 14 ? `Pleno al 15: ${home}${away ? ` - ${away}` : ""}` : `${home} - ${away}`;
    };
    return `
        <div class="type-ticket-card">
            <div class="type-ticket-head">
                <span>Boleto &middot; Jornada ${escapeHtml(String(state.data.jornada || state.jornada || "-"))}</span>
                <span>1&nbsp;&nbsp;X&nbsp;&nbsp;2</span>
            </div>
            <div class="type-ticket-rows">
                ${visible.map((idx) => `
                    <div class="type-ticket-row ${idx === 14 ? "is-pleno" : ""}">
                        <span class="type-ticket-num">${String(idx + 1).padStart(2, "0")}</span>
                        <span class="type-ticket-match">${escapeHtml(labelFor(idx))}</span>
                        <span class="type-ticket-line"></span>
                        <b>${escapeHtml(signs[idx] || "-")}</b>
                    </div>
                `).join("")}
            </div>
            <div class="type-ticket-foot">
                <span>+ 10 partidos en la quiniela completa</span>
                <b>${doubles.length ? `${doubles.length} dobles: ${doubles.join(", ")}` : "sin dobles"}</b>
            </div>
        </div>`;
}

function hydrateCoverTypewriter() {
    const title = document.getElementById("cover-type-title");
    if (!title) return;
    const text = title.dataset.text || title.textContent || "";
    if (!text || window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches) {
        title.textContent = text;
        return;
    }
    title.textContent = "";
    let i = 0;
    const tick = () => {
        if (!document.body.contains(title)) return;
        title.textContent = text.slice(0, i);
        i += 1;
        if (i <= text.length) window.setTimeout(tick, 32 + Math.random() * 42);
    };
    tick();
}

function renderNewspaperCoverPageV3() {
    const matches = state.data.partidos || [];
    const liveCount = matches.filter(match => isLiveStatus(match.status) || isLiveMatch(match)).length;
    const finished = matches.filter(match => isFinishedStatus(match.status)).length;
    const saved = hasSavedTicket();
    const jornada = state.data.jornada || state.jornada || "";
    const headline = saved ? "Tu boleto contra las maquinas." : "Tu, contra la maquina.";
    const ticketState = saved ? "Boleto guardado" : "Boleto pendiente";
    const liveLabel = liveCount ? `${liveCount} de quiniela` : `${finished}/15 resueltos`;
    return `
        <section class="typewriter-cover">
            <article class="typewriter-sheet">
                <b class="typewriter-stamp">J.${escapeHtml(String(jornada || "-"))}<br>${state.data.is_locked ? "Cerrada" : "En juego"}</b>
                <div class="typewriter-main">
                    <section class="typewriter-lead">
                        <p class="typewriter-kicker">Portada &middot; Jornada ${escapeHtml(String(jornada || "-"))}</p>
                        <h2 id="cover-type-title" data-text="${escapeHtml(headline)}">${escapeHtml(headline)}</h2>
                        <p>La Pe&ntilde;a rellena el mismo boleto que los Maestros IA. Se comparan pronosticos, ranking y cierre de jornada sin mezclarlo con el resto de secciones.</p>
                        <div class="typewriter-rail" aria-label="Estado de la jornada">
                            <b>${escapeHtml(ticketState)}</b>
                            <b>${escapeHtml(liveLabel)}</b>
                            <b>${escapeHtml(coverCloseLabel())}</b>
                        </div>
                        ${coverSectionsHtml()}
                        ${coverProgramTicketHtml()}
                    </section>
                    <section class="typewriter-hot">
                        ${coverSpotlightHtml()}
                        ${coverNowHtml({ liveCount, finished, saved })}
                    </section>
                </div>
            </article>
        </section>`;
}
