/* Portada Liga de Maestros v4 - Panel control compacto, español natural
   Encima del rediseño de main: escudo grande a la izquierda del titular,
   nombres directos (El duelo, El partido en disputa, Así vota la Peña,
   Última hora, La porra) y quitado el comentario IA fijo de ejemplo. */

function loadSacramentoFont() {}
function hydrateCoverTypewriter() {}
function startCoverScorebar() {}

let _countdownStarted = false;
let _seasonCountdownStarted = false;
const SEASON_KICKOFF = new Date("2026-08-15T19:30:00");

function formatCountdownDigits(diff) {
    const safe = Math.max(0, diff);
    const days = Math.floor(safe / 86400000);
    const hours = Math.floor((safe % 86400000) / 3600000);
    const mins = Math.floor((safe % 3600000) / 60000);
    const secs = Math.floor((safe % 60000) / 1000);
    const cell = (value, unit) =>
        `<span class="cp-digit"><b>${String(value).padStart(2, "0")}</b><small>${unit}</small></span>`;
    return `${cell(days, "días")}<i aria-hidden="true">:</i>${cell(hours, "hrs")}<i aria-hidden="true">:</i>${cell(mins, "min")}<i aria-hidden="true">:</i>${cell(secs, "seg")}`;
}

function startCoverCountdown() {
    if (_countdownStarted) return;
    const node = document.querySelector("#cp-deadline");
    if (!node) return;
    _countdownStarted = true;
    const tick = () => {
        const deadline = document.querySelector("#cp-deadline");
        if (!deadline) return;
        const raw = (state && state.data && (state.data.edit_deadline || state.data.kickoff_at || "")) || "";
        if (!raw) { deadline.textContent = state?.data?.is_locked ? "CERRADA" : "ABIERTA"; return; }
        const target = new Date(String(raw).replace(" ", "T"));
        if (Number.isNaN(target.getTime())) { deadline.textContent = state?.data?.is_locked ? "CERRADA" : "ABIERTA"; return; }
        const diff = target.getTime() - Date.now();
        if (diff <= 0 || state.data.is_locked) { deadline.textContent = "CERRADA"; deadline.classList.add("is-urgent"); return; }
        const s = Math.max(0, Math.floor(diff / 1000));
        const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60;
        deadline.textContent = h > 0 ? `${h}h ${String(m).padStart(2,"0")}m` : `${String(m).padStart(2,"0")}m ${String(sec).padStart(2,"0")}s`;
        deadline.classList.toggle("is-urgent", diff < 3_600_000);
    };
    tick(); setInterval(tick, 1000);
}

function startSeasonCountdown() {
    const update = () => {
        const timer = document.getElementById("cp-countdown-timer");
        if (!timer) return;
        const label = document.querySelector(".cp-countdown-label");
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
        if (label) {
            label.textContent = usingJornada
                ? "Cierre de jornada"
                : diff <= 0
                    ? "Temporada 26/27"
                    : "Jornada 1 · arranque";
        }
        if (diff <= 0) {
            timer.innerHTML = `<span class="cp-countdown-live">La Liga está en juego</span>`;
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

    // Portada v12 — narrativa corta + duelo + partido + operativa
    const seasonLabel = "Temporada 26/27";
    const featured = disagreement || (matches[0] ? { match: matches[0], picks: [], pena: null } : null);
    let featuredMeta = "";
    if (featured && featured.match) {
        const m = featured.match;
        const when = m.hora || m.kickoff || m.fecha || "";
        featuredMeta = when ? escapeHtml(String(when)) : "Jornada " + escapeHtml(String(jornada || "1"));
    }

    // Mini 1X2 de la Peña sobre el partido destacado
    let featuredPulse = "";
    if (featured && featured.match) {
        const row = consenso.find(r => Number(r.id) === Number(featured.match.id));
        if (row && Number(row.total || 0) > 0) {
            const p1 = Number(row.p1 || 0), px = Number(row.px || 0), p2 = Number(row.p2 || 0);
            const t = p1 + px + p2 || 1;
            featuredPulse = `
                <div class="cp-featured-pulse" aria-label="Voto de La Peña">
                    <div class="cp-featured-pulse-bars">
                        <i class="is-one" style="width:${(p1/t*100).toFixed(1)}%"></i>
                        <i class="is-draw" style="width:${(px/t*100).toFixed(1)}%"></i>
                        <i class="is-two" style="width:${(p2/t*100).toFixed(1)}%"></i>
                    </div>
                    <div class="cp-featured-pulse-labels">
                        <span>1 · ${(p1/t*100).toFixed(0)}%</span>
                        <span>X · ${(px/t*100).toFixed(0)}%</span>
                        <span>2 · ${(p2/t*100).toFixed(0)}%</span>
                    </div>
                    <div class="cp-featured-pulse-foot">${Number(row.total)} votos de La Peña</div>
                </div>`;
        } else if (featured.pena) {
            featuredPulse = `<div class="cp-featured-pulse-foot">La Peña se inclina por <b>${escapeHtml(featured.pena.sign)}</b></div>`;
        }
    }

    // Picks IA del partido destacado
    let featuredPicks = "";
    if (featured && featured.picks && featured.picks.length) {
        const limited = featured.picks.slice(0, 4);
        featuredPicks = `<div class="cp-featured-picks">${limited.map(item =>
            `<span title="${escapeHtml(item.label)}"><small>${escapeHtml(item.label).slice(0, 10)}</small><b>${escapeHtml(item.sign)}</b></span>`
        ).join("")}</div>`;
    }

    // Duelo Peña vs IA
    let duelBody = "";
    if (isFirstOfficial) {
        duelBody = `
            <div class="cp-duel-zero">
                <div class="cp-duel-zero-badge">${escapeHtml(seasonLabel)}</div>
                <div class="cp-duel-zero-title">TODO A CERO</div>
                <p class="cp-duel-zero-text">Las pruebas acabaron. Empieza la liga de verdad.</p>
            </div>
            <div class="cp-duel-scores is-reset">
                <div class="cp-duel-side is-pena">
                    <span class="cp-duel-avatar" aria-hidden="true">👥</span>
                    <span class="cp-duel-side-label">La Peña</span>
                    <strong class="cp-duel-side-value">0</strong>
                    <small>media pruebas 6,9</small>
                </div>
                <div class="cp-duel-vs" aria-hidden="true">VS</div>
                <div class="cp-duel-side is-ia">
                    <span class="cp-duel-avatar" aria-hidden="true">✦</span>
                    <span class="cp-duel-side-label">Maestros IA</span>
                    <strong class="cp-duel-side-value">0</strong>
                    <small>media pruebas 8,2</small>
                </div>
            </div>`;
    } else {
        const diff = (bando.aiAvg - bando.humanAvg);
        const diffStr = (diff >= 0 ? "+" : "") + diff.toFixed(1).replace(".", ",");
        const leader = diff > 0.05 ? "Las máquinas van por delante" : diff < -0.05 ? "La Peña va por delante" : "Empate técnico";
        duelBody = `
            <div class="cp-duel-scores">
                <div class="cp-duel-side is-pena">
                    <span class="cp-duel-side-label">La Peña</span>
                    <strong class="cp-duel-side-value">${escapeHtml(humanAvgStr)}</strong>
                    <small>media aciertos</small>
                </div>
                <div class="cp-duel-vs" aria-hidden="true">VS</div>
                <div class="cp-duel-side is-ia">
                    <span class="cp-duel-side-label">Maestros IA</span>
                    <strong class="cp-duel-side-value">${escapeHtml(aiAvgStr)}</strong>
                    <small>media aciertos</small>
                </div>
            </div>
            <div class="cp-duel-bar" role="img" aria-label="Reparto del duelo">
                <i class="is-pena" style="width:${Math.max(8, Math.min(92, humanPct)).toFixed(1)}%"></i>
                <i class="is-ia" style="width:${Math.max(8, Math.min(92, 100 - humanPct)).toFixed(1)}%"></i>
            </div>
            <div class="cp-duel-foot"><b>${escapeHtml(leader)}</b> · diff ${escapeHtml(diffStr)}</div>`;
    }

    const userDone = (state.my_signs || []).filter(sign => sign && sign !== "-").length;
    const userProgressHtml = state.user ? `
        <div class="cp-user-progress${userDone === 15 ? " is-done" : ""}" data-page-action="TICKET">
            <span>Tu quiniela</span>
            <strong>${userDone}/15</strong>
            <div class="cp-user-track" aria-hidden="true"><i style="width:${((userDone / 15) * 100).toFixed(1)}%"></i></div>
        </div>` : "";
    const assetsV = document.body?.dataset?.assetsV || "";
    const crestSrc = `/static/img/liga_maestros_mark.svg?v=${encodeURIComponent(assetsV)}`;

    const countdownHtml = `<div class="cp-countdown" id="cp-countdown">
        <div class="cp-countdown-label">Jornada 1 · arranque</div>
        <div class="cp-countdown-timer" id="cp-countdown-timer"></div>
        <div class="cp-countdown-date">15 ago · 19:30 · Alavés vs Getafe</div>
    </div>`;

    const featuredHtml = featured && featured.match ? `
        <article class="cp-featured" data-page-action="TICKET">
            <div class="cp-card-head">
                <span>PARTIDO DE LA JORNADA</span>
                <b>${featuredMeta || "Jornada " + escapeHtml(String(jornada || ""))}</b>
            </div>
            ${coverFixtureHtml(featured.match, false)}
            ${featuredPulse}
            ${featuredPicks}
            <button type="button" class="cp-featured-cta" data-page-action="TICKET">Pronosticar →</button>
        </article>` : `
        <article class="cp-featured is-empty">
            <div class="cp-card-head"><span>PARTIDO DE LA JORNADA</span></div>
            <p class="cp-empty">Los partidos se publicarán con el cierre de la jornada anterior.</p>
        </article>`;

    return `<div class="cp">
        <div class="cp-main">
            <header class="cp-hero">
                <img class="cp-hero-crest" src="${crestSrc}" alt="" width="72" height="72">
                <div class="cp-kicker">
                    <span>Quiniela ${escapeHtml(String(jornada || "1"))}</span>
                    <i class="cp-kicker-dot"></i>
                    <span id="cp-deadline">${escapeHtml(statusLabel)}</span>
                    ${liveCount ? `<span class="cp-kicker-live">● ${liveCount} en directo</span>` : ""}
                </div>
                <div class="cp-hero-tagline"><b>1X2</b> · La Peña contra las máquinas</div>
                <h1 class="cp-hero-title">
                    <span class="cp-title-white">LIGA DE </span><span class="cp-title-gold">MAESTROS</span>
                </h1>
                <p class="cp-hero-pitch">Temporada oficial. 15 partidos por jornada. Humanos vs IA. Gana quien acierte más.</p>
                ${countdownHtml}
                ${userProgressHtml}
                <div class="cp-actions">
                    <button type="button" class="cp-primary" data-page-action="TICKET">${escapeHtml(ctaLabel)}</button>
                    <button type="button" class="cp-secondary" data-page-action="CONTEST">Clasificación</button>
                </div>
            </header>

            <section class="cp-arena" aria-label="El duelo">
                <article class="cp-duel">
                    <div class="cp-card-head"><span>EL DUELO</span><b>Peña vs IA</b></div>
                    ${duelBody}
                </article>
                ${featuredHtml}
            </section>
        </div>

        <section class="cp-ops" aria-label="Tu jornada">
            <div class="cp-data-card cp-porra" data-page-action="TICKET">
                <div class="cp-card-head"><span id="cover-porra-title">LA PORRA</span><b>+2 pts</b></div>
                <div id="cover-porra-content" class="cp-porra-content"><span class="cp-porra-loading">Cargando</span></div>
            </div>

            <section class="cp-journey-card" aria-labelledby="cp-journey-title">
                <div class="cp-card-head">
                    <span id="cp-journey-title">TU JORNADA</span>
                    <b>3 pasos</b>
                </div>
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

            <div class="cp-data-card cp-news-card" id="cp-news-card">
                <div class="cp-news-header">
                    <span>ÚLTIMA HORA</span>
                    <a href="#" data-page-action="NEWS">Ver todas →</a>
                </div>
                <div id="cover-news-content" class="cp-news-content"><span class="cp-porra-loading">Cargando...</span></div>
            </div>
        </section>

        ${liveCount ? `<button type="button" class="cp-live" data-page-action="LIVE"><span></span><b>${liveCount} EN DIRECTO</b><em>Seguimiento</em></button>` : ""}
    </div>`;
}
