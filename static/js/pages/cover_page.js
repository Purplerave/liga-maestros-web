/* Portada competitiva de Liga de Maestros. */

function hydrateCoverTypewriter() {}

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

function coverPredictionSigns(entry) {
    if (Array.isArray(entry)) return entry;
    return Array.isArray(entry?.signos) ? entry.signos : [];
}

function coverDisagreementMatch(matches) {
    const columns = coverMasterColumns();
    const predictions = state.data?.predicciones_actuales || {};
    let best = null;
    matches.slice(0, 14).forEach((match, index) => {
        const picks = columns.map(col => ({
            id: col.id,
            label: col.label,
            sign: coverPredictionSigns(predictions[col.id])[index] || "-",
        })).filter(item => item.sign !== "-");
        const unique = new Set(picks.map(item => item.sign)).size;
        const score = unique * 10 + picks.filter(item => item.sign.length > 1).length;
        if (!best || score > best.score) best = { match, picks, unique, score };
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

function coverMatchTimestamp(match) {
    const rawDate = String(match?.fecha_raw || match?.fecha || "").split(" ")[0];
    const rawHour = String(match?.hora || "00:00").slice(0, 5);
    const stamp = Date.parse(`${rawDate}T${rawHour}:00`);
    return Number.isNaN(stamp) ? Number.MAX_SAFE_INTEGER : stamp;
}

function coverNextMatch(matches) {
    const live = matches.find(match => isLiveStatus(match.status) || isLiveMatch(match));
    if (live) return { match: live, live: true };
    const pending = matches
        .filter(match => !(isFinishedStatus(match.status) || isImplicitlyFinished(match)) && coverMatchTimestamp(match) >= Date.now() - 3600000)
        .slice()
        .sort((a, b) => coverMatchTimestamp(a) - coverMatchTimestamp(b));
    return { match: pending[0] || matches[0] || null, live: false };
}

function coverFixtureHtml(match, compact = false) {
    if (!match) return `<span class="cp-empty">Horario pendiente</span>`;
    return `<div class="cp-fixture ${compact ? "is-compact" : ""}">
        <span class="cp-team cp-team-home">${logoBadge(match.local, teamLogo(match, "home"))}<strong>${escapeHtml(getShortName(match.local))}</strong></span>
        <span class="cp-fixture-sep">VS</span>
        <span class="cp-team cp-team-away">${logoBadge(match.visitante, teamLogo(match, "away"))}<strong>${escapeHtml(getShortName(match.visitante))}</strong></span>
    </div>`;
}

function coverNavHtml(liveCount) {
    const links = [
        ["TICKET", "Quiniela"],
        ["LIVE", liveCount ? `Directo ${liveCount}` : "Directo"],
        ["STANDINGS", "Ligas"],
        ["SNAKE", "Juegos"],
        ["CONTEST", "La Pe&ntilde;a"],
    ];
    return links.map(([action, label]) =>
        `<button type="button" class="cp-nav-link" data-page-action="${action}">${label}</button>`
    ).join("");
}

function coverAccountHtml(rankingRows) {
    if (!state.user) return `<a class="cp-account" href="/login/google">Entrar</a>`;
    const uid = String(state.user.id).toLowerCase();
    const index = rankingRows.findIndex(row => String(row.uid).toLowerCase() === uid);
    const row = index >= 0 ? rankingRows[index] : null;
    const firstName = String(state.user.name || "Jugador").split(" ")[0];
    return `<button type="button" class="cp-account is-user" onclick="openProfileView()">
        <strong>${escapeHtml(firstName)}</strong><span>#${index >= 0 ? index + 1 : "-"} &middot; ${row?.total || 0} pts</span>
    </button>`;
}

function renderNewspaperCoverPageV3() {
    const matches = state.data?.partidos || [];
    const closed = coverIsClosed();
    const saved = hasSavedTicket();
    const jornada = state.data?.jornada || state.jornada || "";
    const liveCount = matches.filter(match => isLiveStatus(match.status) || isLiveMatch(match)).length;
    const masterNames = coverMasterNames();
    const masterColumns = coverMasterColumns();
    const penaVotes = Number(state.data?.consenso_pena?.[0]?.total || 0);
    const rankingRows = coverRankingRows();
    const disagreement = coverDisagreementMatch(matches);
    const penaPulse = coverTightPenaMatch(matches);
    const next = coverNextMatch(matches);
    const ctaLabel = closed
        ? (saved ? "Ver mi quiniela" : "Ver resultados")
        : (saved ? "Revisar mi quiniela" : "Hacer mi quiniela");
    const statusLabel = closed ? "Jornada cerrada" : `Cierre en ${coverCloseLabel()}`;
    const distinctReadings = disagreement?.unique || 0;

    return `<div class="cp">
        <header class="cp-masthead">
            <button type="button" class="cp-brand" data-page-action="ALL" aria-label="Portada de Liga de Maestros">
                <img src="/static/img/ligademaestroslogo_trans.png" alt="Liga de Maestros">
            </button>
            <nav class="cp-nav" aria-label="Secciones de Liga de Maestros">${coverNavHtml(liveCount)}</nav>
            ${coverAccountHtml(rankingRows)}
        </header>

        <main class="cp-stage">
            <section class="cp-intro" aria-labelledby="cp-title">
                <div class="cp-kicker"><span>Jornada ${escapeHtml(jornada)}</span><i></i><span>${escapeHtml(statusLabel)}</span></div>
                <h1 id="cp-title">&iexcl;Haz tu quiniela!</h1>
                <p class="cp-lead">Compite contra los Maestros IA y contra toda La Pe&ntilde;a. Suma aciertos, escala en el ranking y conquista la jornada. <strong>&iquest;Qui&eacute;n sabe m&aacute;s de f&uacute;tbol?</strong></p>
                <div class="cp-actions">
                    <button type="button" class="cp-primary" data-page-action="TICKET">${escapeHtml(ctaLabel)}</button>
                    <button type="button" class="cp-secondary" data-page-action="CONTEST">Ver clasificaci&oacute;n</button>
                </div>
                <div class="cp-proof" aria-label="Datos de la competici&oacute;n">
                    <span><b>${rankingRows.length}</b> participantes</span>
                    <span><b>${masterNames.length}</b> Maestros IA</span>
                    <span><b>15</b> partidos</span>
                </div>
            </section>

            <section class="cp-duel" aria-label="La Pe&ntilde;a contra los Maestros IA">
                <div class="cp-duel-kicker">EL DUELO DE LA JORNADA</div>
                <div class="cp-versus">
                    <div class="cp-side is-pena"><span>HUMANOS</span><strong>LA PE&Ntilde;A</strong><small>${penaVotes || rankingRows.length} columnas</small></div>
                    <div class="cp-vs">VS</div>
                    <div class="cp-side is-ai"><span>RIVALES</span><strong>MAESTROS IA</strong><small>${masterNames.length} IAs + Programa</small></div>
                </div>
                ${disagreement ? `<div class="cp-focus">
                    <div class="cp-focus-head"><span>PARTIDO BAJO LUPA</span><b>${distinctReadings} pron&oacute;sticos distintos</b></div>
                    ${coverFixtureHtml(disagreement.match, true)}
                    <div class="cp-picks" aria-label="Pron&oacute;sticos de los Maestros">${disagreement.picks.map(item => `<span class="${String(item.id).toLowerCase() === "programa" ? "is-program" : ""}" title="${escapeHtml(item.label)}"><small>${escapeHtml(item.label)}</small><b>${escapeHtml(item.sign)}</b></span>`).join("")}</div>
                </div>` : ""}
            </section>
        </main>

        ${liveCount ? `<button type="button" class="cp-live" data-page-action="LIVE"><span></span><b>${liveCount} EN DIRECTO</b><em>Entra en la sala de seguimiento</em></button>` : ""}

        <section class="cp-dashboard" aria-label="Estado de la jornada">
            <button type="button" class="cp-data-card cp-next" data-page-action="${next.live ? "LIVE" : "TICKET"}">
                <div class="cp-card-head"><span>${next.live ? "AHORA MISMO" : "PR&Oacute;XIMO PARTIDO"}</span><b>${next.live ? "EN DIRECTO" : formatSmartDate(next.match?.fecha_raw, next.match?.hora)}</b></div>
                ${coverFixtureHtml(next.match)}
            </button>

            <button type="button" class="cp-data-card cp-pulse" data-page-action="TICKET">
                <div class="cp-card-head"><span>PULSO DE LA PE&Ntilde;A</span><b>El partido m&aacute;s abierto</b></div>
                ${penaPulse ? `${coverFixtureHtml(penaPulse.match, true)}
                    <div class="cp-pulse-bars" aria-label="1 ${penaPulse.row.p1}%, X ${penaPulse.row.px}%, 2 ${penaPulse.row.p2}%">
                        <i class="is-one" style="width:${penaPulse.row.p1}%"></i><i class="is-draw" style="width:${penaPulse.row.px}%"></i><i class="is-two" style="width:${penaPulse.row.p2}%"></i>
                    </div>
                    <div class="cp-pulse-labels"><span>1 &middot; ${penaPulse.row.p1}%</span><span>X &middot; ${penaPulse.row.px}%</span><span>2 &middot; ${penaPulse.row.p2}%</span></div>` : `<span class="cp-empty">A&uacute;n no hay pron&oacute;sticos</span>`}
            </button>

            <button type="button" class="cp-data-card cp-leaders" data-page-action="CONTEST">
                <div class="cp-card-head"><span>CLASIFICACI&Oacute;N GENERAL</span><b>La pelea por el liderato</b></div>
                <ol>${rankingRows.slice(0, 3).map((row, index) => `<li><i>${index + 1}</i><strong>${escapeHtml(row.name)}</strong><span>${row.total} pts</span></li>`).join("")}</ol>
            </button>
        </section>
    </div>`;
}
