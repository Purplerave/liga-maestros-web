/* ==========================================================================
   TICKET PAGE — Vista Quiniela compacta (tension, tabla, peña, pleno)
   Funciones extraídas de quantum_final.js para mantener el ticket aislado.
   Dependencias: utils.js, state.js, arena.js helpers, contest.js (pena).
   ========================================================================== */

function renderLiveScrutinyBadge(matches) {
    if (!Array.isArray(matches) || !matches.length) return "";
    const live = matches.filter(m => isLiveMatch(m) || isLiveStatus(m.status)).length;
    const finished = matches.filter(m => isFinishedStatus(m.status) || isImplicitlyFinished(m)).length;
    if (!live && !finished) return "";
    return `<div class="live-scrutiny-badge" aria-live="polite">
        ${live ? `<span class="is-live">${live} en directo</span>` : ""}
        ${finished ? `<span class="is-done">${finished} finalizados</span>` : ""}
    </div>`;
}

function renderTicketCommentsPanel() {
    return `<aside class="ticket-comments-panel" id="ticket-comments-panel">
        <header class="ticket-comments-header">
            <strong>Comentarios de la jornada</strong>
            <button type="button" class="ghost-btn" id="ticket-comments-close" aria-label="Cerrar">×</button>
        </header>
        <div id="ticket-comments-list" class="ticket-comments-list"><div class="empty-state">Cargando...</div></div>
        <form id="ticket-comments-form" class="ticket-comments-form">
            <textarea id="ticket-comment-input" rows="2" maxlength="280" placeholder="Tu comentario (máx. 280)"></textarea>
            <button type="submit" class="primary-btn">Publicar</button>
        </form>
    </aside>`;
}

function maestraInsightHtml(maestra) {
    if (!maestra) return "";
    return `<div class="insight-block">
         <p class="insight-reason"><b>${escapeHtml(maestra.signo || "Maestra")}</b> ${escapeHtml(maestra.razon || "")}</p>
    </div>`;
}

function penaBreakdownHtml(winner, real, status, detail) {
    return `<span class="pena-pick pena-pick-breakdown ${hitClass(winner, real, status)}" title="${escapeHtml(detail)}" aria-label="${escapeHtml(detail)}">${escapeHtml(detail)}</span>`;
}

function renderPenaPickCell(match, idx, preds, real, status) {
    // Simplified: majority of peña
    const counts = { "1": 0, "X": 0, "2": 0 };
    let total = 0;
    for (const uid of Object.keys(preds || {})) {
        const sign = normalizeSign(preds?.[uid]?.signos?.[idx] || "-");
        if (sign !== "-") {
            counts[sign] = (counts[sign] || 0) + 1;
            total += 1;
        }
    }
    if (!total) return `<span class="pena-pick">—</span>`;
    const winner = Object.entries(counts).sort((a, b) => b[1] - a[1])[0][0];
    const pct = Math.round((counts[winner] / total) * 100);
    const detail = `${winner} ${pct}% (${counts[winner]}/${total})`;
    return penaBreakdownHtml(winner, real, status, detail);
}

function renderPlenoPickCell(match, idx, preds, realScore, status) {
    const scores = {};
    let total = 0;
    for (const uid of Object.keys(preds || {})) {
        const sc = (preds?.[uid]?.marcadores?.[idx] || "").trim();
        if (sc) {
            scores[sc] = (scores[sc] || 0) + 1;
            total += 1;
        }
    }
    if (!total) return `<span class="pena-pick">—</span>`;
    const topScore = Object.entries(scores).sort((a, b) => b[1] - a[1])[0][0];
    const pct = Math.round((scores[topScore] / total) * 100);
    const detail = `${topScore} ${pct}%`;
    return `<span class="pena-pick pena-pick-pleno ${hitClass(topScore, realScore, status, true)}" title="${escapeHtml(detail)}"><b>${escapeHtml(topScore)}</b><small>${pct}%</small></span>`;
}

function iaSignoHtml(clean, real, status, exactScore, explanation, cleanReason) {
    return `
            <b class="ia-signo ${cleanReason ? "has-analysis" : ""} ${hitClass(clean, real, status, exactScore)}" title="${escapeHtml(explanation)}">${escapeHtml(clean)}</b>
        `;
}

function userSignoHtml(mySign, real, status, exactScore, canEdit, matchId) {
    if (!canEdit) return `<b class="ia-signo ticket-user-sign active ${hitClass(mySign, real, status, exactScore)}">${escapeHtml(mySign === "-" ? "—" : mySign)}</b>`;
    if (state.ticketLocked) {
        return `<b class="ia-signo ticket-user-sign active ${hitClass(mySign, real, status, exactScore)}">${escapeHtml(mySign === "-" ? "—" : mySign)}</b>`;
    }
    return `<div class="ticket-user-sign-group" data-match-id="${matchId}">
            ${["1", "X", "2"].map(sign => `<button class="ia-signo clickable ${mySign === sign ? "active" : ""}" data-sign="${sign}" type="button">${sign}</button>`).join("")}
        </div>`;
}

function renderArenaTensionBody(matches) {
    const thead = qs("arena-thead");
    const tbody = qs("arena-body");
    if (!thead || !tbody) return;
    const preds = state.data?.predicciones || {};
    const columns = [
        { key: "num", label: "#" },
        { key: "match", label: "Partido" },
        { key: "status", label: "" },
        { key: "programa", label: "PROG" },
        { key: "gemini", label: "GEM" },
        { key: "grok", label: "GROK" },
        { key: "claude", label: "CLAU" },
        { key: "chatgpt", label: "GPT" },
        { key: "pena", label: "PEÑA" },
        { key: "user", label: "TÚ" }
    ];
    thead.innerHTML = `<tr>${columns.map(c => `<th class="th-${c.key}">${escapeHtml(c.label)}</th>`).join("")}</tr>`;
    tbody.innerHTML = matches.map((m, idx) => renderTensionRow(m, idx, preds)).join("");
    if (typeof bindTicketSignClicks === "function") bindTicketSignClicks();
}

function renderTensionRow(m, idx, preds) {
    const real = m.signo_actual || "-";
    const exactScore = false;
    const status = m.status || "NS";
    const pendingResult = Boolean(m.resultado_pendiente) || String(m.marcador || "").toLowerCase().includes("pendiente de resultado");
    const score = pendingResult
        ? (m.marcador || "Pendiente de resultado")
        : (isScheduledStatus(status) && !isLiveMatch(m) && !isFinishedStatus(status)
            ? formatSmartDate(m.fecha_raw, m.hora)
            : (m.marcador || liveScoreDisplay(m, "-")));
    const liveMatch = isLiveMatch(m) || isLiveStatus(status);
    const scheduledMatch = isScheduledStatus(status) && !liveMatch && !isFinishedStatus(status) && !pendingResult;
    const isFinished = isFinishedStatus(m.status) || pendingResult;
    const scoreText = scheduledMatch ? "" : score;
    const statusText = scheduledMatch && !pendingResult ? score : "";
    const scoreBadge = scheduledMatch && !pendingResult
        ? `<span class="match-score-badge is-scheduled-time">${escapeHtml(statusText)}</span>`
        : `<span class="match-score-badge ${liveMatch ? "is-live-score" : (pendingResult ? "is-pending-result" : "")}"${liveScoreAttrs(m, liveMatch)}>${escapeHtml(scoreText)}</span>`;

    const home = getShortName(m.local);
    const away = getShortName(m.visitante);
    const matchCell = `<div class="tension-match-cell">
        <span class="tm-home">${escapeHtml(home)}</span>
        <span class="tm-vs">–</span>
        <span class="tm-away">${escapeHtml(away)}</span>
        ${scoreBadge}
    </div>`;

    const prog = predSign(preds, "programa", idx);
    const gem = predSign(preds, "gemini", idx);
    const grok = predSign(preds, "grok", idx);
    const claude = predSign(preds, "claude", idx);
    const gpt = predSign(preds, "chatgpt", idx) || predSign(preds, "gpt", idx);
    const mySign = normalizeSign(state.myPicks?.[idx] || preds?.[state.userId]?.signos?.[idx] || "-");
    const canEdit = Boolean(state.userId) && !state.ticketLocked;

    return `<tr class="tension-row ${liveMatch ? "is-live" : ""} ${isFinished ? "is-finished" : ""}" data-match-id="${m.id}">
        <td class="td-num">${idx + 1}</td>
        <td class="td-match">${matchCell}</td>
        <td class="td-status">${statusText ? escapeHtml(statusText) : ""}</td>
        <td class="td-ia">${iaSignoHtml(prog, real, status, false, "Programa", false)}</td>
        <td class="td-ia">${iaSignoHtml(gem, real, status, false, "Gemini", false)}</td>
        <td class="td-ia">${iaSignoHtml(grok, real, status, false, "Grok", false)}</td>
        <td class="td-ia">${iaSignoHtml(claude, real, status, false, "Claude", false)}</td>
        <td class="td-ia">${iaSignoHtml(gpt, real, status, false, "ChatGPT", false)}</td>
        <td class="td-pena">${renderPenaPickCell(m, idx, preds, real, status)}</td>
        <td class="td-user">${userSignoHtml(mySign, real, status, false, canEdit, m.id)}</td>
    </tr>`;
}

function patchTicketLiveScores(matches) {
    if (!Array.isArray(matches)) return false;
    const tbody = qs("arena-body");
    if (!tbody) return false;
    let patched = 0;
    for (const match of matches) {
        const row = tbody.querySelector(`tr[data-match-id="${match.id}"]`);
        if (!row) continue;
        const real = match.signo_actual || "-";
        const status = match.status || "NS";
        const pendingResult = Boolean(match.resultado_pendiente) || String(match.marcador || "").toLowerCase().includes("pendiente de resultado");
        const isFinished = isFinishedStatus(match.status) || pendingResult;
        const score = pendingResult
            ? (match.marcador || "Pendiente de resultado")
            : (isScheduledStatus(status) && !isLiveMatch(match) && !isFinishedStatus(status)
                ? formatSmartDate(match.fecha_raw, match.hora)
                : (match.marcador || liveScoreDisplay(match, "-")));
        const liveMatch = isLiveMatch(match) || isLiveStatus(status);
        const scheduledMatch = isScheduledStatus(status) && !liveMatch && !isFinished && !pendingResult;
        const scoreText = scheduledMatch ? "" : score;
        const statusCell = row.querySelector(".td-status");
        const badge = row.querySelector(".match-score-badge");
        if (badge) {
            badge.className = `match-score-badge ${liveMatch ? "is-live-score" : (pendingResult ? "is-pending-result" : "")}`;
            if (liveMatch) {
                badge.setAttribute("data-live-score", "");
                const attrs = liveScoreAttrs(match, true);
                // simplistic attr update
            }
            badge.textContent = scoreText;
        }
        if (statusCell) {
            statusCell.innerHTML = scheduledMatch && !pendingResult
                ? `<span class="match-score-badge is-scheduled-time">${escapeHtml(score)}</span>`
                : "";
        }
        row.classList.toggle("is-live", liveMatch);
        row.classList.toggle("is-finished", isFinished);
        patched += 1;
    }
    return patched > 0;
}

function updatePicksProgress() {
    const done = qs("ticket-picks-done");
    const bar = qs("ticket-picks-bar");
    if (!done) return;
    const picks = state.myPicks || [];
    const count = picks.filter(p => p && p !== "-").length;
    done.textContent = `${count}/15`;
    if (bar) bar.style.width = `${(count / 15) * 100}%`;
}

function bindTicketSignClicks() {
    document.querySelectorAll(".ticket-user-sign-group button.ia-signo.clickable").forEach(btn => {
        btn.onclick = (e) => {
            e.preventDefault();
            const group = btn.closest(".ticket-user-sign-group");
            const matchId = group?.dataset.matchId;
            const sign = btn.dataset.sign;
            if (!matchId || !sign) return;
            const idx = (state.data?.partidos || []).findIndex(m => String(m.id) === String(matchId));
            if (idx < 0) return;
            if (!state.myPicks) state.myPicks = Array(15).fill("-");
            state.myPicks[idx] = sign;
            group.querySelectorAll("button").forEach(b => b.classList.toggle("active", b.dataset.sign === sign));
            updatePicksProgress();
            if (typeof saveMyTicketDebounced === "function") saveMyTicketDebounced();
        };
    });
}

function initTicketComments() {
    // placeholder – real impl may load from API
    const list = qs("ticket-comments-list");
    if (list) list.innerHTML = `<div class="empty-state">Comentarios de la jornada (próximamente)</div>`;
}

function stopTicketComments() {}

function ensureQ15Directo() {
    return Promise.resolve(false);
}

function loadPorra() {
    const body = qs("ticket-porra-body");
    if (body) body.innerHTML = `<div class="empty-state">Porra de la jornada</div>`;
}

/* botón guardar oculto si no hay usuario */
