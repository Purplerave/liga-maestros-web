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

/* ---------- Barras compactas de consenso (Peña e IA) ---------- */

function getSignCandidates(rawSign, isPleno = false) {
    const sign = String(rawSign || "").trim().toUpperCase();
    if (!sign || sign === "-") return [];
    if (isPleno) {
        const m = sign.match(/^([0-9M]+)\s*[-–]\s*([0-9M]+)$/);
        if (m) {
            const hVal = m[1] === "M" ? 3 : Number(m[1]);
            const aVal = m[2] === "M" ? 3 : Number(m[2]);
            if (!Number.isNaN(hVal) && !Number.isNaN(aVal)) {
                if (hVal > aVal) return ["1"];
                if (hVal === aVal) return ["X"];
                return ["2"];
            }
        }
    }
    return ["1", "X", "2"].filter(char => sign.includes(char));
}

function getPena1X2Consensus(c, idx, preds, isPleno = false) {
    if (!isPleno && c && (Number(c.p1) > 0 || Number(c.px) > 0 || Number(c.p2) > 0)) {
        return {
            p1: Math.round(Number(c.p1 || 0)),
            px: Math.round(Number(c.px || 0)),
            p2: Math.round(Number(c.p2 || 0))
        };
    }
    let v1 = 0, vx = 0, v2 = 0;
    const penaIds = getPenaHiddenUserIds();
    penaIds.forEach(uid => {
        const sign = normalizeSign(preds?.[uid]?.signos?.[idx] || "-");
        const candidates = getSignCandidates(sign, isPleno);
        if (candidates.length > 0) {
            const weight = 1 / candidates.length;
            candidates.forEach(cand => {
                if (cand === "1") v1 += weight;
                else if (cand === "X") vx += weight;
                else if (cand === "2") v2 += weight;
            });
        }
    });
    const total = v1 + vx + v2;
    if (total === 0) return { p1: 0, px: 0, p2: 0 };
    const p1 = Math.round((v1 / total) * 100);
    const px = Math.round((vx / total) * 100);
    const p2 = Math.max(0, 100 - p1 - px);
    return { p1, px, p2 };
}

function getAi1X2Consensus(preds, idx, predictorColumns, isPleno = false) {
    let v1 = 0, vx = 0, v2 = 0;
    predictorColumns.forEach(([primary, fallback]) => {
        const sign = getSign(preds, idx, primary, fallback);
        const candidates = getSignCandidates(sign, isPleno);
        if (candidates.length > 0) {
            const weight = 1 / candidates.length;
            candidates.forEach(cand => {
                if (cand === "1") v1 += weight;
                else if (cand === "X") vx += weight;
                else if (cand === "2") v2 += weight;
            });
        }
    });
    const total = v1 + vx + v2;
    if (total === 0) return { p1: 0, px: 0, p2: 0 };
    const p1 = Math.round((v1 / total) * 100);
    const px = Math.round((vx / total) * 100);
    const p2 = Math.max(0, 100 - p1 - px);
    return { p1, px, p2 };
}

function renderCompact1X2Bar(label, data, extraClass = "") {
    const p1 = Number(data?.p1 || 0);
    const px = Number(data?.px || 0);
    const p2 = Number(data?.p2 || 0);
    const title = `${label}: 1 (${p1}%) | X (${px}%) | 2 (${p2}%)`;
    return `
        <div class="ticket-compact-bar-row ${escapeHtml(extraClass)}" title="${escapeHtml(title)}" aria-label="${escapeHtml(title)}">
            <span class="ticket-compact-bar-label">${escapeHtml(label)}</span>
            <div class="ticket-compact-bar-track">
                <i class="bar-1" style="width: ${p1}%"></i>
                <i class="bar-x" style="width: ${px}%"></i>
                <i class="bar-2" style="width: ${p2}%"></i>
            </div>
            <span class="ticket-compact-bar-values">1:<b>${p1}%</b> X:<b>${px}%</b> 2:<b>${p2}%</b></span>
        </div>`;
}

function renderMatchConsensusBarsContent(m, idx, c, preds, predictorColumns, isPleno = false) {
    const penaData = getPena1X2Consensus(c, idx, preds, isPleno);
    const aiData = getAi1X2Consensus(preds, idx, predictorColumns, isPleno);
    return `
        ${renderCompact1X2Bar("Peña", penaData, "is-pena-bar")}
        ${renderCompact1X2Bar("IA", aiData, "is-ai-bar")}`;
}

function renderMatchConsensusBars(m, idx, c, preds, predictorColumns, isPleno = false) {
    return `
        <div class="match-consensus-bars" data-match-idx="${idx}">
            ${renderMatchConsensusBarsContent(m, idx, c, preds, predictorColumns, isPleno)}
        </div>`;
}

/* ---------- Chips de tensión ---------- */

function renderTensionChip(label, sign, real, status, exactScore = false, extraClass = "", reason = "", primary = "", fallback = "", matchIdx = null) {
    const clean = sign && sign !== "-" ? sign : "-";
    const fullLabel = repairMojibakeText(label);
    const compactLabel = compactTensionLabel(fullLabel);
    const cleanReason = repairMojibakeText(reason || "").trim();
    const explanation = cleanReason ? `${fullLabel}: ${cleanReason}` : fullLabel;
    const hasAiButton = Boolean(primary && matchIdx !== null && matchIdx !== undefined);
    return `
        <div class="tension-chip ${escapeHtml(extraClass)}">
            <span title="${escapeHtml(fullLabel)}">${escapeHtml(compactLabel)}</span>
            <div class="tension-chip-sign-group">
                <b class="ia-signo ${cleanReason ? "has-analysis" : ""} ${hitClass(clean, real, status, exactScore)}" title="${escapeHtml(explanation)}">${escapeHtml(clean)}</b>
                ${hasAiButton ? `<button type="button" class="ai-reason-btn" title="Ver explicación de ${escapeHtml(fullLabel)}" aria-label="Ver explicación de ${escapeHtml(fullLabel)}" data-ai-id="${escapeHtml(primary)}" data-fallback-id="${escapeHtml(fallback || "")}" data-match-idx="${Number(matchIdx)}" data-ai-label="${escapeHtml(fullLabel)}">ⓘ</button>` : ""}
            </div>
        </div>`;
}

function getPredictionReason(preds, idx, primary, fallback) {
    const first = preds?.[primary]?.motivos?.[idx];
    if (first) return first;
    return fallback ? (preds?.[fallback]?.motivos?.[idx] || "") : "";
}

function getAiMotivoText(aiId, fallbackId, idx) {
    const preds = state.data?.predicciones_actuales || {};
    let motivo = preds?.[aiId]?.motivos?.[idx];
    if ((!motivo || !String(motivo).trim()) && fallbackId) {
        motivo = preds?.[fallbackId]?.motivos?.[idx];
    }
    const cleanMotivo = repairMojibakeText(motivo || "").trim();
    return cleanMotivo ? cleanMotivo : "Sin explicación disponible";
}

let _aiReasonListenerAttached = false;
function ensureAiReasonListener() {
    if (_aiReasonListenerAttached) return;
    _aiReasonListenerAttached = true;
    document.addEventListener("click", event => {
        const btn = event.target.closest(".ai-reason-btn");
        if (!btn) return;
        event.stopPropagation();
        const aiId = btn.dataset.aiId;
        const fallbackId = btn.dataset.fallbackId || null;
        const idx = Number.parseInt(btn.dataset.matchIdx, 10);
        const aiLabel = btn.dataset.aiLabel;
        if (Number.isNaN(idx)) return;
        showAiReasonModal(aiId, fallbackId, idx, aiLabel);
    });
}

function showAiReasonModal(aiId, fallbackId, idx, aiLabel) {
    const existing = document.getElementById("ai-reason-modal-overlay");
    if (existing) existing.remove();

    const m = state.data?.partidos?.[idx];
    const matchTitle = m
        ? `Partido ${idx + 1}: ${getShortName(m.local)} - ${getShortName(m.visitante)}`
        : `Partido ${idx + 1}`;
    const reasonText = getAiMotivoText(aiId, fallbackId, idx);

    const overlay = document.createElement("div");
    overlay.id = "ai-reason-modal-overlay";
    overlay.className = "ai-reason-modal-overlay";
    overlay.setAttribute("role", "dialog");
    overlay.setAttribute("aria-modal", "true");
    overlay.setAttribute("aria-labelledby", "ai-reason-modal-title");

    overlay.innerHTML = `
        <div class="ai-reason-modal">
            <header class="ai-reason-modal-header">
                <div>
                    <h3 id="ai-reason-modal-title">${escapeHtml(aiLabel || "Maestro IA")}</h3>
                    <p class="ai-reason-modal-subtitle">${escapeHtml(matchTitle)}</p>
                </div>
                <button type="button" class="ai-reason-modal-close" aria-label="Cerrar modal">&times;</button>
            </header>
            <div class="ai-reason-modal-body">
                <p class="ai-reason-text">${escapeHtml(reasonText)}</p>
            </div>
            <footer class="ai-reason-modal-footer">
                <button type="button" class="ai-reason-modal-ok">Cerrar</button>
            </footer>
        </div>`;

    document.body.appendChild(overlay);

    const closeBtn = overlay.querySelector(".ai-reason-modal-close");
    const okBtn = overlay.querySelector(".ai-reason-modal-ok");
    const closeModal = () => {
        overlay.remove();
        document.removeEventListener("keydown", onKeyDown);
    };
    const onKeyDown = (e) => {
        if (e.key === "Escape") closeModal();
    };

    closeBtn?.addEventListener("click", closeModal);
    okBtn?.addEventListener("click", closeModal);
    overlay.addEventListener("click", (e) => {
        if (e.target === overlay) closeModal();
    });
    document.addEventListener("keydown", onKeyDown);

    okBtn?.focus();
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

let _lastPredictionCompletionCheck = 0;

function checkQuinielaCompletion() {
    const done = state.my_signs.filter(s => s !== "-").length;
    if (done === 15 && _lastPredictionCompletionCheck !== 15) {
        _lastPredictionCompletionCheck = 15;
        // 🎊 Quiniela completada
        if (typeof window.launchConfetti === "function") {
            window.launchConfetti({ count: 50, spread: 80, duration: 2500, origin: { x: 0.5, y: 0.2 } });
        }
        if (typeof SoundManager !== "undefined" && SoundManager.playCountComplete) {
            SoundManager.playCountComplete();
        }
        showToast("🎯 ¡Quiniela completa! Ya puedes guardarla.");
    } else if (done < 15) {
        _lastPredictionCompletionCheck = done;
    }
}

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

/* ---------- Comentarios de jornada ---------- */

let ticketCommentsTimer = null;

function ticketCommentTime(value) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "";
    return date.toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit" });
}

function renderTicketCommentsPanel() {
    const signedIn = Boolean(state.user);
    return `
        <aside class="ticket-comments" aria-labelledby="ticket-comments-title">
            <header class="ticket-comments-head">
                <div><span>EN DIRECTO</span><strong id="ticket-comments-title">Comentarios</strong></div>
                <button type="button" data-comments-refresh title="Actualizar comentarios" aria-label="Actualizar comentarios">&#8635;</button>
            </header>
            <div id="ticket-comments-list" class="ticket-comments-list">
                <div class="ticket-comments-empty">Cargando conversaci&oacute;n...</div>
            </div>
            ${signedIn ? `
                <form class="ticket-comments-form" data-comments-form>
                    <label for="ticket-comment-input">Comenta la jornada</label>
                    <div>
                        <input id="ticket-comment-input" name="texto" maxlength="240" autocomplete="off" placeholder="¿Qu&eacute; partido ves m&aacute;s claro?">
                        <button type="submit">Enviar</button>
                    </div>
                </form>` : `
                <div class="ticket-comments-login">Entra con Google para comentar.</div>`}
        </aside>`;
}

function renderTicketComments(comments = []) {
    const target = qs("ticket-comments-list");
    if (!target) return;
    if (!comments.length) {
        target.innerHTML = `<div class="ticket-comments-empty">A&uacute;n no hay comentarios. Abre el debate.</div>`;
        return;
    }
    target.innerHTML = comments.map(comment => `
        <article class="ticket-comment">
            <div><strong>${escapeHtml(comment.nombre || "Participante")}</strong><time>${escapeHtml(ticketCommentTime(comment.created_at))}</time></div>
            <p>${escapeHtml(comment.texto || "")}</p>
        </article>`).join("");
    target.scrollTop = target.scrollHeight;
}

async function loadTicketComments({ quiet = false } = {}) {
    if (state.currentFilter !== "TICKET" || !state.data?.jornada) return;
    try {
        const response = await fetch(`/api/comentarios?j=${encodeURIComponent(state.data.jornada)}`, { cache: "no-store" });
        if (!response.ok) throw new Error("No se pudieron cargar los comentarios");
        const payload = await response.json();
        renderTicketComments(payload.comments || []);
    } catch (error) {
        if (!quiet) {
            const target = qs("ticket-comments-list");
            if (target) target.innerHTML = `<div class="ticket-comments-empty">No se pudieron cargar los comentarios.</div>`;
        }
    }
}

async function submitTicketComment(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const input = form.querySelector("input[name='texto']");
    const text = String(input?.value || "").trim();
    if (!text) return;
    const submit = form.querySelector("button[type='submit']");
    if (submit) submit.disabled = true;
    try {
        const response = await fetch("/api/comentarios", {
            method: "POST",
            headers: authenticatedJsonHeaders(),
            body: JSON.stringify({ jornada: state.data.jornada, texto: text })
        });
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.message || "No se pudo publicar");
        input.value = "";
        await loadTicketComments({ quiet: true });
    } catch (error) {
        showToast(error.message || "No se pudo publicar", "error");
    } finally {
        if (submit) submit.disabled = false;
        input?.focus();
    }
}

function stopTicketComments() {
    if (ticketCommentsTimer) window.clearInterval(ticketCommentsTimer);
    ticketCommentsTimer = null;
}

function initTicketComments() {
    stopTicketComments();
    loadTicketComments();
    qs("matches-body")?.querySelector("[data-comments-form]")?.addEventListener("submit", submitTicketComment);
    qs("matches-body")?.querySelector("[data-comments-refresh]")?.addEventListener("click", () => loadTicketComments());
    ticketCommentsTimer = window.setInterval(() => {
        if (!document.hidden) loadTicketComments({ quiet: true });
    }, 30000);
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

    ensureAiReasonListener();

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
            return `<td class="ticket-pick-cell">${renderTensionChip(label, sign, isPleno ? m.marcador : real, m.status, isPleno, "", reason, primary, fallback, idx)}</td>`;
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
                    ${renderMatchConsensusBars(m, idx, c, preds, predictorColumns, isPleno)}
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

    ensureAiReasonListener();

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

        const consensusBarsEl = row.querySelector(".match-consensus-bars");
        if (consensusBarsEl) {
            consensusBarsEl.innerHTML = renderMatchConsensusBarsContent(match, idx, consensus, preds, predictorColumns, isPleno);
        }

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
                reason,
                primary,
                fallback,
                idx
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
/* botón guardar oculto si no hay usuario */
