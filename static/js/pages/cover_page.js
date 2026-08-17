/* Portada Liga de Maestros v16 — EL BOLETO
   La portada ES el boleto de la quiniela. Sin paneles laterales, sin
   clasificaciones, sin trash talk, sin journey. Solo el boleto de 15
   partidos vivo + el header mínimo + la banda de directos abajo. */

function loadSacramentoFont() {}
function hydrateCoverTypewriter() {}
function startCoverScorebar() {}

let _countdownStarted = false;
let _seasonCountdownStarted = false;
const SEASON_KICKOFF = new Date("2026-08-15T19:30:00");

// ============================================================
// COUNTDOWN (intacto, reutilizado por header)
// ============================================================
function formatCountdownDigits(diff) {
    const safe = Math.max(0, diff);
    const days = Math.floor(safe / 86400000);
    const hours = Math.floor((safe % 86400000) / 3600000);
    const mins = Math.floor((safe % 3600000) / 60000);
    const secs = Math.floor((safe % 60000) / 1000);
    return `<span class="bol-cd-num">${String(days).padStart(2, "0")}</span><i>d</i>`
        + `<span class="bol-cd-num">${String(hours).padStart(2, "0")}</span><i>h</i>`
        + `<span class="bol-cd-num">${String(mins).padStart(2, "0")}</span><i>m</i>`
        + `<span class="bol-cd-num">${String(secs).padStart(2, "0")}</span><i>s</i>`;
}

function startCoverCountdown() {
    if (_countdownStarted) return;
    _countdownStarted = true;
    const tick = () => {
        const deadline = document.querySelector("#bol-deadline");
        if (!deadline) return;
        const raw = (state && state.data && (state.data.edit_deadline || state.data.kickoff_at || "")) || "";
        if (!raw) { deadline.textContent = state?.data?.is_locked ? "CERRADA" : "ABIERTA"; return; }
        const target = new Date(String(raw).replace(" ", "T"));
        if (Number.isNaN(target.getTime())) { deadline.textContent = state?.data?.is_locked ? "CERRADA" : "ABIERTA"; return; }
        const diff = target.getTime() - Date.now();
        if (diff <= 0 || state.data.is_locked) {
            deadline.textContent = "CERRADA";
            deadline.classList.add("is-urgent");
            return;
        }
        const s = Math.max(0, Math.floor(diff / 1000));
        const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60;
        deadline.textContent = h > 0 ? `${h}h ${String(m).padStart(2,"0")}m ${String(sec).padStart(2,"0")}s` : `${String(m).padStart(2,"0")}m ${String(sec).padStart(2,"0")}s`;
        deadline.classList.toggle("is-urgent", diff < 3_600_000);
    };
    tick(); setInterval(tick, 1000);
}

function startSeasonCountdown() {
    const update = () => {
        const timer = document.getElementById("bol-cd");
        if (!timer) return;
        const now = Date.now();
        let target = SEASON_KICKOFF.getTime();
        let usingJornada = false;
        const raw = (state && state.data && (state.data.edit_deadline || state.data.kickoff_at || "")) || "";
        if (now >= target && raw) {
            const deadline = new Date(String(raw).replace(" ", "T"));
            if (!Number.isNaN(deadline.getTime()) && deadline.getTime() > now) {
                target = deadline.getTime();
                usingJornada = true;
            }
        }
        const diff = target - Date.now();
        if (diff <= 0) {
            timer.innerHTML = `<span class="bol-cd-live">EN JUEGO</span>`;
            return;
        }
        timer.innerHTML = formatCountdownDigits(diff);
        timer.classList.toggle("is-urgent", diff < 3_600_000);
    };
    update();
    if (_seasonCountdownStarted) return;
    _seasonCountdownStarted = true;
    setInterval(update, 1000);
}
if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
        startCoverCountdown();
        startSeasonCountdown();
    });
} else {
    startCoverCountdown();
    startSeasonCountdown();
}

// ============================================================
// HELPERS
// ============================================================
function _teamAbbr(name) {
    if (!name) return "—";
    const s = String(name).trim();
    return s.replace(/[^A-Za-zÁÉÍÓÚÜÑáéíóúüñ\s]/g, "")
        .split(/\s+/)
        .map(w => w[0] || "")
        .join("")
        .slice(0, 3)
        .toUpperCase() || s.slice(0, 3).toUpperCase();
}

function _maestroInitial(col) {
    if (!col) return "?";
    const id = String(col.id || col.label || "").toLowerCase();
    if (id.includes("claude")) return "C";
    if (id.includes("gpt") || id.includes("chatgpt")) return "G";
    if (id.includes("gemini")) return "G";
    if (id.includes("grok")) return "X";
    if (id.includes("copilot")) return "K";
    if (id.includes("programa")) return "P";
    return (col.label || id).slice(0, 1).toUpperCase();
}

function _maestroToneClass(col) {
    if (!col) return "is-default";
    const id = String(col.id || col.label || "").toLowerCase();
    if (id.includes("claude")) return "is-claude";
    if (id.includes("gpt") || id.includes("chatgpt")) return "is-chatgpt";
    if (id.includes("gemini")) return "is-gemini";
    if (id.includes("grok")) return "is-grok";
    if (id.includes("copilot")) return "is-copilot";
    if (id.includes("programa")) return "is-programa";
    return "is-default";
}

function _userPickFor(index) {
    const signs = state.my_signs || [];
    const raw = signs[index];
    if (!raw || raw === "-") return null;
    return String(raw).toUpperCase();
}

function _isMatchLive(match) {
    if (!match) return false;
    if (typeof isExpiredLiveMatch === "function" && isExpiredLiveMatch(match)) return false;
    if (typeof isLiveStatus === "function" && isLiveStatus(match.status)) return true;
    if (typeof isLiveMatch === "function" && isLiveMatch(match)) return true;
    return false;
}

function _isMatchClosed(match) {
    if (!match) return false;
    const real = String(match.signo_actual || "").toUpperCase();
    return ["1","X","2"].includes(real);
}

// ============================================================
// BOLETO HELPERS (las funciones legacy de v14 que arena.js y
// otras vistas siguen importando — se mantienen como stubs)
// ============================================================
function coverBandoState() { return "primera"; }
function coverTrashTalkMasters() { return []; }
function coverTrashTalkReplica() { return ""; }
function coverTrashTalkHtml() { return ""; }
function setTrashTalkIdx() {}
function startTrashTalkRotation() {}
function triggerProgressPop() {}
function loadSeasonSummary() {}
function coverCloseLabel() {
    const raw = state?.data?.edit_deadline || state?.data?.kickoff_at || "";
    if (!raw) return state?.data?.is_locked ? "cerrada" : "abierta";
    const date = new Date(String(raw).replace(" ", "T"));
    if (Number.isNaN(date.getTime())) return state?.data?.is_locked ? "cerrada" : "abierta";
    const diff = date.getTime() - Date.now();
    if (diff <= 0 || state?.data?.is_locked) return "cerrada";
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(minutes / 60);
    const mins = minutes % 60;
    if (hours >= 24) return `${Math.floor(hours / 24)}d ${hours % 24}h`;
    if (hours > 0) return `${hours}h ${String(mins).padStart(2, "0")}m`;
    return `${Math.max(1, mins)}m`;
}
function coverIsClosed() { return Boolean(state?.data?.is_locked) || coverCloseLabel() === "cerrada"; }
function coverMasterColumns() {
    return (state.data?.participant_contract?.visible_ai_columns || []).map(col => ({
        id: Array.isArray(col) ? col[0] : col.id,
        label: Array.isArray(col) ? (col[2] || col[0]) : (col.name || col.label || col.id),
    })).filter(col => col.id);
}
function coverMasterNames() { return coverMasterColumns().filter(col => String(col.id).toLowerCase() !== "programa").map(col => col.label); }
function coverDisplayName(uid) {
    const names = state.data?.participant_contract?.names || {};
    const id = String(uid || "").toLowerCase();
    if (state.user && String(state.user.id).toLowerCase() === id) return state.user.name || "Tu";
    return names[id] || names[uid] || String(uid || "").split("@")[0];
}
function coverRankingRows() {
    const ranking = state.data?.ranking_maestros || {};
    const hidden = new Set((state.data?.participant_contract?.hidden_ids || []).map(id => String(id).toLowerCase()));
    return Object.entries(ranking).filter(([uid]) => !hidden.has(String(uid).toLowerCase()))
        .map(([uid, values]) => ({ uid, name: coverDisplayName(uid), total: Number(values?.total || 0), jornada: Number(values?.jornada_live ?? values?.jornada ?? 0) }))
        .sort((a, b) => b.total - a.total || b.jornada - a.jornada || a.name.localeCompare(b.name, "es"));
}
function coverBandoDetailed() {
    return { rows: [], humanTotal: 0, aiTotal: 0, humanCount: 1, aiCount: 1, humanAvg: 0, aiAvg: 0 };
}
function coverPredictionSigns(entry) { if (Array.isArray(entry)) return entry; return Array.isArray(entry?.signos) ? entry.signos : []; }
function coverPenaReading(row) {
    if (!row || !Number(row.total || 0)) return null;
    const readings = [{ sign: "1", percent: Number(row.p1 || 0) }, { sign: "X", percent: Number(row.px || 0) }, { sign: "2", percent: Number(row.p2 || 0) }];
    const peak = Math.max(...readings.map(item => item.percent));
    return { sign: readings.filter(item => item.percent === peak).map(item => item.sign).join(""), percent: peak, total: Number(row.total || 0) };
}
function coverCollectivePenaScore() { return { hits: 0, played: 0, totalMatches: 0 }; }
function coverDisagreementMatch() { return null; }
function coverTightPenaMatch() { return null; }
function coverFixtureHtml() { return ""; }
function updateCoverPorraStep() {}
function hydrateCoverPorra() {}
function updateCpScorebar() {}
function updateCpUrgency() {}

// ============================================================
// RENDER PRINCIPAL — v16 EL BOLETO
// ============================================================
function renderNewspaperCoverPageV3() {
    const matches = (state.data?.partidos || []).slice(0, 15);
    const closed = coverIsClosed();
    const saved = typeof hasSavedTicket === "function" ? hasSavedTicket() : false;
    const jornada = state.data?.jornada || state.jornada || "1";
    const masterCols = coverMasterColumns();
    const predictions = state.data?.predicciones_actuales || {};
    const userDone = (state.my_signs || []).filter(s => s && s !== "-").length;
    const liveMatches = matches.filter(m => _isMatchLive(m));
    const assetsV = document.body?.dataset?.assetsV || "";
    const crestSrc = `/static/img/liga_maestros_mark.svg?v=${encodeURIComponent(assetsV)}`;
    const statusLabel = closed ? "CERRADA" : coverCloseLabel();
    const ctaLabel = closed
        ? (saved ? "Ver mi quiniela" : "Ver resultados")
        : (saved ? "Revisar quiniela" : "Firmar quiniela");
    const userPct = Math.min(100, (userDone / 15) * 100);

    // === HEADER MÍNIMO ===
    const headerHtml = `
        <header class="bol-header">
            <div class="bol-brand">
                <img class="bol-crest" src="${crestSrc}" alt="" width="32" height="32" decoding="async" fetchpriority="high">
                <div class="bol-brand-text">
                    <b>LIGA DE MAESTROS</b>
                    <span>J${escapeHtml(String(jornada))} · La Peña vs IA</span>
                </div>
            </div>
            <div class="bol-cd-block">
                <span class="bol-cd-label">${closed ? "JORNADA" : "CIERRA EN"}</span>
                <span class="bol-cd-value" id="bol-deadline">${escapeHtml(statusLabel)}</span>
                <span class="bol-cd-timer" id="bol-cd">—</span>
            </div>
            <div class="bol-progress-block">
                <span class="bol-progress-label"><b id="bol-done">${userDone}</b>/15</span>
                <span class="bol-progress-track"><i style="width:${userPct.toFixed(1)}%"></i></span>
            </div>
            <button type="button" class="bol-cta-primary" data-page-action="TICKET">${escapeHtml(ctaLabel)} →</button>
        </header>
    `;

    // === BOLETO: 15 casillas en grid ===
    function buildBoletoCell(match, index) {
        if (!match) {
            return `<div class="bol-cell is-empty">
                <span class="bol-cell-num">${String(index + 1).padStart(2, "0")}</span>
                <span class="bol-cell-empty">—</span>
            </div>`;
        }
        const homeAbbr = _teamAbbr(match.local);
        const awayAbbr = _teamAbbr(match.visitante);
        const userPick = _userPickFor(index);
        const isLive = _isMatchLive(match);
        const isClosed = _isMatchClosed(match);
        const realSign = String(match.signo_actual || "").toUpperCase();

        // Picks de los maestros en línea 1X2 compacta
        const maestroSigns = masterCols.map(col => {
            const signs = coverPredictionSigns(predictions[col.id]);
            const sign = signs[index] || "-";
            if (sign === "-") return null;
            return { sign, tone: _maestroToneClass(col), initial: _maestroInitial(col), label: col.label };
        }).filter(Boolean);

        // Línea "1 X 2" del boleto: muestra los maestros como mini-labels con su signo
        const maestroLine = maestroSigns.length
            ? maestroSigns.map(m => `<span class="bol-pick ${m.tone}" title="${escapeHtml(m.label)}"><i>${m.initial}</i><b>${escapeHtml(m.sign)}</b></span>`).join("")
            : `<span class="bol-no-pick">—</span>`;

        return `
            <button type="button" class="bol-cell${userPick ? " is-signed" : ""}${isLive ? " is-live" : ""}${isClosed ? " is-closed" : ""}${userPick && realSign && userPick === realSign ? " is-hit" : ""}${userPick && realSign && userPick !== realSign ? " is-miss" : ""}"
                    data-page-action="TICKET"
                    aria-label="Partido ${index + 1}: ${escapeHtml(match.local)} contra ${escapeHtml(match.visitante)}">
                <span class="bol-cell-num">${String(index + 1).padStart(2, "0")}</span>
                ${isLive ? '<span class="bol-live-dot" aria-label="En directo">●</span>' : ""}
                ${isClosed && realSign ? `<span class="bol-cell-result" aria-label="Resultado ${escapeHtml(realSign)}">${escapeHtml(realSign)}</span>` : ""}
                <span class="bol-cell-teams">
                    <span class="bol-team is-home">${homeAbbr}</span>
                    <span class="bol-cell-sep">·</span>
                    <span class="bol-team is-away">${awayAbbr}</span>
                </span>
                <span class="bol-cell-masters">${maestroLine}</span>
                <span class="bol-cell-mypick">
                    ${userPick ? `<span class="bol-mypick-val">${userPick}</span>` : `<span class="bol-mypick-val is-empty">—</span>`}
                </span>
            </button>
        `;
    }

    const boletoGridHtml = matches.map((m, i) => buildBoletoCell(m, i)).join("");
    const boletoEmpty = matches.length === 0
        ? `<div class="bol-empty-grid">Los partidos se publicarán con el cierre de la jornada anterior.</div>`
        : "";

    const boletoHtml = `
        <main class="bol-main">
            <header class="bol-main-head">
                <div class="bol-main-title">
                    <span class="bol-main-jornada">JORNADA ${escapeHtml(String(jornada))}</span>
                    <span class="bol-main-sub">EL BOLETO · 15 PARTIDOS</span>
                </div>
                <div class="bol-main-status">
                    <b>${userDone}/15</b> FIRMADOS · <b>${15 - userDone}</b> ABIERTOS
                </div>
            </header>
            <div class="bol-grid">
                ${boletoGridHtml}
                ${boletoEmpty}
            </div>
            <footer class="bol-main-foot">
                <div class="bol-legend">
                    <span class="bol-legend-item"><i class="bol-legend-dot is-claude"></i>Claude</span>
                    <span class="bol-legend-item"><i class="bol-legend-dot is-chatgpt"></i>ChatGPT</span>
                    <span class="bol-legend-item"><i class="bol-legend-dot is-gemini"></i>Gemini</span>
                    <span class="bol-legend-item"><i class="bol-legend-dot is-grok"></i>Grok</span>
                    <span class="bol-legend-item"><i class="bol-legend-dot is-copilot"></i>Copilot</span>
                </div>
                <div class="bol-cta-row">
                    <button type="button" class="bol-cta-ghost" data-page-action="TICKET">Ver boletos guardados</button>
                    <button type="button" class="bol-cta-primary bol-cta-big" data-page-action="TICKET">${escapeHtml(ctaLabel)} →</button>
                </div>
            </footer>
        </main>
    `;

    // === BANDA DE DIRECTOS (abajo, viva) ===
    function buildLiveCard(match) {
        if (!match) return "";
        const homeAbbr = _teamAbbr(match.local);
        const awayAbbr = _teamAbbr(match.visitante);
        const score = match.marcador || match.score || match.resultado || "0-0";
        const minute = match.minuto || match.minute || "0";
        const realSign = String(match.signo_actual || "").toUpperCase();
        return `
            <div class="bol-live-card">
                <span class="bol-live-pulse" aria-hidden="true"></span>
                <span class="bol-live-min">${escapeHtml(String(minute))}'</span>
                <span class="bol-live-team">${homeAbbr}</span>
                <span class="bol-live-score">${escapeHtml(String(score))}</span>
                <span class="bol-live-team">${awayAbbr}</span>
                ${realSign ? `<span class="bol-live-sign">${escapeHtml(realSign)}</span>` : ""}
            </div>
        `;
    }

    const liveStripHtml = liveMatches.length ? `
        <aside class="bol-live-strip" aria-label="Partidos en directo">
            <span class="bol-live-strip-label">
                <i class="bol-live-pulse" aria-hidden="true"></i>
                EN DIRECTO · ${liveMatches.length}
            </span>
            <div class="bol-live-track">${liveMatches.map(buildLiveCard).join("")}</div>
            <button type="button" class="bol-live-more" data-page-action="LIVE">Ver todo →</button>
        </aside>
    ` : "";

    return `<div class="bol">
        ${headerHtml}
        ${boletoHtml}
        ${liveStripHtml}
    </div>`;
}
