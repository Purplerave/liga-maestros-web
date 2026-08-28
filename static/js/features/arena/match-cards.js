/** Match card rendering for arena views. */

import { escapeHtml } from "../../shared/utils.js";
import {
    competitionLabel,
    isLiveMatch,
    isFinishedStatus,
    isImplicitlyFinished,
    isExpiredLiveMatch,
    needsFixtureSchedule,
    fixtureScheduleDisplay,
    liveScoreDisplay,
    liveMinuteLabel,
    liveStage,
    liveScoreAttrs,
    liveMatchDomKey,
    matchPairKey
} from "../../shared/match-helpers.js";

function teamCell(name, side, logo) {
    const logoHtml = logo ? `<img class="cx-team-logo" src="${logo}" alt="" width="24" height="24" decoding="async" aria-hidden="true">` : "";
    return `<div class="card-team ${side}">${logoHtml}<span class="card-team-name">${escapeHtml(name)}</span></div>`;
}

function teamLogo(match, side) {
    const name = side === "home"
        ? (match.local || match.home_name || match.home?.name)
        : (match.visitante || match.away_name || match.away?.name);
    if (!name) return "";
    // Logo resolution is handled by the calling context (arena.js has access to team_logos)
    return "";
}

export function renderMatchCard(match) {
    const home = match?.local || match?.home_name || match?.home?.name || "Local";
    const away = match?.visitante || match?.away_name || match?.away?.name || "Visitante";

    const scheduled = needsFixtureSchedule(match);
    const finished = isFinishedStatus(match?.status) || isImplicitlyFinished(match) || isExpiredLiveMatch(match);
    const live = (isLiveMatch(match) || isLiveStatus(match?.status)) && !finished && !scheduled;
    const score = scheduled
        ? fixtureScheduleDisplay(match)
        : live
            ? liveScoreDisplay(match, "-")
            : (match?.marcador || match?.score || match?.scores?.score || "-");
    const minute = live ? (liveMinuteLabel(match) || "EN DIRECTO") : "";

    const cardClass = live ? "is-live" : (finished ? "is-finished" : "");

    return `
        <article class="match-card ${cardClass}" data-match-id="${match?.id || ""}"${live ? ` data-live-key="${escapeHtml(liveMatchDomKey(match))}"` : ""}>
            <div class="card-teams">
                ${teamCell(home, "left", teamLogo(match, "home"))}
                <div class="card-score-area">
                    <div class="match-score-badge ${live ? "is-live-score" : (scheduled ? "is-scheduled-time" : "")}"${live ? " data-live-score" : ""}${liveScoreAttrs(match, live)}>${escapeHtml(score)}</div>
                    ${minute ? `<span class="card-live-minute" data-live-minute-label>${escapeHtml(minute)}</span>` : ""}
                </div>
                ${teamCell(away, "right", teamLogo(match, "away"))}
            </div>
        </article>`;
}

export function renderGroupedMatchCards(matches, singleCompetition = false) {
    if (!Array.isArray(matches) || !matches.length) return "";
    if (singleCompetition) {
        return `<div class="match-card-container">${matches.map(renderMatchCard).join("")}</div>`;
    }
    const groups = [];
    const indexByKey = new Map();
    for (const match of matches) {
        const key = competitionLabel(match);
        if (!indexByKey.has(key)) {
            indexByKey.set(key, groups.length);
            groups.push({ key, label: matchCompetitionMeta(match), matches: [] });
        }
        groups[indexByKey.get(key)].matches.push(match);
    }
    groups.sort((a, b) => {
        const liveDiff = b.matches.filter(isLiveMatch).length - a.matches.filter(isLiveMatch).length;
        if (liveDiff) return liveDiff;
        return a.label.localeCompare(b.label, "es");
    });
    return groups.map(group => `
        <section class="league-match-group" data-competition="${escapeHtml(group.key)}">
            <header class="league-group-header">
                <strong>${escapeHtml(group.label)}</strong>
                <span>${group.matches.length} partido${group.matches.length === 1 ? "" : "s"}</span>
            </header>
            <div class="match-card-container">
                ${group.matches.map(renderMatchCard).join("")}
            </div>
        </section>
    `).join("");
}

function matchCompetitionMeta(match) {
    const comp = competitionLabel(match);
    const country = match?.country || match?.country_code || "";
    if (country) return `${comp} (${country.toUpperCase()})`;
    return comp;
}