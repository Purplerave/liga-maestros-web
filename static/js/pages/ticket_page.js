/* ==========================================================================
   TICKET PAGE — Vista Quiniela compacta (tension, tabla, peña, pleno)
   Funciones extraídas de quantum_final.js para mantenimiento fácil.
   Dependencias: todas las funciones shared/ utility de quantum_final.js
   deben cargarse ANTES que este archivo.
   ========================================================================== */

/* ---------- Insight y detalle de partido ---------- */

function pctTriplet(label, values) {
    if (!values) return "";
    const p1 = values["1"] ?? values[1] ?? "-";
    const px = values["X"] ?? values.x ?? values["x"] ?? "-";
    const p2 = values["2"] ?? values[2] ?? "-";
    return `<span class="insight-chip"><b>${escapeHtml(label)}</b> 1 ${escapeHtml(p1)}% | X ${escapeHtml(px)}% | 2 ${escapeHtml(p2)}%</span>`;
}

function renderMatchInsight(match) {
    const info = state.data?.match_info?.[String(match.id)] || {};
    const maestra = info.maestra || {};
    const chips = [
        pctTriplet("Tendencia", info.q15),
        pctTriplet("LAE", info.lae),
        pctTriplet("Mercado", info.apu)
    ].filter(Boolean).join("");
    const historico = info.historico ?
         `<small class="insight-muted">Histórico: ${escapeHtml(info.historico["1"] || 0)} local | ${escapeHtml(info.historico["X"] || 0)} empates | ${escapeHtml(info.historico["2"] || 0)} visitante</small>`
        : "";
    const reason = maestra.razon ?
         `<p class="insight-reason"><b>${escapeHtml(maestra.signo || "Maestra")}</b> ${escapeHtml(maestra.razon)}</p>`
        : "";
    const detail = info.detalle ?
         `<small class="insight-muted">${escapeHtml(info.detalle).slice(0, 220)}${String(info.detalle).length > 220 ? "..." : ""}</small>`
        : "";
    if (!chips && !reason && !historico && !detail) {
        return `<small class="q15-empty">Sin lectura previa cacheada para este partido.</small>`;
    }
    return `
        <div class="match-insight">
            ${reason}
            ${chips ? `<div class="insight-chips">${chips}</div>` : ""}
            ${historico}
            ${detail}
        </div>`;
}

function renderMatchDetailGrid(m, c) {
    const homeCtx = findStandingContext(m.local);
    const awayCtx = findStandingContext(m.visitante);
    const homeLine = homeCtx ?
         `${getShortName(m.local)} | #${homeCtx.pos} | ${homeCtx.pts} pts`
        : `${getShortName(m.local)} | sin ranking`;
    const awayLine = awayCtx ?
         `${getShortName(m.visitante)} | #${awayCtx.pos} | ${awayCtx.pts} pts`
        : `${getShortName(m.visitante)} | sin ranking`;
    const plenoDetail = Number(m.id) === 15 ? renderPenaPlenoDetail(14) : null;
    return `
        <div class="match-detail-grid">
            <div class="match-detail-box">
                <span class="match-detail-label">La Peña</span>
                ${plenoDetail
                    ? plenoDetail
                    : `<strong>1 ${Number(c.p1 || 0)}% | X ${Number(c.px || 0)}% | 2 ${Number(c.p2 || 0)}%</strong>`}
            </div>
            <div class="match-detail-box">
                <span class="match-detail-label">Tabla</span>
                <strong>${escapeHtml(homeLine)}</strong>
                <small>${escapeHtml(awayLine)}</small>
            </div>
            <div class="match-detail-box match-detail-box-wide">
                <span class="match-detail-label">Lectura previa</span>
                ${renderMatchInsight(m)}
            </div>
            <div class="match-detail-box match-detail-box-wide">
                <span class="match-detail-label">Directo del partido</span>
                ${renderQ15Events(m)}
                ${renderQ15Meta(m)}
            </div>
        </div>`;
}

/* ---------- Consenso y Peña ---------- */

function renderConsensus(c, real, status) {
    const values = [
        ["1", Number(c.p1 || 0), "home"],
        ["X", Number(c.px || 0), "draw"],
        ["2", Number(c.p2 || 0), "away"]
    ];
    const sorted = [...values].sort((a, b) => b[1] - a[1]);
    const rawWinner = normalizeSign(c.ganador);
    const winner = ["1", "X", "2"].includes(rawWinner) ? rawWinner : sorted[0][0];
    const detail = `Peña: 1 ${Number(c.p1 || 0)}% | X ${Number(c.px || 0)}% | 2 ${Number(c.p2 || 0)}%`;
    const breakdown = values.map(([sign, value]) => `
        <span class="pena-breakdown-item ${sign === winner ? "is-leader" : ""}">
            <b>${escapeHtml(sign)}</b><small>${value}%</small>
        </span>`).join("");
    return `<span class="pena-pick pena-pick-breakdown ${hitClass(winner, real, status)}" title="${escapeHtml(detail)}" aria-label="${escapeHtml(detail)}">${breakdown}</span>`;
}

function getPenaHiddenUserIds() {
    const visible = new Set(
        getOfficialAIColumns().flatMap(([primary, fallback]) => [primary, fallback].filter(Boolean).map(id => String(id).toLowerCase()))
    );
    const ignored = new Set(["hermes", "jenova", "consenso", "programa", "v260_omnisciente", "consejo_ias"]);
    return Object.keys(state.data.predicciones_actuales || {}).filter(uid => {
        const lower = String(uid).toLowerCase();
        if (visible.has(lower) || ignored.has(lower)) return false;
        if (state.user && String(state.user.id).toLowerCase() === lower) return false;
        return true;
    });
}

function getPenaPlenoSummary(idx = 14) {
    const serverSummary = state.data?.consenso_pleno_pena;
    if (serverSummary && Number(serverSummary.valid || 0) > 0) return serverSummary;
    const preds = state.data.predicciones_actuales || {};
    const exactCounts = {};
    const homeBuckets = { "0": 0, "1": 0, "2": 0, "M": 0 };
    const awayBuckets = { "0": 0, "1": 0, "2": 0, "M": 0 };
    let valid = 0;
    let invalid = 0;

    getPenaHiddenUserIds().forEach(uid => {
        const sign = normalizeSign(preds?.[uid]?.signos?.[idx] || "-");
        const score = plenoScoreKey(sign);
        if (!score) {
            invalid += 1;
            return;
        }
        const match = score.match(/^([012M])-([012M])$/);
        if (!match) {
            invalid += 1;
            return;
        }
        valid += 1;
        exactCounts[score] = (exactCounts[score] || 0) + 1;
        const homeBucket = match[1];
        const awayBucket = match[2];
        if (homeBucket) homeBuckets[homeBucket] += 1;
        if (awayBucket) awayBuckets[awayBucket] += 1;
    });

    const topScore = Object.entries(exactCounts).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))[0] || null;
    return { valid, invalid, exactCounts, homeBuckets, awayBuckets, topScore };
}

function renderPenaPleno(summary, realScore, status) {
    if (!summary.topScore) {
        return `<span class="pena-pick pena-pick-pleno" title="La Peña todavia no tiene un pleno claro"><b>-</b><small>s/d</small></span>`;
    }
    const [topScore, count] = summary.topScore;
    const pct = summary.valid ? Math.round((count / summary.valid) * 100) : 0;
    const detail = [
        `Peña pleno: ${topScore} (${count}/${summary.valid})`,
        `Local 0:${summary.homeBuckets["0"]} 1:${summary.homeBuckets["1"]} 2:${summary.homeBuckets["2"]} M:${summary.homeBuckets["M"]}`,
        `Visit. 0:${summary.awayBuckets["0"]} 1:${summary.awayBuckets["1"]} 2:${summary.awayBuckets["2"]} M:${summary.awayBuckets["M"]}`,
        summary.invalid ? `Sin marcador valido: ${summary.invalid}` : ""
    ].filter(Boolean).join(" | ");
    return `<span class="pena-pick pena-pick-pleno ${hitClass(topScore, realScore, status, true)}" title="${escapeHtml(detail)}"><b>${escapeHtml(topScore)}</b><small>${pct}%</small></span>`;
}

function renderPenaPlenoDetail(idx = 14) {
    const summary = getPenaPlenoSummary(idx);
    if (!summary.topScore) {
        return `<strong>Sin pleno claro en la Peña</strong><small>Cuando tengan marcadores validos, aqui saldra el reparto 0 | 1 | 2 | M.</small>`;
    }
    const [topScore, count] = summary.topScore;
    const exactTop = Object.entries(summary.exactCounts)
        .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
        .slice(0, 3)
        .map(([score, qty]) => `${score} (${qty})`)
        .join(" | ");
    const bucketLine = (label, buckets) => `${label}: 0 ${buckets["0"]} | 1 ${buckets["1"]} | 2 ${buckets["2"]} | M ${buckets["M"]}`;
    return `
        <strong>${escapeHtml(topScore)} | ${count}/${summary.valid} Peña</strong>
        <small>${escapeHtml(bucketLine("Local", summary.homeBuckets))}</small>
        <small>${escapeHtml(bucketLine("Visit.", summary.awayBuckets))}</small>
        <small>${escapeHtml(`Marcadores: ${exactTop}${summary.invalid ? ` | sin valido ${summary.invalid}` : ""}`)}</small>`;
}

/* ---------- Chips de tensión ---------- */

function renderTensionChip(label, sign, real, status, exactScore = false, extraClass = "", reason = "") {
    const clean = sign && sign !== "-" ? sign : "-";
    const fullLabel = repairMojibakeText(label);
    const compactLabel = compactTensionLabel(fullLabel);
    const cleanReason = repairMojibakeText(reason || "").trim();
    const explanation = cleanReason ? `${fullLabel}: ${cleanReason}` : fullLabel;
    return `
        <div class="tension-chip ${escapeHtml(extraClass)}">
            <span title="${escapeHtml(fullLabel)}">${escapeHtml(compactLabel)}</span>
            <b class="ia-signo ${cleanReason ? "has-analysis" : ""} ${hitClass(clean, real, status, exactScore)}" title="${escapeHtml(explanation)}">${escapeHtml(clean)}</b>
        </div>`;
}

function getPredictionReason(preds, idx, primary, fallback) {
    const first = preds?.[primary]?.motivos?.[idx];
    if (first) return first;
    return fallback ? (preds?.[fallback]?.motivos?.[idx] || "") : "";
}

function renderTensionPenaChip(content, label) {
    const fullLabel = repairMojibakeText(label);
    const compactLabel = compactTensionLabel(fullLabel);
    return `
        <div class="tension-chip tension-chip-pena">
            <span title="${escapeHtml(fullLabel)}">${escapeHtml(compactLabel)}</span>
            ${content}
        </div>`;
}

/* ---------- Celda del usuario ---------- */

function renderMyCell(idx, mySign, real, status, canEdit, exactScore = false) {
    if (!state.user) return `<span class="empty-user-pick" title="Entra para guardar tu quiniela">-</span>`;
    if (!canEdit) return `<b class="ia-signo ticket-user-sign active ${hitClass(mySign, real, status, exactScore)}">${escapeHtml(mySign === "-" ? "—" : mySign)}</b>`;
    if (hasSavedTicket() && !state.editMode && !state.draftDirty) {
        return `<b class="ia-signo ticket-user-sign active ${hitClass(mySign, real, status, exactScore)}">${escapeHtml(mySign === "-" ? "—" : mySign)}</b>`;
    }
    if (idx === 14) {
        return `<button class="pleno-main-btn clickable" data-match-idx="${idx}" data-pleno="1">${escapeHtml(mySign === "-" ? "0-0" : mySign)}</button>`;
    }
    return `
        <div class="action-buttons" data-match-idx="${idx}">
            ${["1", "X", "2"].map(sign => `<button class="ia-signo clickable ${mySign === sign ? "active" : ""}" data-sign="${sign}" type="button">${sign}</button>`).join("")}
        </div>`;
}

/* ---------- Badge de escrutinio live ---------- */

function renderLiveScrutinyBadge(matches) {
    if (!state.user || !Array.isArray(matches) || !matches.some(match => isMatchLiveNow(match))) return "";
    const hits = matches.slice(0, 15).reduce((count, match, idx) => {
        const exactScore = idx === 14;
        const real = exactScore ? scoreOnly(match.marcador) : (match.signo_actual || "-");
        return count + (isHitSign(state.my_signs[idx], real, exactScore) ? 1 : 0);
    }, 0);
    const liveCount = matches.filter(match => isMatchLiveNow(match)).length;
    return `<div class="live-scrutiny-badge">Escrutinio live <strong>${hits}/15</strong> provisionales · ${liveCount} en juego</div>`;
}

/* ---------- Análisis de tensión por partido ---------- */

function renderArenaTensionBody(matches) {
    const tbody = qs("arena-body");
    const thead = qs("arena-thead");
    if (!tbody || !thead) return;

    const councilStyle = isCouncilStyleJornada();
    const predictorColumns = councilStyle
        ? [["programa", "v260_omnisciente", "Programa"], ["consejo_ias", "consenso", "Consejo IA"]]
        : getOfficialAIColumns();
    thead.innerHTML = `
        <tr>
            <th>#</th>
            <th style="text-align:left;">Partido</th>
            <th class="ticket-status-heading">Hora / resultado</th>
            ${predictorColumns.map(([, , label]) => `<th class="ticket-predictor-heading" title="${escapeHtml(label)}">${escapeHtml(label)}</th>`).join("")}
            <th class="ticket-predictor-heading ticket-pena-heading">Peña</th>
            <th class="ticket-user-heading">Tu quiniela</th>
        </tr>`;

    const preds = state.data.predicciones_actuales || {};
    const consenso = state.data.consenso_pena || [];
    const canEdit = Boolean(state.user) && String(state.data.jornada) === String(state.data.max_jornada) && !state.data.is_locked;

    tbody.innerHTML = matches.map((m, idx) => {
        const isPleno = idx === 14;
        const real = m.signo_actual || "-";
        const realScore = scoreOnly(m.marcador);
        const mySign = state.my_signs[idx] || "-";
        const c = consenso.find(item => Number(item.id) === Number(m.id)) || { p1: 0, px: 0, p2: 0, ganador: "-" };
        const consensoPleno = getPenaPlenoSummary(idx);
        const liveMatch = isMatchLiveNow(m);
        const scheduledMatch = isScheduledStatus(m.status) && !liveMatch;
        const score = scheduledMatch ? formatSmartDate(m.fecha_raw, m.hora) : (m.marcador || "-");
        const scoreText = liveMatch ? liveScoreDisplay(m, score) : score;
        const mine = renderMyCell(idx, mySign, isPleno ? m.marcador : real, m.status, canEdit, isPleno);
        const isFinished = isFinishedStatus(m.status);
        const values = [Number(c.p1 || 0), Number(c.px || 0), Number(c.p2 || 0)].sort((a, b) => b - a);
        const splitMatch = idx !== 14 && !isFinished && values[0] > 0 && values[0] - values[1] <= 12;
        const rowClass = [
            councilStyle ? "is-council-row" : "",
            liveMatch ? "is-live-row" : (isFinished ? "is-finished-row" : ""),
            splitMatch ? "is-split-row" : ""
        ].filter(Boolean).join(" ");
        const statusText = scheduledMatch ? score : "";
        const scoreBadge = scheduledMatch
            ? ""
            : `<span class="match-score-badge ${liveMatch ? "is-live-score" : ""}"${liveScoreAttrs(m, liveMatch)}>${escapeHtml(scoreText)}</span>`;
        const penaChip = isPleno ?
             renderTensionPenaChip(renderPenaPleno(consensoPleno, m.marcador, m.status), "Peña")
            : renderTensionPenaChip(renderConsensus(c, real, m.status), "Peña");
        const predictorCells = predictorColumns.map(([primary, fallback, label]) => {
            const sign = getSign(preds, idx, primary, fallback);
            const reason = getPredictionReason(preds, idx, primary, fallback);
            return `<td class="ticket-pick-cell">${renderTensionChip(label, sign, isPleno ? m.marcador : real, m.status, isPleno, "", reason)}</td>`;
        }).join("");

        return `
            <tr class="tension-row ${rowClass}" data-ticket-row="${idx}">
                <td class="match-index-cell">
                    <span class="match-number">${idx + 1}</span>
                </td>
                <td class="fixture-cell tension-fixture-cell">
                    <div class="tension-fixture-main">
                        ${fixtureInline(m.local, m.visitante, teamLogo(m, "home"), teamLogo(m, "away"))}
                    </div>
                </td>
                <td class="ticket-status-cell" data-ticket-status>
                    ${scoreBadge}
                    ${statusText ? `<span class="tension-status">${escapeHtml(statusText)}</span>` : ""}
                </td>
                ${predictorCells}
                <td class="ticket-pick-cell ticket-pena-cell">${penaChip}</td>
                <td class="ticket-pick-cell ticket-user-cell"><div class="tension-chip tension-chip-user"><span title="Tu quiniela">TU</span>${mine}</div></td>
            </tr>
            ${state.expandedMatch === idx ? `
                <tr class="match-detail-row">
                    <td colspan="${predictorColumns.length + 5}">
                        ${renderMatchDetailGrid(m, c)}
                    </td>
                </tr>` : ""}`;
    }).join("");
}

function patchTicketArena() {
    if (state.currentFilter !== "TICKET") return false;
    const matches = state.data?.partidos || [];
    const rows = [...document.querySelectorAll("#arena-body tr.tension-row[data-ticket-row]")];
    if (!matches.length || rows.length !== matches.length) return false;

    const councilStyle = isCouncilStyleJornada();
    const predictorColumns = councilStyle
        ? [["programa", "v260_omnisciente", "Programa"], ["consejo_ias", "consenso", "Consejo IA"]]
        : getOfficialAIColumns();
    const preds = state.data.predicciones_actuales || {};
    const consenso = state.data.consenso_pena || [];
    const canEdit = Boolean(state.user) && String(state.data.jornada) === String(state.data.max_jornada) && !state.data.is_locked;

    for (const [idx, match] of matches.entries()) {
        const row = rows.find(item => Number(item.dataset.ticketRow) === idx);
        if (!row) return false;
        const predictorCells = [...row.querySelectorAll(".ticket-pick-cell:not(.ticket-pena-cell):not(.ticket-user-cell)")];
        if (predictorCells.length !== predictorColumns.length) return false;

        const isPleno = idx === 14;
        const real = match.signo_actual || "-";
        const mySign = state.my_signs[idx] || "-";
        const liveMatch = isMatchLiveNow(match);
        const scheduledMatch = isScheduledStatus(match.status) && !liveMatch;
        const isFinished = isFinishedStatus(match.status);
        const score = scheduledMatch ? formatSmartDate(match.fecha_raw, match.hora) : (match.marcador || "-");
        const scoreText = liveMatch ? liveScoreDisplay(match, score) : score;
        const statusCell = row.querySelector("[data-ticket-status]");
        if (!statusCell) return false;
        statusCell.innerHTML = scheduledMatch
            ? `<span class="tension-status">${escapeHtml(score)}</span>`
            : `<span class="match-score-badge ${liveMatch ? "is-live-score" : ""}"${liveScoreAttrs(match, liveMatch)}>${escapeHtml(scoreText)}</span>`;

        const consensus = consenso.find(item => Number(item.id) === Number(match.id)) || { p1: 0, px: 0, p2: 0, ganador: "-" };
        const values = [Number(consensus.p1 || 0), Number(consensus.px || 0), Number(consensus.p2 || 0)].sort((a, b) => b - a);
        const splitMatch = idx !== 14 && !isFinished && values[0] > 0 && values[0] - values[1] <= 12;
        row.className = [
            "tension-row",
            councilStyle ? "is-council-row" : "",
            liveMatch ? "is-live-row" : (isFinished ? "is-finished-row" : ""),
            splitMatch ? "is-split-row" : ""
        ].filter(Boolean).join(" ");

        predictorColumns.forEach(([primary, fallback, label], columnIdx) => {
            const sign = getSign(preds, idx, primary, fallback);
            const reason = getPredictionReason(preds, idx, primary, fallback);
            predictorCells[columnIdx].innerHTML = renderTensionChip(
                label,
                sign,
                isPleno ? match.marcador : real,
                match.status,
                isPleno,
                "",
                reason
            );
        });

        const penaCell = row.querySelector(".ticket-pena-cell");
        const userCell = row.querySelector(".ticket-user-cell");
        if (!penaCell || !userCell) return false;
        const penaContent = isPleno
            ? renderPenaPleno(getPenaPlenoSummary(idx), match.marcador, match.status)
            : renderConsensus(consensus, real, match.status);
        penaCell.innerHTML = renderTensionPenaChip(penaContent, "Peña");
        const mine = renderMyCell(idx, mySign, isPleno ? match.marcador : real, match.status, canEdit, isPleno);
        userCell.innerHTML = `<div class="tension-chip tension-chip-user"><span title="Tu quiniela">TU</span>${mine}</div>`;
    }
    return true;
}
