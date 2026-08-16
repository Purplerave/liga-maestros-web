/* ==========================================================================
   UTILS — Funciones utilitarias core de Liga de Maestros.
   Sin dependencias internas. Cargar primero que todos los demas modulos.
   ========================================================================== */

const normalizeCache = new Map();

function qs(id) {
    return document.getElementById(id);
}

function escapeHtml(value) {
    return String(value ?? "")
        .replaceAll("&", "&")
        .replaceAll("<", "<")
        .replaceAll(">", ">")
        .replaceAll('"', """)
        .replaceAll("'", "&#039;");
}

function authenticatedJsonHeaders() {
    const headers = { "Content-Type": "application/json" };
    if (typeof state !== "undefined" && state.csrfToken) {
        headers["X-CSRF-Token"] = state.csrfToken;
    }
    return headers;
}

function showToast(message, type = "success") {
    const container = qs("toast-container");
    if (!container) return;
    const toast = document.createElement("div");
    toast.className = `toast ${type}`;
    toast.innerHTML = `<strong>${type === "success" ? "OK" : "AVISO"}</strong> ${escapeHtml(message)}`;
    container.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = "0";
        toast.style.transform = "translateY(8px)";
        setTimeout(() => toast.remove(), 260);
    }, 3200);
}

function getShortName(name) {
    if (!name) return "-";
    const clean = String(name).toUpperCase();
    const normalized = clean.normalize("NFD").replace(/[\u0300-\u036f]/g, "");
    const map = {
        "CLUB ATLETICO DE MADRID": "AT. MADRID",
        "CLUB ATLÉTICO DE MADRID": "AT. MADRID",
        "REAL MADRID C.F.": "R. MADRID",
        "F.C. BARCELONA": "BARCA",
        "ATHLETIC CLUB BILBAO": "ATHLETIC",
        "REAL SOCIEDAD DE FUTBOL": "R. SOCIEDAD",
        "REAL SOCIEDAD DE FÚTBOL": "R. SOCIEDAD",
        "VILLARREAL C.F.": "VILLARREAL",
        "REAL BETIS BALOMPIE": "BETIS",
        "REAL BETIS BALOMPIÉ": "BETIS",
        "DEPORTIVO ALAVES": "ALAVES",
        "DEPORTIVO ALAVÉS": "ALAVES",
        "R.C.D. ESPANYOL DE BARCELONA": "ESPANYOL",
        "R.C.D. MALLORCA": "MALLORCA"
    };
    const normalizedMap = {
        "ATLETICO MADRID": "AT. MADRID",
        "ATLETICO DE MADRID": "AT. MADRID",
        "CLUB ATLETICO DE MADRID": "AT. MADRID",
        "AT. MADRID": "AT. MADRID",
        "REAL MADRID": "R. MADRID",
        "REAL MADRID C.F.": "R. MADRID",
        "R. SOCIEDAD": "R. SOC.",
        "SEVILLA FC": "SEVILLA",
        "FC BARCELONA": "BARCA",
        "BARCELONA": "BARCA",
        "REAL BETIS": "BETIS",
        "VILLARREAL CF": "VILLARREAL",
        "VILLARREAL C.F.": "VILLARREAL",
        "REAL SOCIEDAD": "R. SOC.",
        "REAL SOCIEDAD DE FUTBOL": "R. SOC.",
        "REAL SOCIEDAD DE FUTBOL SAD": "R. SOC.",
        "REAL OVIEDO": "R. OVIEDO",
        "DEPORTIVO LA CORUNA": "DEPOR",
        "RAYO VALLECANO": "RAYO",
        "R. SANTANDER": "RACING",
        "R SANTANDER": "RACING",
        "CA OSASUNA": "OSASUNA",
        "CLUB ATLETICO OSASUNA": "OSASUNA",
        "REAL CLUB DEPORTIVO ESPANYOL": "ESPANYOL",
        "REAL RACING CLUB DE SANTANDER": "RACING",
        "R RACING CLUB": "RACING",
        "R. RACING CLUB": "RACING",
        "RACING CLUB": "RACING",
        "RACING SANTANDER": "RACING",
        "RC DEPORTIVO": "DEPOR",
        "REAL CLUB DEPORTIVO": "DEPOR",
        "CULTURAL Y DEPORTIVA LEONESA": "C. LEONESA",
        "C LEONESA": "C. LEONESA",
        "REAL SPORTING": "SPORTING",
        "ALBACETE BP": "ALBACETE",
        "SPORTING DE GIJON": "SPORTING",
        "SPORTING GIJON": "SPORTING"
    };
    if (map[clean]) return map[clean];
    if (normalizedMap[normalized]) return normalizedMap[normalized];
    const words = clean.split(/\s+/).filter(Boolean);
    if (words.length <= 1) return clean.slice(0, 10);
    if (words[0] === "REAL" || words[0] === "CLUB" || words[0] === "DEPORTIVO") {
        return words.slice(0, 2).join(" ").slice(0, 12);
    }
    return words[0].slice(0, 10);
}

function normalizeName(name) {
    if (!name) return "";
    const key = String(name).toUpperCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/[^A-Z0-9]/g, "");
    if (normalizeCache.has(key)) return normalizeCache.get(key);
    normalizeCache.set(key, key);
    return key;
}

function normalizeSign(sign) {
    const s = String(sign || "-").trim().toUpperCase();
    if (s === "1" || s === "X" || s === "2") return s;
    return "-";
}

function isLiveStatus(status) {
    const raw = String(status || "").toUpperCase().trim();
    return ["LIVE", "IN PLAY", "HT", "HALF TIME BREAK", "EN JUEGO", "1H", "2H"].includes(raw);
}

function isFinishedStatus(status) {
    const raw = String(status || "").toUpperCase().trim();
    return ["FT", "FINISHED", "TERMINADO", "AET", "PEN", "STALE", "AWARDED"].includes(raw);
}

function isScheduledStatus(status) {
    const raw = String(status || "").toUpperCase().trim();
    return ["NS", "SCHEDULED", "NOT STARTED", "POSTPONED", "TBD"].includes(raw) || !raw;
}

function isLiveMatch(match) {
    if (!match) return false;
    if (isFinishedStatus(match.status)) return false;
    return isLiveStatus(match.status) || Boolean(match.minuto_live);
}

function isImplicitlyFinished(match) {
    if (!match) return false;
    const m = String(match.marcador || "").toLowerCase();
    if (m.includes("pendiente de resultado")) return true;
    const score = scoreOnly(match.marcador);
    if (score && score !== "-" && !isLiveMatch(match) && !isScheduledStatus(match.status)) return true;
    return false;
}

function isExpiredLiveMatch(match) {
    return false;
}

function scoreOnly(marcador) {
    if (!marcador) return "";
    const m = String(marcador).replace(/\u00a0/g, " ").trim();
    const match = m.match(/^(\d+)\s*[-:]\s*(\d+)/);
    return match ? `${match[1]}-${match[2]}` : "";
}

function liveScoreDisplay(match, fallback = "-") {
    if (!match) return fallback;
    if (match.marcador_base) return match.marcador_base;
    if (match.goles_local != null && match.goles_visitante != null) {
        return `${match.goles_local}-${match.goles_visitante}`;
    }
    const only = scoreOnly(match.marcador);
    return only || fallback;
}

function matchMinuteValue(match) {
    if (!match) return "";
    return String(match.minuto_live || match.minuto || "").replace(/[^0-9]/g, "");
}

function liveStage(match) {
    if (!match) return "";
    const st = String(match.status || "").toUpperCase();
    if (st === "HT" || st === "HALF TIME BREAK") return "HT";
    return "LIVE";
}

function liveScoreAttrs(match, isLive) {
    if (!isLive) return "";
    return ` data-live-match="${match.id || ""}" data-live-minute="${matchMinuteValue(match)}" data-live-stage="${liveStage(match)}"`;
}

function formatSmartDate(fecha, hora) {
    if (!fecha && !hora) return "Horario pendiente";
    const h = (hora || "").toString().replace(/h$/i, "").trim();
    if (!fecha) return h ? `${h}h` : "Horario pendiente";
    try {
        const d = new Date(String(fecha).slice(0, 10) + "T12:00:00");
        if (isNaN(d.getTime())) return h ? `${h}h` : String(fecha);
        const dias = ["dom", "lun", "mar", "mie", "jue", "vie", "sab"];
        const label = `${dias[d.getDay()]} ${String(d.getDate()).padStart(2, "0")}/${String(d.getMonth() + 1).padStart(2, "0")}`;
        return h ? `${label} ${h}h` : label;
    } catch {
        return h ? `${h}h` : String(fecha || "");
    }
}

function teamCell(name, side, logoUrl) {
    const short = getShortName(name);
    const logo = logoUrl ? `<img class="team-logo" src="${escapeHtml(logoUrl)}" alt="" loading="lazy" onerror="this.style.display='none'">` : "";
    return `<div class="team-cell team-${side}">${logo}<span class="team-name">${escapeHtml(short)}</span></div>`;
}

function teamLogo(match, side) {
    if (!match) return "";
    if (side === "home") return match.logo_local || match.home_logo || "";
    return match.logo_visitante || match.away_logo || "";
}

function competitionLabel(match) {
    return (match.competition || match.liga || match.league || "OTROS").toString().toUpperCase();
}

function matchCompetitionMeta(match) {
    return competitionLabel(match);
}

function getBrowsableLeagueMatches() {
    if (!state.data || !Array.isArray(state.data.partidos_liga)) return [];
    return state.data.partidos_liga;
}

function getLiveLeagueMatches() {
    return getBrowsableLeagueMatches().filter(m => isLiveMatch(m) || isLiveStatus(m.status));
}

function predSign(preds, primary, idx, fallback = null) {
    const first = preds?.[primary]?.signos?.[idx];
    if (first && first !== "-") return normalizeSign(first);
    const alt = fallback ? preds?.[fallback]?.signos?.[idx] : null;
    return normalizeSign(alt);
}

function hitClass(sign, real, status, exactScore = false) {
    // Paint hits when the match is finished/closed (including STALE) and any real 1/X/2 from the server do paint.
    const s = normalizeSign(sign);
    const r = exactScore ? String(real || "").trim() : normalizeSign(real);
    if (!s || s === "-" || !r || r === "-") return "";
    if (!exactScore && !isFinishedStatus(status) && !isImplicitlyFinished({ status, marcador: real })) return "";
    return s === r ? "is-hit" : "is-miss";
}

function currentMainView() {
    return state.currentFilter || "ALL";
}

function isCoverPage() {
    return state.currentFilter === "ALL";
}

function isTicketPage() {
    return state.currentFilter === "TICKET";
}

function isStandingsPage() {
    return String(state.currentFilter || "").startsWith("STANDINGS");
}

function isSnakePage() {
    return state.currentFilter === "SNAKE_PAGE";
}

function isQuizPage() {
    return state.currentFilter === "QUIZ_PAGE";
}

function isContestPage() {
    return state.contestView && state.contestView !== "MATCHES";
}

function isLiveOrLeaguePage() {
    return state.currentFilter === "LIVE" || (state.currentFilter && !isCoverPage() && !isTicketPage() && !isStandingsPage() && !isSnakePage() && !isQuizPage() && !isContestPage());
}

function isProfilePage() {
    return state.contestView === "PROFILE" || state.currentFilter === "PROFILE";
}

function findQ15Directo(match) {
    if (!state.q15Directo || !match) return {};
    const key = matchPairKey(match);
    return state.q15Directo[key] || state.q15Directo[String(match.id)] || {};
}

function eventTypeLabel(type) {
    const t = String(type || "").toLowerCase();
    if (t.includes("goal")) return "Gol";
    if (t.includes("yellow")) return "Amarilla";
    if (t.includes("red")) return "Roja";
    if (t.includes("subst")) return "Cambio";
    return type || "";
}

function renderQ15Events(match) {
    const detail = findQ15Directo(match);
    const groups = detail.events || [];
    const withEvents = groups.filter(group => (group.events || []).length);
    if (!withEvents.length) {
        return `<small class="q15-empty">Sin eventos cacheados para este partido.</small>`;
    }
    return `<div class="q15-events">
        ${withEvents.map(group => `
            <div class="q15-event-team">
                <b>${escapeHtml(getShortName(group.team))}</b>
                ${(group.events || []).map(event => `
                    <span class="q15-event">
                        <em>${escapeHtml(eventTypeLabel(event.type))}</em>
                        <strong>${escapeHtml(event.minute || "")}</strong>
                        <span>${escapeHtml(event.player || "")}</span>
                    </span>
                `).join("")}
            </div>
        `).join("")}
    </div>`;
}

function renderQ15Meta(match) {
    const detail = findQ15Directo(match);
    if (!detail) return "";
    const bits = [];
    if (detail.referee) bits.push(`Arbitro: ${detail.referee}`);
    if (detail.coaches) bits.push(`Tecnicos: ${detail.coaches}`);
    if (!bits.length) return "";
    return `<small class="q15-meta">${escapeHtml(bits.join(" | "))}</small>`;
}

function repairMojibakeText(value) {
    let text = String(value || "");
    for (let i = 0; i < 3 && /[\u00c2\u00c3]/.test(text); i += 1) {
        try {
            const decoded = decodeURIComponent(escape(text));
            if (!decoded || decoded === text) break;
            text = decoded;
        } catch (_) {
            break;
        }
    }
    return text;
}

function compactTensionLabel(label) {
    const fullLabel = repairMojibakeText(label);
    const clean = fullLabel.trim().toLowerCase();
    const map = {
        programa: "PROG",
        gemini: "GEM",
        grok: "GROK",
        claude: "CLAU",
        copilot: "COP",
        chatgpt: "GPT",
        consejo: "CONS",
        pena: "PENA",
        "peña": "PENA",
        tu: "TU",
        "tú": "TU",
        boleto: "TU"
    };
    if (clean === "peña" || clean.includes("peña")) return "PENA";
    if (clean === "tú" || clean.includes("tú")) return "TU";
    return map[clean] || fullLabel.trim().slice(0, 4).toUpperCase();
}

function matchPairKey(match) {
    const home = normalizeName(match.local || match.home_name || "");
    const away = normalizeName(match.visitante || match.away_name || "");
    return `${home}-${away}`;
}
