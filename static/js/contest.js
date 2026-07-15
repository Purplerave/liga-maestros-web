/* ==========================================================================
   CONTEST — La Peña: perfil, ranking, podio, galardones, radar de sorpresas.
   Dependencias: utils.js, logos.js, state.js, ticket_page.js
   ========================================================================== */


function consensusLeader(consensus) {
    const values = [
        ["1", Number(consensus.p1 || 0)],
        ["X", Number(consensus.px || 0)],
        ["2", Number(consensus.p2 || 0)]
    ].sort((a, b) => b[1] - a[1]);
    const rawWinner = normalizeSign(consensus.ganador);
    const sign = ["1", "X", "2"].includes(rawWinner) ? rawWinner : values[0][0];
    const pct = (values.find(([value]) => value === sign) || values[0])[1];
    return {
        sign,
        pct,
        top: values[0],
        second: values[1],
        gap: values[0][1] - values[1][1]
    };
}

function tripletLeader(triplet) {
    if (!triplet) return null;
    const values = [
        ["1", Number(triplet["1"] ?? triplet.p1 ?? 0)],
        ["X", Number(triplet.X ?? triplet.x ?? triplet.px ?? 0)],
        ["2", Number(triplet["2"] ?? triplet.p2 ?? 0)]
    ];
    if (!values.some(([, value]) => value > 0)) return null;
    values.sort((a, b) => b[1] - a[1]);
    return values[0][0];
}

function buildSurpriseRadar(matches) {
    const preds = state.data.predicciones_actuales || {};
    const consenso = state.data.consenso_pena || [];
    const mySigns = state.my_signs || [];
    return (matches || []).slice(0, 14).map((match, idx) => {
        const c = consenso.find(item => Number(item.id) === Number(match.id)) || { p1: 0, px: 0, p2: 0, ganador: "-" };
        const leader = consensusLeader(c);
        if (!leader.top || leader.top[1] <= 0) return null;

        const programSign = normalizeSign(getSign(preds, idx, "programa", "v260_omnisciente"));
        const councilSign = normalizeSign(getSign(preds, idx, "consejo_ias", "consenso"));
        const userSign = normalizeSign(mySigns[idx] || "-");
        const info = state.data?.match_info?.[String(match.id)] || {};
        const externalLeaders = [info.q15, info.lae, info.apu].map(tripletLeader).filter(Boolean);
        const externalSplit = new Set(externalLeaders).size > 1;

        let score = Math.max(0, 64 - leader.top[1]) + Math.max(0, 18 - leader.gap);
        const labels = [];
        if (leader.gap <= 12) labels.push("abierto");
        if (programSign && programSign !== "-" && programSign !== leader.sign) {
            score += 24;
            labels.push("programa contra");
        }
        if (councilSign && councilSign !== "-" && councilSign !== leader.sign) {
            score += 18;
            labels.push("consejo duda");
        }
        if (userSign && userSign !== "-" && userSign !== leader.sign) {
            score += 10;
            labels.push("tu vas contra");
        }
        if (externalSplit) {
            score += 14;
            labels.push("mercado roto");
        }
        if (score < 24) return null;

        return {
            idx,
            title: `${getShortName(match.local)} - ${getShortName(match.visitante)}`,
            sign: leader.sign,
            pct: leader.pct,
            score,
            labels: [...new Set(labels)].slice(0, 2)
        };
    }).filter(Boolean)
        .sort((a, b) => b.score - a.score)
        .slice(0, 3);
}

function renderSurpriseRadar(matches) {
    const items = buildSurpriseRadar(matches);
    if (!items.length) return "";
    return `
        <section class="surprise-radar" aria-label="Radar de partidos con riesgo">
            <div class="surprise-radar-head">
                <span>Radar</span>
                <strong>${items.length} focos</strong>
            </div>
            <div class="surprise-radar-list">
                ${items.map(item => `
                    <button class="surprise-radar-card" type="button" data-radar-match="${item.idx}">
                        <span class="surprise-radar-title">${escapeHtml(item.title)}</span>
                        <span class="surprise-radar-meta">${escapeHtml(item.sign)} ${Math.round(item.pct)}% Â· ${escapeHtml(item.labels.join(" Â· ") || "riesgo")}</span>
                    </button>
                `).join("")}
            </div>
        </section>`;
}

function renderSidebarRadar() {
    const slot = qs("surprise-radar-slot");
    if (!slot) return;
    const matches = state.currentFilter === "ALL" && state.contestView === "MATCHES"
        ? (state.data.partidos || [])
        : [];
    slot.innerHTML = renderSurpriseRadar(matches);
}

function renderPrestigeRanking() {
    const container = qs("ranking-body");
    const ranking = state.data.ranking_maestros;
    if (!container || !ranking) return;
    const hiddenIds = new Set(["hermes", "HERMES", "momo", "MOMO", "jenova", "JENOVA", "manu", "MANU", "consenso", "CONSENSO"]);

    const nameMap = {
        "v260_omnisciente": "TECNO",
        "programa": "PROGRAMA",
        "consejo_ias": "CONSEJO IA",
        "gemini": "GEMA",
        "claude": "CLAUDE",
        "chatgpt": "CHATGPT",
        "grok": "GROK",
        "copilot": "COPILOT",
        "chipi": "CHIPI",
        "deepseek": "CHIPI",
        "ernie": "ERNIE",
        "kimi": "KIMI",
        "pepe": "PEPE",
        "geli": "GELI",
        "profe": "PROFE",
        "fortu": "FORTU",
        "mrpurple": "MRPURPLE",
        "111242361526361637939": "MRPURPLE R.",
        "oraculo": "ORACULO"
    };

    const rows = Object.entries(ranking).filter(([id]) => !hiddenIds.has(id)).map(([id, stats]) => ({
        id,
        name: nameMap[id] || (state.user && id === state.user.id ? "YO" : id.length > 10 ? id.substring(0, 10) : id),
        total: stats.total || 0,
        jornada: stats.jornada || 0,
        isUser: state.user && id === state.user.id
    }));

    const total = [...rows].sort((a, b) => b.total - a.total || b.jornada - a.jornada).slice(0, 8);
    const today = [...rows].filter(item => Number(item.jornada || 0) > 0)
        .sort((a, b) => b.jornada - a.jornada || b.total - a.total)
        .slice(0, 5);
    const dailyBlock = today.length
        ? `<div class="rank-section-title" style="margin-top:10px;">Jornada actual</div>
           ${today.map((item, idx) => renderRankLine(item, idx, "jornada", "hoy")).join("")}`
        : "";

    container.innerHTML = `
        <div class="rank-section-title">ClasificaciÃ³n general</div>
        ${total.map((item, idx) => renderRankLine(item, idx, "total", "")).join("")}
        ${dailyBlock}`;
}

function renderRankLine(item, idx, field, label) {
    return `
        <div class="rank-line ${idx === 0 ? "is-leader" : ""} ${item.isUser ? "is-user" : ""}">
            <span class="rank-pos">${idx + 1}</span>
            <span class="rank-name">${escapeHtml(item.name)}</span>
            <small class="rank-label">${label ? escapeHtml(label) : ""}</small>
            <b class="rank-total">${item[field]}</b>
        </div>`;
}

function renderContestRows(rows = [], limit = 5) {
    return rows.slice(0, limit).map(item => `
        <div class="contest-row ${item.is_user ? "is-user" : ""}">
            <span class="contest-pos">${item.pos}</span>
            <span class="contest-name">${escapeHtml(item.name)}</span>
            <span class="contest-points">${item.points}</span>
        </div>`).join("") || `<div class="empty-state">Sin datos cerrados todavÃ­a.</div>`;
}

function awardTierClass(idx) {
    if (idx === 0) return "gold";
    if (idx === 1) return "silver";
    if (idx === 2) return "bronze";
    return "";
}

function profileBadgeStrip(profile = {}) {
    return "";
}

function renderContestPanel() {
    const container = qs("contest-body");
    const contest = state.contest;
    if (!container || !contest) return;
    const profile = contest.profile;
    const profileBlock = profile ? `
        <div class="contest-card">
            <div class="contest-title"><span>${escapeHtml(profile.name || "Perfil")}</span><small>perfil</small></div>
            <div class="profile-grid">
                <div class="profile-stat"><span>PosiciÃ³n</span><strong>${profile.position ?? "-"}</strong></div>
                <div class="profile-stat"><span>Aciertos</span><strong>${profile.hits ?? 0}</strong></div>
                <div class="profile-stat"><span>% acierto</span><strong>${profile.hit_rate ?? 0}%</strong></div>
                <div class="profile-stat"><span>Jornadas</span><strong>${profile.played ?? 0}</strong></div>
            </div>
            ${profileBadgeStrip(profile) ? `<div class="profile-badge-strip">${profileBadgeStrip(profile)}</div>` : ""}
        </div>` : "";

    const awards = (contest.galardones?.jornadas || []).slice(0, 5).map(item => `
        <div class="award-row">
            <span>J${item.jornada}</span>
            <b class="contest-name">${escapeHtml(item.winner)}</b>
            <strong class="contest-points">${item.points}</strong>
        </div>`).join("") || `<div class="empty-state">Sin galardones.</div>`;

    container.innerHTML = `
        <div class="contest-block">
            ${profileBlock}
            <div class="contest-card">
                <div class="contest-title"><span>General</span><small>temporada</small></div>
                ${renderContestRows(contest.general || [], 6)}
            </div>
            <div class="contest-card">
                <div class="contest-title"><span>Jornada ${contest.jornada?.jornada || ""}</span><small>clasificaciÃ³n</small></div>
                ${renderContestRows(contest.jornada?.rows || [], 6)}
            </div>
            <div class="contest-card">
                <div class="contest-title"><span>Mes ${escapeHtml(contest.monthly?.month || "-")}</span><small>mensual</small></div>
                ${renderContestRows(contest.monthly?.rows || [], 5)}
            </div>
            <div class="contest-card">
                <div class="contest-title"><span>Galardones</span><small>ganadores</small></div>
                ${awards}
            </div>
        </div>`;
}

function renderContestPage(view = "CONTEST_PROFILE") {
    const contest = state.contest;
    if (!contest) return `<div class="empty-state">No se pudo cargar La PeÃ±a.</div>`;
    const profile = contest.profile;
    const profileBlock = profile ? `
        <div class="contest-card">
            <div class="contest-title"><span>${escapeHtml(profile.name || "Perfil")}</span><small>perfil</small></div>
            <div class="profile-grid">
                <div class="profile-stat"><span>PosiciÃ³n</span><strong>${profile.position ?? "-"}</strong></div>
                <div class="profile-stat"><span>PronÃ³sticos</span><strong>${profile.predictions ?? 0}</strong></div>
                <div class="profile-stat"><span>Aciertos</span><strong>${profile.hits ?? 0}</strong></div>
                <div class="profile-stat"><span>% acierto</span><strong>${profile.hit_rate ?? 0}%</strong></div>
                <div class="profile-stat"><span>Jornadas</span><strong>${profile.played ?? 0}</strong></div>
                <div class="profile-stat"><span>Mejor posiciÃ³n</span><strong>${profile.best_position ?? "-"}</strong></div>
            </div>
            ${profileBadgeStrip(profile) ? `<div class="profile-badge-strip">${profileBadgeStrip(profile)}</div>` : ""}
        </div>` : `
        <div class="contest-card">
            <div class="contest-title"><span>Perfil</span><small>sesiÃ³n</small></div>
            <div class="empty-state">Entra con Google para ver tus estadÃ­sticas personales.</div>
        </div>`;

    const awards = (contest.galardones?.jornadas || []).slice(0, 10).map(item => `
        <div class="award-row">
            <span>J${item.jornada}</span>
            <b class="contest-name">${escapeHtml(item.winner)}</b>
            <strong class="contest-points">${item.points}</strong>
        </div>`).join("") || `<div class="empty-state">Sin galardones todavÃ­a.</div>`;

    const results = (profile?.results || []).slice().reverse().map(item => {
        const ticket = (item.ticket || []).map((sign, idx) => idx === 14 ? `[${sign}]` : sign).join(",");
        return `
            <div class="contest-row">
                <span class="contest-pos">J${item.jornada}</span>
                <span class="contest-ticket">${escapeHtml(ticket)}</span>
                <span class="contest-points">${item.points}</span>
            </div>`;
    }).join("") || `<div class="empty-state">Sin resultados personales.</div>`;

    if (view === "CONTEST_PROFILE") {
        if (!profile) {
            return `<section class="contest-page single"><div class="contest-card"><div class="contest-title"><span>Perfil</span><small>sesion</small></div><div class="empty-state">Entra con Google para ver tus estadisticas personales.</div></div></section>`;
        }
        return `
            <section class="contest-page single">
                <div class="contest-card">
                    <div class="contest-title"><span>Perfil y estadisticas de ${escapeHtml(profile.name || "Maestro")}</span><small>personal</small></div>
                    <div class="profile-grid">
                        <div class="profile-stat"><span>Posicion</span><strong>${profile.position ?? "-"}</strong></div>
                        <div class="profile-stat"><span>Pronosticos</span><strong>${profile.predictions ?? 0}</strong></div>
                        <div class="profile-stat"><span>Aciertos</span><strong>${profile.hits ?? 0}</strong></div>
                        <div class="profile-stat"><span>% acierto</span><strong>${profile.hit_rate ?? 0}%</strong></div>
                        <div class="profile-stat"><span>Jornadas jugadas</span><strong>${profile.played ?? 0}</strong></div>
                        <div class="profile-stat"><span>Aciertos/jornada</span><strong>${profile.hits_per_jornada ?? 0}</strong></div>
                        <div class="profile-stat"><span>Mejor posicion</span><strong>${profile.best_position ?? "-"}</strong></div>
                    </div>
                    ${profileBadgeStrip(profile) ? `<div class="profile-badge-strip">${profileBadgeStrip(profile)}</div>` : ""}
                </div>
                <div class="contest-card">
                    <div class="contest-title"><span>Resultados</span><small>quiniela | aciertos | posicion</small></div>
                    ${results}
                </div>
            </section>`;
    }

    if (view === "CONTEST_GENERAL") {
        return `<section class="contest-page single"><div class="contest-card"><div class="contest-title"><span>La PeÃ±a general</span><small>temporada</small></div>${renderContestRows(contest.general || [], 80)}</div></section>`;
    }

    if (view === "CONTEST_MONTHLY") {
        return `<section class="contest-page single"><div class="contest-card"><div class="contest-title"><span>La PeÃ±a mensual</span><small>${escapeHtml(contest.monthly?.month || "-")}</small></div>${renderContestRows(contest.monthly?.rows || [], 80)}</div></section>`;
    }

    if (view === "CONTEST_JORNADA") {
        return `<section class="contest-page single"><div class="contest-card"><div class="contest-title"><span>La PeÃ±a jornada ${contest.jornada?.jornada || ""}</span><small>jornada actual</small></div>${renderContestRows(contest.jornada?.rows || [], 80)}</div></section>`;
    }

    if (view === "CONTEST_AWARDS") {
        const jornadaItems = contest.galardones?.jornadas || [];
        const monthItems = contest.galardones?.meses || [];
        const selectedJornada = String(state.selectedAwardJornada || jornadaItems[0].jornada || "");
        const selectedMonth = String(state.selectedAwardMonth || monthItems[0].month || "");
        const jornadaPick = jornadaItems.find(item => String(item.jornada) === selectedJornada) || jornadaItems[0];
        const monthPick = monthItems.find(item => String(item.month) === selectedMonth) || monthItems[0];
        const renderAwardChip = (item, idx, type = "jornada") => `
            <div class="award-chip ${awardTierClass(idx)}">
                <span class="award-medal">${idx + 1}</span>
                <div><strong>${type === "mes" ? escapeHtml(item.month) : `J${escapeHtml(item.jornada)}`}</strong><small>${type === "mes" ? "mes" : escapeHtml(item.date || "jornada")}</small></div>
                <b>${escapeHtml(item.winner)}</b>
                <em>${item.points}</em>
            </div>`;
        const renderHistoryRow = (item, idx, type = "jornada") => `
            <div class="award-history-row">
                <span>${idx + 1}</span>
                <strong>${type === "mes" ? escapeHtml(item.month) : `J${escapeHtml(item.jornada)}`}</strong>
                <b>${escapeHtml(item.winner)}</b>
                <em>${item.points}</em>
            </div>`;
        const recentJornadas = jornadaItems.slice(0, 5).map((item, idx) => renderAwardChip(item, idx)).join("") || `<div class="empty-state">Sin ganadores de jornada.</div>`;
        const recentMonths = monthItems.slice(0, 5).map((item, idx) => renderAwardChip(item, idx, "mes")).join("") || `<div class="empty-state">Sin ganadores mensuales.</div>`;
        const jornadaHistory = jornadaItems.slice(0, 14).map((item, idx) => renderHistoryRow(item, idx)).join("") || `<div class="empty-state">Sin historico de jornadas.</div>`;
        const monthHistory = monthItems.slice(0, 10).map((item, idx) => renderHistoryRow(item, idx, "mes")).join("") || `<div class="empty-state">Sin historico mensual.</div>`;
        const jornadaOptions = jornadaItems.map(item => `<option value="${escapeHtml(item.jornada)}" ${String(item.jornada) === selectedJornada ? "selected" : ""}>Jornada ${escapeHtml(item.jornada)}</option>`).join("");
        const monthOptions = monthItems.map(item => `<option value="${escapeHtml(item.month)}" ${String(item.month) === selectedMonth ? "selected" : ""}>${escapeHtml(item.month)}</option>`).join("");
        return `
            <section class="contest-page awards-page">
                <div class="contest-card awards-head">
                    <div>
                        <span>Galardones</span>
                        <strong>Campeones de la Pena</strong>
                    </div>
                    <p>Ganadores por jornada y por mes, con consulta rapida del historico.</p>
                    <div class="awards-totals">
                        <b>${jornadaItems.length}</b><small>jornadas</small>
                        <b>${monthItems.length}</b><small>meses</small>
                    </div>
                </div>
                <div class="awards-grid">
                <div class="contest-card awards-card">
                    <div class="contest-title"><span>Ultimos campeones</span><small>jornada</small></div>
                    <div class="award-strip">${recentJornadas}</div>
                    <div class="award-picker">
                        <label>Consultar jornada</label>
                        <select onchange="changeAwardJornada(this.value)">${jornadaOptions}</select>
                    </div>
                    ${jornadaPick ? `<div class="award-feature">
                        <span>J${jornadaPick.jornada}</span>
                        <strong>${escapeHtml(jornadaPick.winner)}</strong>
                        <em>${jornadaPick.points} pts</em>
                    </div>` : ""}
                </div>
                <div class="contest-card awards-card">
                    <div class="contest-title"><span>Reyes del mes</span><small>ultimos 3</small></div>
                    <div class="award-strip">${recentMonths}</div>
                    <div class="award-picker">
                        <label>Consultar mes</label>
                        <select onchange="changeAwardMonth(this.value)">${monthOptions}</select>
                    </div>
                    ${monthPick ? `<div class="award-feature">
                        <span>${escapeHtml(monthPick.month)}</span>
                        <strong>${escapeHtml(monthPick.winner)}</strong>
                        <em>${monthPick.points} pts</em>
                    </div>` : ""}
                </div>
                <div class="contest-card awards-history-card">
                    <div class="contest-title"><span>Historico</span><small>consulta rapida</small></div>
                    <div class="awards-history-grid">
                        <div>
                            <h4>Jornadas</h4>
                            <div class="awards-history-list">${jornadaHistory}</div>
                        </div>
                        <div>
                            <h4>Meses</h4>
                            <div class="awards-history-list">${monthHistory}</div>
                        </div>
                    </div>
                </div>
                </div>
            </section>`;
    }

    return `
        <section class="contest-page">
            <div class="contest-card">
                <div class="contest-title"><span>La PeÃ±a general</span><small>temporada</small></div>
                ${renderContestRows(contest.general || [], 12)}
            </div>
            <div class="contest-grid-secondary">
                ${profileBlock}
                <div class="contest-card">
                    <div class="contest-title"><span>Jornada ${contest.jornada?.jornada || ""}</span><small>La PeÃ±a</small></div>
                    ${renderContestRows(contest.jornada?.rows || [], 8)}
                </div>
            </div>
            <div class="contest-card">
                <div class="contest-title"><span>Mensual ${escapeHtml(contest.monthly?.month || "-")}</span><small>mes actual</small></div>
                ${renderContestRows(contest.monthly?.rows || [], 10)}
            </div>
            <div class="contest-card">
                <div class="contest-title"><span>Galardones</span><small>ganadores de jornada</small></div>
                ${awards}
            </div>
            <div class="contest-card contest-wide">
                <div class="contest-title"><span>Tus resultados</span><small>quiniela Â· aciertos Â· posiciÃ³n</small></div>
                ${results}
            </div>
        </section>`;
}
