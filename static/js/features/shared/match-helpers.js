/** Shared match state helpers. */

import { madridFormatMs, madridWallClockToMs, normalizeTeamKey } from "./utils.js";

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
    const isoDate = String(raw ?? "").slice(0, 10);
    if (isoDate.length < 8) return null;
    // `time` es el minuto en directo ("63"), no la hora de saque, y una
    // quiniela sin horario manda hora "-": solo vale lo que tenga forma de
    // hora (HH:MM). Sin hora conocida, null en vez de inventar las 12:00.
    for (const candidate of [match?.hora, match?.scheduled, match?.time]) {
        const clock = String(candidate ?? "").replace(/h$/i, "").trim();
        if (!/^\d{1,2}:\d{2}/.test(clock)) continue;
        const stamp = madridWallClockToMs(isoDate, clock.slice(0, 5));
        if (stamp !== null) return stamp;
    }
    return null;
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
    const ts = parseMatchTimestamp(match);
    if (!ts) return { day: "", time: "", label: match?.hora || match?.kickoff || "" };
    const day = madridFormatMs(ts, { weekday: "short", day: "2-digit", month: "2-digit" }).replace(/\./g, "");
    const time = madridFormatMs(ts, { hour: "2-digit", minute: "2-digit" });
    return { day, time, label: `${day} ${time}` };
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