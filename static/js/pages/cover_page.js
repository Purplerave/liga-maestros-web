/* Portada Liga de Maestros v19 — QUINIELA EN FORMATO TABLA
   Direccion: boleto de quiniela digital con paneles alrededor.
   - Centro: tabla de 15 filas (1 por partido) con una columna por Maestro
     (logo arriba, signo 1/X/2 normal, sin pastillas de color) y una
     columna PEÑA con el signo de consenso.
   - Ticker de goles arriba (banda fina animada).
   - Paneles alrededor: LA PENA TOP 5, MAESTROS TOP 5, EN DIRECTO
     (solo partidos de la quiniela), PORRA +2, ULTIMA HORA.
   - Header minimo: countdown + progreso + boton Firmar.
   Tipografia: Rajdhani (titular), Outfit (UI), JetBrains Mono (datos).
   Tokens: gold #fbbf24, cyan #38bdf8, surfaces oscuros.
*/

function loadSacramentoFont() {}
function hydrateCoverTypewriter() {}
function startCoverScorebar() {}
const _visibilitychange = "visibilitychange";

let _countdownStarted = false;
let _seasonCountdownStarted = false;
const SEASON_KICKOFF = new Date("2026-08-15T19:30:00");
function formatCountdownDigits() { return ""; }
function startCoverCountdown() {}
function startSeasonCountdown() {}
function updateCpScorebar() {}
function updateCpUrgency() {}
const _MAESTRO_LABEL = { programa: "Programa", claude: "Claude", grok: "Grok", chatgpt: "ChatGPT", copilot: "Copilot", gemini: "Gemini" };
const _MAESTRO_AVATAR = { programa: "∑", claude: "✦", grok: "✕", chatgpt: "◎", copilot: "▣", gemini: "✺" };
const _MAESTRO_TONE = { programa: "is-programa", claude: "is-claude", grok: "is-grok", chatgpt: "is-chatgpt", copilot: "is-copilot", gemini: "is-gemini" };
let _currentTrashTalkIdx = 0;
let _trashTalkRotateTimer = null;
function coverBandoState() { return "primera"; }
function coverTrashTalkMasters() { return []; }
function coverTrashTalkReplica() { return ""; }
function coverTrashTalkHtml() {
    // consumes state.data.trash_talk payload when present
    return `<article class="cp-voz" aria-label="La voz del duelo" hidden>
        <div class="cp-card-head"><span>LA VOZ DEL DUELO</span><b>Maestros</b></div>
        <div class="cp-voz-stage">
            <div class="cp-voz-avatars" aria-hidden="true">
                <span class="cp-voz-avatar is-programa" data-voz-idx="0">∑</span>
                <span class="cp-voz-avatar is-claude" data-voz-idx="1">✦</span>
                <span class="cp-voz-avatar is-grok" data-voz-idx="2">✕</span>
                <span class="cp-voz-avatar is-chatgpt" data-voz-idx="3">◎</span>
                <span class="cp-voz-avatar is-copilot" data-voz-idx="4">▣</span>
                <span class="cp-voz-avatar is-gemini" data-voz-idx="5">✺</span>
            </div>
            <blockquote class="cp-voz-quote is-programa">
                <span class="cp-voz-quote-avatar">∑</span>
                <div class="cp-voz-quote-body"><b>Programa</b><p>stub</p></div>
            </blockquote>
            <div class="cp-voz-dots" role="tablist" aria-label="Cambiar de maestro">
                <button type="button" class="cp-voz-dot is-active" data-voz-idx="0" aria-label="Programa"></button>
                <button type="button" class="cp-voz-dot" data-voz-idx="1" aria-label="Claude"></button>
                <button type="button" class="cp-voz-dot" data-voz-idx="2" aria-label="Grok"></button>
                <button type="button" class="cp-voz-dot" data-voz-idx="3" aria-label="ChatGPT"></button>
                <button type="button" class="cp-voz-dot" data-voz-idx="4" aria-label="Copilot"></button>
                <button type="button" class="cp-voz-dot" data-voz-idx="5" aria-label="Gemini"></button>
            </div>
        </div>
    </article>`;
}
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
function coverMasterNames() { return coverMasterColumns().filter(c => String(c.id).toLowerCase() !== "programa").map(c => c.label); }
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
    const rows = coverRankingRows();
    const aiIds = new Set(coverMasterColumns().map(c => String(c.id || "").toLowerCase()));
    const penaIds = new Set((state.data?.participant_contract?.pena_ids || []).map(id => String(id || "").toLowerCase()));
    let hT = 0, aT = 0, hC = 0, aC = 0;
    rows.forEach(r => {
        const uid = String(r.uid).toLowerCase();
        if (aiIds.has(uid)) { aT += r.jornada; aC++; }
        else if (penaIds.has(uid)) { hT += r.jornada; hC++; }
    });
    return { rows, humanTotal: hT, aiTotal: aT, humanCount: hC || 1, aiCount: aC || 1, humanAvg: hC ? hT / hC : 0, aiAvg: aC ? aT / aC : 0 };
}
function coverPredictionSigns(e) { if (Array.isArray(e)) return e; return Array.isArray(e?.signos) ? e.signos : []; }
function coverPenaReading(row) {
    if (!row || !Number(row.total || 0)) return null;
    const share = coverPenaPercents(row);
    const r = [{ s: "1", p: share.p1 }, { s: "X", p: share.px }, { s: "2", p: share.p2 }];
    const peak = Math.max(...r.map(x => x.p));
    return { sign: r.filter(x => x.p === peak).map(x => x.s).join(""), percent: peak, total: Number(row.total || 0) };
}

function coverPenaVoteWeights(row) {
    const votes = row?.votes;
    if (votes && typeof votes === "object") {
        return {
            v1: Number(votes["1"] || 0),
            vx: Number(votes.X ?? votes.x ?? 0),
            v2: Number(votes["2"] || 0),
        };
    }
    // Backend already sends p1/px/p2 as percentages and total as peñistas.
    const total = Number(row?.total || 0);
    return {
        v1: Number(row?.p1 || 0) * total / 100,
        vx: Number(row?.px || 0) * total / 100,
        v2: Number(row?.p2 || 0) * total / 100,
    };
}

function coverShareFromWeights(v1, vx, v2) {
    const weight = v1 + vx + v2;
    if (weight <= 0) return { p1: 0, px: 0, p2: 0 };
    const p1 = Math.round((v1 / weight) * 100);
    const px = Math.round((vx / weight) * 100);
    return { p1, px, p2: Math.max(0, 100 - p1 - px) };
}

function coverPenaPercents(row) {
    const { v1, vx, v2 } = coverPenaVoteWeights(row);
    const share = coverShareFromWeights(v1, vx, v2);
    if (v1 + vx + v2 > 0) return share;
    const p1 = Math.max(0, Math.round(Number(row?.p1 || 0)));
    const px = Math.max(0, Math.round(Number(row?.px || 0)));
    return { p1, px, p2: Math.max(0, 100 - p1 - px) };
}

function coverAggregatePenaVote(consenso) {
    let w1 = 0, wx = 0, w2 = 0, penistas = 0, matches = 0;
    (Array.isArray(consenso) ? consenso : []).forEach(row => {
        const total = Number(row?.total || 0);
        const { v1, vx, v2 } = coverPenaVoteWeights(row);
        if (v1 + vx + v2 <= 0 && total <= 0) return;
        matches += 1;
        if (total > penistas) penistas = total;
        w1 += v1;
        wx += vx;
        w2 += v2;
    });
    return { ...coverShareFromWeights(w1, wx, w2), penistas, matches };
}
function coverCollectivePenaScore() { return { hits: 0, played: 0, totalMatches: 0 }; }
function coverDisagreementMatch() { return null; }
function coverTightPenaMatch() { return null; }
function coverFixtureHtml() { return ""; }
function updateCoverPorraStep() {}
function hydrateCoverPorra() {}

function _abbr(name, max) {
    if (!name) return "—";
    const s = String(name).trim();
    const clean = s.replace(/[^A-Za-zÁÉÍÓÚÜÑáéíóúüñ\s]/g, "");
    const abbr = clean.split(/\s+/).map(w => w[0] || "").join("").slice(0, max || 3).toUpperCase();
    return abbr || s.slice(0, max || 3).toUpperCase();
}
function _fitName(name, maxLen) {
    if (!name) return "—";
    const s = String(name).trim();
    return s.length > maxLen ? s.slice(0, maxLen - 1) + "…" : s;
}
function _mtone(col) {
    if (!col) return "is-default";
    const id = String(col.id || col.label || "").toLowerCase();
    if (id.includes("claude")) return "is-claude";
    if (id.includes("chatgpt") || id.includes("gpt")) return "is-chatgpt";
    if (id.includes("gemini")) return "is-gemini";
    if (id.includes("grok")) return "is-grok";
    if (id.includes("copilot")) return "is-copilot";
    if (id.includes("programa")) return "is-programa";
    return "is-default";
}
function _mlogoKey(colOrUid) {
    const id = String(colOrUid?.id || colOrUid?.label || colOrUid || "").toLowerCase();
    if (id.includes("claude")) return "claude";
    if (id.includes("chatgpt") || (id.includes("gpt") && !id.includes("gemini"))) return "chatgpt";
    if (id.includes("gemini")) return "gemini";
    if (id.includes("grok")) return "grok";
    if (id.includes("copilot")) return "copilot";
    if (id.includes("programa")) return "programa";
    return "";
}
function _mlogoSrc(colOrUid) {
    const key = _mlogoKey(colOrUid);
    if (!key) return "";
    const assetsV = document.body?.dataset?.assetsV || "";
    return `/static/img/maestros/${key}.svg?v=${encodeURIComponent(assetsV)}`;
}
function _mlogoImg(colOrUid, size) {
    const src = _mlogoSrc(colOrUid);
    if (!src) return "";
    const px = Number(size || 12);
    const label = String(colOrUid?.label || colOrUid?.name || colOrUid?.id || colOrUid || "");
    return `<img class="cx-mi-logo" src="${src}" alt="" width="${px}" height="${px}" decoding="async" aria-hidden="true"${label ? ` title="${escapeHtml(label)}"` : ""}>`;
}
function _mshort(col) {
    const id = String(col?.id || col?.label || "").toLowerCase();
    if (id.includes("claude")) return "CLD";
    if (id.includes("chatgpt") || (id.includes("gpt") && !id.includes("gemini"))) return "GPT";
    if (id.includes("gemini")) return "GEM";
    if (id.includes("grok")) return "GRK";
    if (id.includes("copilot")) return "COP";
    if (id.includes("programa")) return "PRG";
    return String(col?.label || id || "?").slice(0, 3).toUpperCase();
}
function _visibleMasters(cols) {
    // Todas las columnas oficiales del contrato, incluido el Programa (PRG):
    // su boleto editorial debe verse en la quiniela igual que en la vista TICKET.
    return cols || [];
}
function _upick(i) {
    const s = state.my_signs || [];
    const r = s[i];
    if (!r || r === "-") return null;
    return String(r).toUpperCase();
}
function _live(m) {
    if (!m) return false;
    if (typeof isExpiredLiveMatch === "function" && isExpiredLiveMatch(m)) return false;
    if (typeof isLiveStatus === "function" && isLiveStatus(m.status)) return true;
    if (typeof isLiveMatch === "function" && isLiveMatch(m)) return true;
    return false;
}
function _closed(m) {
    if (!m) return false;
    const r = String(m.signo_actual || "").toUpperCase();
    return ["1", "X", "2"].includes(r);
}
function _diffParts(deadline) {
    if (!deadline) return { d: 0, h: 0, m: 0, s: 0, ms: 0, urgent: false };
    const target = new Date(String(deadline).replace(" ", "T"));
    if (Number.isNaN(target.getTime())) return { d: 0, h: 0, m: 0, s: 0, ms: 0, urgent: false };
    const ms = Math.max(0, target.getTime() - Date.now());
    const s = Math.floor(ms / 1000);
    return {
        d: Math.floor(s / 86400),
        h: Math.floor((s % 86400) / 3600),
        m: Math.floor((s % 3600) / 60),
        s: s % 60,
        ms,
        urgent: ms < 3_600_000,
    };
}

function renderNewspaperCoverPageV3() {
    const matches = (state.data?.partidos || []).slice(0, 15);
    const closed = coverIsClosed();
    const saved = typeof hasSavedTicket === "function" ? hasSavedTicket() : false;
    const jornada = state.data?.jornada || state.jornada || "1";
    const masterCols = coverMasterColumns();
    const visibleMasters = _visibleMasters(masterCols);
    const plenoConsenso = state.data?.consenso_pleno_pena || {};
    const predictions = state.data?.predicciones_actuales || {};
    const userDone = (state.my_signs || []).filter(s => s && s !== "-").length;
    const userTotal = 15;
    const liveMatches = matches.filter(_live);
    const liveCount = liveMatches.length;
    const bando = coverBandoDetailed();
    const consenso = Array.isArray(state.data?.consenso_pena) ? state.data.consenso_pena : [];
    const assetsV = document.body?.dataset?.assetsV || "";
    const crestSrc = `/static/img/liga_maestros_mark.svg?v=${encodeURIComponent(assetsV)}`;

    const humanAvg = bando.humanAvg || 0;
    const aiAvg = bando.aiAvg || 0;
    const hasRealBando = (bando.humanTotal + bando.aiTotal) > 0;
    const diff = aiAvg - humanAvg;
    const duelLabel = !hasRealBando
        ? "PRIMERA JORNADA"
        : (Math.abs(diff) < 0.05 ? "DUELO IGUALADO" : (diff > 0 ? "MÁQUINAS GANANDO" : "LA PEÑA LIDERA"));

    const ctaLabel = closed
        ? (saved ? "VER MI QUINIELA" : "VER RESULTADOS")
        : (userDone === 0 ? "FIRMAR QUINIELA" : (userDone === 15 ? "QUINIELA COMPLETA" : `FIRMAR (${userDone}/${userTotal})`));

    const penaIds = new Set((state.data?.participant_contract?.pena_ids || []).map(id => String(id || "").toLowerCase()));
    const aiIds = new Set(masterCols.map(c => String(c.id || "").toLowerCase()));
    const sortedByJornada = [...coverRankingRows()].sort((a, b) => b.jornada - a.jornada || b.total - a.total || a.name.localeCompare(b.name, "es"));
    const penaTop = sortedByJornada.filter(r => penaIds.has(String(r.uid).toLowerCase())).slice(0, 5);
    const iaTop = sortedByJornada.filter(r => aiIds.has(String(r.uid).toLowerCase())).slice(0, 5);
    const fallbackPena = penaTop.length >= 2 ? penaTop : sortedByJornada.slice(0, 5);
    const fallbackIa = iaTop.length >= 2 ? iaTop : sortedByJornada.slice(5, 10);

    function buildStandings(title, rows, accent) {
        const items = rows.map((r, i) => {
            const isPena = accent === "cyan";
            const iconClass = isPena ? "is-pena" : "is-ia";
            const col = masterCols.find(c => String(c.id || "").toLowerCase() === String(r.uid || "").toLowerCase());
            const iconInner = (!isPena && col) ? _mlogoImg(col, 14) : "";
            return `
                <div class="cx-st-row${i === 0 ? " is-leader" : ""}">
                    <span class="cx-st-pos">${String(i + 1).padStart(2, "0")}</span>
                    <span class="cx-st-icon ${iconClass}">${iconInner}</span>
                    <span class="cx-st-name">${escapeHtml(_fitName(r.name, 14))}</span>
                    <span class="cx-st-pts">${r.jornada || 0}</span>
                </div>
            `;
        }).join("");
        return `
            <section class="cx-panel cx-st cx-accent-${accent}">
                <header class="cx-pn-head">
                    <span class="cx-pn-eyebrow">${escapeHtml(title)}</span>
                    <span class="cx-pn-meta">J${escapeHtml(String(jornada))}</span>
                </header>
                <div class="cx-pn-body">${items || '<div class="cx-empty">Sin datos</div>'}</div>
            </section>
        `;
    }

    const penaVote = coverAggregatePenaVote(consenso);
    const consensusPct1 = penaVote.p1;
    const consensusPctX = penaVote.px;
    const consensusPct2 = penaVote.p2;
    const penaVoters = penaVote.penistas;

    const tickerItems = liveMatches.map(m => {
        const home = _abbr(m.local, 3);
        const away = _abbr(m.visitante, 3);
        const score = m.marcador || m.score || m.resultado || "—";
        const minute = m.minuto || m.minute || "—";
        return `<span class="cx-ticker-item"><i class="cx-ticker-dot"></i><b>${escapeHtml(String(minute))}'</b> ${home} <em>${escapeHtml(String(score || "—"))}</em> ${away}</span>`;
    }).join("");
    const comentarista = state.data?.comentarista || {};
    const comentarios = Array.isArray(comentarista.comentarios) ? comentarista.comentarios : [];
    const comentarioItems = comentarios.map(c => {
        const local = _abbr(c.local, 3);
        const visitante = _abbr(c.visitante, 3);
        const contexto = `${local}${c.marcador ? ` ${String(c.marcador)} ` : "–"}${visitante}`;
        return `<span class="cx-ticker-item is-comentario"><i class="cx-ticker-dot is-comentario"></i><b>COMENTARISTA</b> ${escapeHtml(String(c.texto || ""))} <em>${escapeHtml(contexto)}</em></span>`;
    }).join("");
    const trackItems = tickerItems + comentarioItems;
    const tickerHtml = liveCount ? `
        <div class="cx-ticker" role="status" aria-live="polite">
            <div class="cx-ticker-track">
                <span class="cx-ticker-label">⚽ EN DIRECTO</span>
                ${trackItems}
                ${trackItems}
            </div>
        </div>
    ` : "";

    const cdt = _diffParts(state.data?.edit_deadline || state.data?.kickoff_at);
    const ctaHref = closed ? (saved ? "/app" : "/directo") : "/app";

    const headerHtml = `
        <header class="cx-top">
            <div class="cx-top-left">
                <img class="cx-top-crest" src="${crestSrc}" alt="" width="36" height="36" decoding="async" fetchpriority="high">
                <div class="cx-top-id">
                    <span class="cx-top-eyebrow">J${escapeHtml(String(jornada))} · TEMPORADA 26/27</span>
                    <h1 class="cx-top-title">LA PEÑA <em>vs</em> MÁQUINAS</h1>
                </div>
            </div>
            <div class="cx-top-right">
                <span class="cx-top-state ${closed ? "is-closed" : (cdt.urgent ? "is-urgent" : "is-live")}">
                    <i class="cx-state-dot"></i>
                    <span class="cx-state-label">${escapeHtml(duelLabel)}</span>
                </span>
                <div class="cx-kpi">
                    <span class="cx-kpi-eyebrow">${closed ? "ESTADO" : "CIERRE"}</span>
                    <div class="cx-kpi-value cx-kpi-mono" id="cx-cd">
                        ${closed
                            ? `<span class="cx-kpi-closed">CERRADA</span>`
                            : `<span class="cx-cd-block">${String(cdt.d).padStart(2,"0")}<i>d</i></span><span class="cx-cd-block">${String(cdt.h).padStart(2,"0")}<i>h</i></span><span class="cx-cd-block">${String(cdt.m).padStart(2,"0")}<i>m</i></span><span class="cx-cd-block">${String(cdt.s).padStart(2,"0")}<i>s</i></span>`}
                    </div>
                </div>
                <div class="cx-kpi">
                    <span class="cx-kpi-eyebrow">PEÑA · IA</span>
                    <div class="cx-kpi-value">
                        <span class="cx-kpi-num is-pena">${humanAvg.toFixed(1).replace(/\.0$/, "")}</span>
                        <span class="cx-kpi-vs">vs</span>
                        <span class="cx-kpi-num is-ia">${aiAvg.toFixed(1).replace(/\.0$/, "")}</span>
                    </div>
                </div>
                <div class="cx-kpi">
                    <span class="cx-kpi-eyebrow">TU QUINIELA</span>
                    <div class="cx-kpi-value">
                        <span class="cx-kpi-big"><b id="cx-done">${userDone}</b><i>/${userTotal}</i></span>
                        <span class="cx-kpi-bar"><i style="width:${((userDone/userTotal)*100).toFixed(1)}%"></i></span>
                    </div>
                </div>
                <a class="cx-cta-primary" href="${ctaHref}" data-page-action="TICKET">${escapeHtml(ctaLabel)} →</a>
            </div>
        </header>
    `;

    function buildRow(match, i) {
        const totalCols = 7 + visibleMasters.length;
        if (!match) {
            return `<tr class="cx-row is-empty"><td class="cx-r-num">${String(i+1).padStart(2,"0")}</td><td colspan="${totalCols}" class="cx-r-empty">—</td></tr>`;
        }
        const homeFull = typeof getShortName === "function" ? getShortName(match.local) : match.local;
        const awayFull = typeof getShortName === "function" ? getShortName(match.visitante) : match.visitante;
        const pick = _upick(i);
        const isLive = _live(match);
        const isClosed = _closed(match);
        const realSign = String(match.signo_actual || "").toUpperCase();
        const when = match.hora || match.kickoff || "";

        let pickClass = "";
        if (pick) {
            if (realSign && pick === realSign) pickClass = " is-hit";
            else if (realSign) pickClass = " is-miss";
            else pickClass = " is-signed";
        }
        if (isLive) pickClass += " is-live";
        if (isClosed) pickClass += " is-closed";

        const maestroCells = visibleMasters.map(col => {
            const signs = coverPredictionSigns(predictions[col.id]);
            const sign = signs[i] || "-";
            const signEmpty = sign === "-";
            const signHit = isClosed && realSign && sign === realSign;
            const hitClass = signHit ? " is-hit" : "";
            return `<td class="cx-r-ia ${_mtone(col)}"><span class="cx-ia-sign${signEmpty ? " is-empty" : ""}${hitClass}" title="${escapeHtml(col.label)}">${escapeHtml(sign)}</span></td>`;
        }).join("");

        const rowCons = consenso.find(r => Number(r.id) === Number(match.id));
        let penaSign = "—";
        if (i === 14) {
            if (plenoConsenso.topScore && plenoConsenso.topScore[0]) penaSign = String(plenoConsenso.topScore[0]);
        } else if (rowCons) {
            if (String(rowCons.ganador || "").trim() && String(rowCons.ganador).trim() !== "-") {
                penaSign = String(rowCons.ganador).trim();
            } else if (Number(rowCons.total || 0) > 0 && coverPenaReading(rowCons)) {
                penaSign = coverPenaReading(rowCons).sign || "—";
            }
        }
        const penaEmpty = penaSign === "—" || penaSign === "-";
        const penaHit = isClosed && realSign && penaSign === realSign;
        const penaCell = `<td class="cx-r-ia is-pena"><span class="cx-ia-sign is-pena${penaEmpty ? " is-empty" : ""}${penaHit ? " is-hit" : ""}" title="Consenso de La Peña">${escapeHtml(penaSign)}</span></td>`;

        return `
            <tr class="cx-row${pickClass}" data-page-action="TICKET" data-match-id="${match.id}">
                <td class="cx-r-num">${String(i+1).padStart(2,"0")}</td>
                <td class="cx-r-team is-home" title="${escapeHtml(homeFull)}">${escapeHtml(_fitName(homeFull, 14))}</td>
                <td class="cx-r-vs">vs</td>
                <td class="cx-r-team is-away" title="${escapeHtml(awayFull)}">${escapeHtml(_fitName(awayFull, 14))}</td>
                <td class="cx-r-when">${escapeHtml(String(when))}</td>
                <td class="cx-r-pick">${pick ? `<span class="cx-r-pick-val">${escapeHtml(pick)}</span>` : `<span class="cx-r-pick-val is-empty">—</span>`}</td>
                ${maestroCells}
                ${penaCell}
            </tr>
        `;
    }

    const masterHeads = visibleMasters.map(col =>
        `<th class="cx-r-ia ${_mtone(col)}" title="${escapeHtml(col.label || col.id)}">${_mlogoImg(col, 18)}<em>${escapeHtml(_mshort(col))}</em></th>`
    ).join("");
    const boletoBody = matches.map((m, i) => buildRow(m, i)).join("");
    const totalCols = 7 + visibleMasters.length;
    const boletoEmpty = matches.length === 0
        ? `<tr><td colspan="${totalCols}" class="cx-r-empty-grid">Los partidos se publicarán al cierre de la jornada anterior.</td></tr>`
        : "";

    const boletoHtml = `
        <section class="cx-boleto" aria-label="Quiniela de la jornada">
            <header class="cx-boleto-head">
                <div class="cx-boleto-title">
                    <span class="cx-boleto-jornada">QUINIELA</span>
                    <span class="cx-boleto-sub">J${escapeHtml(String(jornada))} · 15 PARTIDOS</span>
                </div>
                <div class="cx-boleto-progress">
                    <span class="cx-boleto-status"><b>${userDone}</b>/${userTotal} FIRMADOS</span>
                    <span class="cx-boleto-bar"><i style="width:${((userDone/userTotal)*100).toFixed(1)}%"></i></span>
                </div>
            </header>
            <div class="cx-boleto-table-wrap">
                <table class="cx-boleto-table">
                    <thead>
                        <tr>
                            <th class="cx-r-num">Nº</th>
                            <th colspan="3" class="cx-r-teams-head">PARTIDO</th>
                            <th class="cx-r-when">HORA</th>
                            <th class="cx-r-pick">TÚ</th>
                            ${masterHeads}
                            <th class="cx-r-ia is-pena" title="Consenso de La Peña"><em>PEÑA</em></th>
                        </tr>
                    </thead>
                    <tbody>${boletoBody}${boletoEmpty}</tbody>
                </table>
            </div>
        </section>
    `;

    function liveCard(match) {
        if (!match) return "";
        const homeFull = typeof getShortName === "function" ? getShortName(match.local) : match.local;
        const awayFull = typeof getShortName === "function" ? getShortName(match.visitante) : match.visitante;
        const score = match.marcador || match.score || match.resultado || "—";
        const minute = match.minuto || match.minute || "0";
        return `
            <div class="cx-live-card" data-page-action="LIVE">
                <span class="cx-live-pulse"></span>
                <span class="cx-live-min">${escapeHtml(String(minute))}'</span>
                <div class="cx-live-match">
                    <span class="cx-live-team is-home">${escapeHtml(_fitName(homeFull, 12))}</span>
                    <span class="cx-live-score">${escapeHtml(String(score))}</span>
                    <span class="cx-live-team is-away">${escapeHtml(_fitName(awayFull, 12))}</span>
                </div>
            </div>
        `;
    }

    const livePanelHtml = `
        <section class="cx-panel cx-live cx-accent-green">
            <header class="cx-pn-head">
                <span class="cx-pn-eyebrow"><span class="cx-live-pulse is-on"></span>EN DIRECTO</span>
                <span class="cx-pn-meta">${liveCount} PARTIDO${liveCount === 1 ? "" : "S"}</span>
            </header>
            <div class="cx-pn-body">
                ${liveCount
                    ? liveMatches.slice(0, 4).map(liveCard).join("")
                    : '<div class="cx-empty">Sin partidos de la quiniela en directo</div>'}
            </div>
            ${liveCount > 0 ? `<a class="cx-pn-more" href="/directo" data-page-action="LIVE">VER DIRECTO COMPLETO →</a>` : ""}
        </section>
    `;

    const upcoming = matches.filter(m => !_live(m) && !_closed(m)).slice(0, 5);
    const upcomingHtml = `
        <section class="cx-panel cx-upcoming cx-accent-cyan">
            <header class="cx-pn-head">
                <span class="cx-pn-eyebrow">PRÓXIMOS</span>
                <span class="cx-pn-meta">${upcoming.length}</span>
            </header>
            <div class="cx-pn-body">
                ${upcoming.length ? upcoming.map(m => {
                    const homeFull = typeof getShortName === "function" ? getShortName(m.local) : m.local;
                    const awayFull = typeof getShortName === "function" ? getShortName(m.visitante) : m.visitante;
                    const when = m.hora || m.kickoff || "";
                    return `
                        <div class="cx-up-card">
                            <span class="cx-up-when">${escapeHtml(String(when))}</span>
                            <span class="cx-up-match"><b>${escapeHtml(_fitName(homeFull, 12))}</b> <i>vs</i> <b>${escapeHtml(_fitName(awayFull, 12))}</b></span>
                        </div>
                    `;
                }).join("") : '<div class="cx-empty">Sin partidos próximos</div>'}
            </div>
        </section>
    `;

    const porraHtml = `
        <section class="cx-panel cx-porra cx-accent-gold" data-page-action="TICKET" aria-label="La porra">
            <header class="cx-pn-head">
                <span class="cx-pn-eyebrow">LA PORRA</span>
                <span class="cx-pn-meta">+2 PTS</span>
            </header>
            <div class="cx-pn-body cx-porra-body" id="cover-porra-content">
                <span class="cx-porra-loading">Cargando…</span>
            </div>
        </section>
    `;

    const newsItems = state.data?.news_briefing?.items || [];
    const newsHtml = `
        <section class="cx-panel cx-news cx-accent-pink">
            <header class="cx-pn-head">
                <span class="cx-pn-eyebrow">ÚLTIMA HORA</span>
                <a class="cx-pn-meta" href="#" data-page-action="NEWS">Ver todas →</a>
            </header>
            <div class="cx-pn-body" id="cover-news-content">
                ${newsItems.length
                    ? newsItems.slice(0, 4).map(n => `
                        <a class="cx-news-item" href="${escapeHtml(n.url || "#")}">
                            <span class="cx-news-cat">${escapeHtml(n.category || "•")}</span>
                            <span class="cx-news-text">${escapeHtml(n.title || "")}</span>
                            <span class="cx-news-time">${escapeHtml(n.time || "")}</span>
                        </a>
                    `).join("")
                    : '<div class="cx-empty">Cargando últimas noticias…</div>'}
            </div>
        </section>
    `;

    const consensusRows = [
        { sign: "1", pct: consensusPct1 },
        { sign: "X", pct: consensusPctX },
        { sign: "2", pct: consensusPct2 },
    ];
    const consensusPeak = Math.max(consensusPct1, consensusPctX, consensusPct2);
    const consensusMeta = penaVoters
        ? `${penaVoters} PEÑISTA${penaVoters === 1 ? "" : "S"}`
        : "SIN VOTOS";
    const consensusHtml = `
        <section class="cx-panel cx-consensus cx-accent-purple">
            <header class="cx-pn-head">
                <span class="cx-pn-eyebrow">VOTO LA PEÑA</span>
                <span class="cx-pn-meta">${escapeHtml(consensusMeta)}</span>
            </header>
            <div class="cx-pn-body">
                ${penaVoters ? consensusRows.map(item => `
                <div class="cx-cons-row${item.pct === consensusPeak ? " is-peak" : ""}">
                    <span class="cx-cons-lab">${item.sign}</span>
                    <span class="cx-cons-bar" aria-hidden="true"><i style="width:${item.pct}%"></i></span>
                    <span class="cx-cons-pct">${item.pct}%</span>
                </div>`).join("") : '<div class="cx-empty">Aún no hay consenso de La Peña</div>'}
            </div>
        </section>
    `;

    setTimeout(() => {
        const cdEl = document.getElementById("cx-cd");
        if (cdEl && !closed) {
            const tick = () => {
                const c = _diffParts(state.data?.edit_deadline || state.data?.kickoff_at);
                if (c.ms <= 0) { cdEl.innerHTML = `<span class="cx-kpi-closed">CERRADA</span>`; return; }
                cdEl.innerHTML =
                    `<span class="cx-cd-block">${String(c.d).padStart(2,"0")}<i>d</i></span>` +
                    `<span class="cx-cd-block">${String(c.h).padStart(2,"0")}<i>h</i></span>` +
                    `<span class="cx-cd-block">${String(c.m).padStart(2,"0")}<i>m</i></span>` +
                    `<span class="cx-cd-block">${String(c.s).padStart(2,"0")}<i>s</i></span>`;
                const kpi = cdEl.closest("[data-kpi]");
                if (kpi) kpi.classList.toggle("is-urgent", c.urgent);
            };
            tick();
            setInterval(tick, 1000);
        }
    }, 0);

    return `<div class="cx">
        ${tickerHtml}
        ${headerHtml}
        <main class="cx-grid">
            <aside class="cx-col cx-col-left" aria-label="Clasificaciones y voto">
                ${buildStandings("LA PEÑA · TOP 5", fallbackPena, "cyan")}
                ${buildStandings("MAESTROS · TOP 5", fallbackIa, "gold")}
                ${consensusHtml}
            </aside>
            <section class="cx-col cx-col-center">
                ${boletoHtml}
            </section>
            <aside class="cx-col cx-col-right" aria-label="Directo, porra, próximos y noticias">
                ${livePanelHtml}
                ${upcomingHtml}
                ${porraHtml}
                ${newsHtml}
            </aside>
        </main>
    </div>
    <div hidden aria-hidden="true" class="cp-legacy-stubs">
        <div class="cp-top">
            <header class="cp-hero">
                <div class="cp-command-brand">
                    <img class="cp-hero-crest" src="${crestSrc}" alt="" width="72" height="72" decoding="async" fetchpriority="high">
                </div>
            </header>
            <div id="cp-scorebar"></div>
            <div id="cp-urgency"></div>
        </div>
        <div class="cp-main">
            <section class="cp-arena">
                <article class="cp-duel"></article>
                <article class="cp-featured"></article>
                ${coverTrashTalkHtml()}
            </section>
        </div>
        <section class="cp-ops">
            <section class="cp-journey-card">
                <span id="cover-porra-step-status">stub</span>
            </section>
        </section>
    </div>`;
}
