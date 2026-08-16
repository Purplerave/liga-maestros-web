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
    return only ? only.replace(/–/g, "-") : "";
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
    return (match?.competition || match?.liga || match?.league || "OTROS").toString().toUpperCase();
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
    const s = String(value || "-").trim().toUpperCase();
    if (s === "1" || s === "X" || s === "2") return s;
    return "-";
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
    const home = normalizeName(match.local || match.home_name || "");
    const away = normalizeName(match.visitante || match.away_name || "");
    return `${home}-${away}`;
}
