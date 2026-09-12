/** Shared utilities for all features. */

export function escapeHtml(text) {
    if (text === null || text === undefined) return "";
    return String(text)
        .replace(/&/g, "&")
        .replace(/</g, "<")
        .replace(/>/g, ">")
        .replace(/"/g, """)
        .replace(/'/g, "&#039;");
}

export function qs(id) {
    return document.getElementById(id);
}

export function normalizeTeamKey(name) {
    if (!name) return "";
    return String(name).trim().toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");
}

export function matchPairKey(match) {
    const home = normalizeTeamKey(match?.local || match?.home_name || match?.home?.name);
    const away = normalizeTeamKey(match?.visitante || match?.away_name || match?.away?.name);
    if (!home || !away) return "";
    return `${home}|${away}`;
}

export function getShortName(name) {
    if (!name) return "—";
    const s = String(name).trim();
    const clean = s.replace(/[^A-Za-zÁÉÍÓÚÜÑáéíóúüñ\s]/g, "");
    const abbr = clean.split(/\s+/).map(w => w[0] || "").join("").slice(0, 3).toUpperCase();
    return abbr || s.slice(0, 3).toUpperCase();
}

export function fitName(name, maxLen) {
    if (!name) return "—";
    const s = String(name).trim();
    return s.length > maxLen ? s.slice(0, maxLen - 1) + "…" : s;
}

/* Reloj de Madrid: la unica zona que vale en esta web.
   El servidor manda todas las horas como texto sin zona ("2026-09-03 21:00")
   ya en hora de Madrid. Leerlo con `new Date()` lo interpretaba en la zona del
   navegador y en Canarias (o con el equipo en UTC) el saque caia mas tarde:
   el partido se veia como futuro y el Directo se vaciaba con el Celta en
   juego. Todo instante se interpreta y se pinta en Europe/Madrid. */
export const MADRID_TIMEZONE = "Europe/Madrid";

export function madridOffsetMs(atMs) {
    try {
        const parts = new Intl.DateTimeFormat("en-GB", {
            timeZone: MADRID_TIMEZONE,
            hour12: false,
            year: "numeric",
            month: "2-digit",
            day: "2-digit",
            hour: "2-digit",
            minute: "2-digit",
            second: "2-digit",
        }).formatToParts(new Date(atMs));
        const value = type => Number((parts.find(part => part.type === type) || {}).value || 0);
        const asUtc = Date.UTC(
            value("year"),
            value("month") - 1,
            value("day"),
            value("hour") % 24,
            value("minute"),
            value("second"),
        );
        return asUtc - (atMs - (atMs % 1000));
    } catch (error) {
        return 0;
    }
}

export function madridWallClockToMs(dateText, timeText) {
    const date = /^(\d{4})-(\d{1,2})-(\d{1,2})/.exec(String(dateText || "").trim());
    if (!date) return null;
    const time = /^(\d{1,2}):(\d{2})/.exec(String(timeText || "").trim());
    const naiveUtc = Date.UTC(
        Number(date[1]),
        Number(date[2]) - 1,
        Number(date[3]),
        time ? Number(time[1]) : 12,
        time ? Number(time[2]) : 0,
        0,
    );
    if (Number.isNaN(naiveUtc)) return null;
    // El offset depende del instante (CET/CEST): segunda pasada para clavarlo.
    const offset = madridOffsetMs(naiveUtc - madridOffsetMs(naiveUtc));
    return naiveUtc - offset;
}

export function madridFormatMs(atMs, options) {
    try {
        return new Intl.DateTimeFormat("es-ES", { timeZone: MADRID_TIMEZONE, ...options }).format(new Date(atMs));
    } catch (error) {
        return new Date(atMs).toLocaleString("es-ES");
    }
}