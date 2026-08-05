/* Portada Liga de Maestros — Rediseño limpio v2
   - Hero ancho potente, sin logo duplicado
   - 3 módulos iguales, 2 secundarios
   - Sin 7 columnas, responsive vuelve a 900px
*/

// Stubs requeridos por arena.js (evita ReferenceError si se llama desde renderArena)
function loadSacramentoFont() {}
function hydrateCoverTypewriter() {}
function startCoverScorebar() {}

let _countdownStarted = false;

function startCoverCountdown() {
    if (_countdownStarted) return;
    const node = document.querySelector("#cp-deadline");
    if (!node) return;
    _countdownStarted = true;
    const tick = () => {
        const raw = (state && state.data && (state.data.edit_deadline || state.data.kickoff_at || "")) || "";
        if (!raw) {
            node.textContent = state?.data?.is_locked ? "CERRADA" : "ABIERTA";
            return;
        }
        const target = new Date(String(raw).replace(" ", "T"));
        if (Number.isNaN(target.getTime())) {
            node.textContent = state?.data?.is_locked ? "CERRADA" : "ABIERTA";
            return;
        }
        const diff = target.getTime() - Date.now();
        if (diff <= 0 || (state && state.data && state.data.is_locked)) {
            node.textContent = "CERRADA";
            node.classList.add("is-urgent");
            return;
        }
        const s = Math.max(0, Math.floor(diff / 1000));
        const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60;
        node.textContent = h > 0 ? `${h}h ${String(m).padStart(2,"0")}m` : `${String(m).padStart(2,"0")}m ${String(sec).padStart(2,"0")}s`;
        node.classList.toggle("is-urgent", diff < 3_600_000);
    };
    tick();
    setInterval(tick, 1000);
}
if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", startCoverCountdown);
} else {
    startCoverCountdown();
}

/* Helpers sin cambios funcionales */
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
function coverIsClosed() {
    return Boolean(state.data.is_locked) || coverCloseLabel() === "cerrada";
}
function coverMasterColumns() {
    return (state.data?.participant_contract?.visible_ai_columns || []).map(col => ({
        id: Array.isArray(col) ? col[0] : col.id,
        label: Array.isArray(col) ? (col[2] || col[0]) : (col.name || col.label || col.id),
    })).filter(col => col.id);
}
function coverMasterNames() {
    return coverMasterColumns()
        .filter(col => String(col.id).toLowerCase() !== "programa")
        .map(col => col.label);
}
function coverDisplayName(uid) {
    const names = state.data?.participant_contract?.names || {};
    const id = String(uid || "").toLowerCase();
    if (state.user && String(state.user.id).toLowerCase() === id) return state.user.name || "Tu";
    return names[id] || names[uid] || String(uid || "").split("@")[0];
}
function coverRankingRows() {
    const ranking = state.data?.ranking_maestros || {};
    const hidden = new Set((state.data?.participant_contract?.hidden_ids || []).map(id => String(id).toLowerCase()));
    return Object.entries(ranking)
        .filter(([uid]) => !hidden.has(String(uid).toLowerCase()))
        .map(([uid, values]) => ({
            uid,
            name: coverDisplayName(uid),
            total: Number(values?.total || 0),
            jornada: Number(values?.jornada_live ?? values?.jornada ?? 0),
        }))
        .sort((a, b) => b.total - a.total || b.jornada - a.jornada || a.name.localeCompare(b.name, "es"));
}
function coverBandoScores() {
    const rows = coverRankingRows();
    const aiIds = new Set(coverMasterColumns().map(col => String(col.id || "").toLowerCase()));
    const penaIds = new Set((state.data?.participant_contract?.pena_ids || []).map(id => String(id || "").toLowerCase()));
    return rows.reduce((acc, row) => {
        const uid = String(row.uid).toLowerCase();
        if (aiIds.has(uid)) acc.ai += row.jornada;
        else if (penaIds.has(uid)) acc.human += row.jornada;
        return acc;
    }, { human: 0, ai: 0 });
}
function coverPredictionSigns(entry) {
    if (Array.isArray(entry)) return entry;
    return Array.isArray(entry?.signos) ? entry.signos : [];
}
function coverPenaReading(row) {
    if (!row || !Number(row.total || 0)) return null;
    const readings = [
        { sign: "1", percent: Number(row.p1 || 0) },
        { sign: "X", percent: Number(row.px || 0) },
        { sign: "2", percent: Number(row.p2 || 0) },
    ];
    const peak = Math.max(...readings.map(item => item.percent));
    return {
        sign: readings.filter(item => item.percent === peak).map(item => item.sign).join(""),
        percent: peak,
        total: Number(row.total || 0),
    };
}
function coverDisagreementMatch(matches) {
    const columns = coverMasterColumns();
    const predictions = state.data?.predicciones_actuales || {};
    const penaRows = Array.isArray(state.data?.consenso_pena) ? state.data.consenso_pena : [];
    let best = null;
    matches.slice(0, 14).forEach((match, index) => {
        const picks = columns.map(col => ({
            id: col.id,
            label: col.label,
            sign: coverPredictionSigns(predictions[col.id])[index] || "-",
        })).filter(item => item.sign !== "-");
        const penaRow = penaRows.find(row => Number(row.id) === Number(match.id));
        const pena = coverPenaReading(penaRow);
        const allSigns = pena ? [pena.sign, ...picks.map(item => item.sign)] : picks.map(item => item.sign);
        const unique = new Set(allSigns).size;
        const score = unique * 10 + allSigns.filter(sign => sign.length > 1).length;
        if (!best || score > best.score) best = { match, picks, pena, unique, score };
    });
    return best;
}
function coverTightPenaMatch(matches) {
    const rows = Array.isArray(state.data?.consenso_pena) ? state.data.consenso_pena : [];
    let best = null;
    rows.forEach(row => {
        const match = matches.find(item => Number(item.id) === Number(row.id));
        if (!match || !Number(row.total || 0)) return;
        const peak = Math.max(Number(row.p1 || 0), Number(row.px || 0), Number(row.p2 || 0));
        if (!best || peak < best.peak) best = { match, row, peak };
    });
    return best;
}
function coverFixtureHtml(match, compact = false) {
    if (!match) return `<span class="cp-empty">Horario pendiente</span>`;
    return `<div class="cp-fixture ${compact ? "is-compact" : ""}">
        <span class="cp-team cp-team-home">${logoBadge(match.local, teamLogo(match, "home"))}<strong>${escapeHtml(getShortName(match.local))}</strong></span>
        <span class="cp-fixture-sep">VS</span>
        <span class="cp-team cp-team-away">${logoBadge(match.visitante, teamLogo(match, "away"))}<strong>${escapeHtml(getShortName(match.visitante))}</strong></span>
    </div>`;
}
function hydrateCoverPorra(data) {
    const target = document.getElementById("cover-porra-content");
    const title = document.getElementById("cover-porra-title");
    if (!target) return;
    if (!data?.enabled || !data.match) {
        target.innerHTML = `<span class="cp-empty">${escapeHtml(data?.message || "Sin porra disponible")}</span>`;
        return;
    }
    const match = data.match;
    if (title) title.textContent = data.label || "Porra de la jornada";
    const mine = data.mine || {};
    const hasMine = mine.goles_local !== undefined && mine.goles_local !== null
        && mine.goles_visitante !== undefined && mine.goles_visitante !== null;
    const totalEntries = Number(data.total_entries || 0);
    const leaders = (data.distribution || []).slice(0, 3);
    const status = hasMine
        ? `Tu porra: ${Number(mine.goles_local)}-${Number(mine.goles_visitante)}`
        : data.locked ? "Porra cerrada" : "Haz tu porra";
    target.innerHTML = `
        ${coverFixtureHtml(match, true)}
        <div class="cp-porra-foot">
            <strong>${escapeHtml(status)}</strong>
            ${leaders.length ? `<span>${leaders.map(item => `${Number(item.goles_local)}-${Number(item.goles_visitante)} <small>${totalEntries === 1 ? "pron&oacute;stico &uacute;nico" : `${Number(item.percent || 0).toLocaleString("es-ES", { maximumFractionDigits: 0 })}%`}</small>`).join(" &middot; ")}</span>` : `<span>S&eacute; el primero en mojarte</span>`}
        </div>`;
}

/* ====== RENDER NUEVO ====== */
function renderNewspaperCoverPageV3() {
    const matches = state.data?.partidos || [];
    const closed = coverIsClosed();
    const saved = hasSavedTicket();
    const jornada = state.data?.jornada || state.jornada || "";
    const liveCount = matches.filter(match => isLiveStatus(match.status) || isLiveMatch(match)).length;
    const masterNames = coverMasterNames();
    const rankingRows = coverRankingRows();
    const disagreement = coverDisagreementMatch(matches);
    const penaPulse = coverTightPenaMatch(matches);
    const bandoScores = coverBandoScores();
    const totalBando = bandoScores.human + bandoScores.ai;
    const humanPct = totalBando > 0 ? (bandoScores.human / totalBando) * 100 : 50;
    const penaVotes = Math.max(0, ...(state.data?.consenso_pena || []).map(row => Number(row.total || 0)));

    const ctaLabel = closed
        ? (saved ? "Ver mi quiniela" : "Ver resultados")
        : (saved ? "Revisar quiniela" : "Jugar quiniela");

    const statusLabel = closed ? "Cerrada" : `${coverCloseLabel()}`;

    // Texto líder dinámico
    let leadTitle = "Grok lidera con 144 puntos. Claude y ChatGPT siguen la persecución.";
    if (rankingRows.length >= 3) {
        leadTitle = `${escapeHtml(rankingRows[0].name)} lidera con ${rankingRows[0].total} puntos. ${escapeHtml(rankingRows[1].name)} y ${escapeHtml(rankingRows[2].name)} siguen la persecución.`;
    } else if (rankingRows.length === 2) {
        leadTitle = `${escapeHtml(rankingRows[0].name)} lidera con ${rankingRows[0].total} puntos. ${escapeHtml(rankingRows[1].name)} a ${rankingRows[0].total - rankingRows[1].total} puntos.`;
    } else if (rankingRows.length === 1) {
        leadTitle = `${escapeHtml(rankingRows[0].name)} lidera con ${rankingRows[0].total} puntos.`;
    }

    // Picks limitados: Peña + max 3 IA
    let picksHtml = "";
    if (disagreement) {
        const limited = disagreement.picks.slice(0, 3);
        const extra = disagreement.picks.length > 3 ? disagreement.picks.length - 3 : 0;
        picksHtml = `
            ${disagreement.pena ? `<span class="is-pena" title="${disagreement.pena.total} pronósticos"><small>Peña</small><b>${escapeHtml(disagreement.pena.sign)}</b></span>` : ""}
            ${limited.map(item => `<span class="${String(item.id).toLowerCase() === "programa" ? "is-program" : ""}" title="${escapeHtml(item.label)}"><small>${escapeHtml(item.label).slice(0,10)}</small><b>${escapeHtml(item.sign)}</b></span>`).join("")}
            ${extra ? `<span title="${extra} más"><small>+${extra}</small></span>` : ""}
        `;
    }

    return `<div class="cp">
        <main class="cp-stage" aria-labelledby="cp-main-title">
            <section class="cp-intro">
                <div class="cp-kicker">
                    <span>Jornada ${escapeHtml(String(jornada))}</span>
                    <i class="cp-kicker-dot" aria-hidden="true"></i>
                    <span id="cp-deadline">${escapeHtml(statusLabel)}</span>
                    ${liveCount ? `<span style="display:inline-flex;align-items:center;gap:4px;margin-left:6px;color:#6ee7b7;">● ${liveCount} en directo</span>` : ""}
                </div>
                <h1 id="cp-main-title">LA PEÑA<br>CONTRA LAS<br>MÁQUINAS</h1>
                <p class="cp-lead">${leadTitle}<span class="cp-challenge">¿Quién sabe más de fútbol?</span></p>
                <div class="cp-actions">
                    <button type="button" class="cp-primary" data-page-action="TICKET">${escapeHtml(ctaLabel)}</button>
                    <button type="button" class="cp-secondary" data-page-action="CONTEST">Clasificación</button>
                </div>
            </section>

            <section class="cp-duel" aria-label="Marcador humanos contra máquinas">
                <div class="cp-duel-kicker">Pulso colectivo · Jornada ${escapeHtml(String(jornada))}</div>
                <div class="cp-versus">
                    <div class="cp-side is-pena">
                        <span>Humanos</span>
                        <b>${bandoScores.human}</b>
                        <small>La Peña</small>
                    </div>
                    <div class="cp-vs">—</div>
                    <div class="cp-side is-ai">
                        <span>Máquinas</span>
                        <b>${bandoScores.ai}</b>
                        <small>Maestros IA</small>
                    </div>
                </div>
                <div class="cp-scorebar-inline-track" aria-hidden="true">
                    <div class="cp-scorebar-inline-fill" style="width:${humanPct}%"></div>
                </div>
                <div class="cp-duel-foot">${penaVotes || rankingRows.length} pronósticos · ${masterNames.length} IAs en juego · ${closed ? "jornada cerrada" : "jornada abierta"}</div>
            </section>
        </main>

        ${liveCount ? `<button type="button" class="cp-live" data-page-action="LIVE"><span></span><b>${liveCount} EN DIRECTO</b><em>Entra al seguimiento</em></button>` : ""}

        <section class="cp-dashboard" aria-label="Estado de la jornada">
            <button type="button" class="cp-data-card cp-focus" data-page-action="TICKET">
                <div class="cp-card-head"><span>Partido bajo lupa</span><b>${disagreement ? `${disagreement.unique} posturas` : "Análisis"}</b></div>
                ${disagreement ? `${coverFixtureHtml(disagreement.match, true)}<div class="cp-picks">${picksHtml}</div>` : `<span class="cp-empty">Aún sin cruces destacados</span>`}
            </button>

            <button type="button" class="cp-data-card cp-pulse" data-page-action="TICKET">
                <div class="cp-card-head"><span>Pulso de la Peña</span><b>${penaPulse ? "Más abierto" : "Consenso"}</b></div>
                ${penaPulse ? `${coverFixtureHtml(penaPulse.match, true)}
                    <div class="cp-pulse-bars" aria-label="1 ${penaPulse.row.p1}%, X ${penaPulse.row.px}%, 2 ${penaPulse.row.p2}%">
                        <i class="is-one" style="width:${penaPulse.row.p1}%"></i><i class="is-draw" style="width:${penaPulse.row.px}%"></i><i class="is-two" style="width:${penaPulse.row.p2}%"></i>
                    </div>
                    <div class="cp-pulse-labels"><span>1 · ${penaPulse.row.p1}%</span><span>X · ${penaPulse.row.px}%</span><span>2 · ${penaPulse.row.p2}%</span></div>
                ` : `<span class="cp-empty">Aún no hay pronósticos</span>`}
            </button>

            <button type="button" class="cp-data-card cp-leaders" data-page-action="CONTEST">
                <div class="cp-card-head"><span>Clasificación general</span><b>Top ${Math.min(5, rankingRows.length)}</b></div>
                <ol>${rankingRows.slice(0, 5).map((row, index) => `<li><i>${index + 1}</i><strong>${escapeHtml(row.name)}</strong><span>${row.total}</span></li>`).join("") || `<li><i>—</i><strong>Sin datos</strong><span>0</span></li>`}</ol>
            </button>
        </section>

        <section class="cp-secondary-grid" aria-label="Contenido secundario">
            <div class="cp-data-card cp-news-card" id="cp-news-card">
                <div class="cp-card-head"><span>Novedades</span><b>Prensa deportiva</b></div>
                <div id="cover-news-content" class="cp-news-content" aria-live="polite">
                    <span class="cp-porra-loading">Cargando...</span>
                </div>
            </div>

            <button type="button" class="cp-data-card cp-porra" data-page-action="TICKET">
                <div class="cp-card-head"><span id="cover-porra-title">Porra de la jornada</span><b>Marcador exacto</b></div>
                <div id="cover-porra-content" class="cp-porra-content" aria-live="polite">
                    <span class="cp-porra-loading">Buscando partido</span>
                </div>
            </button>
        </section>
    </div>`;
}
