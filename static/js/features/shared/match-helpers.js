/** Shared match state helpers. */

import { normalizeTeamKey } from "./utils.js";

export function competitionLabel(match) {
    const comp = match?.competition?.name || match?.competition_name || "";
    return String(comp).toUpperCase();
}

export function isLiveStatus(status) {
    const raw = String(status || "").toUpperCase();
    return ["LIVE", "IN PLAY", "HT", "HALF TIME BREAK", "EN JUEGO", "1H", "2H", "ET", "P"].includes(raw);
}

export function isLiveMatch(match) {
    if (!match) return false;
    if (isLiveStatus(match.status)) return true;
    const liveIndicators = match?.live || match?.is_live || match?.in_play;
    return Boolean(liveIndicators);
}

export function isFinishedStatus(status) {
    const raw = String(status || "").toUpperCase();
    return ["FT", "FINISHED", "TERMINADO", "COMPLETED", "AET", "PEN"].includes(raw);
}

export function isImplicitlyFinished(match) {
    if (!match) return false;
    if (match.goles_local != null && match.goles_visitante != null) return true;
    if (match.marcador_base && String(match.marcador_base).trim()) return true;
    return false;
}

export function isExpiredLiveMatch(match) {
    if (!match) return false;
    if (!isLiveMatch(match)) return false;
    const now = Date.now();
    const kickoff = parseMatchTimestamp(match);
    if (!kickoff) return false;
    const elapsed = now - kickoff;
    // More than 3 hours after kickoff with no update
    return elapsed > 3 * 60 * 60 * 1000;
}

export function needsFixtureSchedule(match) {
    if (!match) return true;
    if (isFinishedStatus(String(match?.status || ""))) return false;
    if (isLiveMatch(match)) return false;
    if (match.goles_local != null && match.goles_visitante != null) return false;
    if (match.marcador_base && String(match.marcador_base).trim()) return false;
    return true;
}

export function parseMatchTimestamp(match) {
    const raw = match?.added || match?.fecha_raw || match?.hora_raw || match?.kickoff;
    if (!raw) return null;
    try {
        const dateStr = String(raw).replace(" ", "T");
        const dt = new Date(dateStr);
        return Number.isNaN(dt.getTime()) ? null : dt.getTime();
    } catch {
        return null;
    }
}

export function matchMinuteValue(match) {
    const candidates = [match?.minuto_live, match?.minuto, match?.minute, match?.time, match?.minuto_raw];
    for (const raw of candidates) {
        const clean = String(raw ?? "").trim();
        if (!clean || clean === "-" || clean === "—") continue;
        const parsed = clean.match(/\d{1,3}/);
        if (parsed) return parseInt(parsed[0], 10);
    }
    return 0;
}

export function fixtureScheduleDisplay(match) {
    if (!match) return "";
    const parts = fixtureScheduleParts(match);
    if (parts.day && parts.time) {
        return `${parts.day} ${parts.time}`;
    }
    return parts.label || match?.hora || match?.kickoff || "";
}

export function fixtureScheduleParts(match) {
    if (!match) return { day: "", time: "", label: "" };
    const dateStr = match?.added || match?.fecha_raw || match?.fecha || "";
    if (!dateStr) return { day: "", time: "", label: match?.hora || match?.kickoff || "" };
    try {
        const dt = new Date(String(dateStr).replace(" ", "T"));
        if (Number.isNaN(dt.getTime())) throw new Error("Invalid date");
        const day = dt.toLocaleDateString("es-ES", { weekday: "short", day: "2-digit", month: "2-digit" }).replace(/\./g, "");
        const time = dt.toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit" });
        return { day, time, label: `${day} ${time}` };
    } catch {
        return { day: "", time: "", label: match?.hora || match?.kickoff || "" };
    }
}

export function liveScoreDisplay(match, fallback) {
    if (match.goles_local != null && match.goles_visitante != null) {
        return `${match.goles_local}-${match.goles_visitante}`;
    }
    return match?.marcador || match?.score || fallback || "—";
}

export function liveScoreWithMinute(match, score) {
    const minute = liveMinuteLabel(match);
    return minute && minute !== "LIVE" ? `${score} · ${minute}` : score;
}

export function liveMinuteLabel(match) {
    const candidates = [match?.minuto_live, match?.minuto, match?.minute, match?.time];
    for (const raw of candidates) {
        const clean = String(raw ?? "").trim();
        if (!clean || clean === "-" || clean === "—") continue;
        if (/^(HT|DESC|DESCANSO|HALF)/i.test(clean)) return "Desc.";
        const parsed = clean.match(/\d{1,3}/);
        if (parsed) return `${parsed[0]}'`;
        return clean;
    }
    const numeric = matchMinuteValue(match);
    if (numeric > 0) return `${numeric}'`;
    return (typeof isLiveStatus === "function" && isLiveStatus(match?.status)) ? "LIVE" : "LIVE";
}

export function liveStage(match) {
    const status = String(match?.status || "").toUpperCase();
    if (status === "HT" || status === "HALF TIME BREAK") return "HT";
    if (isLiveStatus(status)) return "LIVE";
    if (isFinishedStatus(status)) return "FT";
    return "NS";
}

export function liveScoreAttrs(match, isLive) {
    if (!isLive) return "";
    return `data-live-match="${String(match?.id || "")}" data-live-minute="${String(matchMinuteValue(match) || "")}" data-live-stage="${liveStage(match)}"`;
}

export function isMatchLiveNow(match) {
    if (!match) return false;
    if (isFinishedStatus(String(match?.status || ""))) return false;
    if (isLiveMatch(match)) return true;
    return false;
}