/* ==========================================================================
   CONTEST — La Peña: perfil, ranking, podio, galardones, radar de sorpresas.
   Dependencias: utils.js, logos.js, state.js, ticket_page.js
   ========================================================================== */

let contestRequest = null;

async function ensureContestData({ force = false } = {}) {
    if (!state.data) return null;
    const jornada = String(state.data.jornada || state.jornada || "");
    if (!force && state.contest && state.contestJornada === jornada) {
        return state.contest;
    }
    if (contestRequest) return contestRequest;

    contestRequest = fetch(`/api/concurso?j=${encodeURIComponent(jornada)}`, { cache: "no-store" })
        .then(response => {
            if (!response.ok) throw new Error("No se pudo cargar La Peña");
            return response.json();
        })
        .then(payload => {
            state.contest = payload;
            state.contestJornada = jornada;
            return payload;
        })
        .finally(() => {
            contestRequest = null;
        });
    return contestRequest;
}

function formatMonthES(month) {
    if (!month || typeof month !== "string") return month || "-";
    const parts = month.split("-");
    if (parts.length === 2) {
        return `${parts[1]}-${parts[0]}`;
    }
    return month;
}

function renderContestRows(rows = [], limit = 5, options = {}) {
    const { showTop = true, highlightUser = true, showMedals = true, compactWide = false } = options;
    const limited = rows.slice(0, limit);
    if (!limited.length) return `<div class="empty-state">Sin datos cerrados todavía.</div>`;

    const userRow = highlightUser ? rows.find(r => r.is_user) : null;
    const userPos = userRow ? userRow.pos : null;

    const rankingHead = compactWide
        ? `<div class="contest-ranking-head"><span>Puesto</span><span>Participante</span><span>Puntos</span></div>`
        : "";
    return `<div class="${compactWide ? "contest-ranking-table" : ""}">${rankingHead}<div class="contest-rows-grid ${compactWide ? "is-wide-compact" : ""}">${limited.map((item, idx) => {
        const rank = showMedals && idx < 3 ? ["1º", "2º", "3º"][idx] : item.pos;
        const isUser = item.is_user;
        const isNearUser = userPos && Math.abs(item.pos - userPos) <= 2 && !isUser && item.pos !== userPos;
        const separator = userPos && item.pos === userPos - 1 && limited[idx + 1]?.pos === userPos;

        let html = `<div class="contest-card-row ${isUser ? "is-user" : ""} ${isNearUser ? "is-near-user" : ""}">`;
        html += `<span class="ccr-rank">${rank}</span>`;
        html += `<span class="ccr-name">${escapeHtml(item.name)}</span>`;
        html += `<span class="ccr-pts">${item.points}</span>`;
        html += `</div>`;

        if (separator) {
            html += `<div class="contest-separator"><small>TU POSICION</small></div>`;
        }

        return html;
    }).join("")}</div></div>`;
}

function awardTierClass(idx) {
    if (idx === 0) return "gold";
    if (idx === 1) return "silver";
    if (idx === 2) return "bronze";
    return "";
}

let _seasonSummaryCache = null;
async function fetchSeasonSummaryForPena() {
    if (_seasonSummaryCache) return _seasonSummaryCache;
    try {
        const res = await fetch("/api/season-summary", { cache: "no-store" });
        if (!res.ok) throw new Error();
        _seasonSummaryCache = await res.json();
        return _seasonSummaryCache;
    } catch { return null; }
}
function hasSeasonStats(contest) {
    // Hay estadisticas en cuanto la temporada ha producido algo puntuable:
    // puntos en la general, filas de la jornada en curso o galardones.
    if (!contest) return false;
    const scored = rows => (rows || []).some(row => Number(row?.points || 0) > 0);
    if (scored(contest.general)) return true;
    if (scored(contest.jornada?.rows)) return true;
    if (scored(contest.monthly?.rows)) return true;
    if ((contest.galardones?.jornadas || []).length) return true;
    if ((contest.galardones?.meses || []).length) return true;
    return false;
}

function renderNewSeasonPenaPlaceholder() {
    // Podio de pruebas guardado en season_2025_2026_summary.json
    // Mientras no haya resultados de la nueva temporada, mostramos solo el podio + mensaje чulo
    const placeholder = `<section class="contest-page new-season-page">
        <div class="contest-card new-season-hero" style="text-align:center; padding:22px 18px; background: radial-gradient(600px 240px at 50% -20%, rgba(245,181,63,0.12), transparent 60%), linear-gradient(180deg, #0e1526 0%, #080e1c 100%); border:1px solid rgba(255,255,255,0.08);">
            <div style="display:inline-flex; align-items:center; gap:8px; padding:4px 10px; border:1px solid rgba(245,181,63,0.25); border-radius:999px; background:rgba(245,181,63,0.08); color:#f5b53f; font-size:0.62rem; font-weight:800; letter-spacing:0.06em; text-transform:uppercase;">🏁 Pruebas finalizadas — Temporada 2025/26</div>
            <h2 style="margin:10px 0 6px; font-family: Rajdhani, Outfit, sans-serif; font-size:1.55rem; font-weight:900; color:#fff; letter-spacing:0.02em;">Podio del calentamiento</h2>
            <p style="margin:0 auto; max-width:560px; color:#c8d4e8; font-size:0.78rem; line-height:1.5;">Estas fueron las pruebas. Los tres mejores del calentamiento ya tienen su sitio en la historia. <b style="color:#f5b53f;">Ahora todo vuelve a cero</b> y la nueva temporada arranca en breve.</p>
            <div id="pena-season-podium" style="margin-top:16px; display:grid; gap:8px; max-width:420px; margin-left:auto; margin-right:auto;"><div class="cp-porra-loading" style="height:56px; margin:0 auto;"></div></div>
            <div style="margin-top:14px; padding:10px 14px; border-radius:10px; background:rgba(56,217,255,0.06); border:1px solid rgba(56,217,255,0.12); color:#8ea2c0; font-size:0.74rem; line-height:1.45;">
                📊 Las estadísticas se irán actualizando <b style="color:#eef3fb;">jornada a jornada</b> en cuanto empiece la nueva temporada.<br>
                Mientras tanto, <a href="#" data-page-action="TICKET" style="color:#38d9ff; font-weight:800; text-decoration:none;">haz tu primera quiniela</a> y asegúrate un sitio en la salida.
            </div>
            <div style="margin-top:14px; display:flex; gap:8px; justify-content:center; flex-wrap:wrap;">
                <button type="button" class="cp-primary" data-page-action="TICKET" style="min-height:32px; padding:0 18px; border-radius:999px; border:1px solid rgba(245,181,63,0.9); background:#f5b53f; color:#111827; font-weight:800; cursor:pointer;">Jugar la Quiniela J1</button>
                <button type="button" class="cp-secondary" onclick="window.location.href='/login/google'" style="min-height:32px; padding:0 18px; border-radius:999px; border:1px solid rgba(255,255,255,0.18); background:rgba(255,255,255,0.06); color:#e6eaf0; font-weight:700; cursor:pointer;">Entrar con Google</button>
            </div>
            <small style="display:block; margin-top:10px; color:#6b7a93; font-size:0.62rem;">¿Aún no estás registrado? Entra y deja tu quiniela lista antes del pitido inicial. La Peña te está esperando.</small>
        </div>
    </section>`;
    // Carga asíncrona del podio real
    setTimeout(async () => {
        const target = document.getElementById("pena-season-podium");
        if (!target) return;
        const summary = await fetchSeasonSummaryForPena();
        const top3 = summary?.top_3 || [];
        if (!top3.length) {
            target.innerHTML = `<div class="empty-state">Pronto verás aquí el podio de la nueva temporada.</div>`;
            return;
        }
        const medals = ["🥇","🥈","🥉"];
        target.innerHTML = top3.map((p,i) => `
            <div style="display:flex; align-items:center; gap:10px; padding:8px 10px; border-radius:10px; border:1px solid rgba(255,255,255,0.06); background:${i===0?'rgba(245,181,63,0.10)':'rgba(255,255,255,0.04)'};">
                <span style="font-size:1.1rem; width:28px; text-align:center;">${medals[i]||(i+1)}</span>
                <span style="flex:1; text-align:left; color:#eef3fb; font-weight:700; font-size:0.84rem;">${escapeHtml(p.name)}</span>
                <span style="color:#f5b53f; font-weight:900; font-family:Rajdhani, sans-serif;">${p.points} pts</span>
            </div>
        `).join("") + `<small style="color:#6b7a93; font-size:0.62rem; margin-top:4px; display:block;">${summary.total_participants||0} participantes · ${summary.total_jornadas||0} jornadas de pruebas</small>`;
    }, 50);
    return placeholder;
}

function renderContestOverview(contest) {
    const generalRows = contest.general || [];
    // El podio de pruebas solo se muestra mientras NO haya ni un punto de la
    // temporada nueva. En cuanto hay resultados, mandan las estadisticas reales.
    if (!hasSeasonStats(contest)) {
        return renderNewSeasonPenaPlaceholder();
    }
    const top10 = generalRows.slice(0, 10);
    const hasMore = generalRows.length > 10;
    const recentAwards = (contest.galardones?.jornadas || []).slice(0, 5);

    return `
        <div class="contest-compact">
            <div class="contest-compact-columns">
                <div class="contest-compact-left">
                    <div class="contest-compact-card contest-compact-general">
                        <div class="contest-compact-header">
                            <span class="contest-compact-title">General</span>
                            <span class="contest-compact-sub">temporada</span>
                        </div>
                        <div id="compact-general-top10">${renderContestRows(top10, 10, { showTop: true, highlightUser: true, showMedals: true })}</div>
                        ${hasMore ? `
                            <button type="button" class="contest-expand-btn" data-contest-expand="compact-general-full" aria-expanded="false">Ver todos</button>
                            <div id="compact-general-full" class="contest-full-list">${renderContestRows(generalRows.slice(10), generalRows.length, { showMedals: false })}</div>
                        ` : ""}
                    </div>
                </div>
                <div class="contest-compact-right">
                    <div class="contest-compact-top">
                        <div class="contest-compact-card">
                            <div class="contest-compact-header">
                                <span class="contest-compact-title">J${contest.jornada?.jornada || ""}</span>
                                <span class="contest-compact-sub">jornada</span>
                            </div>
                            ${renderContestRows(contest.jornada?.rows || [], 6, { showMedals: true })}
                        </div>
                        <div class="contest-compact-card">
                            <div class="contest-compact-header">
                                <span class="contest-compact-title">${escapeHtml(formatMonthES(contest.monthly?.month))}</span>
                                <span class="contest-compact-sub">mensual</span>
                            </div>
                            ${renderContestRows(contest.monthly?.rows || [], 6, { showMedals: true })}
                        </div>
                    </div>
                    <div class="contest-compact-card">
                        <div class="contest-compact-header">
                            <span class="contest-compact-title">Galardones</span>
                            <span class="contest-compact-sub">ultimos</span>
                        </div>
                        ${recentAwards.map(item => `
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
        const diffLabel = diff > 0 ? `+${diff} sobre media` : diff < 0 ? `${diff} bajo media` : "en la media";
        return `
            <div class="profile-result-row">
                <strong>J${escapeHtml(item.jornada)}</strong>
                <span class="profile-result-score">${points}<small> aciertos</small></span>
                <span class="profile-result-position">#${escapeHtml(item.pos || "-")}</span>
                <span class="profile-result-diff ${profileTone(diff)}" title="${escapeHtml(diffLabel)}">${diff > 0 ? "+" : ""}${diff}</span>
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
                        <small>Aciertos · puesto · diferencia con la media de La Pe&ntilde;a</small>
                    </div>
                    <div class="profile-result-head"><span>Jornada</span><span>Aciertos</span><span>Puesto</span><span title="Diferencia entre tus aciertos y la media de La Pena">Dif. Media</span><span>Rendimiento</span></div>
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

function renderContestPage(view = "CONTEST_GENERAL") {
    const tabs = [
        ["CONTEST_GENERAL", "General"],
        ["CONTEST_JORNADA", "Jornada"],
        ["CONTEST_MONTHLY", "Mensual"],
        ["CONTEST_AWARDS", "Galardones"],
        ["CONTEST_PROFILE", "Mi perfil"]
    ];
    return `
        <section class="contest-section">
            <nav class="contest-view-tabs" aria-label="Secciones de La Peña">
                ${tabs.map(([value, label]) => `
                    <button type="button" class="${view === value ? "active" : ""}" data-contest-view="${value}">
                        ${label}
                    </button>`).join("")}
            </nav>
            <div class="contest-view">${renderContestPageContent(view)}</div>
        </section>`;
}

function renderContestPageContent(view = "CONTEST_GENERAL") {
    const contest = state.contest;
    if (!contest) return `<div class="empty-state">No se pudo cargar La Peña.</div>`;
    // Solo se oculta la seccion mientras la temporada no ha dado ni un punto.
    if (!hasSeasonStats(contest) && view !== "CONTEST_PROFILE") {
        return renderNewSeasonPenaPlaceholder();
    }
    const profile = contest.profile;

    if (view === "CONTEST_PROFILE") {
        if (!profile) {
            return `<section class="contest-page single"><div class="contest-card"><div class="contest-title"><span>Perfil</span><small>sesion</small></div><div class="empty-state">Entra con Google para ver tus estadisticas personales.</div></div></section>`;
        }
        return renderProfileDashboard(profile);
    }

    if (view === "CONTEST_GENERAL") return renderContestOverview(contest);

    if (view === "CONTEST_MONTHLY") {
        const monthlyMonths = contest.monthly?.months || [];
        const defaultMonth = contest.monthly?.month || "";
        const selectedMonth = monthlyMonths.includes(state.selectedContestMonth)
            ? state.selectedContestMonth
            : defaultMonth;
        const monthRows = contest.monthly?.data?.[selectedMonth] || contest.monthly?.rows || [];
        const monthSelector = monthlyMonths.length > 1 ? `
            <div class="contest-month-selector" role="tablist" aria-label="Seleccionar mes">
                ${monthlyMonths.map(m => `<button type="button" role="tab" aria-selected="${m === selectedMonth}" class="month-btn ${m === selectedMonth ? "active" : ""}" data-month="${escapeHtml(m)}">${escapeHtml(formatMonthES(m))}</button>`).join("")}
            </div>` : "";
        const leader = monthRows[0];
        return `<section class="contest-page single">
            <div class="contest-card contest-month-hero">
                <div class="contest-title"><span>La Peña mensual</span><small>${escapeHtml(formatMonthES(selectedMonth))}</small></div>
                ${leader ? `<div class="contest-month-leader"><span class="cml-label">Líder del mes</span><strong>${escapeHtml(leader.name)}</strong><b>${leader.points} pts</b></div>` : ""}
                ${monthSelector}
                <div id="monthly-rows">${renderContestRows(monthRows, 80, { showMedals: true, compactWide: true })}</div>
            </div>
        </section>`;
    }

    if (view === "CONTEST_JORNADA") {
        const jornadaList = (contest.jornada?.jornadas || []).map(String);
        const defaultJornada = String(contest.jornada?.jornada || "");
        const selectedJornada = jornadaList.includes(String(state.selectedContestJornada))
            ? String(state.selectedContestJornada)
            : defaultJornada;
        const jornadaRows = contest.jornada?.data?.[selectedJornada] || contest.jornada?.rows || [];
        const jornadaSelector = jornadaList.length > 1 ? `
            <div class="contest-month-selector contest-jornada-selector" role="tablist" aria-label="Seleccionar jornada">
                ${jornadaList.map(j => `<button type="button" role="tab" aria-selected="${j === selectedJornada}" class="month-btn ${j === selectedJornada ? "active" : ""}" data-contest-jornada="${escapeHtml(j)}">J${escapeHtml(j)}</button>`).join("")}
            </div>` : "";
        const isCurrent = selectedJornada === defaultJornada;
        const leader = jornadaRows[0];
        const hasClosedResult = Number(leader?.points || 0) > 0;
        return `<section class="contest-page single">
            <div class="contest-card contest-month-hero">
                <div class="contest-title"><span>La Peña · Jornada ${escapeHtml(selectedJornada)}</span><small>${isCurrent ? "actual" : "histórico"}</small></div>
                ${hasClosedResult ? `<div class="contest-month-leader"><span class="cml-label">${isCurrent ? "L&iacute;der provisional" : "Ganador de la jornada"}</span><strong>${escapeHtml(leader.name)}</strong><b>${leader.points} pts</b></div>` : `<div class="contest-pending-note">La clasificaci&oacute;n se activar&aacute; con el primer resultado cerrado.</div>`}
                ${jornadaSelector}
                ${renderContestRows(jornadaRows, 80, { showMedals: true, compactWide: true })}
            </div>
        </section>`;
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
        const selectedJornada = String(state.selectedAwardJornada || jornadaItems[0]?.jornada || "");
        const selectedMonth = String(state.selectedAwardMonth || monthItems[0]?.month || "");
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

    return renderContestOverview(contest);
}
