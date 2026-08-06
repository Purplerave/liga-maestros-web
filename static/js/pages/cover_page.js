/* Portada Liga de Maestros v4 - Panel control compacto, español natural
   Encima del rediseño de main: escudo grande a la izquierda del titular,
   nombres directos (El duelo, El partido en disputa, Así vota la Peña,
   Última hora, La porra) y quitado el comentario IA fijo de ejemplo. */

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
        if (!raw) { node.textContent = state?.data?.is_locked ? "CERRADA" : "ABIERTA"; return; }
        const target = new Date(String(raw).replace(" ", "T"));
        if (Number.isNaN(target.getTime())) { node.textContent = state?.data?.is_locked ? "CERRADA" : "ABIERTA"; return; }
        const diff = target.getTime() - Date.now();
        if (diff <= 0 || state.data.is_locked) { node.textContent = "CERRADA"; node.classList.add("is-urgent"); return; }
        const s = Math.max(0, Math.floor(diff / 1000));
        const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60;
        node.textContent = h > 0 ? `${h}h ${String(m).padStart(2,"0")}m` : `${String(m).padStart(2,"0")}m ${String(sec).padStart(2,"0")}s`;
        node.classList.toggle("is-urgent", diff < 3_600_000);
    };
    tick(); setInterval(tick, 1000);
}

function startSeasonCountdown() {
    const timer = document.getElementById('cp-countdown-timer');
    if (!timer) return;
    const seasonStart = new Date('2026-08-15T19:30:00');
    const update = () => {
        const diff = seasonStart.getTime() - Date.now();
        if (diff <= 0) {
            timer.textContent = '¡La Liga ha empezado!';
            return;
        }
        const days = Math.floor(diff / (1000 * 60 * 60 * 24));
        const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
        const mins = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
        const secs = Math.floor((diff % (1000 * 60)) / 1000);
        timer.textContent = `${days}d ${String(hours).padStart(2,'0')}h ${String(mins).padStart(2,'0')}m ${String(secs).padStart(2,'0')}s`;
    };
    update();
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
function coverIsClosed() { return Boolean(state.data.is_locked) || coverCloseLabel() === "cerrada"; }
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
    const rows = coverRankingRows();
    const aiIds = new Set(coverMasterColumns().map(col => String(col.id || "").toLowerCase()));
    const penaIds = new Set((state.data?.participant_contract?.pena_ids || []).map(id => String(id || "").toLowerCase()));
    let humanTotal = 0, aiTotal = 0, humanCount = 0, aiCount = 0;
    rows.forEach(row => {
        const uid = String(row.uid).toLowerCase();
        if (aiIds.has(uid)) { aiTotal += row.jornada; aiCount++; }
        else if (penaIds.has(uid)) { humanTotal += row.jornada; humanCount++; }
    });
    return { rows, humanTotal, aiTotal, humanCount: humanCount || 1, aiCount: aiCount || 1, humanAvg: humanCount ? humanTotal / humanCount : 0, aiAvg: aiCount ? aiTotal / aiCount : 0 };
}
function coverPredictionSigns(entry) { if (Array.isArray(entry)) return entry; return Array.isArray(entry?.signos) ? entry.signos : []; }
function coverPenaReading(row) {
    if (!row || !Number(row.total || 0)) return null;
    const readings = [{ sign: "1", percent: Number(row.p1 || 0) }, { sign: "X", percent: Number(row.px || 0) }, { sign: "2", percent: Number(row.p2 || 0) }];
    const peak = Math.max(...readings.map(item => item.percent));
    return { sign: readings.filter(item => item.percent === peak).map(item => item.sign).join(""), percent: peak, total: Number(row.total || 0) };
}
function coverCollectivePenaScore(matches, consensoRows) {
    let hits = 0, played = 0;
    matches.forEach(match => {
        const real = String(match.signo_actual || "").toUpperCase();
        if (!["1","X","2"].includes(real)) return;
        const row = consensoRows.find(r => Number(r.id) === Number(match.id));
        if (!row) return;
        const reading = coverPenaReading(row);
        if (!reading || !reading.sign) return;
        played++;
        if (reading.sign.includes(real)) hits++;
    });
    return { hits, played, totalMatches: matches.length };
}
function coverDisagreementMatch(matches) {
    const columns = coverMasterColumns();
    const predictions = state.data?.predicciones_actuales || {};
    const penaRows = Array.isArray(state.data?.consenso_pena) ? state.data.consenso_pena : [];
    let best = null;
    matches.slice(0, 14).forEach((match, index) => {
        const picks = columns.map(col => ({ id: col.id, label: col.label, sign: coverPredictionSigns(predictions[col.id])[index] || "-" })).filter(item => item.sign !== "-");
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
    if (!match) return `<span class="cp-empty">Pendiente</span>`;
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
        target.innerHTML = `<span class="cp-empty">${escapeHtml(data?.message || "Sin porra")}</span>`;
        return;
    }
    const match = data.match;
    if (title) title.textContent = data.label ? String(data.label).replace(/^porra( de la jornada)?$/i, "La porra") : "La porra";
    const mine = data.mine || {};
    const hasMine = mine.goles_local !== undefined && mine.goles_local !== null && mine.goles_visitante !== undefined && mine.goles_visitante !== null;
    const totalEntries = Number(data.total_entries || 0);
    const leaders = (data.distribution || []).slice(0, 3);
    const status = hasMine ? `Llevas ${Number(mine.goles_local)}-${Number(mine.goles_visitante)}` : data.locked ? "Cerrada" : "Pon tu marcador";
    target.innerHTML = `${coverFixtureHtml(match, true)}
        <div class="cp-porra-foot"><strong>${escapeHtml(status)}</strong>
            ${leaders.length ? `<span>${leaders.map(item => `${Number(item.goles_local)}-${Number(item.goles_visitante)} <small>${Number(item.percent || 0).toLocaleString("es-ES", { maximumFractionDigits: 0 })}%</small>`).join(" · ")}</span>` : `<span>Anímate</span>`}
        </div>`;
}

function renderNewspaperCoverPageV3() {
    const matches = state.data?.partidos || [];
    const closed = coverIsClosed();
    const saved = hasSavedTicket();
    const jornada = state.data?.jornada || state.jornada || "";
    const liveCount = matches.filter(m => isLiveStatus(m.status) || isLiveMatch(m)).length;
    const rankingRows = coverRankingRows();
    const disagreement = coverDisagreementMatch(matches);
    const penaPulse = coverTightPenaMatch(matches);
    const bando = coverBandoDetailed();
    const consenso = Array.isArray(state.data?.consenso_pena) ? state.data.consenso_pena : [];
    const collective = coverCollectivePenaScore(matches, consenso);
    const humanAvgStr = bando.humanAvg.toFixed(1).replace(".0","").replace(".",",");
    const aiAvgStr = bando.aiAvg.toFixed(1).replace(".0","").replace(".",",");
    const totalBando = bando.humanTotal + bando.aiTotal;
    const humanPct = totalBando > 0 ? (bando.humanTotal / totalBando) * 100 : 50;

    const rankingForCover = [...rankingRows].sort((a,b) => b.jornada - a.jornada || b.total - a.total || a.name.localeCompare(b.name,"es"));
    const top3Pruebas = [...rankingRows].sort((a,b) => b.total - a.total).slice(0,3);
    const bestPenaPruebas = rankingRows.filter(r => {
        const penaIds = new Set((state.data?.participant_contract?.pena_ids || []).map(id => String(id).toLowerCase()));
        return penaIds.has(String(r.uid).toLowerCase());
    }).sort((a,b) => b.total - a.total).slice(0,3);

    const ctaLabel = closed ? (saved ? "Ver mi quiniela" : "Ver resultados") : (saved ? "Revisar quiniela" : "Jugar quiniela");
    const statusLabel = closed ? "Cerrada" : `${coverCloseLabel()}`;
    const isFirstOfficial = rankingRows.length === 0 || bando.humanTotal === 0 && bando.aiTotal === 0 || collective.played === 0;

    // Texto bienvenida - con titular gancho
    const explica = `<span class="cp-headline">Tu Quiniela contra las IAs</span><br><span class="cp-subhead">Cada jornada, 15 partidos. Tú, La Peña y las máquinas con el mismo boleto.</span><br><br>Haz tus pronósticos cada jornada, suma puntos por cada acierto y sube en la clasificación. Competirás contra el resto de jugadores, el pronóstico colectivo de La Peña, nuestro Programa y varias de las IAs más conocidas.<br><br>En las jornadas de prueba, las IAs consiguieron <b>8,2 aciertos de media</b>. La Peña se quedó en <b>6,9</b>.<br><br>Las máquinas ganaron el calentamiento. Pero ahora todos vuelven a cero.<br><br><span class="cp-challenge">¿Quién sabe más de fútbol?</span><br><span class="cp-loteria">¿Confías de verdad en tus pronósticos? También puedes <a href="https://www.labarcadeoro.com/" target="_blank" rel="noopener">echar tu Quiniela online →</a></span>`;

    // Countdown a la primera jornada
    const seasonStart = new Date('2026-08-15T19:30:00');
    const countdownHtml = `<div class="cp-countdown" id="cp-countdown">
        <div class="cp-countdown-label">La Liga empieza en</div>
        <div class="cp-countdown-timer" id="cp-countdown-timer">--</div>
        <div class="cp-countdown-date">15 ago · 19:30 · Alavés vs Getafe</div>
    </div>`;

    let picksHtml = "";
    if (disagreement) {
        const limited = disagreement.picks.slice(0, 3);
        const extra = disagreement.picks.length > 3 ? disagreement.picks.length - 3 : 0;
        picksHtml = `
            ${disagreement.pena ? `<span class="is-pena" title="${disagreement.pena.total} pronósticos"><small>Peña</small><b>${escapeHtml(disagreement.pena.sign)}</b></span>` : ""}
            ${limited.map(item => `<span class="${String(item.id).toLowerCase() === "programa" ? "is-program" : ""}" title="${escapeHtml(item.label)}"><small>${escapeHtml(item.label).slice(0,8)}</small><b>${escapeHtml(item.sign)}</b></span>`).join("")}
            ${extra ? `<span><small>+${extra}</small></span>` : ""}
        `;
    }

    // Clasificación - mostrar resultados de pruebas
    let clasifHtml = `
        <div style="margin-top:8px;">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
                <div style="text-align:center;flex:1;">
                    <div style="color:var(--cp-muted);font-size:0.52rem;font-weight:700;text-transform:uppercase;letter-spacing:0.05em;">LA PEÑA</div>
                    <div style="color:var(--cp-gold);font-size:clamp(1.4rem,2vw,1.8rem);font-weight:800;font-family:var(--cp-font-display);">6.9</div>
                    <div style="color:var(--cp-dim);font-size:0.48rem;">puntos/partido</div>
                </div>
                <div style="color:var(--cp-dim);font-size:0.58rem;font-weight:800;">VS</div>
                <div style="text-align:center;flex:1;">
                    <div style="color:var(--cp-muted);font-size:0.52rem;font-weight:700;text-transform:uppercase;letter-spacing:0.05em;">IAs</div>
                    <div style="color:var(--cp-cyan);font-size:clamp(1.4rem,2vw,1.8rem);font-weight:800;font-family:var(--cp-font-display);">8.2</div>
                    <div style="color:var(--cp-dim);font-size:0.48rem;">puntos/partido</div>
                </div>
            </div>
            <div style="text-align:center;padding:6px 0;border-top:1px solid var(--cp-line);">
                <div style="color:var(--cp-gold);font-size:0.58rem;font-weight:700;">Las IAs ganaron las pruebas</div>
                <div style="color:var(--cp-dim);font-size:0.50rem;margin-top:2px;">Pero la temporada empieza ahora</div>
            </div>
        </div>`;

    return `<div class="cp">
        <main class="cp-stage">
            <div class="cp-hero-left">
                <section class="cp-intro">
                    <div class="cp-kicker">
                        <span>Quiniela ${escapeHtml(String(jornada))}</span>
                        <i class="cp-kicker-dot"></i>
                        <span id="cp-deadline">${escapeHtml(statusLabel)}</span>
                        ${liveCount ? `<span style="margin-left:6px;color:#6ee7b7;">● ${liveCount} en directo</span>` : ""}
                    </div>
                    <div class="cp-hero-tagline"><b>1X2</b> · La Peña vs IA</div>
                    <div class="cp-hero-titles">
                        <h1 id="cp-main-title">
                            <span class="cp-title-main"><span class="cp-title-white">LIGA </span><span class="cp-title-white">DE </span><span class="cp-title-gold">MAESTROS</span></span>
                            <span class="cp-title-accent"></span>
                            <span class="cp-title-sub">LA PEÑA CONTRA LAS MÁQUINAS</span>
                        </h1>
                    </div>
                    <p class="cp-lead">${explica}<span class="cp-challenge">¿Quién sabe más de fútbol?</span></p>
                    ${countdownHtml}
                    <div class="cp-actions">
                        <button type="button" class="cp-primary" data-page-action="TICKET">${escapeHtml(ctaLabel)}</button>
                        <button type="button" class="cp-secondary" data-page-action="CONTEST">Clasificación</button>
                    </div>
                </section>
            </div>

            <div class="cp-hero-right">
                <div class="cp-quicklinks">
                    <button type="button" data-page-action="LIVE"><span>⚽</span><b>Directo</b><small>${liveCount ? liveCount + " partidos" : "Marcadores"}</small></button>
                    <button type="button" data-page-action="STANDINGS"><span>🏆</span><b>Ligas</b><small>Tabla</small></button>
                    <button type="button" data-page-action="SNAKE"><span>🎮</span><b>Juegos</b><small>Puntos</small></button>
                </div>

                <section class="cp-leaders">
                    <div class="cp-card-head"><span>PRUEBAS FINALIZADAS</span><b>TEMPORADA 26/27</b></div>
                    ${clasifHtml}
                    <div class="cp-leaders-foot"><a href="#" data-page-action="CONTEST">Ver clasificación completa →</a></div>
                </section>

                <div class="cp-right-bottom">
                    <div class="cp-right-bottom-top">
                        <div class="cp-data-card cp-porra" data-page-action="TICKET">
                            <div class="cp-card-head"><span id="cover-porra-title">LA PORRA</span><b>Marcador exacto</b></div>
                            <div id="cover-porra-content" class="cp-porra-content"><span class="cp-porra-loading">Cargando</span></div>
                        </div>

                        <section class="cp-duel" aria-label="El duelo: La Peña contra las IAs">
                            <div class="cp-duel-kicker">EL DUELO</div>
                            <div class="cp-versus">
                                <div class="cp-side is-pena"><span>PEÑA</span><b>${humanAvgStr}</b></div>
                                <div class="cp-vs">VS</div>
                                <div class="cp-side is-ai"><span>IA</span><b>${aiAvgStr}</b></div>
                            </div>
                            <div class="cp-scorebar-inline-track"><div class="cp-scorebar-inline-fill" style="width:${humanPct}%"></div></div>
                            <div class="cp-duel-foot">Media de aciertos</div>
                        </section>
                    </div>

                    <div class="cp-data-card cp-news-card" id="cp-news-card">
                        <div class="cp-news-header">
                            <span>ÚLTIMAS NOTICIAS</span>
                            <a href="#" data-page-action="NEWS">Ver todas →</a>
                        </div>
                        <div id="cover-news-content" class="cp-news-content"><span class="cp-porra-loading">Cargando...</span></div>
                    </div>
                </div>
            </div>
        </main>

        ${liveCount ? `<button type="button" class="cp-live" data-page-action="LIVE"><span></span><b>${liveCount} EN DIRECTO</b><em>Seguimiento</em></button>` : ""}
    </div>`;
}
