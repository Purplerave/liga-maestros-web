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

function loadSeasonSummary() {
    var target = document.getElementById("cp-season-summary");
    if (!target) return;
    fetch("/api/season-summary")
        .then(function (res) { if (!res.ok) throw new Error(); return res.json(); })
        .then(function (data) {
            var top3 = data.top_3 || [];
            var medals = ["🥇", "🥈", "🥉"];
            var rowsHtml = top3.map(function (p, i) {
                return '<div class="cp-leader-row">' +
                    '<span class="cp-leader-pos">' + (medals[i] || (i + 1)) + '</span>' +
                    '<span class="cp-leader-name">' + escapeHtml(p.name) + '</span>' +
                    '<span class="cp-leader-pts">' + p.points + ' pts</span>' +
                    '</div>';
            }).join("");
            var statsHtml = '<div class="cp-season-stats">' +
                '<span>' + (data.total_participants || 0) + ' participantes</span>' +
                '<span>' + (data.total_jornadas || 0) + ' jornadas</span>' +
                '</div>';
            target.innerHTML =
                '<div class="cp-season-label">Resultados ' + escapeHtml(data.season || "Pruebas") + '</div>' +
                rowsHtml + statsHtml;
        })
        .catch(function () {
            target.innerHTML = '<span class="cp-empty">Próximamente: clasificación de la temporada</span>';
        });
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
function updateCoverPorraStep(label, stateName = "") {
    const step = document.getElementById("cover-porra-step");
    const status = document.getElementById("cover-porra-step-status");
    if (!step || !status) return;
    status.textContent = label;
    step.classList.toggle("is-done", stateName === "done");
    step.classList.toggle("is-muted", stateName === "unavailable");
}

function hydrateCoverPorra(data) {
    const target = document.getElementById("cover-porra-content");
    const title = document.getElementById("cover-porra-title");
    if (!target) return;
    if (!data?.enabled || !data.match) {
        const msg = data?.message || "Porra no disponible para esta jornada";
        target.innerHTML = `<div class="cp-porra-empty"><span class="cp-porra-empty-icon">🎯</span><span class="cp-porra-empty-text">${escapeHtml(msg)}</span></div>`;
        updateCoverPorraStep("No disponible", "unavailable");
        return;
    }
    const match = data.match;
    if (title) title.textContent = "La porra — +2 pts";
    const mine = data.mine || {};
    const hasMine = mine.goles_local !== undefined && mine.goles_local !== null && mine.goles_visitante !== undefined && mine.goles_visitante !== null;
    const leaders = (data.distribution || []).slice(0, 3);
    const hint = data.hint || "Marcador exacto: +2 puntos.";
    const status = hasMine ? `Tu porra: ${Number(mine.goles_local)}-${Number(mine.goles_visitante)}` : data.locked ? "Cerrada" : "Elige tu partido — +2 pts si aciertas";
    const changes = data.my_changes || 0;
    const jornadaLocked = data.jornada_locked || false;

    if (hasMine) updateCoverPorraStep(`${Number(mine.goles_local)}-${Number(mine.goles_visitante)} guardado`, "done");
    else updateCoverPorraStep(data.locked ? "Cerrada" : "Elige marcador");

    let changeInfo = "";
    if (hasMine && !jornadaLocked) {
        if (changes === 0) {
            changeInfo = `<span class="cp-porra-change">Puedes cambiarla 1 vez</span>`;
        } else {
            changeInfo = `<span class="cp-porra-change locked">Ya no puedes cambiar</span>`;
        }
    }
    const porraHintHtml = !hasMine && !data.locked ? `<div class="cp-porra-hint">${escapeHtml(hint)}</div>` : "";

    target.innerHTML = `${coverFixtureHtml(match, true)}
        <div class="cp-porra-foot"><strong>${escapeHtml(status)}</strong>
            ${leaders.length ? `<span>${leaders.map(item => `${Number(item.goles_local)}-${Number(item.goles_visitante)} <small>${Number(item.percent || 0).toLocaleString("es-ES", { maximumFractionDigits: 0 })}%</small>`).join(" · ")}</span>` : `<span>Sé el primero</span>`}
        </div>
        ${porraHintHtml}
        ${changeInfo}`;
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
    const ticketStepLabel = saved ? "Guardada" : closed ? "Ver resultados" : "Pendiente";
    const liveStepLabel = liveCount ? `${liveCount} en directo` : "Horarios y resultados";
    const isFirstOfficial = rankingRows.length === 0 || bando.humanTotal === 0 && bando.aiTotal === 0 || collective.played === 0;

    // Texto bienvenida - nueva temporada a punto de arrancar
    const explica = `<span class="cp-headline">Las pruebas han terminado</span><br><span class="cp-subhead">Fue solo el calentamiento. Ahora empieza la temporada de verdad.</span><br><br>Hemos cerrado la fase de pruebas con la clasificación final del calentamiento (ver podio a la derecha). Las máquinas se llevaron esta primera batalla — <b>8,2 aciertos de media</b> frente a <b>6,9</b> de La Peña — pero ahora <b>todos volvemos a cero</b>.<br><br>En breve arranca la nueva temporada y cada jornada volverá a contar: 15 partidos, tu quiniela 1X2 y el duelo directo contra el resto de jugadores, La Peña y los Maestros IA. Suma aciertos, escala en la general y demuestra quién entiende de verdad este juego.<br><br><span class="cp-challenge">¿Te apuntas? La nueva Liga te está esperando.</span><br><span class="cp-loteria">¿Confías de verdad en tus pronósticos? También puedes <a href="https://www.labarcadeoro.com/" target="_blank" rel="noopener">echar tu Quiniela online →</a></span>`;

    // Countdown a la primera jornada
    const seasonStart = new Date('2026-08-15T19:30:00');
    const countdownHtml = `<div class="cp-countdown" id="cp-countdown">
        <div class="cp-countdown-label">Jornada 1 empieza en</div>
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

    // Clasificación - se carga dinámicamente desde season summary
    let clasifHtml = `<div id="cp-season-summary" class="cp-season-summary"><span class="cp-porra-loading">Cargando</span></div>`;

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
                    <p class="cp-lead">${explica}</p>
                    ${countdownHtml}
                    <div class="cp-actions">
                        <button type="button" class="cp-primary" data-page-action="TICKET">${escapeHtml(ctaLabel)}</button>
                        <button type="button" class="cp-secondary" data-page-action="CONTEST">Clasificación</button>
                    </div>
                </section>
            </div>

            <div class="cp-hero-right">
                <section class="cp-leaders">
                    <div class="cp-card-head"><span>PODIO PRUEBAS 25/26</span><b>TOP 3</b></div>
                    ${clasifHtml}
                </section>

                <div class="cp-right-bottom">
                    <div class="cp-right-bottom-top">
                        <div class="cp-data-card cp-porra" data-page-action="TICKET">
                            <div class="cp-card-head"><span id="cover-porra-title">LA PORRA</span><b>Marcador exacto</b></div>
                            <div id="cover-porra-content" class="cp-porra-content"><span class="cp-porra-loading">Cargando</span></div>
                        </div>

                        <div class="cp-data-card cp-news-card" id="cp-news-card">
                            <div class="cp-news-header">
                                <span>ÚLTIMAS NOTICIAS</span>
                                <a href="#" data-page-action="NEWS">Ver todas →</a>
                            </div>
                            <div id="cover-news-content" class="cp-news-content"><span class="cp-porra-loading">Cargando...</span></div>
                        </div>
                    </div>

                    <section class="cp-journey-card" aria-labelledby="cp-journey-title">
                        <div class="cp-card-head">
                            <span id="cp-journey-title">TU JORNADA</span>
                            <b>3 pasos</b>
                        </div>
                        <p>Haz tu jugada, busca el +2 y sigue los marcadores.</p>
                        <div class="cp-journey-steps">
                            <button type="button" class="cp-journey-step${saved ? " is-done" : ""}" data-page-action="TICKET">
                                <span class="cp-journey-number" aria-hidden="true">1</span>
                                <span><b>Quiniela</b><small>${escapeHtml(ticketStepLabel)}</small></span>
                                <i aria-hidden="true">→</i>
                            </button>
                            <button type="button" class="cp-journey-step" id="cover-porra-step" data-page-action="TICKET">
                                <span class="cp-journey-number" aria-hidden="true">2</span>
                                <span><b>Porra</b><small id="cover-porra-step-status">Cargando...</small></span>
                                <i aria-hidden="true">→</i>
                            </button>
                            <button type="button" class="cp-journey-step${liveCount ? " is-live" : ""}" data-page-action="LIVE">
                                <span class="cp-journey-number" aria-hidden="true">3</span>
                                <span><b>Directo</b><small>${escapeHtml(liveStepLabel)}</small></span>
                                <i aria-hidden="true">→</i>
                            </button>
                        </div>
                    </section>
                </div>
            </div>
        </main>
        <div class="cp-quicklinks cp-quicklinks-footer">
            <button type="button" data-page-action="LIVE"><span>⚽</span><b>Directo</b><small>${liveCount ? liveCount + " partidos" : "Marcadores"}</small></button>
            <button type="button" data-page-action="STANDINGS"><span>🏆</span><b>Ligas</b><small>Tabla</small></button>
            <button type="button" data-page-action="SNAKE"><span>🎮</span><b>Juegos</b><small>Puntos</small></button>
        </div>
        ${liveCount ? `<button type="button" class="cp-live" data-page-action="LIVE"><span></span><b>${liveCount} EN DIRECTO</b><em>Seguimiento</em></button>` : ""}
    </div>`;
}
