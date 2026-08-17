/* ==========================================================================
   STANDINGS — Clasificaciones completa y lateral, live results, form dots.
   Dependencias: utils.js, logos.js, state.js
   ========================================================================== */


/* Resultados provisionales de los partidos que se estan jugando AHORA.
   Un partido acabado nunca puede llegar hasta aqui: en cuanto termina, sus
   puntos ya estan en la tabla y el marcador en vivo debe desaparecer. Por eso
   se usa `isMatchLiveNow` (que descarta finalizados, directos caducados y
   snapshots congelados) en lugar de mirar solo la etiqueta de estado. */
function getLiveStandingsResults() {
    const liveResults = {};
    const allMatches = (state.data.partidos || []).filter(isMatchLiveNow);
    (state.data.all_league_matches || []).forEach(m => {
        const home = m.home_name || m.home?.name || m.local;
        const away = m.visitante || m.away_name || m.away?.name;
        const league = competitionLabel(m);
        if (!["LA LIGA", "SEGUNDA DIVISION"].includes(league)) return;
        if (!isMatchLiveNow(m)) return;
        const score = scoreOnly(m.score || m.scores?.score || m.marcador);
        if (home && away && score) allMatches.push({ local: home, visitante: away, marcador: score, status: "LIVE" });
    });
    allMatches.forEach(match => {
        const cleanScore = scoreOnly(match.marcador || match.marcador_base || match.score);
        if (!cleanScore) return;
        const [gl, gv] = cleanScore.split("-").map(n => Number.parseInt(n, 10));
        if (Number.isNaN(gl) || Number.isNaN(gv)) return;
        liveResults[normalizeName(match.local)] = { pts: gl > gv ? 3 : gl === gv ? 1 : 0, gf: gl, gc: gv, tag: `${gl}-${gv}`, status: match.status };
        liveResults[normalizeName(match.visitante)] = { pts: gv > gl ? 3 : gl === gv ? 1 : 0, gf: gv, gc: gl, tag: `${gv}-${gl}`, status: match.status };
    });
    return liveResults;
}

/* Equipos cuyo partido de la jornada el navegador ya sabe que ha terminado.
   La tabla llega con `en_juego` calculado en el servidor y ese dato puede
   quedarse viejo (respuesta cacheada, colector caido). Si el propio cliente ve
   el partido finalizado, el distintivo de directo no se pinta. */
function getFinishedStandingsTeams() {
    const finished = new Set();
    const consider = match => {
        const home = match.local || match.home_name || match.home?.name;
        const away = match.visitante || match.away_name || match.away?.name;
        if (!home || !away) return;
        if (isMatchLiveNow(match)) return;
        if (!isFinishedStatus(match.status) && !isImplicitlyFinished(match) && !isExpiredLiveMatch(match)) return;
        finished.add(normalizeName(home));
        finished.add(normalizeName(away));
    };
    (state.data?.partidos || []).forEach(consider);
    (state.data?.all_league_matches || []).forEach(consider);
    return finished;
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

/* Las letras que circulan por dentro (W/D/L) son codigo de maquina.
   En pantalla se muestran en espanol, como en la cabecera G/E/P:
   G = ganado, E = empatado, P = perdido. */
function formOutcomeLetter(code) {
    if (code === "W") return "G";
    if (code === "D") return "E";
    if (code === "L") return "P";
    return String(code || "");
}

function formOutcomeTitle(code) {
    if (code === "W") return "Ganado";
    if (code === "D") return "Empatado";
    if (code === "L") return "Perdido";
    return "";
}

/* La racha llega como "3W", "2D"... se traduce solo la letra final. */
function spanishStreak(streak) {
    const raw = String(streak || "").trim();
    if (!raw) return "";
    return raw.replace(/([WDL])$/i, m => formOutcomeLetter(m.toUpperCase()));
}

function streakOutcomeTitle(streak) {
    const match = String(streak || "").match(/([WDL])$/i);
    return match ? formOutcomeTitle(match[1].toUpperCase()) : "";
}

/* Procedimiento de cada liga: que significa cada zona coloreada. */
function standingsLegend(zoneKey, leagueName = "") {
    const name = String(leagueName || "").toUpperCase();
    if (zoneKey === "segunda") {
        return `
        <div class="standings-legend" role="note">
            <span class="legend-item zone-direct"><i aria-hidden="true"></i>1º y 2º: ascenso directo a Primera</span>
            <span class="legend-item zone-playoff"><i aria-hidden="true"></i>3º a 6º: playoff de ascenso (semifinales y final)</span>
            <span class="legend-item zone-danger"><i aria-hidden="true"></i>Últimos 4: descenso</span>
        </div>`;
    }
    const descenso = name.includes("LA LIGA") ? "descienden a Segunda" : "descenso";
    return `
        <div class="standings-legend" role="note">
            <span class="legend-item zone-champions"><i aria-hidden="true"></i>1º a 4º: Champions League</span>
            <span class="legend-item zone-europe"><i aria-hidden="true"></i>5º y 6º: Europa League</span>
            <span class="legend-item zone-danger"><i aria-hidden="true"></i>Últimos 3: ${descenso}</span>
        </div>`;
}

function standingsFreshnessLabel() {
    // La cabecera debe decir la verdad: cuantas jornadas se han jugado y si
    // hay partidos en curso ahora mismo (que aun no suman puntos). Se usa el
    // mismo criterio que las filas para no anunciar directos ya terminados.
    const leagues = state.data?.multi_league_standings?.leagues || [];
    const liveResults = getLiveStandingsResults();
    const finishedTeams = getFinishedStandingsTeams();
    const playing = leagues.some(l => (l.teams || []).some(t => teamLiveState(t, liveResults, finishedTeams).live));
    const jornada = Number(state.data?.jornada_liga || 0);
    const parts = [];
    parts.push(jornada > 0 ? `${jornada} ${jornada === 1 ? "jornada jugada" : "jornadas jugadas"}` : "Temporada sin empezar");
    parts.push(playing ? "hay partidos en juego (no suman hasta el final)" : "actualizada al ultimo resultado");
    return parts.join(" · ");
}

/* Estado en directo definitivo de una fila de la clasificacion.
   Se cruzan las dos fuentes: la marca `en_juego` del servidor y lo que el
   navegador ve en los partidos. Basta con que una de las dos diga que el
   partido esta en juego para mostrarlo, y basta con que el cliente lo vea
   terminado para ocultarlo. Asi un directo ajeno a la quiniela tambien se ve,
   y un partido acabado deja de mostrar marcador aunque el servidor tarde en
   enterarse. */
function teamLiveState(team, liveResults, finishedTeams) {
    const key = normalizeName(team.n);
    if (finishedTeams.has(key)) return { live: false, score: "" };
    const clientLive = liveResults[key];
    if (clientLive) return { live: true, score: clientLive.tag };
    if (team.en_juego) return { live: true, score: team.marcador_live || "" };
    return { live: false, score: "" };
}

function renderFullStandingsPage() {
    const liveResults = getLiveStandingsResults();
    const finishedTeams = getFinishedStandingsTeams();
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
            ${renderMultiLeagueTable(league, liveResults, finishedTeams)}
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
                    <small>${escapeHtml(standingsFreshnessLabel())}</small>
                </div>
                <div class="league-tabs">${tabsHtml}</div>
                ${panelsHtml}
            </div>
        </section>`;
}

function renderMultiLeagueTable(league, liveResults = {}, finishedTeams = new Set()) {
    const rows = league.teams || [];
    if (rows.length === 0) return `<div class="empty-state">Sin datos para esta liga.</div>`;
    const showStreak = rows.some(team => String(team.streak || "").trim());
    const showForm = rows.some(team => Array.isArray(team.form) && team.form.length > 0);
    // Las zonas (Champions/descenso, ascenso/playoff) dependen de la liga.
    const zoneKey = /SEGUNDA/i.test(league.name || "") ? "segunda" : "primera";

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
                const liveState = teamLiveState(team, liveResults, finishedTeams);
                const live = liveState.live
                    ? `<span class="standings-live" title="Partido en juego: ${escapeHtml(liveState.score || "en juego")}">● ${escapeHtml(liveState.score || "en juego")}</span>`
                    : "";
                return `
                    <tr class="zone-${standingsZone(idx, rows.length, zoneKey)} ${liveState.live ? "is-playing" : ""}">
                        <td class="full-pos">${idx + 1}</td>
                        <td class="full-club">${logoBadge(team.n, team.logo || findTeamLogo(team.n))}<span>${escapeHtml(team.n)}</span>${live}</td>
                        <td>${team.pj}</td>
                        <td>${team.pg}</td>
                        <td>${team.pe}</td>
                        <td>${team.pp}</td>
                        <td>${team.gf}</td>
                        <td>${team.gc}</td>
                        <td>${team.dg}</td>
                        <td class="full-points">${team.pts}</td>
                        ${showStreak ? `<td title="${escapeHtml(streakOutcomeTitle(team.streak))}">${escapeHtml(spanishStreak(team.streak))}</td>` : ""}
                        ${showForm ? `<td class="form-cell">${formArr.map(f => {
                            const cls = f === "W" ? "form-win" : f === "D" ? "form-draw" : "form-loss";
                            return `<span class="form-dot ${cls}" title="${escapeHtml(formOutcomeTitle(f))}">${escapeHtml(formOutcomeLetter(f))}</span>`;
                        }).join("")}</td>` : ""}
                    </tr>`;
            }).join("")}</tbody>
        </table>
        ${standingsLegend(zoneKey, league.name)}`;
}
