/* ==========================================================================
   TICKET PAGE — Vista Quiniela compacta (tension, tabla, peña, pleno)
   ========================================================================== */

function penaPercents(c) {
    // p1/px/p2 already arrive as 0-100. Do not scale them again.
    const p1 = Math.max(0, Math.round(Number(c?.p1 || 0)));
    const px = Math.max(0, Math.round(Number(c?.px || 0)));
    const p2 = Math.max(0, Math.round(Number(c?.p2 || 0)));
    return { p1, px, p2 };
}

function renderMatchInsight(match) {
    return "";
}

function renderMatchDetailGrid(m, c) {
    return `<div class="match-detail-grid"><div class="empty-state">Detalle del partido</div></div>`;
}

function renderConsensus(c, real, status) {
    const { p1, px, p2 } = penaPercents(c);
    const winner = c.ganador || "-";
    if (!Number(c.total || 0) && p1 + px + p2 <= 0) {
        return `<span class="pena-pick">—</span>`;
    }
    const items = [
        { sign: "1", pct: p1 },
        { sign: "X", pct: px },
        { sign: "2", pct: p2 },
    ];
    const peak = Math.max(p1, px, p2);
    const detail = `1 ${p1}% · X ${px}% · 2 ${p2}%`;
    const breakdown = items.map(item => {
        const leader = item.pct === peak && peak > 0 ? " is-leader" : "";
        return `<em class="pena-breakdown-item${leader}"><b>${item.sign}</b><small>${item.pct}%</small></em>`;
    }).join("");
    return `<span class="pena-pick ${hitClass(winner, real, status)}" title="${escapeHtml(detail)}"><span class="pena-pick-breakdown">${breakdown}</span></span>`;
}

function getPenaHiddenUserIds() {
    return new Set();
}

function getPenaPlenoSummary(idx = 14) {
    if (idx !== 14) return { top: "-", pct: 0, total: 0 };
    const summary = state.data?.consenso_pleno_pena || {};
    const topScore = Array.isArray(summary.topScore) ? summary.topScore : [];
    const top = plenoScoreKey(topScore[0]) || "-";
    const votes = Number(topScore[1] || 0);
    const total = Number(summary.valid || 0);
    return { top, votes, total, pct: total ? Math.round((votes * 100) / total) : 0 };
}

function renderPenaPleno(summary, realScore, status) {
    if (!summary?.total || summary.top === "-") return `<span class="pena-pick">—</span>`;
    const detail = `${summary.top} · ${summary.votes}/${summary.total} votos`;
    return `<span class="pena-pick pena-pick-pleno ${hitClass(summary.top, realScore, status, true)}" title="${escapeHtml(detail)}"><b>${escapeHtml(summary.top)}</b><small>${summary.pct}%</small></span>`;
}

function renderPenaPlenoDetail(idx = 14) {
    const summary = getPenaPlenoSummary(idx);
    return summary.total ? `${summary.top} · ${summary.votes}/${summary.total}` : "";
}

function renderTensionChip(label, sign, real, status, exactScore = false, extraClass = "", reason = "") {
    const clean = normalizeSign(sign);
    return `<div class="tension-chip ${extraClass}"><span title="${escapeHtml(label)}">${escapeHtml(compactTensionLabel(label))}</span><b class="ia-signo ${hitClass(clean, real, status, exactScore)}" title="${escapeHtml(reason || label)}">${escapeHtml(clean === "-" ? "—" : clean)}</b></div>`;
}

function getPredictionReason(preds, idx, primary, fallback) {
    const reasonFor = id => preds?.[id]?.razones?.[idx] || preds?.[id]?.motivos?.[idx] || "";
    return reasonFor(primary) || reasonFor(fallback);
}

function renderTensionPenaChip(content, label) {
    return `<div class="tension-chip tension-chip-pena"><span title="${escapeHtml(label)}">${escapeHtml(compactTensionLabel(label))}</span>${content}</div>`;
}

function checkQuinielaCompletion() {
    const done = (state.my_signs || []).filter(s => s && s !== "-").length;
    const el = qs("ticket-picks-done");
    if (el) el.textContent = `${done}/15`;
    const bar = qs("ticket-picks-bar");
    if (bar) bar.style.width = `${(done / 15) * 100}%`;
}

function renderMyCell(idx, mySign, real, status, canEdit, exactScore = false) {
    if (!canEdit) {
        // An empty pleno is not a real 0-0 pick; prompt the user to choose instead.
        const shown = exactScore && mySign === "-" ? "Elegir" : (mySign === "-" ? "—" : mySign);
        return `<b class="ia-signo ticket-user-sign active ${hitClass(mySign, real, status, exactScore)}">${escapeHtml(shown)}</b>`;
    }
    return `<div class="ticket-user-sign-group" data-match-idx="${idx}">${["1", "X", "2"].map(sign => `<button class="ia-signo clickable ${mySign === sign ? "active" : ""}" data-sign="${sign}" type="button">${sign}</button>`).join("")}</div>`;
}

function ticketCommentTime(value) {
    return String(value || "");
}

function renderTicketCommentsPanel() {
    return `<aside class="ticket-comments-panel" id="ticket-comments-panel"><header class="ticket-comments-header"><strong>Comentarios</strong></header><div id="ticket-comments-list" class="ticket-comments-list"><div class="empty-state">Cargando...</div></div></aside>`;
}

function renderTicketComments(comments = []) {
    const list = qs("ticket-comments-list");
    if (!list) return;
    if (!comments.length) {
        list.innerHTML = `<div class="empty-state">Sin comentarios</div>`;
        return;
    }
    list.innerHTML = comments.map(c => `<div class="ticket-comment"><b>${escapeHtml(c.nombre || "Anon")}</b><span>${escapeHtml(c.texto || "")}</span></div>`).join("");
}

function stopTicketComments() {}

function initTicketComments() {
    const list = qs("ticket-comments-list");
    if (list) list.innerHTML = `<div class="empty-state">Comentarios de la jornada</div>`;
}

function renderLiveScrutinyBadge(matches) {
    if (!Array.isArray(matches) || !matches.length) return "";
    const live = matches.filter(m => isMatchLiveNow(m)).length;
    const finished = matches.filter(m => isFinishedStatus(m.status) || isImplicitlyFinished(m)).length;
    if (!live && !finished) return "";
    return `<div class="live-scrutiny-badge" aria-live="polite">${live ? `<span class="is-live">${live} en directo</span>` : ""}${finished ? `<span class="is-done">${finished} finalizados</span>` : ""}</div>`;
}

function renderArenaTensionBody(matches) {
    const tbody = qs("arena-body");
    const thead = qs("arena-thead");
    if (!tbody || !thead) return;

    const councilStyle = typeof isCouncilStyleJornada === "function" && isCouncilStyleJornada();
    const predictorColumns = councilStyle
        ? [["programa", "v260_omnisciente", "Programa"], ["consejo_ias", "consenso", "Consejo IA"]]
        : (typeof getOfficialAIColumns === "function" ? getOfficialAIColumns() : [["programa", null, "PROG"], ["gemini", null, "GEM"], ["grok", null, "GROK"], ["claude", null, "CLAU"], ["chatgpt", "gpt", "GPT"]]);

    thead.innerHTML = `<tr><th>#</th><th style="text-align:left;">Partido</th><th class="ticket-status-heading">Hora / resultado</th>${predictorColumns.map(([, , label]) => `<th class="ticket-predictor-heading" title="${escapeHtml(label)}">${escapeHtml(label)}</th>`).join("")}<th class="ticket-predictor-heading ticket-pena-heading">Peña</th><th class="ticket-user-heading">Tu quiniela</th></tr>`;

    const preds = state.data?.predicciones_actuales || state.data?.predicciones || {};
    const consenso = state.data?.consenso_pena || [];
    const canEdit = Boolean(state.user) && String(state.data?.jornada) === String(state.data?.max_jornada) && !state.data?.is_locked;

    tbody.innerHTML = matches.map((m, idx) => {
        const isPleno = idx === 14;
        const real = m.signo_actual || "-";
        const mySign = (state.my_signs || [])[idx] || "-";
        const plenoLabel = mySign === "-" ? "Elegir" : mySign;
        const c = consenso.find(item => Number(item.id) === Number(m.id)) || { p1: 0, px: 0, p2: 0, ganador: "-" };
        const scheduledMatch = needsFixtureSchedule(m);
        const liveMatch = isMatchLiveNow(m) && !scheduledMatch;
        const score = scheduledMatch ? fixtureScheduleDisplay(m) : (m.marcador || m.score || "-");
        const scoreText = liveMatch ? liveScoreDisplay(m, score) : score;
        const isFinished = isFinishedStatus(m.status) || isImplicitlyFinished(m);
        const values = [Number(c.p1 || 0), Number(c.px || 0), Number(c.p2 || 0)].sort((a, b) => b - a);
        const splitMatch = idx !== 14 && !isFinished && values[0] > 0 && values[0] - values[1] <= 12;
        const rowClass = [
            councilStyle ? "is-council-row" : "",
            isPleno ? "is-pleno-row" : "",
            liveMatch ? "is-live-row" : (isFinished ? "is-finished-row" : ""),
            splitMatch ? "is-split-row" : ""
        ].filter(Boolean).join(" ");
        const statusText = scheduledMatch ? score : "";
        const scoreBadge = scheduledMatch
            ? ""
            : `<span class="match-score-badge ${liveMatch ? "is-live-score" : ""}"${liveScoreAttrs(m, liveMatch)}>${escapeHtml(scoreText)}</span>`;
        const penaChip = isPleno
            ? renderTensionPenaChip(renderPenaPleno(getPenaPlenoSummary(idx), m.marcador, m.status), "Peña")
            : renderTensionPenaChip(renderConsensus(c, real, m.status), "Peña");
        const mine = renderMyCell(idx, mySign, isPleno ? m.marcador : real, m.status, canEdit, isPleno);
        const predictorCells = predictorColumns.map(([primary, fallback, label]) => {
            const sign = getSign(preds, idx, primary, fallback);
            const reason = getPredictionReason(preds, idx, primary, fallback);
            return `<td class="ticket-pick-cell">${renderTensionChip(label, sign, isPleno ? m.marcador : real, m.status, isPleno, "", reason)}</td>`;
        }).join("");

        return `<tr class="tension-row ${rowClass}" data-ticket-row="${idx}">
            <td class="match-index-cell"><span class="match-number">${idx + 1}</span></td>
            <td class="fixture-cell tension-fixture-cell"><div class="tension-fixture-main">${fixtureInline(m.local, m.visitante, m.logo_local, m.logo_visitante)}</div></td>
            <td class="ticket-status-cell" data-ticket-status>${scoreBadge}${statusText ? `<span class="tension-status">${escapeHtml(statusText)}</span>` : ""}</td>
            ${predictorCells}
            <td class="ticket-pick-cell ticket-pena-cell">${penaChip}</td>
            <td class="ticket-pick-cell ticket-user-cell"${isPleno ? ` title="Elegir resultado del Pleno al 15" data-pleno-label="${plenoLabel}"` : ""}><div class="tension-chip tension-chip-user"><span title="Tu quiniela">TU</span>${mine}</div></td>
        </tr>${state.expandedMatch === idx ? `<tr class="match-detail-row"><td colspan="${predictorColumns.length + 5}">${renderMatchDetailGrid(m, c)}</td></tr>` : ""}`;
    }).join("");

    document.querySelectorAll(".ticket-user-sign-group button.ia-signo.clickable").forEach(btn => {
        btn.onclick = (e) => {
            e.preventDefault();
            const group = btn.closest(".ticket-user-sign-group");
            const idx = Number(group?.dataset.matchIdx);
            const sign = btn.dataset.sign;
            if (Number.isNaN(idx) || !sign) return;
            if (!state.my_signs) state.my_signs = Array(15).fill("-");
            state.my_signs[idx] = sign;
            group.querySelectorAll("button").forEach(b => b.classList.toggle("active", b.dataset.sign === sign));
            checkQuinielaCompletion();
            if (typeof saveMyTicketDebounced === "function") saveMyTicketDebounced();
        };
    });
    checkQuinielaCompletion();
}

function patchTicketArena() {
    if (state.currentFilter !== "TICKET") return false;
    const matches = state.data?.partidos || [];
    const rows = [...document.querySelectorAll("#arena-body tr.tension-row[data-ticket-row]")];
    if (!matches.length || rows.length !== matches.length) return false;

    for (const [idx, match] of matches.entries()) {
        const row = rows.find(item => Number(item.dataset.ticketRow) === idx);
        if (!row) continue;
        const scheduledMatch = needsFixtureSchedule(match);
        const liveMatch = isMatchLiveNow(match) && !scheduledMatch;
        const isFinished = isFinishedStatus(match.status) || isImplicitlyFinished(match);
        const score = scheduledMatch ? fixtureScheduleDisplay(match) : (match.marcador || match.score || "-");
        const scoreText = liveMatch ? liveScoreDisplay(match, score) : score;
        const statusCell = row.querySelector("[data-ticket-status]");
        if (!statusCell) continue;
        statusCell.innerHTML = scheduledMatch
            ? `<span class="tension-status">${escapeHtml(score)}</span>`
            : `<span class="match-score-badge ${liveMatch ? "is-live-score" : ""}"${liveScoreAttrs(match, liveMatch)}>${escapeHtml(scoreText)}</span>`;
        row.classList.toggle("is-live-row", liveMatch);
        row.classList.toggle("is-finished-row", isFinished);
    }
    return true;
}

function ensureQ15Directo() {
    return Promise.resolve(false);
}

function loadPorra() {
    const body = qs("ticket-porra-body");
    if (body) body.innerHTML = `<div class="empty-state">Porra de la jornada</div>`;
}
