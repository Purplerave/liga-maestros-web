/* ==========================================================================
   STANDINGS — Clasificaciones completa y lateral, live results, form dots.
   Dependencias: utils.js, logos.js, state.js
   ========================================================================== */


function renderLiveStandings() {
    const multi = state.data.multi_league_standings;
    const leagues = multi?.leagues || [];

    if (leagues.length === 0 && state.data.standings) {
        const liveResults = getLiveStandingsResults();
        drawStandings(state.data.standings.primera || [], "standings-1-body", liveResults, "primera");
        drawStandings(state.data.standings.segunda || [], "standings-2-body", liveResults, "segunda");
        return;
    }

    const primera = leagues.find(l => /la liga/i.test(l.name));
    const segunda = leagues.find(l => /segunda/i.test(l.name));

    if (primera) {
        const container = qs("standings-1-body");
        if (container) {
            container.innerHTML = `<div class="side-standings-list">
                ${primera.teams.slice(0, 10).map((team, idx) => `
                    <div class="side-standing-row zone-${standingsZone(idx, primera.teams.length)}" title="PJ ${team.pj} - G ${team.pg} / E ${team.pe} / P ${team.pp} - GF ${team.gf} / GC ${team.gc} - Dif ${team.dg}">
                        <span class="side-standing-pos">${idx + 1}</span>
                        <span class="side-standing-team">${logoBadge(team.n, findTeamLogo(team.n))}<span class="side-standing-name">${escapeHtml(getShortName(team.n))}</span></span>
                        <span class="side-standing-meta">${team.streak || `PJ ${team.pj}`}</span>
                        <strong class="side-standing-pts">${team.pts}</strong>
                    </div>`).join("")}
            </div>`;
        }
    }

    if (segunda) {
        const container = qs("standings-2-body");
        if (container) {
            container.innerHTML = `<div class="side-standings-list">
                ${segunda.teams.slice(0, 10).map((team, idx) => `
                    <div class="side-standing-row zone-${standingsZone(idx, segunda.teams.length, "segunda")}" title="PJ ${team.pj} - G ${team.pg} / E ${team.pe} / P ${team.pp} - GF ${team.gf} / GC ${team.gc} - Dif ${team.dg}">
                        <span class="side-standing-pos">${idx + 1}</span>
                        <span class="side-standing-team">${logoBadge(team.n, findTeamLogo(team.n))}<span class="side-standing-name">${escapeHtml(getShortName(team.n))}</span></span>
                        <span class="side-standing-meta">${team.streak || `PJ ${team.pj}`}</span>
                        <strong class="side-standing-pts">${team.pts}</strong>
                    </div>`).join("")}
            </div>`;
        }
    }
}

function getLiveStandingsResults() {
    const liveResults = {};
    const allMatches = [...(state.data.partidos || [])];
    (state.data.all_league_matches || []).forEach(m => {
        const home = m.home_name || m.home?.name || m.local;
        const away = m.visitante || m.away_name || m.away?.name;
        const league = competitionLabel(m);
        if (!["LA LIGA", "SEGUNDA DIVISION"].includes(league)) return;
        const score = scoreOnly(m.score || m.scores.score || m.marcador);
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

function drawStandingsLegacyTable(teams, containerId, liveResults) {
    const container = qs(containerId);
    if (!container) return;
    const rows = buildLiveStandingsRows(teams, liveResults);
    container.innerHTML = `
        <table class="cls-table">
            <thead><tr><th style="text-align:center;">#</th><th style="text-align:left;">Equipo</th><th style="text-align:center;" title="Partidos jugados">PJ</th><th style="text-align:center;">Jor</th><th style="text-align:center;">Pts</th></tr></thead>
            <tbody>${rows.map((team, idx) => `
                <tr class="zone-${idx < 4 ? "champions" : idx < 6 ? "europe" : idx >= rows.length - 3 ? "danger" : "mid"}" title="G ${team.pgLive} / E ${team.peLive} / P ${team.ppLive} Â· GF ${team.gfLive} / GC ${team.gcLive} Â· Dif ${team.diffLive}">
                    <td class="cls-pos" style="text-align:center;">${idx + 1}</td>
                    <td class="cls-team"><span class="cls-team-main">${logoBadge(team.n, findTeamLogo(team.n))}<span>${escapeHtml(getShortName(team.n))}</span></span></td>
                    <td class="cls-pj" style="text-align:center;">${team.pjLive}</td>
                    <td class="cls-jor" style="text-align:center;">${team.live ? `<span class="cls-live-badge ${liveResultClass(team.live)}">${team.live.tag}</span>` : ""}</td>
                    <td class="cls-pts" style="text-align:center;">${team.ptsLive}</td>
                </tr>`).join("")}</tbody>
        </table>`;
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

function drawStandings(teams, containerId, liveResults, league = "primera") {
    const container = qs(containerId);
    if (!container) return;
    const rows = buildLiveStandingsRows(teams, liveResults);
    container.innerHTML = `
        <div class="side-standings-list">
            ${rows.map((team, idx) => `
                <div class="side-standing-row zone-${standingsZone(idx, rows.length, league)}" title="PJ ${team.pjLive} - G ${team.pgLive} / E ${team.peLive} / P ${team.ppLive} - GF ${team.gfLive} / GC ${team.gcLive} - Dif ${team.diffLive}">
                    <span class="side-standing-pos">${idx + 1}</span>
                    <span class="side-standing-team">${logoBadge(team.n, findTeamLogo(team.n))}<span class="side-standing-name">${escapeHtml(getShortName(team.n))}</span></span>
                    <span class="side-standing-meta">${team.live ? `<span class="cls-live-badge ${liveResultClass(team.live)}">${team.live.tag}</span>` : `PJ ${team.pjLive}`}</span>
                    <strong class="side-standing-pts">${team.ptsLive}</strong>
                </div>`).join("")}
        </div>`;
}

function buildLiveStandingsRows(teams, liveResults) {
    return teams.map(team => {
        const live = liveResults[normalizeName(team.n)];
        const pg = Number(team.pg ?? 0);
        const pe = Number(team.pe ?? 0);
        const pp = Number(team.pp ?? 0);
        const gf = Number(team.gf ?? 0);
        const gc = Number(team.gc ?? 0);
        const liveWin = live?.pts === 3 ? 1 : 0;
        const liveDraw = live?.pts === 1 ? 1 : 0;
        const liveLoss = live && live.pts === 0 ? 1 : 0;
        return {
            ...team,
            live,
            pjLive: Number(team.pj || 0) + (live ? 1 : 0),
            pgLive: pg + liveWin,
            peLive: pe + liveDraw,
            ppLive: pp + liveLoss,
            gfLive: gf + (live?.gf || 0),
            gcLive: gc + (live?.gc || 0),
            ptsLive: Number(team.pts || 0) + (live?.pts || 0)
        };
    }).map(team => ({ ...team, diffLive: team.gfLive - team.gcLive }))
      .sort((a, b) => b.ptsLive - a.ptsLive || b.diffLive - a.diffLive || b.gfLive - a.gfLive || (a.pos || 99) - (b.pos || 99));
}

function liveResultClass(live) {
    return live.pts === 3 ? "cls-win" : live.pts === 1 ? "cls-draw" : "cls-loss";
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
                    <th>Racha</th>
                    <th>Ultimos 5</th>
                </tr>
            </thead>
            <tbody>${rows.map((team, idx) => {
                const formArr = team.form || [];
                return `
                    <tr class="zone-${standingsZone(idx, rows.length)}">
                        <td class="full-pos">${idx + 1}</td>
                        <td class="full-club">${logoBadge(team.n, findTeamLogo(team.n))}<span>${escapeHtml(team.n)}</span></td>
                        <td>${team.pj}</td>
                        <td>${team.pg}</td>
                        <td>${team.pe}</td>
                        <td>${team.pp}</td>
                        <td>${team.gf}</td>
                        <td>${team.gc}</td>
                        <td>${team.dg}</td>
                        <td class="full-points">${team.pts}</td>
                        <td>${escapeHtml(team.streak || "")}</td>
                        <td class="form-cell">${formArr.map(f => {
                            const cls = f === "W" ? "form-win" : f === "D" ? "form-draw" : "form-loss";
                            return `<span class="form-dot ${cls}">${f}</span>`;
                        }).join("")}</td>
                    </tr>`;
            }).join("")}</tbody>
        </table>`;
}

function renderFullStandingsTable(teams, liveResults, league = "primera") {
    const rows = buildLiveStandingsRows(teams, liveResults);
    return `
        <table class="full-standings-table">
            <thead>
                <tr>
                    <th style="text-align:center;">#</th>
                    <th>Club</th>
                    <th>PJ</th>
                    <th>Jor</th>
                    <th>G</th>
                    <th>E</th>
                    <th>P</th>
                    <th>GF</th>
                    <th>GC</th>
                    <th>DG</th>
                    <th>Pts</th>
                    <th>Ultimos 5</th>
                </tr>
            </thead>
            <tbody>${rows.map((team, idx) => {
                const form = String(team.racha || "").trim();
                return `
                    <tr class="zone-${standingsZone(idx, rows.length, league)}">
                        <td class="full-pos">${idx + 1}</td>
                        <td class="full-club">${logoBadge(team.n, findTeamLogo(team.n))}<span>${escapeHtml(team.n)}</span></td>
                        <td>${team.pjLive}</td>
                        <td>${team.live ? `<span class="cls-live-badge ${liveResultClass(team.live)}">${team.live.tag}</span>` : ""}</td>
                        <td>${team.pgLive}</td>
                        <td>${team.peLive}</td>
                        <td>${team.ppLive}</td>
                        <td>${team.gfLive}</td>
                        <td>${team.gcLive}</td>
                        <td>${team.diffLive}</td>
                        <td class="full-points">${team.ptsLive}</td>
                        <td class="form-cell">${renderFormDots(form)}</td>
                    </tr>`;
            }).join("")}</tbody>
        </table>`;
}

function renderFormDots(form) {
    if (!form) return `<span class="form-muted">-</span>`;
    return form.split("").slice(-5).map(ch => {
        const value = ch.toUpperCase();
        const cls = value === "G" || value === "W" ? "form-win" : value === "E" || value === "D" ? "form-draw" : "form-loss";
        return `<span class="form-dot ${cls}">${escapeHtml(value === "W" ? "G" : value === "D" ? "E" : value)}</span>`;
    }).join("");
}
