/* ==========================================================================
   STANDINGS — Clasificaciones completa y lateral, live results, form dots.
   Dependencias: utils.js, logos.js, state.js
   ========================================================================== */


function getLiveStandingsResults() {
    const liveResults = {};
    const allMatches = [...(state.data.partidos || [])];
    (state.data.all_league_matches || []).forEach(m => {
        const home = m.home_name || m.home?.name || m.local;
        const away = m.visitante || m.away_name || m.away?.name;
        const league = competitionLabel(m);
        if (!["LA LIGA", "SEGUNDA DIVISION"].includes(league)) return;
        const score = scoreOnly(m.score || m.scores?.score || m.marcador);
        if (home && away && score) allMatches.push({ local: home, visitante: away, marcador: score, status: isLiveMatch(m) ? "LIVE" : m.status });
    });
    allMatches.forEach(match => {
        if (!isLiveStatus(match.status)) return;
        const cleanScore = scoreOnly(match.marcador);
        if (!cleanScore) return;
        const [gl, gv] = cleanScore.split("-").map(n => Number.parseInt(n, 10));
        if (Number.isNaN(gl) || Number.isNaN(gv)) return;
        liveResults[normalizeName(match.local)] = { pts: gl > gv ? 3 : gl === gv ? 1 : 0, gf: gl, gc: gv, tag: `${gl}-${gv}`, status: match.status };
        liveResults[normalizeName(match.visitante)] = { pts: gv > gl ? 3 : gl === gv ? 1 : 0, gf: gv, gc: gl, tag: `${gv}-${gl}`, status: match.status };
    });
    return liveResults;
}

function standingsZone(idx, total, league = "primera") {
    if (league === "segunda") {
        if (idx < 2) return "direct";
        if (idx < 6) return "playoff";
        if (idx >= total - 4) return "danger";
        return "mid";
    }
    if (idx < 4) return "champions";
    if (idx < 6) return "europe";
    if (idx >= total - 3) return "danger";
    return "mid";
}

function renderFullStandingsPage() {
    const liveResults = getLiveStandingsResults();
    const multi = state.data.multi_league_standings;
    const leagues = multi?.leagues || [];

    if (leagues.length === 0) {
        return `<section class="full-standings-page"><div class="empty-state">No hay clasificaciones disponibles.</div></section>`;
    }

    const tabsHtml = leagues.map((league, i) => {
        const safeId = league.name.replace(/[^a-zA-Z0-9]/g, "_").toLowerCase();
        return `<button class="tab-btn ${i === 0 ? "active" : ""}" type="button" data-league-tab="${safeId}">${escapeHtml(league.name)}</button>`;
    }).join("");

    const panelsHtml = leagues.map((league, i) => {
        const safeId = league.name.replace(/[^a-zA-Z0-9]/g, "_").toLowerCase();
        return `<div id="league-standings-${safeId}" class="league-standings-pane ${i === 0 ? "active" : ""}">
            ${renderMultiLeagueTable(league, liveResults)}
        </div>`;
    }).join("");

    return `
        <section class="full-standings-page">
            <div class="full-standings-card">
                <div class="full-standings-head">
                    <div>
                        <span class="section-kicker">Clasificaciones</span>
                        <h2>Todas las ligas</h2>
                    </div>
                    <small>Calculada desde resultados · actualizacion automatica</small>
                </div>
                <div class="league-tabs">${tabsHtml}</div>
                ${panelsHtml}
            </div>
        </section>`;
}

function renderMultiLeagueTable(league, liveResults) {
    const rows = league.teams || [];
    if (rows.length === 0) return `<div class="empty-state">Sin datos para esta liga.</div>`;
    const showStreak = rows.some(team => String(team.streak || "").trim());
    const showForm = rows.some(team => Array.isArray(team.form) && team.form.length > 0);

    return `
        <table class="full-standings-table">
            <thead>
                <tr>
                    <th style="text-align:center;">#</th>
                    <th>Club</th>
                    <th>PJ</th>
                    <th>G</th>
                    <th>E</th>
                    <th>P</th>
                    <th>GF</th>
                    <th>GC</th>
                    <th>DG</th>
                    <th>Pts</th>
                    ${showStreak ? "<th>Racha</th>" : ""}
                    ${showForm ? "<th>Ultimos 5</th>" : ""}
                </tr>
            </thead>
            <tbody>${rows.map((team, idx) => {
                const formArr = team.form || [];
                return `
                    <tr class="zone-${standingsZone(idx, rows.length)}">
                        <td class="full-pos">${idx + 1}</td>
                        <td class="full-club">${logoBadge(team.n, team.logo || findTeamLogo(team.n))}<span>${escapeHtml(team.n)}</span></td>
                        <td>${team.pj}</td>
                        <td>${team.pg}</td>
                        <td>${team.pe}</td>
                        <td>${team.pp}</td>
                        <td>${team.gf}</td>
                        <td>${team.gc}</td>
                        <td>${team.dg}</td>
                        <td class="full-points">${team.pts}</td>
                        ${showStreak ? `<td>${escapeHtml(team.streak || "")}</td>` : ""}
                        ${showForm ? `<td class="form-cell">${formArr.map(f => {
                            const cls = f === "W" ? "form-win" : f === "D" ? "form-draw" : "form-loss";
                            return `<span class="form-dot ${cls}">${f}</span>`;
                        }).join("")}</td>` : ""}
                    </tr>`;
            }).join("")}</tbody>
        </table>`;
}
