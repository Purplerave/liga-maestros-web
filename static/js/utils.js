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
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
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
        "CLUB ATLÃ‰TICO DE MADRID": "AT. MADRID",
        "REAL MADRID C.F.": "R. MADRID",
        "F.C. BARCELONA": "BARCA",
        "ATHLETIC CLUB BILBAO": "ATHLETIC",
        "REAL SOCIEDAD DE FUTBOL": "R. SOCIEDAD",
        "REAL SOCIEDAD DE FÃšTBOL": "R. SOCIEDAD",
        "VILLARREAL C.F.": "VILLARREAL",
        "REAL BETIS BALOMPIE": "BETIS",
        "REAL BETIS BALOMPIÃ‰": "BETIS",
        "DEPORTIVO ALAVES": "ALAVES",
        "DEPORTIVO ALAVÃ‰S": "ALAVES",
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
        "SPORTING GIJON": "SPORTING",
        "GETAFE CF": "GETAFE",
        "VALENCIA CF": "VALENCIA",
        "ELCHE CF": "ELCHE",
        "LEVANTE UD": "LEVANTE",
        "RCD MALLORCA": "MALLORCA",
        "GIRONA FC": "GIRONA",
        "MALAGA CF": "MALAGA",
        "CADIZ CF": "CADIZ"
    };
    return map[clean] || normalizedMap[normalized] || clean
        .replaceAll(" CLUB", "")
        .replaceAll("R.C.D. ", "")
        .replaceAll("F.C. ", "")
        .replaceAll("C.F. ", "");
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

/* ---------- Fechas y estados de partido ---------- */

function formatSmartDate(fechaRaw, horaRaw) {
    const fechaParts = String(fechaRaw || "").split(" ");
    const rawDate = fechaParts[0] || "";
    const embeddedHour = fechaParts[1]?.substring(0, 5) || "";
    const h = String(horaRaw || embeddedHour || "").substring(0, 5);
    if (!rawDate && !h) return "Horario pendiente";
    if (!rawDate) return `${escapeHtml(h)}h`;
    const iso = rawDate.includes("/") ? rawDate.split("/").reverse().join("-") : rawDate;
    const parts = iso.split("-");
    const hourLabel = h ? `${h}h` : "hora pendiente";
    if (parts.length < 3) return `${escapeHtml(rawDate)} ${escapeHtml(hourLabel)}`;
    const now = new Date();
    const today = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
    if (iso === today) return hourLabel;
    return `${parts[2]}/${parts[1]} ${hourLabel}`;
}

function formatStatus(status, time = "", scheduled = "") {
    const raw = String(status || "").toUpperCase();
    if (["SCHEDULED", "NS", "NOT STARTED", ""].includes(raw)) {
        const h = String(scheduled || time || "").substring(0, 5);
        return h ? `${h}h` : "Por jugar";
    }
    if (["FT", "FINISHED", "TERMINADO", "STALE"].includes(raw)) return "";
    if (["LIVE", "IN PLAY", "EN JUEGO"].includes(raw)) return time ? `En directo ${time}` : "En directo";
    if (raw === "HT" || raw === "HALF TIME BREAK") return "Descanso";
    return status || "";
}

function isPastScheduled(match) {
    const raw = String(match.status || "").toUpperCase();
    if (!["SCHEDULED", "NS", "NOT STARTED", ""].includes(raw)) return false;
    const dateText = String(match.added || match.fecha_raw || "").slice(0, 10);
    if (!dateText) return false;
    const now = new Date();
    const today = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
    return dateText < today;
}

function isLiveStatus(status) {
    const raw = String(status || "").toUpperCase();
    return ["LIVE", "IN PLAY", "EN JUEGO", "1H", "2H", "HT", "ET", "P", "SUSPENDED"].includes(raw);
}

function isFinishedStatus(status) {
    const raw = String(status || "").toUpperCase();
    return ["FT", "FINISHED", "TERMINADO", "AET", "PEN", "STALE", "AWARDED"].includes(raw);
}

function isScheduledStatus(status) {
    const raw = String(status || "").toUpperCase();
    return ["SCHEDULED", "NS", "NOT STARTED", ""].includes(raw);
}

function matchMinuteValue(match) {
    const direct = String(match.time || match.minute || "").match(/\d{1,3}/);
    if (direct) return Number(direct[0]);
    const score = String(match.marcador || match.score || match.scores?.score || "");
    const embedded = score.match(/\((\d{1,3})\s*['’]?\)/) || score.match(/\b(\d{1,3})\s*['’]/);
    return embedded ? Number(embedded[1]) : 0;
}

function isImplicitlyFinished(match) {
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
    const raw = String(value || "").trim().toUpperCase();
    const m = raw.match(/^([0-9M]+)\s*[-–]\s*([0-9M]+)$/);
    if (!m) return raw;
    const bucket = valuePart => valuePart === "M" || Number(valuePart) >= 3 ? "M" : String(Number(valuePart));
    return `${bucket(m[1])}-${bucket(m[2])}`;
}

/* ---------- Live score ---------- */

function liveStage(match) {
    const raw = String(match.status || "").toUpperCase();
    if (["HT", "HALF TIME BREAK"].includes(raw)) return "HT";
    if (["FT", "FINISHED", "TERMINADO"].includes(raw)) return "FT";
    if (["LIVE", "IN PLAY", "EN JUEGO", "1H", "2H", "ET", "P"].includes(raw)) return "LIVE";
    return "";
}

function liveScoreLabel(match) {
    const stage = liveStage(match);
    if (stage === "HT") return "Descanso";
    if (stage === "FT") return "";
    const minute = matchMinuteValue(match);
    if (minute) return `${minute}'`;
    if (stage === "LIVE") return "En vivo";
    return "";
}

function liveScoreAttrs(match, live) {
    if (!live) return "";
    const minute = matchMinuteValue(match);
    const stage = liveStage(match);
    const attrs = [`data-live-match="${match.id || ""}"`];
    if (minute) attrs.push(`data-live-minute="${minute}"`);
    if (stage) attrs.push(`data-live-stage="${stage}"`);
    return " " + attrs.join(" ");
}

function liveScoreDisplay(match, fallbackScore = "") {
    const rawScore = match.marcador || match.score || match.scores?.score || fallbackScore || "";
    const score = scoreOnly(rawScore) || rawScore;
    const minute = matchMinuteValue(match);
    const stage = liveStage(match);
    if (stage === "HT") return `${score} · Descanso`;
    if (minute) return `${score} · ${minute}'`;
    return score;
}

function isMatchLiveNow(match) {
    if (!match) return false;
    const status = String(match.status || "").toUpperCase();
    if (isLiveStatus(status)) return true;
    if (isLiveMatch(match)) return true;
    return false;
}

/* ---------- Competición ---------- */

function competitionLabel(match) {
    const raw = String(match.competition_name || match.competition?.name || "Liga").toUpperCase();
    const home = normalizeName(match.local || match.home_name || match.home?.name);
    const away = normalizeName(match.visitante || match.away_name || match.away?.name);
    const teams = `${home}|${away}`;
    const generic = ["LIGA", "COMPETICION", "FRIENDLIES", "FRIENDLIES CLUBS"].includes(raw);
    const norwegianTeams = ["BODOGLIMT", "FREDRIKSTAD", "HAMKAM", "TROMSOIL", "LILLESTROMSK", "KFUMOSLO", "KRISTIANSUND", "SARPSBORG", "START", "ROSENBORG", "MOLDEFK", "BRANN", "VIKING", "SANDEFJORD"];
    const swedishTeams = ["MJALLBY", "VASTERASSKFK", "AIK", "GAISGOTEBORG", "IFKGOTEBORG", "BROMMAPOJKARNA", "ELFSBORG", "SIRIUS", "HAMMARBY", "DEGERFORSIF", "HALMSTAD", "HACKEN", "KALMARFF", "MALMOE"];
    if (generic && norwegianTeams.some(team => teams.includes(team))) return "ELITESERIEN";
    if (generic && swedishTeams.some(team => teams.includes(team))) return "ALLSVENSKAN";
    const lowerTierHint = home.includes("ESTEPONA") || away.includes("ESTEPONA") || home.includes("MADRIDIII") || away.includes("MADRIDIII") || home.includes("REALMADRIDIII") || away.includes("REALMADRIDIII");
    if (raw === "SEGUNDA DIVISION" && lowerTierHint) return "SEGUNDA FEDERACION";
    if (raw === "SEGUNDA DIVISION") return "SEGUNDA DIVISION";
    return raw;
}

function matchCompetitionMeta(match) {
    const league = competitionLabel(match);
    const inferredCountry = league === "ELITESERIEN" ? "Noruega" : league === "ALLSVENSKAN" ? "Suecia" : "";
    const country = String(match.country || match.country_name || match.competition?.country?.name || inferredCountry).trim();
    const code = String(match.country_code || match.country?.code || match.competition?.country?.code || "").trim().toUpperCase();
    const cleanLeague = league === "LIGA" ? "COMPETICION" : league;
    const suffix = country || code;
    return suffix ? `${cleanLeague} - ${suffix}` : cleanLeague;
}

/* ---------- Signos y aciertos ---------- */

function getSign(preds, idx, primary, fallback) {
    const first = preds?.[primary]?.signos?.[idx];
    if (first && first !== "-") return first;
    const alt = fallback ? preds?.[fallback]?.signos?.[idx] : null;
    return alt || first || "-";
}

function normalizeSign(value) {
    const raw = String(value || "").trim().toUpperCase();
    if (raw === "0") return "X";
    if (raw && [...raw].every(char => ["1", "X", "2"].includes(char))) {
        return ["1", "X", "2"].filter(char => raw.includes(char)).join("");
    }
    return raw || "-";
}

function standardSignMatches(sign, real) {
    const prediction = normalizeSign(sign);
    const result = normalizeSign(real);
    return ["1", "X", "2"].includes(result) && prediction.includes(result);
}

function hitClass(sign, real, status, exactScore = false) {
    if (!sign || sign === "-") return "";
    if (isScheduledStatus(status) && !isImplicitlyFinished({ status })) return "";
    if (exactScore) {
        const userKey = plenoScoreKey(sign);
        const realKey = plenoScoreKey(real);
        return userKey === realKey ? "hit-exact" : "";
    }
    return standardSignMatches(sign, real) ? "hit" : "miss";
}

function isHitSign(sign, real, exactScore = false) {
    if (!sign || sign === "-") return false;
    if (exactScore) return plenoScoreKey(sign) === plenoScoreKey(real);
    return standardSignMatches(sign, real);
}

/* ---------- Timestamps ---------- */

function formatKickoffShort(fechaRaw, horaRaw) {
    const h = String(horaRaw || "").substring(0, 5);
    return h ? `${h}h` : "";
}

function parseMatchTimestamp(match) {
    const rawDate = String(match.added || match.fecha_raw || match.fecha || "").trim();
    if (!rawDate) return null;
    const datePart = rawDate.split(/[ T]/)[0];
    const isoDate = datePart.includes("/") ? datePart.split("/").reverse().join("-") : datePart;
    const embeddedTime = rawDate.match(/[ T](\d{1,2}:\d{2})/)?.[1] || "";
    const explicitTime = String(match.hora || match.scheduled || "").match(/\d{1,2}:\d{2}/)?.[0] || "";
    const timePart = explicitTime || embeddedTime || "00:00";
    const ts = new Date(`${isoDate}T${timePart}`).getTime();
    return Number.isNaN(ts) ? null : ts;
}

function isUpcomingScheduledMatch(match, graceMinutes = 15) {
    if (!isScheduledStatus(match.status)) return false;
    const ts = parseMatchTimestamp(match);
    if (!ts) return false;
    return ts > Date.now() - graceMinutes * 60 * 1000;
}

function findMostOpenMatch() {
    const matches = state.data?.partidos || [];
    const consenso = state.data?.consenso_pena || [];
    let best = null;
    let bestGap = Infinity;
    matches.slice(0, 14).forEach((m, idx) => {
        if (isFinishedStatus(m.status) || isLiveStatus(m.status)) return;
        const c = consenso.find(item => Number(item.id) === Number(m.id));
        if (!c) return;
        const values = [Number(c.p1 || 0), Number(c.px || 0), Number(c.p2 || 0)].sort((a, b) => b - a);
        const gap = values[0] - values[1];
        if (gap < bestGap) {
            bestGap = gap;
            best = { match: m, idx, gap };
        }
    });
    return best;
}

function sameSigns(a, b) {
    return JSON.stringify(a) === JSON.stringify(b);
}

/* ---------- Q15 Directo ---------- */

function findQ15Directo(match) {
    const matches = state.q15Directo.matches || [];
    const byId = matches.find(item => Number(item.id) === Number(match.id));
    if (byId) return byId;
    const home = normalizeName(match.local);
    const away = normalizeName(match.visitante);
    return matches.find(item => normalizeName(item.local) === home && normalizeName(item.visitante) === away) || null;
}

function eventTypeLabel(type) {
    const raw = String(type || "").toLowerCase();
    if (raw.includes("goal")) return "GOL";
    if (raw.includes("yellow")) return "AM";
    if (raw.includes("red")) return "ROJA";
    if (raw.includes("sub")) return "CAM";
    return "EV";
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
    for (let i = 0; i < 3 && /[ÃÃ‚]/.test(text); i += 1) {
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
        "peÃ±a": "PENA",
        tu: "TU",
        "tÃº": "TU",
        boleto: "TU"
    };
    if (clean === "peÃ±a" || clean.includes("peÃ±a")) return "PENA";
    if (clean === "tÃº" || clean.includes("tÃº")) return "TU";
    return map[clean] || fullLabel.trim().slice(0, 4).toUpperCase();
}

function matchPairKey(match) {
    const home = normalizeName(match.local || match.home_name || "");
    const away = normalizeName(match.visitante || match.away_name || "");
    return `${home}-${away}`;
}
