/* Portada Liga de Maestros — Rediseño limpio v3
   - Fix Jornada 75 (oficial) vs clasificación que parte de cero
   - Pulso colectivo justo: media por boleto, no suma bruta 90 vs 53
   - Boleto colectivo de La Peña para 1vs1 contra IAs
   - Hero con mensaje pretemporada + desafío oficial
*/

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
    return {
        rows,
        humanTotal, aiTotal,
        humanCount: humanCount || 1,
        aiCount: aiCount || 1,
        humanAvg: humanCount ? humanTotal / humanCount : 0,
        aiAvg: aiCount ? aiTotal / aiCount : 0,
    };
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
function coverCollectivePenaScore(matches, consensoRows) {
    // Calcula aciertos del boleto colectivo de La Peña (signo más votado vs resultado real)
    if (!matches || !consensoRows) return 0;
    let hits = 0, played = 0;
    matches.forEach(match => {
        const real = String(match.signo_actual || "").toUpperCase();
        if (!["1","X","2"].includes(real)) return;
        const row = consensoRows.find(r => Number(r.id) === Number(match.id));
        if (!row) return;
        const reading = coverPenaReading(row);
        if (!reading || !reading.sign) return;
        played++;
        // Si el consenso tiene "1X" y el real es "1", cuenta como acierto del colectivo
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

function renderNewspaperCoverPageV3() {
    const matches = state.data?.partidos || [];
    const closed = coverIsClosed();
    const saved = hasSavedTicket();
    const jornada = state.data?.jornada || state.jornada || "";
    const liveMatches = matches.filter(match => isLiveStatus(match.status) || isLiveMatch(match));
    const liveCount = liveMatches.length;
    const masterNames = coverMasterNames();
    const rankingRows = coverRankingRows();
    const disagreement = coverDisagreementMatch(matches);
    const penaPulse = coverTightPenaMatch(matches);
    const bando = coverBandoDetailed();
    const consola = Array.isArray(state.data?.consenso_pena) ? state.data.consenso_pena : [];
    const collective = coverCollectivePenaScore(matches, consola);
    const humanAvgStr = bando.humanAvg.toFixed(1).replace(".0","").replace(".",",");
    const aiAvgStr = bando.aiAvg.toFixed(1).replace(".0","").replace(".",",");
    const totalBando = bando.humanTotal + bando.aiTotal;
    const humanPct = totalBando > 0 ? (bando.humanTotal / totalBando) * 100 : 50;
    const penaVotes = Math.max(0, ...consola.map(row => Number(row.total || 0)));

    // Ranking con boleto colectivo de La Peña incluido para 1-vs-1 justo
    const rankingWithCollective = [...rankingRows];
    if (collective.played > 0 || !closed) {
        rankingWithCollective.push({
            uid: "pena_colectiva",
            name: "La Peña",
            total: collective.hits, // en oficial parte de cero, mostramos jornada
            jornada: collective.hits,
            isCollective: true,
        });
    }
    // Para portada: ordenamos por jornada actual (todos parten de cero)
    const rankingForCover = [...rankingWithCollective].sort((a,b) => b.jornada - a.jornada || b.total - a.total || a.name.localeCompare(b.name,"es"));

    const ctaLabel = closed
        ? (saved ? "Ver mi quiniela" : "Ver resultados")
        : (saved ? "Revisar quiniela" : "Jugar quiniela");

    const statusLabel = closed ? "Cerrada" : `${coverCloseLabel()}`;
    const isFirstOfficial = (rankingRows.length === 0 || bando.humanTotal === 0 && bando.aiTotal === 0 || collective.played === 0) ? true : false;

    // Texto épico para arranque oficial (Jornada 75 pero temporada limpia)
    const leadText = isFirstOfficial
        ? `En las jornadas de prueba, las IAs tomaron ventaja. Pero aquello solo fue el calentamiento.<br><strong>La competici&oacute;n oficial empieza ahora: La Pe&ntilde;a, el Programa y ${masterNames.slice(0,3).join(", ")} parten de cero.</strong>`
        : `${rankingForCover[0] ? `${escapeHtml(rankingForCover[0].name)} lidera con ${rankingForCover[0].jornada} aciertos. ` : ""}La Pe&ntilde;a y las IAs compiten jornada a jornada en la Quiniela ${escapeHtml(String(jornada))}.`;

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

    const rightKicker = isFirstOfficial ? "COMIENZA EL DESAFIO" : "PULSO COLECTIVO · MEDIA POR BOLETO";
    const rightFoot = isFirstOfficial
        ? `Pretemporada: M&aacute;quinas 1-0 Pe&ntilde;a. Ahora todos parten de cero · ${bando.humanCount} humanos vs ${bando.aiCount} IAs`
        : `${bando.humanTotal} aciertos totales Pe&ntilde;a (${bando.humanCount} boletos) · ${bando.aiTotal} aciertos IAs (${bando.aiCount} modelos) · Media justa arriba`;

    // Texto que explica QUE ES ESTO - pedido usuario
    const explicaQueEs = `Liga de Maestros es una competici&oacute;n abierta que usa <b>La Quiniela oficial</b> (J${escapeHtml(String(jornada))}) para ver qui&eacute;n es m&aacute;s listo. Cada jornada compiten con el <b>mismo boleto de 15 partidos</b>: <b>t&uacute;, el resto de La Pe&ntilde;a, nuestro Programa y cinco IAs</b> (ChatGPT, Grok, Gemini, Claude y Copilot). Al final de temporada sabremos si arriba queda la intuici&oacute;n humana o el c&aacute;lculo.<br><span class="cp-lead-extra">Sigue los resultados en <b>Directo</b>, consulta la tabla completa en <b>Ligas</b> y deja tu r&eacute;cord en <b>Juegos</b>. El boleto colectivo de La Pe&ntilde;a (signo m&aacute;s votado) compite 1-vs-1 contra cada IA, no 15-vs-6.</span>`;

    return `<div class="cp">
        <main class="cp-stage" aria-labelledby="cp-main-title">
            <section class="cp-intro">
                <div class="cp-kicker">
                    <span>Quiniela ${escapeHtml(String(jornada))} · J${escapeHtml(String(jornada))}</span>
                    <i class="cp-kicker-dot" aria-hidden="true"></i>
                    <span id="cp-deadline">${escapeHtml(statusLabel)}</span>
                    ${liveCount ? `<span style="display:inline-flex;align-items:center;gap:4px;margin-left:6px;color:#6ee7b7;">● ${liveCount} en directo</span>` : ""}
                </div>
                <div class="cp-hero-brand">
                    <img class="cp-hero-logo" src="/static/img/ligademaestroslogo_trans.png" alt="Liga de Maestros 1X2" loading="eager">
                    <span class="cp-hero-brand-text">LA PE&Ntilde;A VS IA · 1X2</span>
                    <span style="margin-left:auto;font:700 0.62rem/1 var(--cp-font-ui);letter-spacing:0.08em;text-transform:uppercase;color:var(--cp-dim);border:1px solid var(--cp-line);padding:4px 8px;border-radius:999px;">TEMPORADA 1 · OFICIAL</span>
                </div>
                <h1 id="cp-main-title">
                    <span class="cp-title-thin">LA PEÑA</span>
                    <span class="cp-title-mid">CONTRA LAS</span>
                    <span class="cp-title-bold">MÁQUINAS</span>
                </h1>
                <p class="cp-lead cp-lead-explique">${explicaQueEs}<span class="cp-challenge">¿Qui&eacute;n sabe m&aacute;s de f&uacute;tbol?</span></p>
                ${!isFirstOfficial ? `<p class="cp-lead" style="margin-top:10px;font-size:0.82rem;color:var(--cp-muted);">${leadText}</p>` : `<p class="cp-lead" style="margin-top:8px;font-size:0.82rem;color:var(--cp-dim);">En las jornadas de prueba las IAs tomaron ventaja. <strong>Ahora todos parten de cero.</strong></p>`}
                <div class="cp-actions">
                    <button type="button" class="cp-primary" data-page-action="TICKET">${escapeHtml(ctaLabel)}</button>
                    <button type="button" class="cp-secondary" data-page-action="CONTEST">Clasificación</button>
                </div>
                <div class="cp-quicklinks">
                    <button type="button" data-page-action="LIVE"><span>● En vivo</span><b>Directo</b><small>${liveCount ? liveCount + " partidos ahora" : "Resultados minuto a minuto"}</small></button>
                    <button type="button" data-page-action="STANDINGS"><b>Ligas</b><small>Tabla completa</small></button>
                    <button type="button" data-page-action="SNAKE"><b>Juegos</b><small>Deja tu puntuaci&oacute;n</small></button>
                </div>
            </section>

            <section class="cp-duel" aria-label="Pulso colectivo">
                <div class="cp-duel-kicker">${rightKicker}</div>
                ${isFirstOfficial ? `
                    <div class="cp-versus" style="grid-template-columns:1fr;">
                        <div class="cp-side is-pena" style="width:100%;">
                            <span>Estado</span>
                            <b style="font-size:clamp(2rem,4.5vw,3rem);">TODOS<br>PARTEN DE CERO</b>
                            <small>La pretemporada fue para las m&aacute;quinas. Ahora empieza la liga</small>
                        </div>
                    </div>
                ` : `
                    <div class="cp-versus">
                        <div class="cp-side is-pena">
                            <span>Media Pe&ntilde;a</span>
                            <b>${humanAvgStr}</b>
                            <small>${bando.humanTotal} aciertos / ${bando.humanCount} boletos</small>
                        </div>
                        <div class="cp-vs">—</div>
                        <div class="cp-side is-ai">
                            <span>Media IA</span>
                            <b>${aiAvgStr}</b>
                            <small>${bando.aiTotal} aciertos / ${bando.aiCount} modelos</small>
                        </div>
                    </div>
                    <div class="cp-scorebar-inline-track" aria-hidden="true">
                        <div class="cp-scorebar-inline-fill" style="width:${humanPct}%"></div>
                    </div>
                `}
                <div class="cp-duel-foot">${rightFoot}</div>
                ${collective.played > 0 ? `<div class="cp-duel-foot" style="margin-top:6px;color:var(--cp-gold);">Boleto colectivo Pe&ntilde;a: ${collective.hits}/${collective.played} aciertos · ${collective.hits >= Math.max(...rankingForCover.map(r=>r.jornada)) ? "¡Liderando!" : "en pelea"}</div>` : ""}
            </section>
        </main>

        ${liveCount ? `<button type="button" class="cp-live" data-page-action="LIVE"><span></span><b>${liveCount} EN DIRECTO</b><em>Entra al seguimiento · se excluyen partidos atascados >3h</em></button>` : ""}

        <section class="cp-dashboard" aria-label="Estado de la jornada">
            <button type="button" class="cp-data-card cp-focus" data-page-action="TICKET">
                <div class="cp-card-head"><span>Partido bajo lupa</span><b>${disagreement ? `${disagreement.unique} posturas` : "Análisis"}</b></div>
                ${disagreement ? `${coverFixtureHtml(disagreement.match, true)}<div class="cp-picks">${picksHtml}</div>` : `<span class="cp-empty">Aún sin cruces destacados</span>`}
            </button>

            <button type="button" class="cp-data-card cp-pulse" data-page-action="TICKET">
                <div class="cp-card-head"><span>Pulso de la Peña</span><b>${penaPulse ? "Más abierto" : "Consenso colectivo 1 boleto"}</b></div>
                ${penaPulse ? `${coverFixtureHtml(penaPulse.match, true)}
                    <div class="cp-pulse-bars" aria-label="1 ${penaPulse.row.p1}%, X ${penaPulse.row.px}%, 2 ${penaPulse.row.p2}%">
                        <i class="is-one" style="width:${penaPulse.row.p1}%"></i><i class="is-draw" style="width:${penaPulse.row.px}%"></i><i class="is-two" style="width:${penaPulse.row.p2}%"></i>
                    </div>
                    <div class="cp-pulse-labels"><span>1 · ${penaPulse.row.p1}%</span><span>X · ${penaPulse.row.px}%</span><span>2 · ${penaPulse.row.p2}%</span></div>
                    <div style="margin-top:8px;font-size:0.62rem;color:var(--cp-dim);">Boleto colectivo Pe&ntilde;a = signo m&aacute;s votado. 1 vs 1 contra cada IA, no 15 vs 6.</div>
                ` : `<span class="cp-empty">Aún no hay pronósticos</span>`}
            </button>

            <button type="button" class="cp-data-card cp-leaders" data-page-action="CONTEST">
                <div class="cp-card-head"><span>Clasificación · Jornada ${escapeHtml(String(jornada))}</span><b>Todos parten de cero</b></div>
                <ol>${rankingForCover.slice(0, 6).map((row, index) => `<li class="${row.isCollective ? "is-collective" : ""}"><i>${index + 1}</i><strong>${escapeHtml(row.name)} ${row.isCollective ? "· colectivo" : ""}</strong><span>${row.jornada}</span></li>`).join("") || `<li><i>—</i><strong>Sin datos</strong><span>0</span></li>`}</ol>
                <div style="margin-top:8px;font-size:0.6rem;color:var(--cp-dim);">General hist&oacute;rico separado de temporada oficial. En portada se muestra rendimiento de esta jornada.</div>
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
