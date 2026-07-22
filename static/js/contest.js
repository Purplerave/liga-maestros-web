/* ==========================================================================
   CONTEST — La Peña: perfil, ranking, podio, galardones, radar de sorpresas.
   Dependencias: utils.js, logos.js, state.js, ticket_page.js
   ========================================================================== */

function formatMonthES(month) {
    if (!month || typeof month !== "string") return month || "-";
    const parts = month.split("-");
    if (parts.length === 2) {
        return `${parts[1]}-${parts[0]}`;
    }
    return month;
}

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

function renderContestRows(rows = [], limit = 5, options = {}) {
    const { showTop = true, highlightUser = true, showMedals = true } = options;
    const limited = rows.slice(0, limit);
    if (!limited.length) return `<div class="empty-state">Sin datos cerrados todavÃ­a.</div>`;

    const userRow = highlightUser ? rows.find(r => r.is_user) : null;
    const userPos = userRow ? userRow.pos : null;

    return limited.map((item, idx) => {
        const medal = showMedals && idx === 0 ? "🥇" : showMedals && idx === 1 ? "🥈" : showMedals && idx === 2 ? "🥉" : "";
        const isUser = item.is_user;
        const isNearUser = userPos && Math.abs(item.pos - userPos) <= 2 && !isUser && item.pos !== userPos;
        const separator = userPos && item.pos === userPos - 1 && limited[idx + 1]?.pos === userPos;

        let html = `<div class="contest-row ${isUser ? "is-user" : ""} ${isNearUser ? "is-near-user" : ""}">`;
        if (medal) {
            html += `<span class="contest-medal">${medal}</span>`;
        } else {
            html += `<span class="contest-pos">${item.pos}</span>`;
        }
        html += `<span class="contest-name">${escapeHtml(item.name)}</span>`;
        html += `<span class="contest-hit-rate">${item.played ? Math.round((item.points / (item.played * 15)) * 100) : 0}%</span>`;
        html += `<span class="contest-points">${item.points} pts</span>`;
        html += `</div>`;

        if (separator) {
            html += `<div class="contest-separator"><span></span><small>TU POSICIÓN</small><span></span></div>`;
        }

        return html;
    }).join("");
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

    const generalRows = contest.general || [];
    const top10 = generalRows.slice(0, 10);
    const hasMore = generalRows.length > 10;

    container.innerHTML = `
        <div class="contest-compact">
            ${profileBlock ? `<div class="contest-compact-profile">${profileBlock}</div>` : ""}
            <div class="contest-compact-columns">
                <div class="contest-compact-left">
                    <div class="contest-compact-card contest-compact-general">
                        <div class="contest-compact-header">
                            <span class="contest-compact-title">🏆 General</span>
                            <span class="contest-compact-sub">temporada</span>
                        </div>
                        <div id="compact-general-top10">${renderContestRows(top10, 10, { showTop: true, highlightUser: true, showMedals: true })}</div>
                        ${hasMore ? `<button type="button" class="contest-expand-btn" onclick="document.getElementById('compact-general-full').classList.toggle('is-visible');this.textContent=this.textContent.includes('Ver todos')?'Ocultar ▴':'Ver todos ▾'">Ver todos ▾</button>
                        <div id="compact-general-full" class="contest-full-list">${renderContestRows(generalRows.slice(10), generalRows.length, { showMedals: false })}</div>` : ""}
                    </div>
                </div>
                <div class="contest-compact-right">
                    <div class="contest-compact-top">
                        <div class="contest-compact-card">
                            <div class="contest-compact-header">
                                <span class="contest-compact-title">⚡ J${contest.jornada?.jornada || ""}</span>
                                <span class="contest-compact-sub">jornada</span>
                            </div>
                            ${renderContestRows(contest.jornada?.rows || [], 6, { showMedals: true })}
                        </div>
                        <div class="contest-compact-card">
                            <div class="contest-compact-header">
                                <span class="contest-compact-title">📅 ${escapeHtml(formatMonthES(contest.monthly?.month))}</span>
                                <span class="contest-compact-sub">mensual</span>
                            </div>
                            ${renderContestRows(contest.monthly?.rows || [], 6, { showMedals: true })}
                        </div>
                    </div>
                    <div class="contest-compact-card">
                        <div class="contest-compact-header">
                            <span class="contest-compact-title">🎖️ Galardones</span>
                        <span class="contest-compact-sub">últimos</span>
                    </div>
                    ${(contest.galardones?.jornadas || []).slice(0, 5).map(item => `
                        <div class="contest-compact-award">
                            <span class="contest-compact-award-j">J${item.jornada}</span>
                            <span class="contest-compact-award-name">${escapeHtml(item.winner)}</span>
                            <span class="contest-compact-award-pts">${item.points} pts</span>
                        </div>`).join("") || `<div class="empty-state">Sin galardones.</div>`}
                </div>
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
        const generalRows = contest.general || [];
        const top10 = generalRows.slice(0, 10);
        const hasMore = generalRows.length > 10;
        return `
        <div class="contest-compact">
            <div class="contest-compact-columns">
                <div class="contest-compact-left">
                    <div class="contest-compact-card contest-compact-general">
                        <div class="contest-compact-header">
                            <span class="contest-compact-title">🏆 General</span>
                            <span class="contest-compact-sub">temporada</span>
                        </div>
                        <div id="compact-general-top10">${renderContestRows(top10, 10, { showTop: true, highlightUser: true, showMedals: true })}</div>
                        ${hasMore ? `<button type="button" class="contest-expand-btn" onclick="document.getElementById('compact-general-full').classList.toggle('is-visible');this.textContent=this.textContent.includes('Ver todos')?'Ocultar ▴':'Ver todos ▾'">Ver todos ▾</button>
                        <div id="compact-general-full" class="contest-full-list">${renderContestRows(generalRows.slice(10), generalRows.length, { showMedals: false })}</div>` : ""}
                    </div>
                </div>
                <div class="contest-compact-right">
                    <div class="contest-compact-top">
                        <div class="contest-compact-card">
                            <div class="contest-compact-header">
                                <span class="contest-compact-title">⚡ J${contest.jornada?.jornada || ""}</span>
                                <span class="contest-compact-sub">jornada</span>
                            </div>
                            ${renderContestRows(contest.jornada?.rows || [], 6, { showMedals: true })}
                        </div>
                        <div class="contest-compact-card">
                            <div class="contest-compact-header">
                                <span class="contest-compact-title">📅 ${escapeHtml(formatMonthES(contest.monthly?.month))}</span>
                                <span class="contest-compact-sub">mensual</span>
                            </div>
                            ${renderContestRows(contest.monthly?.rows || [], 6, { showMedals: true })}
                        </div>
                    </div>
                    <div class="contest-compact-card">
                        <div class="contest-compact-header">
                            <span class="contest-compact-title">🎖️ Galardones</span>
                            <span class="contest-compact-sub">últimos</span>
                        </div>
                        ${(contest.galardones?.jornadas || []).slice(0, 5).map(item => `
                            <div class="contest-compact-award">
                                <span class="contest-compact-award-j">J${item.jornada}</span>
                                <span class="contest-compact-award-name">${escapeHtml(item.winner)}</span>
                                <span class="contest-compact-award-pts">${item.points} pts</span>
                            </div>`).join("") || `<div class="empty-state">Sin galardones.</div>`}
                    </div>
                </div>
            </div>
        </div>`;
    }

    if (view === "CONTEST_MONTHLY") {
        const monthlyMonths = contest.monthly?.months || [];
        const currentMonth = contest.monthly?.month || "";
        const monthSelector = monthlyMonths.length > 1 ? `
            <div class="contest-month-selector">
                ${monthlyMonths.map(m => `<button type="button" class="month-btn ${m === currentMonth ? "active" : ""}" data-month="${escapeHtml(m)}">${escapeHtml(formatMonthES(m))}</button>`).join("")}
            </div>` : "";
        return `<section class="contest-page single">
            <div class="contest-card">
                <div class="contest-title"><span>La Peña mensual</span><small>${escapeHtml(formatMonthES(currentMonth))}</small></div>
                ${monthSelector}
                <div id="monthly-rows">${renderContestRows(contest.monthly?.rows || [], 80, { showMedals: true })}</div>
            </div>
        </section>`;
    }

    if (view === "CONTEST_JORNADA") {
        return `<section class="contest-page single"><div class="contest-card"><div class="contest-title"><span>La Peña jornada ${contest.jornada?.jornada || ""}</span><small>jornada actual</small></div>${renderContestRows(contest.jornada?.rows || [], 80, { showMedals: true })}</div></section>`;
    }

    if (view === "CONTEST_HISTORY") {
        const historyMonths = contest.history?.months || [];
        const selectedHistoryMonth = state.selectedHistoryMonth || (historyMonths[0] || "");
        const historyRows = contest.history?.data?.[selectedHistoryMonth] || [];
        const monthSelector = historyMonths.length > 1 ? `
            <div class="contest-month-selector">
                ${historyMonths.map(m => `<button type="button" class="month-btn ${m === selectedHistoryMonth ? "active" : ""}" data-history-month="${escapeHtml(m)}">${escapeHtml(m)}</button>`).join("")}
            </div>` : "";
        return `<section class="contest-page single">
            <div class="contest-card">
                <div class="contest-title"><span>Histórico</span><small>${escapeHtml(selectedHistoryMonth || "todos los meses")}</small></div>
                ${monthSelector}
                <div id="history-rows">${renderContestRows(historyRows, 80, { showMedals: true })}</div>
            </div>
        </section>`;
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
                <div><strong>${type === "mes" ? escapeHtml(formatMonthES(item.month)) : `J${escapeHtml(item.jornada)}`}</strong><small>${type === "mes" ? "mes" : escapeHtml(item.date || "jornada")}</small></div>
                <b>${escapeHtml(item.winner)}</b>
                <em>${item.points}</em>
            </div>`;
        const renderHistoryRow = (item, idx, type = "jornada") => `
            <div class="award-history-row">
                <span>${idx + 1}</span>
                <strong>${type === "mes" ? escapeHtml(formatMonthES(item.month)) : `J${escapeHtml(item.jornada)}`}</strong>
                <b>${escapeHtml(item.winner)}</b>
                <em>${item.points}</em>
            </div>`;
        const recentJornadas = jornadaItems.slice(0, 5).map((item, idx) => renderAwardChip(item, idx)).join("") || `<div class="empty-state">Sin ganadores de jornada.</div>`;
        const recentMonths = monthItems.slice(0, 5).map((item, idx) => renderAwardChip(item, idx, "mes")).join("") || `<div class="empty-state">Sin ganadores mensuales.</div>`;
        const jornadaHistory = jornadaItems.map((item, idx) => renderHistoryRow(item, idx)).join("") || `<div class="empty-state">Sin historico de jornadas.</div>`;
        const monthHistory = monthItems.map((item, idx) => renderHistoryRow(item, idx, "mes")).join("") || `<div class="empty-state">Sin historico mensual.</div>`;
        const jornadaOptions = jornadaItems.map(item => `<option value="${escapeHtml(item.jornada)}" ${String(item.jornada) === selectedJornada ? "selected" : ""}>Jornada ${escapeHtml(item.jornada)}</option>`).join("");
        const monthOptions = monthItems.map(item => `<option value="${escapeHtml(item.month)}" ${String(item.month) === selectedMonth ? "selected" : ""}>${escapeHtml(formatMonthES(item.month))}</option>`).join("");
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
                        <select data-award-jornada>${jornadaOptions}</select>
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
                        <select data-award-month>${monthOptions}</select>
                    </div>
                    ${monthPick ? `<div class="award-feature">
                        <span>${escapeHtml(formatMonthES(monthPick.month))}</span>
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

    const generalRows = contest.general || [];
    const top10 = generalRows.slice(0, 10);
    const hasMore = generalRows.length > 10;

    return `
        <div class="contest-compact">
            <div class="contest-compact-columns">
                <div class="contest-compact-left">
                    <div class="contest-compact-card contest-compact-general">
                        <div class="contest-compact-header">
                            <span class="contest-compact-title">🏆 General</span>
                            <span class="contest-compact-sub">temporada</span>
                        </div>
                        <div id="compact-general-top10">${renderContestRows(top10, 10, { showTop: true, highlightUser: true, showMedals: true })}</div>
                        ${hasMore ? `<button type="button" class="contest-expand-btn" onclick="document.getElementById('compact-general-full').classList.toggle('is-visible');this.textContent=this.textContent.includes('Ver todos')?'Ocultar ▴':'Ver todos ▾'">Ver todos ▾</button>
                        <div id="compact-general-full" class="contest-full-list">${renderContestRows(generalRows.slice(10), generalRows.length, { showMedals: false })}</div>` : ""}
                    </div>
                </div>
                <div class="contest-compact-right">
                    <div class="contest-compact-top">
                        <div class="contest-compact-card">
                            <div class="contest-compact-header">
                                <span class="contest-compact-title">⚡ J${contest.jornada?.jornada || ""}</span>
                                <span class="contest-compact-sub">jornada</span>
                            </div>
                            ${renderContestRows(contest.jornada?.rows || [], 6, { showMedals: true })}
                        </div>
                        <div class="contest-compact-card">
                            <div class="contest-compact-header">
                                <span class="contest-compact-title">📅 ${escapeHtml(formatMonthES(contest.monthly?.month))}</span>
                                <span class="contest-compact-sub">mensual</span>
                            </div>
                            ${renderContestRows(contest.monthly?.rows || [], 6, { showMedals: true })}
                        </div>
                    </div>
                    <div class="contest-compact-card">
                        <div class="contest-compact-header">
                            <span class="contest-compact-title">🎖️ Galardones</span>
                            <span class="contest-compact-sub">últimos</span>
                        </div>
                        ${(contest.galardones?.jornadas || []).slice(0, 5).map(item => `
                            <div class="contest-compact-award">
                                <span class="contest-compact-award-j">J${item.jornada}</span>
                                <span class="contest-compact-award-name">${escapeHtml(item.winner)}</span>
                                <span class="contest-compact-award-pts">${item.points} pts</span>
                            </div>`).join("") || `<div class="empty-state">Sin galardones.</div>`}
                    </div>
                </div>
            </div>
        </div>`;
}
