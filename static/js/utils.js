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
        .replaceAll("&", "&" + "amp;")
        .replaceAll("<", "&" + "lt;")
        .replaceAll(">", "&" + "gt;")
        .replaceAll('"', "&" + "quot;")
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

/* Nombres cortos de equipo.
   Regla: el nombre debe leerse entero. Nunca se corta una palabra a medias
   ("LAS PALMAS" no puede quedarse en "LAS"), nunca se deja solo el prefijo
   juridico del club ("CE SABADELL" no puede quedarse en "CE") y dos equipos
   distintos no pueden compartir etiqueta (Celta / Celta Fortuna). Por eso la
   plantilla oficial de Primera y Segunda esta mapeada a mano y el fallback
   solo se aplica a nombres desconocidos (ligas extranjeras, copas). */
const SHORT_NAME_MAX = 14;

// Ruido juridico/organizativo que no identifica al club.
const SHORT_NAME_NOISE = [
    "FC", "CF", "CD", "CE", "CP", "UD", "UE", "SD", "AD", "CA", "RC", "RCD", "SAD",
    "BP", "B.P.", "AC", "CFS", "SAF", "FUTBOL", "BALOMPIE", "CLUB"
];

const SHORT_NAME_EXACT = {
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

// Clave: nombre en mayusculas y sin acentos. Cubre la plantilla 2026-27 de
// Primera y Segunda mas las variantes que envian los proveedores.
const SHORT_NAME_NORMALIZED = {
    // --- Primera ---
    "ATLETICO MADRID": "AT. MADRID",
    "ATLETICO DE MADRID": "AT. MADRID",
    "CLUB ATLETICO DE MADRID": "AT. MADRID",
    "AT. MADRID": "AT. MADRID",
    "REAL MADRID": "R. MADRID",
    "REAL MADRID C.F.": "R. MADRID",
    "REAL MADRID CF": "R. MADRID",
    "FC BARCELONA": "BARCA",
    "BARCELONA": "BARCA",
    "VILLARREAL": "VILLARREAL",
    "VILLARREAL CF": "VILLARREAL",
    "VILLARREAL C.F.": "VILLARREAL",
    "REAL BETIS": "BETIS",
    "REAL BETIS BALOMPIE": "BETIS",
    "BETIS": "BETIS",
    "CELTA": "CELTA",
    "RC CELTA": "CELTA",
    "RC CELTA DE VIGO": "CELTA",
    "CELTA DE VIGO": "CELTA",
    "CELTA VIGO": "CELTA",
    "GETAFE": "GETAFE",
    "GETAFE CF": "GETAFE",
    "RAYO VALLECANO": "RAYO",
    "VALENCIA": "VALENCIA",
    "VALENCIA CF": "VALENCIA",
    "REAL SOCIEDAD": "R. SOCIEDAD",
    "R. SOCIEDAD": "R. SOCIEDAD",
    "REAL SOCIEDAD DE FUTBOL": "R. SOCIEDAD",
    "REAL SOCIEDAD DE FUTBOL SAD": "R. SOCIEDAD",
    "ESPANYOL": "ESPANYOL",
    "RCD ESPANYOL": "ESPANYOL",
    "RCD ESPANYOL DE BARCELONA": "ESPANYOL",
    "REAL CLUB DEPORTIVO ESPANYOL": "ESPANYOL",
    "ATHLETIC": "ATHLETIC",
    "ATHLETIC CLUB": "ATHLETIC",
    "ATHLETIC CLUB BILBAO": "ATHLETIC",
    "ATHLETIC BILBAO": "ATHLETIC",
    "SEVILLA": "SEVILLA",
    "SEVILLA FC": "SEVILLA",
    "DEPORTIVO ALAVES": "ALAVES",
    "ALAVES": "ALAVES",
    "ELCHE": "ELCHE",
    "ELCHE CF": "ELCHE",
    "LEVANTE": "LEVANTE",
    "LEVANTE UD": "LEVANTE",
    "OSASUNA": "OSASUNA",
    "CA OSASUNA": "OSASUNA",
    "CLUB ATLETICO OSASUNA": "OSASUNA",
    "R. RACING CLUB": "RACING",
    "R RACING CLUB": "RACING",
    "RACING CLUB": "RACING",
    "RACING SANTANDER": "RACING",
    "RACING DE SANTANDER": "RACING",
    "REAL RACING CLUB DE SANTANDER": "RACING",
    "R. SANTANDER": "RACING",
    "R SANTANDER": "RACING",
    "RC DEPORTIVO": "DEPOR",
    "REAL CLUB DEPORTIVO": "DEPOR",
    "DEPORTIVO LA CORUNA": "DEPOR",
    "RC DEPORTIVO DE LA CORUNA": "DEPOR",
    "MALAGA": "MALAGA",
    "MALAGA CF": "MALAGA",
    // --- Segunda ---
    "RCD MALLORCA": "MALLORCA",
    "MALLORCA": "MALLORCA",
    "GIRONA": "GIRONA",
    "GIRONA FC": "GIRONA",
    "REAL OVIEDO": "R. OVIEDO",
    "OVIEDO": "R. OVIEDO",
    "UD ALMERIA": "ALMERIA",
    "ALMERIA": "ALMERIA",
    "UD LAS PALMAS": "LAS PALMAS",
    "LAS PALMAS": "LAS PALMAS",
    "CD CASTELLON": "CASTELLON",
    "CASTELLON": "CASTELLON",
    "BURGOS CF": "BURGOS",
    "BURGOS": "BURGOS",
    "SD EIBAR": "EIBAR",
    "EIBAR": "EIBAR",
    "CORDOBA CF": "CORDOBA",
    "CORDOBA": "CORDOBA",
    "ALBACETE BP": "ALBACETE",
    "ALBACETE BALOMPIE": "ALBACETE",
    "ALBACETE": "ALBACETE",
    "AD CEUTA FC": "CEUTA",
    "AD CEUTA": "CEUTA",
    "CEUTA": "CEUTA",
    "FC ANDORRA": "ANDORRA",
    "ANDORRA": "ANDORRA",
    "REAL SPORTING": "SPORTING",
    "REAL SPORTING DE GIJON": "SPORTING",
    "SPORTING DE GIJON": "SPORTING",
    "SPORTING GIJON": "SPORTING",
    "SPORTING": "SPORTING",
    "GRANADA CF": "GRANADA",
    "GRANADA": "GRANADA",
    "R. SOCIEDAD B": "R. SOCIEDAD B",
    "REAL SOCIEDAD B": "R. SOCIEDAD B",
    "SANSE": "R. SOCIEDAD B",
    "REAL VALLADOLID CF": "VALLADOLID",
    "REAL VALLADOLID": "VALLADOLID",
    "VALLADOLID": "VALLADOLID",
    "CADIZ CF": "CADIZ",
    "CADIZ": "CADIZ",
    "CD LEGANES": "LEGANES",
    "LEGANES": "LEGANES",
    "CD TENERIFE": "TENERIFE",
    "TENERIFE": "TENERIFE",
    "CD ELDENSE": "ELDENSE",
    "ELDENSE": "ELDENSE",
    "CE SABADELL": "SABADELL",
    "CE SABADELL FC": "SABADELL",
    "SABADELL": "SABADELL",
    "CELTA FORTUNA": "CELTA FORTUNA",
    "CELTA B": "CELTA FORTUNA",
    // --- Otros clubes espanoles habituales ---
    "REAL ZARAGOZA": "ZARAGOZA",
    "ZARAGOZA": "ZARAGOZA",
    "SD HUESCA": "HUESCA",
    "HUESCA": "HUESCA",
    "RACING DE FERROL": "R. FERROL",
    "RACING FERROL": "R. FERROL",
    "CD MIRANDES": "MIRANDES",
    "MIRANDES": "MIRANDES",
    "CULTURAL Y DEPORTIVA LEONESA": "C. LEONESA",
    "CULTURAL LEONESA": "C. LEONESA",
    "C LEONESA": "C. LEONESA",
    "C. LEONESA": "C. LEONESA"
};

function shortNameLookup(table, key) {
    const value = table[key];
    return typeof value === "string" ? value : "";
}

function shortNameFallback(normalized) {
    // Un nombre desconocido (liga extranjera, copa) se limpia sin mutilarlo:
    // se quitan las siglas del club y, si aun sobra, se abrevian las primeras
    // palabras. La ultima palabra (la que identifica al equipo) nunca se corta;
    // si es larga se muestra entera y es el CSS quien decide como encajarla.
    const words = normalized.replace(/[.,]/g, " ").split(/\s+/).filter(Boolean);
    const noise = new Set(SHORT_NAME_NOISE);
    const meaningful = words.filter(word => !noise.has(word) && !/^\d+$/.test(word));
    const parts = (meaningful.length ? meaningful : words).slice();
    let label = parts.join(" ");
    for (let i = 0; i < parts.length - 1 && label.length > SHORT_NAME_MAX; i++) {
        parts[i] = `${parts[i].charAt(0)}.`;
        label = parts.join(" ");
    }
    return label.length > SHORT_NAME_MAX ? parts[parts.length - 1] : label;
}

function getShortName(name) {
    if (!name) return "-";
    const clean = String(name).trim().toUpperCase();
    if (!clean) return "-";
    const normalized = clean.normalize("NFD").replace(/[\u0300-\u036f]/g, "");
    return shortNameLookup(SHORT_NAME_EXACT, clean)
        || shortNameLookup(SHORT_NAME_NORMALIZED, normalized)
        || shortNameFallback(normalized);
}

function normalizeName(text) {
    if (!text) return "";
    const cacheKey = String(text);
    if (normalizeCache.has(cacheKey)) return normalizeCache.get(cacheKey);
    const rawCollapsed = String(text)
        .toUpperCase()
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .replace(/[^A-Z0-9]/g, "");
    const normalized = String(text)
        .toUpperCase()
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .replace(/\b(REAL|CLUB|FC|CF|RC|RCD|CD|UD|SD|SAD|BALOMPIE|DEPORTIVO)\b/g, "")
        .replace(/[^A-Z0-9]/g, "");
    const aliases = {
        DEPOR: "LACORUNA",
        DEPORTIVO: "LACORUNA",
        DEPORTIVOLACORUNA: "LACORUNA",
        LACORUNA: "LACORUNA",
        ATMADRID: "ATLETICOMADRID",
        ATLETICOMADRID: "ATLETICOMADRID",
        CELTA: "CELTADEVIGO",
        CELTAVIGO: "CELTADEVIGO",
        CELTADEVIGO: "CELTADEVIGO",
        ESPANYOL: "ESPANYOL",
        RCDESPANYOL: "ESPANYOL",
        RCDESPANYOLDEBARCELONA: "ESPANYOL",
        OVIEDO: "OVIEDO",
        REALOVIEDO: "OVIEDO",
        RSOCIEDAD: "SOCIEDAD",
        REALSOCIEDAD: "SOCIEDAD",
        RAYO: "RAYOVALLECANO",
        RAYOVALLECANO: "RAYOVALLECANO",
        ALAVES: "ALAVES",
        DEPORTIVOALAVES: "ALAVES",
        RZARAGOZA: "ZARAGOZA",
        REALZARAGOZA: "ZARAGOZA",
        RACINGDESANTANDER: "RACINGSANTANDER",
        RACINGSANTANDER: "RACINGSANTANDER",
        UDLASPALMAS: "LASPALMAS"
    };
    const result = aliases[normalized] || aliases[rawCollapsed] || normalized;
    normalizeCache.set(cacheKey, result);
    return result;
}

function formatSmartDate(fechaRaw, horaRaw) {
    if (!fechaRaw && !horaRaw) return "Horario pendiente";
    const h = (horaRaw || "").toString().replace(/h$/i, "").trim();
    if (!fechaRaw) return h ? `${h}h` : "Horario pendiente";
    try {
        const d = new Date(String(fechaRaw).slice(0, 10) + "T12:00:00");
        if (isNaN(d.getTime())) return h ? `${h}h` : String(fechaRaw);
        const dias = ["dom", "lun", "mar", "mie", "jue", "vie", "sab"];
        const label = `${dias[d.getDay()]} ${String(d.getDate()).padStart(2, "0")}/${String(d.getMonth() + 1).padStart(2, "0")}`;
        return h ? `${label} ${h}h` : label;
    } catch {
        return h ? `${h}h` : String(fechaRaw || "");
    }
}

function fixtureScheduleDisplay(match) {
    const fecha = String(match?.fecha_raw || match?.fecha || match?.added || "").slice(0, 10);
    const hora = String(match?.hora || match?.scheduled || "").replace(/h$/i, "").trim();
    const serverToday = typeof state !== "undefined" ? String(state.data?.today_madrid || "") : "";
    if (fecha && serverToday && fecha === serverToday) return hora ? `${hora}h` : "Horario por confirmar";
    return formatSmartDate(fecha, hora);
}

/* El horario ("lun 17/08 19:00h") no cabe en una sola linea dentro de la celda
   de la quiniela: se parte en dia y hora para pintarlo en dos lineas y que la
   hora nunca quede recortada. */
function fixtureScheduleParts(match) {
    const label = String(fixtureScheduleDisplay(match) || "").trim();
    const parsed = /^(.*?)\s*(\d{1,2}:\d{2}h?)$/.exec(label);
    if (!parsed) return { day: label, time: "", label };
    return { day: parsed[1].trim(), time: parsed[2], label };
}

function hasUnconfirmedFixtureResult(match) {
    const display = String(match?.marcador || match?.score || "").toLowerCase();
    return display.includes("pendiente de resultado") && !scoreOnly(display);
}

function needsFixtureSchedule(match) {
    if (!match) return false;
    if (isScheduledStatus(match.status) || hasUnconfirmedFixtureResult(match)) return true;
    const hasScore = Boolean(scoreOnly(match.marcador || match.score || match.scores?.score))
        || (match.goles_local != null && match.goles_visitante != null);
    return isFinishedStatus(match.status) && !hasScore;
}

function isLiveStatus(status) {
    const raw = String(status || "").toUpperCase();
    return ["LIVE", "IN PLAY", "HT", "HALF TIME BREAK", "EN JUEGO", "1H", "2H"].includes(raw);
}

function isFinishedStatus(status) {
    const raw = String(status || "").toUpperCase();
    return ["FT", "FINISHED", "TERMINADO", "AET", "PEN", "STALE", "AWARDED"].includes(raw);
}

function isExpiredLiveMatch(match, maxAgeMs = 2 * 60 * 60 * 1000) {
    if (!match || !isLiveStatus(match.status)) return false;
    const kickoff = parseMatchTimestamp(match);
    if (!kickoff) return false;
    const elapsedMs = Date.now() - kickoff;
    if (elapsedMs < -5 * 60 * 1000) return true;
    const minute = matchMinuteValue(match);
    if (minute > 0 && minute > elapsedMs / 60000 + 15) return true;
    return elapsedMs > maxAgeMs;
}

function isScheduledStatus(status) {
    const raw = String(status || "").toUpperCase();
    return ["SCHEDULED", "NS", "NOT STARTED", ""].includes(raw);
}

function matchMinuteValue(match) {
    const direct = String(match.time || match.minute || match.minuto_live || "").match(/\d{1,3}/);
    if (direct) return Number(direct[0]);
    const score = String(match.marcador || match.score || match.scores?.score || "");
    const embedded = score.match(/\((\d{1,3})\s*['’]?\)/) || score.match(/\b(\d{1,3})\s*['’]/);
    return embedded ? Number(embedded[1]) : 0;
}

function isImplicitlyFinished(match) {
    if (!match) return false;
    if (String(match.marcador || "").toLowerCase().includes("pendiente de resultado")) return true;
    if (!isScheduledStatus(match.status)) return false;
    const ts = parseMatchTimestamp(match);
    if (!ts) return false;
    return Date.now() - ts > 2.5 * 60 * 60 * 1000;
}

function scoreOnly(value) {
    const raw = String(value || "").trim().toUpperCase();
    if (!raw || raw === "-") return null;
    const m = raw.match(/^([0-9M]+\s*[-–]\s*[0-9M]+)/);
    return m ? m[1].replace(/\s/g, "") : null;
}

function plenoScoreKey(value) {
    const only = scoreOnly(value);
    if (!only) return "";
    const parts = only.replace(/–/g, "-").split("-");
    if (parts.length !== 2) return "";
    const buckets = parts.map(goal => {
        if (goal === "M") return "M";
        const numeric = Number.parseInt(goal, 10);
        if (Number.isNaN(numeric) || numeric < 0) return "";
        return numeric >= 3 ? "M" : String(numeric);
    });
    return buckets.every(Boolean) ? buckets.join("-") : "";
}

function liveStage(match) {
    const st = String(match?.status || "").toUpperCase();
    if (st === "HT" || st === "HALF TIME BREAK") return "HT";
    return "LIVE";
}

function liveScoreAttrs(match, live) {
    if (!live) return "";
    return ` data-live-match="${match.id || ""}" data-live-minute="${matchMinuteValue(match)}" data-live-stage="${liveStage(match)}"`;
}

function liveScoreDisplay(match, fallbackScore = "") {
    if (match?.marcador_base) return match.marcador_base;
    if (match?.goles_local != null && match?.goles_visitante != null) {
        return `${match.goles_local}-${match.goles_visitante}`;
    }
    const only = scoreOnly(match?.marcador || match?.score);
    return only || fallbackScore || "-";
}

function isMatchLiveNow(match) {
    if (!match) return false;
    if (isFinishedStatus(match.status) || isImplicitlyFinished(match)) return false;
    if (isExpiredLiveMatch(match)) return false;
    return isLiveStatus(match.status) || Boolean(match.minuto_live);
}

function competitionLabel(match) {
    const candidates = [
        match?.competition_name,
        match?._competition_name,
        match?.competition,
        match?.liga,
        match?.league
    ];
    for (const candidate of candidates) {
        if (typeof candidate === "string" && candidate.trim()) return candidate.trim().toUpperCase();
        if (candidate && typeof candidate === "object") {
            const name = candidate.name || candidate.nombre || candidate.label;
            if (typeof name === "string" && name.trim()) return name.trim().toUpperCase();
        }
    }
    return "OTROS";
}

function matchCompetitionMeta(match) {
    return competitionLabel(match);
}

function getSign(preds, idx, primary, fallback) {
    const first = preds?.[primary]?.signos?.[idx];
    if (first && first !== "-") return normalizeSign(first);
    const alt = fallback ? preds?.[fallback]?.signos?.[idx] : null;
    return normalizeSign(alt);
}

function normalizeSign(value) {
    const raw = String(value || "-")
        .trim()
        .toUpperCase()
        .replace(/[–—]/g, "-")
        .replaceAll(" ", "");
    if (!raw || raw === "-") return "-";

    const pleno = plenoScoreKey(raw);
    if (pleno) return pleno;

    if (!/^[1X2]+$/.test(raw)) return "-";
    const ordered = ["1", "X", "2"].filter(sign => raw.includes(sign)).join("");
    return ordered || "-";
}

function standardSignMatches(sign, real) {
    const prediction = String(sign || "-").trim().toUpperCase();
    const result = String(real || "-").trim().toUpperCase();
    if (prediction === "-" || result === "-") return false;
    return prediction.includes(result);
}

function hitClass(sign, real, status, exactScore = false) {
    if (!sign || sign === "-") return "";
    if (isScheduledStatus(status) && !isImplicitlyFinished({ status, marcador: real })) return "";
    if (exactScore) {
        const userKey = plenoScoreKey(sign);
        const realKey = plenoScoreKey(real);
        if (!userKey || !realKey) return "";
        return userKey === realKey ? "hit hit-exact" : "miss";
    }
    if (!["1", "X", "2"].includes(normalizeSign(real))) return "";
    return standardSignMatches(sign, real) ? "hit" : "miss";
}

function isHitSign(sign, real, exactScore = false) {
    if (!sign || sign === "-") return false;
    if (exactScore) return plenoScoreKey(sign) === plenoScoreKey(real);
    return standardSignMatches(sign, real);
}

function formatKickoffShort(fechaRaw, horaRaw) {
    return formatSmartDate(fechaRaw, horaRaw);
}

function parseMatchTimestamp(match) {
    if (!match) return null;
    const fecha = match.fecha_raw || match.fecha || match.added || "";
    const timePart = (match.hora || match.scheduled || match.time || "").toString().replace(/h$/i, "").trim();
    if (!fecha && !timePart) return null;
    const isoDate = String(fecha).slice(0, 10);
    if (!isoDate || isoDate.length < 8) return null;
    // Combine the ISO date with the kickoff time part into a full timestamp.
    const ts = timePart
        ? new Date(`${isoDate}T${timePart}`).getTime()
        : new Date(`${isoDate}T12:00`).getTime();
    return Number.isNaN(ts) ? null : ts;
}

function isUpcomingScheduledMatch(match, graceMinutes = 15) {
    if (!isScheduledStatus(match?.status)) return false;
    const ts = parseMatchTimestamp(match);
    if (!ts) return false;
    return ts > Date.now() - graceMinutes * 60 * 1000;
}

function findMostOpenMatch() {
    const matches = (typeof getAllLeagueMatches === "function" ? getAllLeagueMatches() : []) || [];
    const open = matches.filter(m => isMatchLiveNow(m) || isUpcomingScheduledMatch(m));
    if (!open.length) return null;
    return open.sort((a, b) => (parseMatchTimestamp(a) || 0) - (parseMatchTimestamp(b) || 0))[0];
}

function sameSigns(a, b) {
    const left = Array.isArray(a) ? a : [];
    const right = Array.isArray(b) ? b : [];
    if (left.length !== right.length) return false;
    return left.every((sign, idx) => normalizeSign(sign) === normalizeSign(right[idx]));
}

function findQ15Directo(match) {
    if (!state?.q15Directo || !match) return {};
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
    return `<div class="q15-events">${withEvents.map(group => `<div class="q15-event-team"><b>${escapeHtml(getShortName(group.team))}</b>${(group.events || []).map(event => `<span class="q15-event"><em>${escapeHtml(eventTypeLabel(event.type))}</em><strong>${escapeHtml(event.minute || "")}</strong><span>${escapeHtml(event.player || "")}</span></span>`).join("")}</div>`).join("")}</div>`;
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
        programa: "PROG", gemini: "GEM", grok: "GROK", claude: "CLAU",
        copilot: "COP", chatgpt: "GPT", consejo: "CONS",
        pena: "PENA", "peña": "PENA", tu: "TU", "tú": "TU", boleto: "TU"
    };
    if (clean === "peña" || clean.includes("peña")) return "PENA";
    if (clean === "tú" || clean.includes("tú")) return "TU";
    return map[clean] || fullLabel.trim().slice(0, 4).toUpperCase();
}

function matchPairKey(match) {
    const home = normalizeName(match.local || match.home_name || match.home?.name || "");
    const away = normalizeName(match.visitante || match.away_name || match.away?.name || "");
    if (!home && !away) return "";
    return `${home}-${away}`;
}
