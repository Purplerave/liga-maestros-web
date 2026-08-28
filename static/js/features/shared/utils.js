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