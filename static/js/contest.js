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

function profileTone(value) {
    const number = Number(value || 0);
    return number > 0 ? "good" : number < 0 ? "bad" : "mid";
}

function renderProfileDashboard(profile) {
    const results = (profile.results || []).slice().reverse();
    const vsPena = profile.vs_pena || {};
    const streak = profile.streak || {};
    const rivalries = profile.rivalries || [];
    const awards = profile.awards || [];
    const initials = String(profile.name || "M")
        .split(/\s+/).filter(Boolean).map(part => part[0]).join("").slice(0, 2).toUpperCase();
    const comparison = Number(vsPena.diff || 0);
    const comparisonText = comparison > 0 ? `+${comparison}` : String(comparison || 0);
    const resultRows = results.map(item => {
        const points = Number(item.points || 0);
        const peerAverage = Number(item.pena_avg || 0);
        const diff = Math.round((points - peerAverage) * 10) / 10;
        const ticket = (item.ticket || []).join(" ");
        return `
            <div class="profile-result-row">
                <strong>J${escapeHtml(item.jornada)}</strong>
                <span class="profile-result-score">${points}<small> aciertos</small></span>
                <span class="profile-result-position">#${escapeHtml(item.pos || "-")}</span>
                        <span class="profile-result-diff ${profileTone(diff)}">${diff > 0 ? "+" : ""}${diff}</span>
                <span class="profile-result-meter"><i style="width:${Math.min(100, Math.max(0, points / 15 * 100))}%"></i></span>
                <span class="profile-result-ticket" title="${escapeHtml(ticket)}">${escapeHtml(ticket)}</span>
            </div>`;
    }).join("") || `<div class="profile-empty">Aun no hay jornadas cerradas en tu historial.</div>`;
    const rivalryRows = rivalries.slice(0, 5).map(item => `
        <div class="profile-rival-row">
            <span>${escapeHtml(item.name)}</span>
            <strong class="${profileTone(item.diff)}">${item.wins}-${item.draws}-${item.losses}</strong>
            <small>${Number(item.diff || 0) > 0 ? "+" : ""}${item.diff}</small>
        </div>`).join("") || `<div class="profile-empty compact">Aun no hay duelos comparables.</div>`;
    const awardRows = awards.slice(0, 4).map(item => `
        <div class="profile-award-row"><span>J${escapeHtml(item.jornada)}</span><strong>Campeon</strong><b>${item.points}</b></div>`
    ).join("") || `<div class="profile-empty compact">Tu primer galardon sigue en juego.</div>`;

    return `
        <section class="profile-page-pro">
            <header class="profile-summary">
                <button type="button" class="profile-back" data-page-action="ALL">&larr; Portada</button>
                <div class="profile-identity">
                    <div class="profile-avatar-compact">${escapeHtml(initials || "M")}</div>
                    <div>
                        <span>Mi temporada</span>
                        <h2>${escapeHtml(profile.name || "Maestro")}</h2>
                    </div>
                </div>
                <div class="profile-summary-rank"><span>Clasificacion</span><strong>#${profile.position ?? "-"}</strong></div>
                <div class="profile-summary-actions">
                    <a href="/cuenta">Cuenta</a>
                    <a href="/logout">Salir</a>
                </div>
            </header>

            <div class="profile-kpi-strip">
                <div><span>Puntos</span><strong>${profile.points ?? profile.hits ?? 0}</strong></div>
                <div><span>Aciertos</span><strong>${profile.hits ?? 0}</strong></div>
                <div><span>Pronosticos</span><strong>${profile.predictions ?? 0}</strong></div>
                <div><span>Eficacia</span><strong>${profile.hit_rate ?? 0}%</strong></div>
                <div><span>Jornadas</span><strong>${profile.played ?? 0}</strong></div>
                <div><span>Media</span><strong>${profile.hits_per_jornada ?? 0}</strong></div>
                <div><span>Mejor puesto</span><strong>#${profile.best_position ?? "-"}</strong></div>
            </div>

            <div class="profile-dashboard-grid">
                <section class="profile-panel profile-results-panel">
                    <div class="profile-panel-head">
                        <div><span>Evolucion</span><h3>Jornada a jornada</h3></div>
                        <small>Aciertos · puesto · diferencia con La Pe&ntilde;a</small>
                    </div>
                    <div class="profile-result-head"><span>Jornada</span><span>Aciertos</span><span>Puesto</span><span>Vs Pena</span><span>Rendimiento</span></div>
                    <div class="profile-results-list">${resultRows}</div>
                </section>

                <aside class="profile-side-column">
                    <section class="profile-panel profile-comparison-panel">
                        <div class="profile-panel-head"><div><span>Tu nivel</span><h3>Frente a La Pe&ntilde;a</h3></div></div>
                        <div class="profile-comparison-value ${profileTone(comparison)}">${comparisonText}<small> puntos</small></div>
                        <p>Media de la Pe&ntilde;a: <b>${vsPena.average_points ?? 0}</b>. Vas por delante de <b>${vsPena.ahead_of ?? 0}</b> rivales.</p>
                        <div class="profile-mini-stats">
                            <div><span>Racha 8+</span><b>${streak.current ?? 0}</b></div>
                            <div><span>Mejor racha</span><b>${streak.best ?? 0}</b></div>
                            <div><span>Mejorando</span><b>${streak.improving ?? 0}</b></div>
                        </div>
                    </section>
                    <section class="profile-panel">
                        <div class="profile-panel-head"><div><span>Ultimas 5</span><h3>Rivales directos</h3></div><small>G-E-P</small></div>
                        <div class="profile-rivals-list">${rivalryRows}</div>
                    </section>
                    <section class="profile-panel">
                        <div class="profile-panel-head"><div><span>Palmares</span><h3>Tus jornadas</h3></div></div>
                        <div class="profile-awards-list">${awardRows}</div>
                    </section>
                </aside>
            </div>
        </section>`;
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
        return renderProfileDashboard(profile);
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
        const selectedJornada = String(state.selectedAwardJornada || jornadaItems[0]?.jornada || "");
        const selectedMonth = String(state.selectedAwardMonth || monthItems[0]?.month || "");
        const jornadaPick = jornadaItems.find(item => String(item.jornada) === selectedJornada) || jornadaItems[0];
        const monthPick = monthItems.find(item => String(item.month) === selectedMonth) || monthItems[0];

        const renderAwardChip = (item, idx, type = "jornada") => {
            const tier = awardTierClass(idx);
            const medalClass = tier ? tier : "neutral";
            return `
                <div class="award-chip ${tier}">
                    <span class="award-medal ${medalClass}">${idx + 1}</span>
                    <div>
                        <strong>${type === "mes" ? escapeHtml(item.month) : `J${escapeHtml(item.jornada)}`}</strong>
                        <small>${type === "mes" ? "mes" : escapeHtml(item.date || "jornada")}</small>
                    </div>
                    <b>${escapeHtml(item.winner)}</b>
                    <em>${item.points} pts</em>
                </div>`;
        };

        const renderHistoryRow = (item, idx, type = "jornada") => {
            const rankClass = idx < 3 ? `rank-${idx + 1}` : "";
            return `
                <div class="award-history-row ${rankClass}">
                    <span>${idx + 1}</span>
                    <strong>${type === "mes" ? escapeHtml(item.month) : `J${escapeHtml(item.jornada)}`}</strong>
                    <b>${escapeHtml(item.winner)}</b>
                    <em>${item.points} pts</em>
                </div>`;
        };

        const recentJornadas = jornadaItems.slice(0, 5).map((item, idx) => renderAwardChip(item, idx)).join("") || `<div class="empty-state">Sin ganadores de jornada.</div>`;
        const recentMonths = monthItems.slice(0, 5).map((item, idx) => renderAwardChip(item, idx, "mes")).join("") || `<div class="empty-state">Sin ganadores mensuales.</div>`;
        const jornadaHistory = jornadaItems.slice(0, 14).map((item, idx) => renderHistoryRow(item, idx)).join("") || `<div class="empty-state">Sin histórico de jornadas.</div>`;
        const monthHistory = monthItems.slice(0, 10).map((item, idx) => renderHistoryRow(item, idx, "mes")).join("") || `<div class="empty-state">Sin histórico mensual.</div>`;
        const jornadaOptions = jornadaItems.map(item => `<option value="${escapeHtml(item.jornada)}" ${String(item.jornada) === selectedJornada ? "selected" : ""}>Jornada ${escapeHtml(item.jornada)}</option>`).join("");
        const monthOptions = monthItems.map(item => `<option value="${escapeHtml(item.month)}" ${String(item.month) === selectedMonth ? "selected" : ""}>${escapeHtml(item.month)}</option>`).join("");

        return `
            <section class="contest-page awards-page">
                <div class="contest-card awards-head">
                    <div class="awards-head-left">
                        <div class="awards-trophy-container">
                            <svg class="awards-trophy-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                                <path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6"></path>
                                <path d="M18 9h1.5a2.5 2.5 0 0 0 0-5H18"></path>
                                <path d="M4 22h16"></path>
                                <path d="M10 14.66V17c0 .55-.45 1-1 1H4v2h16v-2h-5c-.55 0-1-.45-1-1v-2.34"></path>
                                <path d="M12 2a5 5 0 0 0-5 5v3.5c0 1.5 1.4 3.5 3.5 4.3a4.5 4.5 0 0 0 3 0c2.1-.8 3.5-2.8 3.5-4.3V7a5 5 0 0 0-5-5z"></path>
                            </svg>
                        </div>
                        <div>
                            <span>Galardones</span>
                            <strong>Campeones de la Peña</strong>
                            <p>Ganadores por jornada y por mes, con consulta rápida del histórico.</p>
                        </div>
                    </div>
                    <div class="awards-totals">
                        <div>
                            <b>${jornadaItems.length}</b>
                            <small>jornadas</small>
                        </div>
                        <div>
                            <b>${monthItems.length}</b>
                            <small>meses</small>
                        </div>
                    </div>
                </div>
                <div class="awards-grid">
                <div class="contest-card awards-card">
                    <div class="contest-title"><span>Últimos campeones</span><small>jornada</small></div>
                    <div class="award-strip">${recentJornadas}</div>
                    <div class="award-picker">
                        <label>Consultar jornada</label>
                        <select data-award-jornada>${jornadaOptions}</select>
                    </div>
                    ${jornadaPick ? `
                        <div class="award-feature">
                            <div class="award-feature-header">
                                <span class="award-feature-badge">🏆 CAMPEÓN J${jornadaPick.jornada}</span>
                                <span class="award-feature-title">Destacado</span>
                            </div>
                            <div class="award-feature-main">
                                <div class="award-feature-trophy">
                                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                                        <path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6"></path>
                                        <path d="M18 9h1.5a2.5 2.5 0 0 0 0-5H18"></path>
                                        <path d="M4 22h16"></path>
                                        <path d="M10 14.66V17c0 .55-.45 1-1 1H4v2h16v-2h-5c-.55 0-1-.45-1-1v-2.34"></path>
                                        <path d="M12 2a5 5 0 0 0-5 5v3.5c0 1.5 1.4 3.5 3.5 4.3a4.5 4.5 0 0 0 3 0c2.1-.8 3.5-2.8 3.5-4.3V7a5 5 0 0 0-5-5z"></path>
                                    </svg>
                                </div>
                                <div class="award-feature-info">
                                    <span>Soberano de la Jornada</span>
                                    <strong>${escapeHtml(jornadaPick.winner)}</strong>
                                </div>
                                <div class="award-feature-score">
                                    ${jornadaPick.points} <small style="font-size: 0.65em; font-weight: 800;">pts</small>
                                </div>
                            </div>
                        </div>
                    ` : ""}
                </div>
                <div class="contest-card awards-card">
                    <div class="contest-title"><span>Reyes del mes</span><small>últimos 3</small></div>
                    <div class="award-strip">${recentMonths}</div>
                    <div class="award-picker">
                        <label>Consultar mes</label>
                        <select data-award-month>${monthOptions}</select>
                    </div>
                    ${monthPick ? `
                        <div class="award-feature">
                            <div class="award-feature-header">
                                <span class="award-feature-badge" style="background: rgba(167, 139, 250, 0.15); color: #c084fc; border-color: rgba(167, 139, 250, 0.25);">👑 REY DEL MES</span>
                                <span class="award-feature-title">${escapeHtml(monthPick.month)}</span>
                            </div>
                            <div class="award-feature-main">
                                <div class="award-feature-trophy" style="background: linear-gradient(135deg, #a78bfa, #7c3aed); border-color: #ddd6fe; box-shadow: 0 4px 10px rgba(124, 58, 237, 0.2);">
                                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                                        <path d="M2 4l3 12h14l3-12-6 7-4-7-4 7-6-7z"></path>
                                        <path d="M5 20h14a1 1 0 0 0 1-1v-1H4v1a1 1 0 0 0 1 1z"></path>
                                    </svg>
                                </div>
                                <div class="award-feature-info">
                                    <span>Líder de la Peña</span>
                                    <strong>${escapeHtml(monthPick.winner)}</strong>
                                </div>
                                <div class="award-feature-score" style="background: linear-gradient(135deg, #ddd6fe, #7c3aed); color: #fff; border-color: #ddd6fe; box-shadow: 0 4px 12px rgba(124, 58, 237, 0.15);">
                                    ${monthPick.points} <small style="font-size: 0.65em; font-weight: 800;">pts</small>
                                </div>
                            </div>
                        </div>
                    ` : ""}
                </div>
                <div class="contest-card awards-history-card">
                    <div class="contest-title"><span>Histórico</span><small>consulta rápida</small></div>
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
