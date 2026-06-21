const state = {
    data: null,
    contest: null,
    jornada: new URLSearchParams(window.location.search).get("j") || "",
    user: null,
    my_signs: Array(15).fill("-"),
    server_signs: Array(15).fill("-"),
    draftDirty: false,
    editMode: false,
    lastUserEdit: 0,
    currentFilter: "ALL",
    contestView: "MATCHES",
    expandedMatch: null,
    q15Directo: {},
    evolutionChart: null,
    selectedAwardJornada: "",
    selectedAwardMonth: "",
    commentsOpen: false,
    commentsLastSeenId: 0
};

const initialView = new URLSearchParams(window.location.search).get("view");
if (initialView) state.currentFilter = initialView === "MATCHES" ? "ALL" : initialView;
const initialContest = new URLSearchParams(window.location.search).get("contest");
if (initialContest) state.contestView = initialContest;
if (state.currentFilter === "CONTEST") {
    state.currentFilter = "ALL";
    state.contestView = "CONTEST_PROFILE";
}

const AI_COLUMNS = [
    ["programa", "v260_omnisciente", "PROG"],
    ["consejo_ias", "consenso", "CONS"],
    ["gemini", null, "GEM"],
    ["grok", null, "GROK"],
    ["claude", null, "CLAU"],
    ["copilot", null, "COP"],
    ["chatgpt", null, "GPT"]
];

const COUNCIL_STYLE_JORNADAS = new Set(["67"]);

function isCouncilStyleJornada() {
    return COUNCIL_STYLE_JORNADAS.has(String(state.data?.jornada || state.jornada || ""));
}

function getVisibleAIColumns(matches = state.data?.partidos || []) {
    const preds = state.data?.predicciones_actuales || {};
    return AI_COLUMNS.filter(([primary, fallback]) =>
        matches.some((_, idx) => {
            const sign = getSign(preds, idx, primary, fallback);
            return sign && sign !== "-";
        })
    );
}

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
    const normalized = clean.normalize("NFD").replace(/[̀-ͯ]/g, "");
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

function teamToken(name) {
    const short = getShortName(name);
    const cleaned = short.replace(/[^A-Z0-9]/g, "");
    return cleaned.slice(0, 2) || "--";
}

function teamLogo(match, side) {
    if (!match) return "";
    const teamName = side === "home"
        ? (match.local || match.home_name || match.home?.name || "")
        : (match.visitante || match.away_name || match.away?.name || "");
    const direct = side === "home"
        ? (match.logo_local || match.home_logo || match.home?.logo || "")
        : (match.logo_visitante || match.away_logo || match.away?.logo || "");
    return direct || fixedTeamLogo(teamName);
}

function fixedTeamLogo(name) {
    const target = logoLookupKey(name);
    const contractLogos = state.data?.team_contract?.logos || {};
    for (const [rawName, logo] of Object.entries(contractLogos)) {
        if (logoLookupKey(rawName) === target && logo) return logo;
    }
    const fixedLogos = state.data?.team_logos || {};
    for (const [rawName, logo] of Object.entries(fixedLogos)) {
        if (logoLookupKey(rawName) === target && logo) return logo;
    }
    return TEAM_LOGO_FILES[target] || "";
}

const TEAM_LOGO_ALIASES = {
    "FC BARCELONA": "BARCELONA",
    "F C BARCELONA": "BARCELONA",
    "BARCA": "BARCELONA",
    "VILLARREAL CF": "VILLARREAL",
    "VILLARREAL C F": "VILLARREAL",
    "CLUB ATLETICO DE MADRID": "ATLETICO MADRID",
    "ATLETICO DE MADRID": "ATLETICO MADRID",
    "AT MADRID": "ATLETICO MADRID",
    "AT. MADRID": "ATLETICO MADRID",
    "GETAFE CF": "GETAFE",
    "VALENCIA CF": "VALENCIA",
    "ELCHE CF": "ELCHE",
    "LEVANTE UD": "LEVANTE",
    "CA OSASUNA": "OSASUNA",
    "CLUB ATLETICO OSASUNA": "OSASUNA",
    "RCD MALLORCA": "MALLORCA",
    "R C D MALLORCA": "MALLORCA",
    "GIRONA FC": "GIRONA",
    "MALAGA CF": "MALAGA",
    "RC DEPORTIVO": "DEPORTIVO LA CORUNA",
    "REAL CLUB DEPORTIVO": "DEPORTIVO LA CORUNA",
    "DEPORTIVO": "DEPORTIVO LA CORUNA",
    "R RACING CLUB": "RACING SANTANDER",
    "R. RACING CLUB": "RACING SANTANDER",
    "RACING CLUB": "RACING SANTANDER",
    "REAL RACING CLUB DE SANTANDER": "RACING SANTANDER",
    "R SANTANDER": "RACING SANTANDER",
    "R. SANTANDER": "RACING SANTANDER",
    "CADIZ CF": "CADIZ",
    "RCD ESPANYOL DE BARCELONA": "RCD ESPANYOL",
    "REAL CLUB DEPORTIVO ESPANYOL": "RCD ESPANYOL",
    "UD ALMERIA": "ALMERIA",
    "CD CASTELLON": "CASTELLON",
    "BURGOS CF": "BURGOS",
    "SD EIBAR": "EIBAR",
    "CORDOBA CF": "CORDOBA",
    "ALBACETE BP": "ALBACETE",
    "ALBACETE BALOMP": "ALBACETE",
    "REAL SPORTING": "SPORTING GIJON",
    "SPORTING": "SPORTING GIJON",
    "REAL VALLADOLID CF": "VALLADOLID",
    "CD LEGANES": "LEGANES",
    "CD MIRANDES": "MIRANDES",
    "SD HUESCA": "HUESCA",
    "CULTURAL Y DEPORTIVA LEONESA": "CULTURAL LEONESA",
    "C LEONESA": "CULTURAL LEONESA",
    "ALEMANIA": "GERMANY",
    "JAPON": "JAPAN",
    "ISLANDIA": "ICELAND",
    "FINLANDIA": "FINLAND",
    "INGLATERRA": "INGLATERRA",
    "ENGLAND": "INGLATERRA",
    "ESCOCIA": "ESCOCIA",
    "SCOTLAND": "ESCOCIA",
    "GALES": "GALES",
    "WALES": "GALES",
    "RUMANIA": "RUMANIA",
    "ROMANIA": "RUMANIA",
    "NUEVA ZELANDA": "NUEVA ZELANDA",
    "NEW ZEALAND": "NUEVA ZELANDA",
    "SUIZA": "SUIZA",
    "SWITZERLAND": "SUIZA",
    "TUNEZ": "TUNEZ",
    "TUNISIA": "TUNEZ",
    "MARRUECOS": "MARRUECOS",
    "MOROCCO": "MARRUECOS",
    "BELGIUM": "BELGICA",
    "BRAZIL": "BRASIL",
    "UNITED STATES": "EE UU",
    "USA": "EE UU",
    "ESTADOS UNIDOS": "EE UU",
    "COTE D IVOIRE": "COSTA DE MARFIL",
    "IVORY COAST": "COSTA DE MARFIL",
    "CURACAO": "CURACAO",
    "TURKEY": "TURQUIA",
    "TURKIYE": "TURQUIA",
    "IRAN": "IRAN",
    "FRANCE": "FRANCIA",
    "EGYPT": "EGIPTO",
    "SAUDI ARABIA": "ARABIA SAUDI",
    "CAPE VERDE": "CABO VERDE",
    "NETHERLANDS": "HOLANDA",
    "PAISES BAJOS": "HOLANDA"
};

const TEAM_LOGO_FILES = {
    "ATLETICOMADRID": "/static/img/team_logos/ATLETICO_MADRID.png",
    "OSASUNA": "/static/img/team_logos/OSASUNA.png",
    "CULTURALLEONESA": "/static/img/team_logos/CULTURAL_LEONESA.png",
    "SPORTINGGIJON": "/static/img/team_logos/SPORTING_GIJON.png",
    "ALBACETE": "/static/img/team_logos/ALBACETE.png",
    "LACORUNA": "/static/img/team_logos/DEPORTIVO_LA_CORUNA.png",
    "RACINGSANTANDER": "/static/img/team_logos/RACING_SANTANDER.png"
};

function logoLookupKey(name) {
    const key = normalizeName(name);
    const contractAliases = state.data?.team_contract?.aliases || {};
    for (const [rawName, canonicalName] of Object.entries(contractAliases)) {
        if (normalizeName(rawName) === key) return normalizeName(canonicalName);
    }
    for (const [rawName, canonicalName] of Object.entries(TEAM_LOGO_ALIASES)) {
        if (normalizeName(rawName) === key) return normalizeName(canonicalName);
    }
    return key;
}

function logoBadge(name, logo) {
    if (logo) {
        return `<span class="team-badge has-logo"><img src="${escapeHtml(logo)}" alt=""></span>`;
    }
    return `<span class="team-badge">${escapeHtml(teamToken(name))}</span>`;
}

function teamCell(name, side = "left", logo = "") {
    return `<div class="team-cell ${side}">
        ${logoBadge(name, logo)}
        <span class="match-team">${escapeHtml(getShortName(name))}</span>
    </div>`;
}

function fixtureInline(homeName, awayName, homeLogo = "", awayLogo = "") {
    return `<div class="fixture-inline">
        <span class="fixture-team">${logoBadge(homeName, homeLogo)}<span class="fixture-name">${escapeHtml(getShortName(homeName))}</span></span>
        <span class="fixture-sep">-</span>
        <span class="fixture-team">${logoBadge(awayName, awayLogo)}<span class="fixture-name">${escapeHtml(getShortName(awayName))}</span></span>
    </div>`;
}

function findStandingContext(teamName) {
    const standings = state.data?.standings || {};
    const needle = normalizeName(teamName);
    for (const cat of ["primera", "segunda"]) {
        for (const team of (standings[cat] || [])) {
            if (normalizeName(team.n) === needle) {
                return {
                    pos: team.pos ?? "-",
                    pts: team.pts ?? "-",
                    pj: team.pj ?? "-"
                };
            }
        }
    }
    return null;
}

function findQ15Directo(match) {
    const matches = state.q15Directo?.matches || [];
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
    const groups = detail?.events || [];
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

function pctTriplet(label, values) {
    if (!values) return "";
    const p1 = values["1"] ?? values[1] ?? "-";
    const px = values["X"] ?? values.x ?? values["x"] ?? "-";
    const p2 = values["2"] ?? values[2] ?? "-";
    return `<span class="insight-chip"><b>${escapeHtml(label)}</b> 1 ${escapeHtml(p1)}% | X ${escapeHtml(px)}% | 2 ${escapeHtml(p2)}%</span>`;
}

function renderMatchInsight(match) {
    const info = state.data?.match_info?.[String(match.id)] || {};
    const maestra = info.maestra || {};
    const chips = [
        pctTriplet("Tendencia", info.q15),
        pctTriplet("LAE", info.lae),
        pctTriplet("Mercado", info.apu)
    ].filter(Boolean).join("");
    const historico = info.historico
        ? `<small class="insight-muted">Histórico: ${escapeHtml(info.historico["1"] || 0)} local | ${escapeHtml(info.historico["X"] || 0)} empates | ${escapeHtml(info.historico["2"] || 0)} visitante</small>`
        : "";
    const reason = maestra.razon
        ? `<p class="insight-reason"><b>${escapeHtml(maestra.signo || "Maestra")}</b> ${escapeHtml(maestra.razon)}</p>`
        : "";
    const detail = info.detalle
        ? `<small class="insight-muted">${escapeHtml(info.detalle).slice(0, 220)}${String(info.detalle).length > 220 ? "..." : ""}</small>`
        : "";
    if (!chips && !reason && !historico && !detail) {
        return `<small class="q15-empty">Sin lectura previa cacheada para este partido.</small>`;
    }
    return `
        <div class="match-insight">
            ${reason}
            ${chips ? `<div class="insight-chips">${chips}</div>` : ""}
            ${historico}
            ${detail}
        </div>`;
}

function renderMatchDetail(m, c) {
    return `
        <div class="match-detail-row">
            ${renderMatchDetailGrid(m, c)}
        </div>`;
}

function renderMatchDetailGrid(m, c) {
    const homeCtx = findStandingContext(m.local);
    const awayCtx = findStandingContext(m.visitante);
    const homeLine = homeCtx
        ? `${getShortName(m.local)} | #${homeCtx.pos} | ${homeCtx.pts} pts`
        : `${getShortName(m.local)} | sin ranking`;
    const awayLine = awayCtx
        ? `${getShortName(m.visitante)} | #${awayCtx.pos} | ${awayCtx.pts} pts`
        : `${getShortName(m.visitante)} | sin ranking`;
    const plenoDetail = Number(m.id) === 15 ? renderPenaPlenoDetail(14) : null;
    return `
        <div class="match-detail-grid">
            <div class="match-detail-box">
                <span class="match-detail-label">La Peña</span>
                ${plenoDetail
                    ? plenoDetail
                    : `<strong>1 ${Number(c.p1 || 0)}% | X ${Number(c.px || 0)}% | 2 ${Number(c.p2 || 0)}%</strong>`}
            </div>
            <div class="match-detail-box">
                <span class="match-detail-label">Tabla</span>
                <strong>${escapeHtml(homeLine)}</strong>
                <small>${escapeHtml(awayLine)}</small>
            </div>
            <div class="match-detail-box match-detail-box-wide">
                <span class="match-detail-label">Lectura previa</span>
                ${renderMatchInsight(m)}
            </div>
            <div class="match-detail-box match-detail-box-wide">
                <span class="match-detail-label">Directo del partido</span>
                ${renderQ15Events(m)}
                ${renderQ15Meta(m)}
            </div>
        </div>`;
}

function normalizeName(text) {
    if (!text) return "";
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
    return aliases[normalized] || aliases[rawCollapsed] || normalized;
}

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
    if (["FT", "FINISHED", "TERMINADO"].includes(raw)) return "";
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

function competitionLabel(match) {
    const raw = String(match.competition_name || match.competition?.name || "Liga").toUpperCase();
    const home = normalizeName(match.local || match.home_name || match.home?.name);
    const away = normalizeName(match.visitante || match.away_name || match.away?.name);
    const lowerTierHint = home.includes("ESTEPONA") || away.includes("ESTEPONA") || home.includes("MADRIDIII") || away.includes("MADRIDIII") || home.includes("REALMADRIDIII") || away.includes("REALMADRIDIII");
    if (raw === "SEGUNDA DIVISION" && lowerTierHint) return "SEGUNDA FEDERACION";
    if (raw === "SEGUNDA DIVISION") return "SEGUNDA DIVISION";
    return raw;
}

function getSign(preds, idx, primary, fallback) {
    const first = preds?.[primary]?.signos?.[idx];
    const second = fallback ? preds?.[fallback]?.signos?.[idx] : null;
    return normalizeSign(first && first !== "-" ? first : (second || "-"));
}

function normalizeSign(value) {
    return String(value ?? "-").trim().toUpperCase();
}

function hitClass(sign, real, status, exactScore = false) {
    const cleanSign = normalizeSign(sign);
    const cleanReal = normalizeSign(real);
    if (!cleanReal || cleanReal === "-" || !cleanSign || cleanSign === "-") return "";
    const hit = exactScore
        ? Boolean(plenoScoreKey(cleanSign) && plenoScoreKey(cleanReal) && plenoScoreKey(cleanSign) === plenoScoreKey(cleanReal))
        : cleanSign.includes(cleanReal);
    const finished = isFinishedStatus(status);
    const live = isLiveStatus(status);
    if (finished) return hit ? "hit" : "miss";
    if (live) return hit ? "hit-live" : "miss";
    return "";
}

function isHitSign(sign, real, exactScore = false) {
    const cleanSign = normalizeSign(sign);
    const cleanReal = normalizeSign(real);
    if (!cleanReal || cleanReal === "-" || !cleanSign || cleanSign === "-") return false;
    if (exactScore) {
        return Boolean(plenoScoreKey(cleanSign) && plenoScoreKey(cleanReal) && plenoScoreKey(cleanSign) === plenoScoreKey(cleanReal));
    }
    return cleanSign.includes(cleanReal);
}

function isLiveStatus(status) {
    return ["LIVE", "IN PLAY", "HT", "EN JUEGO"].includes(String(status || "").toUpperCase());
}

function isFinishedStatus(status) {
    return ["FT", "FINISHED", "TERMINADO"].includes(String(status || "").toUpperCase());
}

function matchMinuteValue(match) {
    const raw = String(match?.time || "").trim();
    const m = raw.match(/(\d{1,3})/);
    return m ? Number.parseInt(m[1], 10) : 0;
}

function isImplicitlyFinished(match) {
    const score = scoreOnly(match?.score || match?.marcador || "");
    const minute = matchMinuteValue(match);
    return Boolean(score && minute >= 105);
}

function isScheduledStatus(status) {
    return ["NS", "SCHEDULED", "NOT STARTED", ""].includes(String(status || "").toUpperCase());
}

function scoreOnly(value) {
    const match = String(value || "").trim().match(/(\d+)\s*-\s*(\d+)/);
    return match ? `${match[1]}-${match[2]}` : "";
}

function plenoScoreKey(value) {
    const match = String(value || "").trim().toUpperCase().replace(/\s+/g, "").match(/([0-9M]+)-([0-9M]+)/);
    if (!match) return "";
    const bucket = part => {
        if (part === "M") return "M";
        const goals = Number.parseInt(part, 10);
        if (!Number.isFinite(goals)) return "";
        return goals >= 3 ? "M" : String(goals);
    };
    const home = bucket(match[1]);
    const away = bucket(match[2]);
    return home && away ? `${home}-${away}` : "";
}

function liveStage(match) {
    const text = String(match?.marcador || match?.time || "").toUpperCase();
    if (text.includes("DESC")) return "Desc.";
    const minute = text.match(/(\d+)'/);
    return minute ? `${minute[1]}'` : "Directo";
}

function changeJornada(jornada) {
    persistDraft();
    state.jornada = jornada;
    syncUrlState();
    refreshData();
}

function filterLeague(league) {
    state.currentFilter = !league || league === "MATCHES" ? "ALL" : league;
    state.contestView = "MATCHES";
    syncUrlState();
    renderArena();
    loadLeagueNav();
    hydrateContestNav();
    hydrateStandingsNav();
    updateWarRoomButton();
}

function currentMainView() {
    if (state.contestView !== "MATCHES") return "CONTEST";
    if (String(state.currentFilter || "").startsWith("STANDINGS_")) return "STANDINGS";
    if (state.currentFilter === "LIVE" || state.currentFilter === "WAR_ROOM") return "LIVE";
    if (state.currentFilter && state.currentFilter !== "ALL") return "LEAGUES";
    return "ALL";
}

function changeMainView(view) {
    const target = view || "ALL";
    if (target === "CONTEST") {
        state.currentFilter = "ALL";
        state.contestView = "CONTEST_GENERAL";
    } else if (target === "STANDINGS") {
        state.currentFilter = "STANDINGS_PRIMERA";
        state.contestView = "MATCHES";
    } else if (target === "LIVE") {
        state.currentFilter = "LIVE";
        state.contestView = "MATCHES";
    } else if (target === "LEAGUES") {
        const leagues = getAvailableLeagueOptions();
        state.currentFilter = leagues[0]?.[0] || "LIVE";
        state.contestView = "MATCHES";
    } else {
        state.currentFilter = "ALL";
        state.contestView = "MATCHES";
    }
    syncUrlState();
    renderArena();
    hydrateHero();
    loadLeagueNav();
    updateWarRoomButton();
}

function changeSecondaryView(value) {
    if (!value) return;
    if (String(value).startsWith("CONTEST_")) {
        changeContestView(value);
        return;
    }
    if (String(value).startsWith("STANDINGS_")) {
        changeStandingsView(value);
        return;
    }
    filterLeague(value);
}

function goHome() {
    state.currentFilter = "ALL";
    state.contestView = "MATCHES";
    syncUrlState();
    renderArena();
    hydrateHero();
    loadLeagueNav();
    hydrateContestNav();
    hydrateStandingsNav();
    updateWarRoomButton();
}

function changeContestView(view) {
    state.contestView = view || "MATCHES";
    if (state.contestView !== "MATCHES") {
        state.currentFilter = "ALL";
    }
    syncUrlState();
    renderArena();
    hydrateHero();
    loadLeagueNav();
    hydrateContestNav();
    hydrateStandingsNav();
    updateWarRoomButton();
}

function changeStandingsView(view) {
    if (!view || view === "MATCHES") {
        goHome();
        return;
    }
    state.currentFilter = view || "ALL";
    state.contestView = "MATCHES";
    syncUrlState();
    renderArena();
    loadLeagueNav();
    hydrateContestNav();
    hydrateStandingsNav();
    updateWarRoomButton();
}

function openProfileView() {
    state.contestView = "CONTEST_PROFILE";
    if (state.currentFilter === "WAR_ROOM") state.currentFilter = "ALL";
    syncUrlState();
    renderArena();
    hydrateHero();
    hydrateContestNav();
    updateWarRoomButton();
}

function changeAwardJornada(value) {
    state.selectedAwardJornada = value || "";
    renderArena();
}

function changeAwardMonth(value) {
    state.selectedAwardMonth = value || "";
    renderArena();
}

function syncUrlState() {
    try {
        const url = new URL(window.location.href);
        if (state.jornada) url.searchParams.set("j", state.jornada);
        if (state.currentFilter && state.currentFilter !== "ALL") url.searchParams.set("view", state.currentFilter);
        else url.searchParams.delete("view");
        if (state.contestView && state.contestView !== "MATCHES") url.searchParams.set("contest", state.contestView);
        else url.searchParams.delete("contest");
        window.history.replaceState({}, "", url.toString());
    } catch {}
}

async function refreshData(options = {}) {
    if (options.auto && Date.now() - state.lastUserEdit < 12000) return;
    const preserveLocalTicket = Boolean(options.auto && (state.editMode || state.draftDirty));
    try {
        const [userRes, dataRes, syncRes, contestRes] = await Promise.all([
            fetch("/api/user/status"),
            fetch(`/api/liga/data?j=${encodeURIComponent(state.jornada)}`),
            fetch(`/api/sync/status?j=${encodeURIComponent(state.jornada)}`),
            fetch(`/api/concurso?j=${encodeURIComponent(state.jornada)}`)
        ]);
        state.user = (await userRes.json()).user;
        state.data = await dataRes.json();
        state.contest = await contestRes.json();
        state.jornada = String(state.data.jornada || state.jornada);
        const sync = await syncRes.json();
        try {
            const q15Res = await fetch(`/api/q15/directo?j=${encodeURIComponent(state.jornada)}`);
            state.q15Directo = await q15Res.json();
        } catch {
            state.q15Directo = {};
        }
        if (state.currentFilter === "WAR_ROOM" && !hasLiveLeagueMatches()) {
            state.currentFilter = "ALL";
            syncUrlState();
        }

        hydrateJornadaNav();
        hydrateUserSigns({ preserveLocalTicket });
        hydrateStatus(sync);
        hydrateHero();
        updateAuthUI();
        updateWarRoomButton();
        renderArena();
        renderPrestigeRanking();
        renderLiveStandings();
        loadComments();
        renderEvolutionChart();
        loadLeagueNav();
        hydrateContestNav();
        hydrateStandingsNav();
    } catch (error) {
        console.error(error);
        const body = qs("matches-body");
        if (body) body.innerHTML = `<div class="empty-state">No se pudo cargar la Arena. Revisa que Flask y la base de datos esten activos.</div>`;
    }
}

function hydrateJornadaNav() {
    const nav = qs("jornada-nav");
    if (!nav || !state.data) return;
    const max = Number(state.data.max_jornada || state.data.jornada || 64);
    const min = Math.max(1, max - 14);
    nav.innerHTML = "";
    for (let i = max; i >= min; i--) {
        const opt = document.createElement("option");
        opt.value = String(i);
        opt.textContent = `Jornada ${i}`;
        opt.selected = String(i) === String(state.data.jornada);
        nav.appendChild(opt);
    }
}

function hydrateStatus(sync) {
    const statLive = qs("stat-live");
    const statPending = qs("stat-pending");
    const statSync = qs("stat-sync");
    const statApi = qs("stat-api");
    const liveMatches = Number(sync.live_matches ?? 0);
    if (statLive) statLive.textContent = liveMatches;
    if (statPending) statPending.textContent = sync.pending_matches ?? 0;
    if (statSync) statSync.textContent = sync.last_sync ?? "--:--";
    if (statApi) {
        const usage = sync.api_usage || {};
        statApi.textContent = `${usage.calls ?? 0}/${usage.limit ?? 7500}`;
        statApi.title = `Quedan ${usage.remaining ?? "-"} llamadas; reserva ${usage.reserve ?? "-"}`;
    }
    document.body.classList.toggle("live-now", liveMatches > 0);
}

function hydrateHero() {
    if (!state.data) return;
    const title = state.contestView !== "MATCHES"
        ? contestViewTitle(state.contestView)
        : state.currentFilter === "ALL"
        ? "Quiniela oficial"
        : state.currentFilter === "LIVE"
            ? "Partidos en directo"
            : state.currentFilter === "WAR_ROOM"
                ? "Directo"
                : state.currentFilter === "STANDINGS_FULL"
                    ? "Clasificaciones"
                    : state.currentFilter === "STANDINGS_PRIMERA"
                    ? "Clasificacion Primera"
                    : state.currentFilter === "STANDINGS_SEGUNDA"
                    ? "Clasificacion Segunda"
                : state.currentFilter;
    const arenaTitle = qs("arena-title");
    const arenaKicker = qs("arena-kicker");
    const topbarTitle = qs("topbar-title");
    const topbarKicker = qs("topbar-kicker");
    if (arenaTitle) arenaTitle.textContent = title;
    if (arenaKicker) arenaKicker.textContent = `Jornada ${state.data.jornada}`;
    if (topbarTitle) topbarTitle.textContent = title;
    if (topbarKicker) topbarKicker.textContent = `Jornada ${state.data.jornada}`;
    const save = qs("save-quiniela-btn");
    if (save) {
        const canSave = Boolean(state.user) && String(state.data.jornada) === String(state.data.max_jornada) && !state.data.is_locked;
        const hasSaved = hasSavedTicket();
        save.hidden = !state.user;
        save.disabled = !canSave;
        if (!canSave) {
            save.textContent = "Cerrada";
        } else if (hasSaved && !state.editMode && !state.draftDirty) {
            save.textContent = "Editar quiniela";
        } else {
            save.textContent = hasSaved ? "Guardar cambios" : "Guardar quiniela";
        }
    }
    const share = qs("share-ticket-btn");
    if (share) {
        share.hidden = !state.user;
        share.disabled = !state.data?.partidos?.length;
    }
    updatePicksProgress();
    updateHeroStrip();
}

function updateWarRoomButton() {
    const btn = qs("warroom-btn");
    if (!btn) return;
    if (state.contestView !== "MATCHES") {
        btn.hidden = true;
        return;
    }
    const liveAvailable = hasLiveLeagueMatches();
    if (!liveAvailable && state.currentFilter !== "WAR_ROOM") {
        btn.hidden = true;
        return;
    }
    btn.hidden = false;
    const active = state.currentFilter === "WAR_ROOM";
    btn.classList.toggle("is-active", active);
    btn.textContent = active ? "↩" : "◫";
    btn.title = active ? "Volver a la quiniela" : "Abrir Modo Directo";
}

function isContestView(value) {
    return String(value || "").startsWith("CONTEST_");
}

function contestViewTitle(value) {
    return {
        CONTEST_PROFILE: "Mi perfil",
        CONTEST_GENERAL: "La Peña general",
        CONTEST_MONTHLY: "La Peña mensual",
        CONTEST_JORNADA: "La Peña jornada",
        CONTEST_AWARDS: "Galardones"
    }[value] || "La Peña";
}

function getAllLeagueMatches() {
    return state.data?.all_league_matches || [];
}

function isLiveMatch(match) {
    const status = String(match?.status || "").toUpperCase();
    if (isImplicitlyFinished(match)) return false;
    if (status.includes("LIVE") || status === "IN PLAY" || status === "HT" || status === "EN JUEGO") return true;
    const score = scoreOnly(match?.score || match?.marcador || "");
    if (score && !isFinishedStatus(status)) return true;
    const dateText = String(match?.added || match?.fecha_raw || "").slice(0, 10);
    const now = new Date();
    const today = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
    return Boolean(score && dateText === today && !isFinishedStatus(status));
}

function getLiveLeagueMatches() {
    const officialLive = (state.data?.partidos || []).filter(m => isLiveStatus(m.status) || isLiveMatch(m));
    const seen = new Set(officialLive.map(matchPairKey));
    const externalLive = getAllLeagueMatches()
        .filter(m => isLiveStatus(m.status) || isLiveMatch(m))
        .filter(m => competitionLabel(m) !== "FRIENDLIES")
        .filter(m => {
            const key = matchPairKey(m);
            if (!key || seen.has(key)) return false;
            seen.add(key);
            return true;
        });
    return [...officialLive, ...externalLive];
}

function hasLiveLeagueMatches() {
    return getLiveLeagueMatches().length > 0;
}

function getNextLeagueMatch() {
    const officialNext = (state.data?.partidos || [])
        .filter(m => isUpcomingScheduledMatch(m))
        .sort((a, b) => parseMatchTimestamp(a) - parseMatchTimestamp(b))[0];
    if (officialNext) return officialNext;
    return getAllLeagueMatches()
        .filter(m => isUpcomingScheduledMatch(m))
        .filter(m => competitionLabel(m) !== "FRIENDLIES")
        .sort((a, b) => parseMatchTimestamp(a) - parseMatchTimestamp(b))[0] || null;
}

function hasSavedTicket() {
    return state.server_signs.some(sign => sign && sign !== "-");
}

function draftKey() {
    const owner = state.user?.id || "anon";
    const jornada = state.data?.jornada || state.jornada || "actual";
    return `liga_maestros_borrador_${owner}_${jornada}`;
}

function commentsSeenKey(jornada = state.data?.jornada || state.jornada || "actual") {
    return `liga_maestros_comments_seen_${jornada}`;
}

function readSeenCommentId(jornada = state.data?.jornada || state.jornada || "actual") {
    try {
        return Number(window.localStorage.getItem(commentsSeenKey(jornada)) || "0");
    } catch {
        return 0;
    }
}

function writeSeenCommentId(value, jornada = state.data?.jornada || state.jornada || "actual") {
    state.commentsLastSeenId = Number(value || 0);
    try {
        window.localStorage.setItem(commentsSeenKey(jornada), String(value));
    } catch {}
}

function setCommentsOpen(nextOpen) {
    state.commentsOpen = Boolean(nextOpen);
    const panel = document.querySelector(".comments-panel-side");
    const content = qs("comments-panel-content");
    if (panel) panel.classList.toggle("is-open", state.commentsOpen);
    if (content) content.hidden = !state.commentsOpen;
}

function hydrateCommentsPanel() {
    state.commentsOpen = false;
    state.commentsLastSeenId = readSeenCommentId();
    setCommentsOpen(state.commentsOpen);
}

function updatePicksProgress() {
    const done = state.my_signs.filter(sign => String(sign || "-").trim() !== "-").length;
    const total = 15;
    const doneNode = qs("picks-done");
    const captionNode = qs("picks-caption");
    const barNode = qs("picks-progress-bar");
    if (doneNode) doneNode.textContent = `${done}/${total}`;
    if (barNode) barNode.style.width = `${(done / total) * 100}%`;
    if (captionNode) {
        captionNode.textContent = done === 0
            ? "Todavia no has marcado ningun partido."
            : done === total
                ? "Quiniela completa. Ya puedes guardarla."
                : `Te faltan ${total - done} partido${total - done === 1 ? "" : "s"} por cerrar.`;
    }
}

function updateHeroStrip() {
    const picksNode = qs("hero-picks");
    const nextNode = qs("hero-next");
    const alertNode = qs("hero-alert");
    const done = state.my_signs.filter(sign => String(sign || "-").trim() !== "-").length;
    if (picksNode) picksNode.textContent = `${done}/15`;

    const partidos = state.data?.partidos || [];
    const nextMatch = partidos.find(match => isScheduledStatus(match.status));
    if (nextNode) {
        nextNode.textContent = nextMatch
            ? `${getShortName(nextMatch.local)} ${formatKickoffShort(nextMatch.fecha_raw, nextMatch.hora)}`
            : "Jornada en juego";
    }

    if (!alertNode) return;
    const liveCount = partidos.filter(match => isLiveStatus(match.status)).length;
    if (liveCount > 0) {
        alertNode.textContent = `${liveCount} en directo`;
        return;
    }
    const openMatch = findMostOpenMatch();
    if (openMatch) {
        alertNode.textContent = `${getShortName(openMatch.local)} abierto`;
        return;
    }
    alertNode.textContent = done === 15 ? "Quiniela lista" : "Marca tu quiniela";
}

function formatKickoffShort(fechaRaw, horaRaw) {
    const hour = String(horaRaw || "").slice(0, 5);
    const datePart = String(fechaRaw || "").split(" ")[0];
    if (!datePart) return hour || "--:--";
    const iso = datePart.includes("/") ? datePart.split("/").reverse().join("-") : datePart;
    const now = new Date();
    const today = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
    return iso === today ? (hour || "hoy") : `${iso.slice(5).replace("-", "/")} ${hour || ""}`.trim();
}

function parseMatchTimestamp(match) {
    const rawDate = String(match?.added || match?.fecha_raw || "").split(" ")[0].trim();
    const rawHour = String(match?.scheduled || match?.time || match?.hora || "").trim().slice(0, 5);
    if (!rawDate) return Number.MAX_SAFE_INTEGER;
    const isoDate = rawDate.includes("/") ? rawDate.split("/").reverse().join("-") : rawDate;
    const clock = /^\d{2}:\d{2}$/.test(rawHour) ? rawHour : "23:59";
    const dt = new Date(`${isoDate}T${clock}:00`);
    const ts = dt.getTime();
    return Number.isNaN(ts) ? Number.MAX_SAFE_INTEGER : ts;
}

function isUpcomingScheduledMatch(match, graceMinutes = 15) {
    if (!isScheduledStatus(match?.status) || isImplicitlyFinished(match) || isLiveMatch(match)) return false;
    const ts = parseMatchTimestamp(match);
    if (!Number.isFinite(ts) || ts === Number.MAX_SAFE_INTEGER) return false;
    return ts >= Date.now() - (graceMinutes * 60 * 1000);
}

function findMostOpenMatch() {
    const partidos = state.data?.partidos || [];
    const consenso = state.data?.consenso_pena || [];
    let best = null;
    let bestGap = Infinity;
    for (const match of partidos) {
        if (isFinishedStatus(match.status) || isLiveStatus(match.status)) continue;
        const c = consenso.find(item => Number(item.id) === Number(match.id));
        if (!c) continue;
        const values = [Number(c.p1 || 0), Number(c.px || 0), Number(c.p2 || 0)].sort((a, b) => b - a);
        if (!values[0]) continue;
        const gap = values[0] - values[1];
        if (gap < bestGap) {
            bestGap = gap;
            best = match;
        }
    }
    return best;
}

function sameSigns(a, b) {
    return JSON.stringify(a || []) === JSON.stringify(b || []);
}

function readDraft() {
    try {
        const raw = window.localStorage.getItem(draftKey());
        if (!raw) return null;
        const draft = JSON.parse(raw);
        return Array.isArray(draft.signos) && draft.signos.length === 15 ? draft.signos : null;
    } catch {
        return null;
    }
}

function persistDraft() {
    if (!state.data) return;
    try {
        window.localStorage.setItem(draftKey(), JSON.stringify({
            jornada: state.data.jornada,
            signos: state.my_signs,
            updated_at: new Date().toISOString()
        }));
    } catch {}
}

function clearDraft() {
    try {
        window.localStorage.removeItem(draftKey());
    } catch {}
    state.draftDirty = false;
}

function hydrateUserSigns({ preserveLocalTicket = false } = {}) {
    const serverSigns = Array(15).fill("-");
    if (state.user && state.data?.predicciones_actuales?.[state.user.id]?.signos) {
        state.data.predicciones_actuales[state.user.id].signos.forEach((sign, idx) => {
            serverSigns[idx] = sign || "-";
        });
    }
    state.server_signs = serverSigns;
    if (preserveLocalTicket) {
        state.my_signs = Array.isArray(state.my_signs) && state.my_signs.length ? state.my_signs : serverSigns;
        state.draftDirty = !sameSigns(state.my_signs, serverSigns);
        return;
    }
    const draft = readDraft();
    state.my_signs = draft || serverSigns;
    state.draftDirty = Boolean(draft && !sameSigns(draft, serverSigns));
    if (!state.draftDirty && hasSavedTicket()) state.editMode = false;
}

function updateAuthUI() {
    const navAuth = qs("user-profile-nav");
    if (!navAuth) return;
    if (!state.user) {
        navAuth.innerHTML = `<a class="login-btn topbar-login-btn" href="/login/google">Entrar</a>`;
        return;
    }
    const stats = state.data?.ranking_maestros?.[state.user.id] || { total: 0, jornada: 0 };
    const profile = state.contest?.profile || {};
    const points = Number(stats.total ?? profile.hits ?? 0);
    const rank = profile.position ?? getUserRankingPosition();
    const rankText = rank ? `#${rank}` : "-";
    const firstName = String(state.user.name || "Maestro").split(" ")[0];
    navAuth.innerHTML = `
        <div class="topbar-user-summary" title="${escapeHtml(`${stats.jornada || 0} aciertos en la jornada actual`)}">
            <button class="topbar-user-name profile-link" type="button" onclick="openProfileView()">${escapeHtml(firstName)}</button>
            <span class="topbar-user-score topbar-user-points"><b>${points}</b> pts</span>
            <span class="topbar-user-score topbar-user-rank"><b>${escapeHtml(rankText)}</b> ranking</span>
        </div>
        <a class="logout-link compact-logout" href="/logout">Salir</a>`;
}

function getUserRankingPosition() {
    if (!state.user) return null;
    const uid = String(state.user.id);
    const ranking = state.data?.ranking_maestros || {};
    const rows = Object.entries(ranking)
        .map(([id, stats]) => ({
            id,
            total: Number(stats?.total || 0),
            jornada: Number(stats?.jornada || 0)
        }))
        .sort((a, b) => b.total - a.total || b.jornada - a.jornada || a.id.localeCompare(b.id));
    const idx = rows.findIndex(row => String(row.id) === uid);
    if (idx >= 0) return idx + 1;
    const contestRow = (state.contest?.general || []).find(row => String(row.id) === uid || row.is_user);
    return contestRow?.pos || null;
}

async function loadLeagueNav() {
    const nav = qs("league-nav");
    if (!nav) return;
    hydrateMainViewNav();
    hydrateSecondaryNav();
}

function hydrateMainViewNav() {
    const nav = qs("league-nav");
    if (!nav) return;
    const options = [
        ["ALL", "La Quiniela"],
        ["LIVE", `Directo (${getLiveLeagueMatches().length})`],
        ["LEAGUES", "Ligas"],
        ["CONTEST", "La Peña"],
        ["STANDINGS", "Clasificaciones"]
    ];
    const selected = currentMainView();
    nav.innerHTML = options.map(([value, label]) =>
        `<option value="${escapeHtml(value)}" ${selected === value ? "selected" : ""}>${escapeHtml(label)}</option>`
    ).join("");
}

function getAvailableLeagueOptions() {
    const allMatches = state.data?.all_league_matches || [];
    const counts = allMatches.reduce((acc, match) => {
        const key = competitionLabel(match);
        acc[key] = (acc[key] || 0) + 1;
        return acc;
    }, {});
    return Object.keys(counts)
        .sort((a, b) => a.localeCompare(b))
        .map(key => [key, `${key.replaceAll("_", " ")} (${counts[key]})`]);
}

function hydrateSecondaryNav() {
    const nav = qs("contest-nav");
    const group = nav?.closest(".field-group");
    const filters = qs("league-nav")?.closest(".topbar-filters");
    if (!nav || !group) return;
    const main = currentMainView();
    let options = [];
    let selected = "";
    let placeholder = "Detalle";

    if (main === "CONTEST") {
        placeholder = "La Peña";
        selected = state.contestView;
        options = [
            ["CONTEST_GENERAL", "General"],
            ["CONTEST_MONTHLY", "Mensual"],
            ["CONTEST_JORNADA", "Jornada"],
            ["CONTEST_AWARDS", "Galardones"]
        ];
    } else if (main === "STANDINGS") {
        placeholder = "Clasificación";
        selected = state.currentFilter;
        options = [
            ["STANDINGS_PRIMERA", "Primera"],
            ["STANDINGS_SEGUNDA", "Segunda"]
        ];
    } else if (main === "LEAGUES") {
        placeholder = "Liga";
        selected = state.currentFilter;
        options = getAvailableLeagueOptions();
    }

    const hasOptions = options.length > 0;
    group.classList.toggle("is-hidden", !hasOptions);
    filters?.classList.toggle("has-secondary", hasOptions);
    if (!hasOptions) {
        nav.innerHTML = "";
        return;
    }
    nav.innerHTML = [
        `<option value="" disabled hidden>${escapeHtml(placeholder)}</option>`,
        ...options.map(([value, label]) =>
            `<option value="${escapeHtml(value)}" ${selected === value ? "selected" : ""}>${escapeHtml(label)}</option>`
        )
    ].join("");
    if (options.some(([value]) => value === selected)) {
        nav.value = selected;
    }
}

function matchPairKey(match) {
    const home = match?.local || match?.home_name || match?.home?.name || "";
    const away = match?.visitante || match?.away_name || match?.away?.name || "";
    const a = logoLookupKey(home);
    const b = logoLookupKey(away);
    return a && b ? `${a}__${b}` : "";
}

function hydrateContestNav() {
    hydrateSecondaryNav();
}

function hydrateStandingsNav() {
    hydrateSecondaryNav();
}

function renderArena() {
    const container = qs("matches-body");
    if (!container || !state.data) return;
    hydrateHero();
    updateTopbarLiveTicker();
    renderSidebarRadar();
    document.body.classList.remove("standings-focus");

    if (state.currentFilter === "WAR_ROOM") {
        container.className = "arena-content warroom-content";
        container.innerHTML = renderWarRoom();
        return;
    }

    if (state.contestView !== "MATCHES") {
        container.className = "arena-content contest-page-mode";
        container.innerHTML = renderContestPage(state.contestView);
        return;
    }

    if (state.currentFilter === "STANDINGS_FULL" || state.currentFilter === "STANDINGS_PRIMERA" || state.currentFilter === "STANDINGS_SEGUNDA") {
        container.className = "arena-content standings-full-mode";
        container.innerHTML = renderFullStandingsPage();
        return;
    }

    if (state.currentFilter === "ALL") {
        const matches = state.data.partidos || [];
        container.className = "arena-content table-mode";
        container.innerHTML = `
            ${renderLiveScrutinyBadge(matches)}
            <div class="arena-table-wrap">
                <table class="arena-table">
                    <thead id="arena-thead"></thead>
                    <tbody id="arena-body"></tbody>
                </table>
            </div>`;
        renderArenaTensionBody(matches);
        return;
    }

    const allMatches = state.data.all_league_matches || [];
    const matches = state.currentFilter === "LIVE"
        ? getLiveLeagueMatches()
        : allMatches.filter(m => competitionLabel(m) === state.currentFilter.toUpperCase());

    container.className = "arena-content arena-grid";
    if (matches.length === 0) {
        container.innerHTML = `<div class="empty-state">No hay partidos para ${escapeHtml(state.currentFilter)}.</div>`;
        return;
    }
    container.innerHTML = matches.map(renderMatchCard).join("");
}

function renderArenaTensionBody(matches) {
    const tbody = qs("arena-body");
    const thead = qs("arena-thead");
    if (!tbody || !thead) return;

    const councilStyle = isCouncilStyleJornada();
    thead.innerHTML = `
        <tr>
            <th>#</th>
            <th style="text-align:left;">Partido</th>
            <th>${councilStyle ? "Programa · Consejo · Peña · Tu quiniela" : "Consenso + signos"}</th>
        </tr>`;

    const preds = state.data?.predicciones_actuales || {};
    const consenso = state.data?.consenso_pena || [];
    const canEdit = Boolean(state.user) && String(state.data?.jornada) === String(state.data?.max_jornada) && !state.data?.is_locked;

    tbody.innerHTML = matches.map((m, idx) => {
        const isPleno = idx === 14;
        const real = m.signo_actual || "-";
        const realScore = scoreOnly(m.marcador);
        const mySign = state.my_signs[idx] || "-";
        const c = consenso.find(item => Number(item.id) === Number(m.id)) || { p1: 0, px: 0, p2: 0, ganador: "-" };
        const consensoPleno = getPenaPlenoSummary(idx);
        const liveMatch = isLiveStatus(m.status);
        const scheduledMatch = isScheduledStatus(m.status);
        const score = scheduledMatch ? formatSmartDate(m.fecha_raw, m.hora) : (m.marcador || "-");
        const mine = renderMyCell(idx, mySign, isPleno ? m.marcador : real, m.status, canEdit, isPleno);
        const isFinished = isFinishedStatus(m.status);
        const values = [Number(c.p1 || 0), Number(c.px || 0), Number(c.p2 || 0)].sort((a, b) => b - a);
        const splitMatch = idx !== 14 && !isFinished && values[0] > 0 && values[0] - values[1] <= 12;
        const rowClass = [
            councilStyle ? "is-council-row" : "",
            liveMatch ? "is-live-row" : (isFinished ? "is-finished-row" : ""),
            splitMatch ? "is-split-row" : ""
        ].filter(Boolean).join(" ");
        const statusText = scheduledMatch ? score : "";
        const tension = getMatchTensionInfo(m, idx, c, preds, mySign);
        const scoreBadge = scheduledMatch
            ? ""
            : `<span class="match-score-badge ${liveMatch ? "is-live-score" : ""}">${escapeHtml(score)}</span>`;
        const penaChip = isPleno
            ? renderTensionPenaChip(renderPenaPleno(consensoPleno, m.marcador, m.status), "Peña")
            : renderTensionPenaChip(renderConsensus(c, real, m.status), "Peña");

        return `
            <tr class="tension-row ${rowClass}">
                <td class="match-index-cell">
                    <span class="match-number">${idx + 1}</span>
                </td>
                <td class="fixture-cell tension-fixture-cell">
                    <div class="tension-fixture-layout">
                        <div class="tension-fixture-main">
                            ${fixtureInline(m.local, m.visitante, teamLogo(m, "home"), teamLogo(m, "away"))}
                        </div>
                        <div class="tension-meta-line">
                            ${scoreBadge}
                            ${statusText ? `<span class="tension-status">${escapeHtml(statusText)}</span>` : ""}
                        </div>
                    </div>
                </td>
                <td class="tension-consensus-cell">
                    ${renderConsensusBar(c, isPleno)}
                    <div class="tension-sign-row">
                        ${councilStyle
                            ? renderCouncilStyleChips(preds, idx, isPleno ? m.marcador : real, m.status, isPleno)
                            : renderTensionAiChips(preds, idx, isPleno ? m.marcador : real, m.status, isPleno)}
                        ${penaChip}
                        <div class="tension-chip tension-chip-user"><span>Tú</span>${mine}</div>
                    </div>
                </td>
            </tr>
            ${state.expandedMatch === idx ? `
                <tr class="match-detail-row">
                    <td colspan="3">
                        ${renderMatchDetailGrid(m, c)}
                    </td>
                </tr>` : ""}`;
    }).join("");
}

function getMatchTensionInfo(match, idx, consensus, preds, mySign) {
    const isPleno = idx === 14;
    const values = [
        ["1", Number(consensus.p1 || 0)],
        ["X", Number(consensus.px || 0)],
        ["2", Number(consensus.p2 || 0)]
    ].sort((a, b) => b[1] - a[1]);
    const rawWinner = normalizeSign(consensus.ganador);
    const winner = ["1", "X", "2"].includes(rawWinner) ? rawWinner : values[0][0];
    const gap = values[0][1] - values[1][1];
    const programSign = getSign(preds, idx, "programa", "v260_omnisciente");
    const maestro = pickFeaturedMaster(preds, idx);
    const signs = AI_COLUMNS.map(([primary, fallback]) => getSign(preds, idx, primary, fallback))
        .concat([mySign])
        .map(normalizeSign)
        .filter(sign => sign && sign !== "-");
    const disagreements = signs.filter(sign => {
        if (isPleno) return sign !== programSign;
        return sign !== winner;
    }).length;

    let badge = "";
    if (isPleno) badge = "Pleno caliente";
    else if (programSign && programSign !== "-" && programSign !== winner) badge = "Golpe del programa";
    else if (winner === "X" && Number(consensus.px || 0) >= 28) badge = "Empate oculto";
    else if (values[0][1] >= 60 && gap >= 24) badge = "Fijo";
    else if (disagreements >= 3) badge = "Partido dividido";
    else if (gap <= 10 && values[0][1] > 0) badge = "Partido abierto";
    else if (gap <= 16 && values[0][1] > 0) badge = "Trampa del consenso";

    return {
        badge,
        disagreements,
        programSign,
        maestroSign: maestro.sign,
        maestroLabel: maestro.label
    };
}

function renderLiveScrutinyBadge(matches) {
    if (!state.user || !Array.isArray(matches) || !matches.some(match => isLiveStatus(match.status))) return "";
    const hits = matches.slice(0, 15).reduce((count, match, idx) => {
        const exactScore = idx === 14;
        const real = exactScore ? scoreOnly(match.marcador) : (match.signo_actual || "-");
        return count + (isHitSign(state.my_signs[idx], real, exactScore) ? 1 : 0);
    }, 0);
    const liveCount = matches.filter(match => isLiveStatus(match.status)).length;
    return `<div class="live-scrutiny-badge">Escrutinio live <strong>${hits}/15</strong> provisionales · ${liveCount} en juego</div>`;
}

function consensusLeader(consensus) {
    const values = [
        ["1", Number(consensus?.p1 || 0)],
        ["X", Number(consensus?.px || 0)],
        ["2", Number(consensus?.p2 || 0)]
    ].sort((a, b) => b[1] - a[1]);
    const rawWinner = normalizeSign(consensus?.ganador);
    const sign = ["1", "X", "2"].includes(rawWinner) ? rawWinner : values[0][0];
    const pct = (values.find(([value]) => value === sign) || values[0])[1];
    return {
        sign,
        pct,
        top: values[0],
        second: values[1],
        gap: values[0][1] - values[1][1]
    };
}

function tripletLeader(triplet) {
    if (!triplet) return null;
    const values = [
        ["1", Number(triplet["1"] ?? triplet.p1 ?? 0)],
        ["X", Number(triplet.X ?? triplet.x ?? triplet.px ?? 0)],
        ["2", Number(triplet["2"] ?? triplet.p2 ?? 0)]
    ];
    if (!values.some(([, value]) => value > 0)) return null;
    values.sort((a, b) => b[1] - a[1]);
    return values[0][0];
}

function buildSurpriseRadar(matches) {
    const preds = state.data?.predicciones_actuales || {};
    const consenso = state.data?.consenso_pena || [];
    const mySigns = state.my_signs || [];
    return (matches || []).slice(0, 14).map((match, idx) => {
        const c = consenso.find(item => Number(item.id) === Number(match.id)) || { p1: 0, px: 0, p2: 0, ganador: "-" };
        const leader = consensusLeader(c);
        if (!leader.top || leader.top[1] <= 0) return null;

        const programSign = normalizeSign(getSign(preds, idx, "programa", "v260_omnisciente"));
        const councilSign = normalizeSign(getSign(preds, idx, "consejo_ias", "consenso"));
        const userSign = normalizeSign(mySigns[idx] || "-");
        const info = state.data?.match_info?.[String(match.id)] || {};
        const externalLeaders = [info.q15, info.lae, info.apu].map(tripletLeader).filter(Boolean);
        const externalSplit = new Set(externalLeaders).size > 1;

        let score = Math.max(0, 64 - leader.top[1]) + Math.max(0, 18 - leader.gap);
        const labels = [];
        if (leader.gap <= 12) labels.push("abierto");
        if (programSign && programSign !== "-" && programSign !== leader.sign) {
            score += 24;
            labels.push("programa contra");
        }
        if (councilSign && councilSign !== "-" && councilSign !== leader.sign) {
            score += 18;
            labels.push("consejo duda");
        }
        if (userSign && userSign !== "-" && userSign !== leader.sign) {
            score += 10;
            labels.push("tu vas contra");
        }
        if (externalSplit) {
            score += 14;
            labels.push("mercado roto");
        }
        if (score < 24) return null;

        return {
            idx,
            title: `${getShortName(match.local)} - ${getShortName(match.visitante)}`,
            sign: leader.sign,
            pct: leader.pct,
            score,
            labels: [...new Set(labels)].slice(0, 2)
        };
    }).filter(Boolean)
        .sort((a, b) => b.score - a.score)
        .slice(0, 3);
}

function renderSurpriseRadar(matches) {
    const items = buildSurpriseRadar(matches);
    if (!items.length) return "";
    return `
        <section class="surprise-radar" aria-label="Radar de partidos con riesgo">
            <div class="surprise-radar-head">
                <span>Radar</span>
                <strong>${items.length} focos</strong>
            </div>
            <div class="surprise-radar-list">
                ${items.map(item => `
                    <button class="surprise-radar-card" type="button" data-radar-match="${item.idx}">
                        <span class="surprise-radar-title">${escapeHtml(item.title)}</span>
                        <span class="surprise-radar-meta">${escapeHtml(item.sign)} ${Math.round(item.pct)}% · ${escapeHtml(item.labels.join(" · ") || "riesgo")}</span>
                    </button>
                `).join("")}
            </div>
        </section>`;
}

function renderSidebarRadar() {
    const slot = qs("surprise-radar-slot");
    if (!slot) return;
    const matches = state.currentFilter === "ALL" && state.contestView === "MATCHES"
        ? (state.data?.partidos || [])
        : [];
    slot.innerHTML = renderSurpriseRadar(matches);
}

function pickFeaturedMaster(preds, idx) {
    const preferred = [
        ["grok", null, "Grok"],
        ["claude", null, "Claude"],
        ["chatgpt", null, "GPT"],
        ["gemini", null, "Gemini"],
        ["copilot", null, "Copilot"]
    ];
    for (const [primary, fallback, label] of preferred) {
        const sign = getSign(preds, idx, primary, fallback);
        if (sign && sign !== "-") return { label, sign };
    }
    return { label: "Maestro", sign: "-" };
}

function renderConsensusBar(consensus, isPleno = false) {
    if (isPleno) {
        return `<div class="consensus-bar-wrap consensus-bar-pleno"><span>Pleno al 15</span></div>`;
    }
    const p1 = Math.max(0, Number(consensus.p1 || 0));
    const px = Math.max(0, Number(consensus.px || 0));
    const p2 = Math.max(0, Number(consensus.p2 || 0));
    const total = p1 + px + p2 || 1;
    const w1 = Math.max(4, (p1 / total) * 100);
    const wx = Math.max(4, (px / total) * 100);
    const w2 = Math.max(4, (p2 / total) * 100);
    return `
        <div class="consensus-bar-wrap" title="Consenso Pena: 1 ${p1}% | X ${px}% | 2 ${p2}%">
            <div class="consensus-bar">
                <span class="consensus-seg seg-1" style="width:${w1}%"></span>
                <span class="consensus-seg seg-x" style="width:${wx}%"></span>
                <span class="consensus-seg seg-2" style="width:${w2}%"></span>
            </div>
            <div class="consensus-labels">
                <span>1 · ${p1}%</span>
                <span>X · ${px}%</span>
                <span>2 · ${p2}%</span>
            </div>
        </div>`;
}

function renderTensionChip(label, sign, real, status, exactScore = false, extraClass = "") {
    const clean = sign && sign !== "-" ? sign : "-";
    return `
        <div class="tension-chip ${escapeHtml(extraClass)}">
            <span>${escapeHtml(label)}</span>
            <b class="ia-signo ${hitClass(clean, real, status, exactScore)}">${escapeHtml(clean)}</b>
        </div>`;
}

function renderTensionAiChips(preds, idx, real, status, exactScore = false) {
    return AI_COLUMNS.map(([primary, fallback, label]) => {
        const sign = getSign(preds, idx, primary, fallback);
        return renderTensionChip(label, sign, real, status, exactScore);
    }).join("");
}

function renderCouncilStyleChips(preds, idx, real, status, exactScore = false) {
    const programSign = getSign(preds, idx, "programa", "v260_omnisciente");
    const councilSign = getSign(preds, idx, "consejo_ias", "consenso");
    return [
        renderTensionChip("Programa", programSign, real, status, exactScore, "tension-chip-program"),
        renderTensionChip("Consejo IA", councilSign, real, status, exactScore, "tension-chip-council")
    ].join("");
}

function renderTensionPenaChip(content, label) {
    return `
        <div class="tension-chip tension-chip-pena">
            <span>${escapeHtml(label)}</span>
            ${content}
        </div>`;
}

function renderArenaTableBody(matches) {
    const tbody = qs("arena-body");
    const thead = qs("arena-thead");
    if (!tbody || !thead) return;
    const visibleAIColumns = getVisibleAIColumns(matches);

    const scoreHeader = matches.some(m => isScheduledStatus(m.status)) ? "Hora" : "Marcador";
    thead.innerHTML = `
        <tr>
            <th>#</th>
            <th style="text-align:left;">Partido</th>
            <th style="text-align:center;">Estado / Marcador</th>
            ${visibleAIColumns.map(col => `<th>${col[2]}</th>`).join("")}
            <th>Tu</th>
            <th>Peña</th>
        </tr>`;

    const preds = state.data?.predicciones_actuales || {};
    const consenso = state.data?.consenso_pena || [];
    const canEdit = Boolean(state.user) && String(state.data?.jornada) === String(state.data?.max_jornada) && !state.data?.is_locked;

    tbody.innerHTML = matches.map((m, idx) => {
        const isPleno = idx === 14;
        const real = m.signo_actual || "-";
        const mySign = state.my_signs[idx] || "-";
        const c = consenso.find(item => Number(item.id) === Number(m.id)) || { p1: 0, px: 0, p2: 0, ganador: "-" };
        const consensoPleno = getPenaPlenoSummary(idx);
        const consensus = isPleno
            ? renderPenaPleno(consensoPleno, m.marcador, m.status)
            : renderConsensus(c, real, m.status);
        const liveMatch = isLiveStatus(m.status);
        const scheduledMatch = isScheduledStatus(m.status);
        const score = scheduledMatch ? formatSmartDate(m.fecha_raw, m.hora) : (m.marcador || "-");
        const aiCells = visibleAIColumns.map(([primary, fallback, label]) => {
            const sign = getSign(preds, idx, primary, fallback);
            return `<td class="rival-cell"><span class="ia-signo ${hitClass(sign, isPleno ? m.marcador : real, m.status, isPleno)}" title="${escapeHtml(label)}">${escapeHtml(sign)}</span></td>`;
        }).join("");
        const mine = renderMyCell(idx, mySign, isPleno ? m.marcador : real, m.status, canEdit, isPleno);
        const isFinished = isFinishedStatus(m.status);
        const values = [Number(c.p1 || 0), Number(c.px || 0), Number(c.p2 || 0)].sort((a, b) => b - a);
        const splitMatch = idx !== 14 && !isFinished && values[0] > 0 && values[0] - values[1] <= 12;
        const rowClass = [
            liveMatch ? "is-live-row" : (isFinished ? "is-finished-row" : ""),
            splitMatch ? "is-split-row" : ""
        ].filter(Boolean).join(" ");
        const statusBadge = liveMatch ? `<span class="badge badge-live">LIVE</span>` : "";

        return `
            <tr class="${rowClass}">
                <td class="match-index-cell">
                    <span class="match-number">${idx + 1}</span>
                    <button class="match-detail-toggle table-info-toggle" type="button" data-detail-toggle="1" data-match-idx="${idx}" title="Ver detalle">INFO</button>
                </td>
                <td class="fixture-cell">${fixtureInline(m.local, m.visitante, teamLogo(m, "home"), teamLogo(m, "away"))}</td>
                <td style="text-align:center;"><span class="match-score-badge ${liveMatch ? "is-live-score" : ""} ${scheduledMatch ? "is-scheduled-time" : ""}">${escapeHtml(score)}</span>${statusBadge}</td>
                ${aiCells}
                <td class="my-cell">${mine}</td>
                <td class="pena-cell">${consensus}</td>
            </tr>
            ${state.expandedMatch === idx ? `
                <tr class="match-detail-row">
                    <td colspan="${6 + visibleAIColumns.length}">
                        ${renderMatchDetailGrid(m, c)}
                    </td>
                </tr>` : ""}`;
    }).join("");
}

function renderMatchCard(match) {
    const status = String(match.status || "");
    const finished = isFinishedStatus(status) || isImplicitlyFinished(match);
    const live = isLiveMatch(match);
    const scheduled = isScheduledStatus(status) && !live && !finished;
    const score = scheduled
        ? formatSmartDate(match.added || match.fecha_raw, match.scheduled || match.time || match.hora)
        : (match.marcador || match.score || match.scores?.score || "-");
    const statusText = live ? "En directo" : (scheduled ? "" : formatStatus(finished ? "FINISHED" : status, match.time, match.scheduled));
    const home = match.local || match.home_name || match.home?.name || "-";
    const away = match.visitante || match.away_name || match.away?.name || "-";
    const homeLogo = teamLogo(match, "home");
    const awayLogo = teamLogo(match, "away");
    return `
        <article class="match-card ${live ? "is-live" : ""} ${finished ? "is-finished" : ""}">
            <div class="card-teams">
                ${teamCell(home, "left", homeLogo)}
                <div class="card-score-area">
                    <div class="match-score-badge ${live ? "is-live-score" : (scheduled ? "is-scheduled-time" : "")}">${escapeHtml(score)}</div>
                    ${statusText ? `<div class="card-status">${escapeHtml(statusText)}</div>` : ""}
                </div>
                ${teamCell(away, "right", awayLogo)}
            </div>
        </article>`;
}

function renderArenaCards(matches) {
    const preds = state.data.predicciones_actuales || {};
    const consenso = state.data.consenso_pena || [];
    const canEdit = Boolean(state.user) && String(state.data.jornada) === String(state.data.max_jornada) && !state.data.is_locked;

    return matches.map((m, idx) => {
        const isPleno = idx === 14;
        const real = m.signo_actual || "-";
        const realScore = scoreOnly(m.marcador);
        const realCell = isPleno
            ? (isFinishedStatus(m.status) && realScore
                ? `<span class="pleno-real-score">${escapeHtml(realScore)}</span>`
                : `<span class="pleno-res-muted">-</span>`)
            : `<span class="ia-signo active">${escapeHtml(real)}</span>`;
        const mySign = state.my_signs[idx] || "-";
        const c = consenso.find(item => Number(item.id) === Number(m.id)) || { p1: 0, px: 0, p2: 0, ganador: "-" };
        const consensoPleno = getPenaPlenoSummary(idx);
        const consensus = isPleno
            ? renderPenaPleno(consensoPleno, m.marcador, m.status)
            : renderConsensus(c, real, m.status);
        const finishedMatch = isFinishedStatus(m.status) || isImplicitlyFinished(m);
        const liveMatch = (isLiveMatch(m) || isLiveStatus(m.status)) && !finishedMatch;
        const scheduledMatch = isScheduledStatus(m.status) && !liveMatch && !finishedMatch;
        const score = scheduledMatch
            ? formatSmartDate(m.added || m.fecha_raw, m.scheduled || m.time || m.hora)
            : (m.marcador || m.score || m.scores?.score || "-");

        const aiCells = AI_COLUMNS.map(([primary, fallback, label]) => {
            const sign = getSign(preds, idx, primary, fallback);
            return `<span class="ia-signo ${hitClass(sign, isPleno ? m.marcador : real, m.status, isPleno)}" title="${escapeHtml(label)}">${escapeHtml(sign)}</span>`;
        }).join(" ");

        const mine = renderMyCell(idx, mySign, isPleno ? m.marcador : real, m.status, canEdit, isPleno);
        const isFinished = finishedMatch;

        const isFav = ["REAL MADRID", "BARCELONA", "ATLETICO MADRID"].includes(normalizeName(m.local)) || ["REAL MADRID", "BARCELONA", "ATLETICO MADRID"].includes(normalizeName(m.visitante));
        const isSurprise = liveMatch && isFav && (m.goles_local === m.goles_visitante || (normalizeName(m.local) === "REAL MADRID" && m.goles_local < m.goles_visitante) || (normalizeName(m.visitante) === "REAL MADRID" && m.goles_visitante < m.goles_local));
        const values = [Number(c.p1 || 0), Number(c.px || 0), Number(c.p2 || 0)].sort((a, b) => b - a);
        const splitMatch = idx !== 14 && !isFinished && values[0] > 0 && values[0] - values[1] <= 12;

        const cardClass = [
            liveMatch ? "is-live" : (isFinished ? "is-finished" : ""),
            isSurprise ? "match-trap" : "",
            splitMatch ? "is-split" : ""
        ].filter(Boolean).join(" ");

        const statusBadge = liveMatch ? `<span class="badge badge-live">LIVE</span>` : "";
        const surpriseBadge = isSurprise ? `<span class="badge badge-surprise">SORPRESA</span>` : "";

        return `
            <div class="match-card-container">
                <article class="match-card ${cardClass}" data-match-idx="${idx}">
                    <div class="card-teams">
                        ${teamCell(m.local, "left", teamLogo(m, "home"))}
                        <div class="card-score-area">
                            <div class="match-score-badge ${liveMatch ? "is-live-score" : (scheduledMatch ? "is-scheduled-time" : "")}">${escapeHtml(score)}</div>
                            <div class="card-status">${statusBadge}${surpriseBadge}</div>
                        </div>
                        ${teamCell(m.visitante, "right", teamLogo(m, "away"))}
                    </div>
                    <div class="match-controls">
                        <div class="user-pick-area">${mine}</div>
                        <div class="ai-picks-area">${aiCells}</div>
                        <div class="pena-cell">${consensus}</div>
                    </div>
                </article>
                ${state.expandedMatch === idx ? renderMatchDetail(m, c) : ""}
                <div class="match-detail-toggle-container" style="text-align:center; margin-top:-8px; margin-bottom:8px;">
                    <button class="match-detail-toggle" data-detail-toggle="1" data-match-idx="${idx}">INFO</button>
                </div>
            </div>`;
    }).join("");
}

function renderConsensus(c, real, status) {
    const values = [
        ["1", Number(c.p1 || 0), "home"],
        ["X", Number(c.px || 0), "draw"],
        ["2", Number(c.p2 || 0), "away"]
    ];
    const sorted = [...values].sort((a, b) => b[1] - a[1]);
    const rawWinner = normalizeSign(c.ganador);
    const winner = ["1", "X", "2"].includes(rawWinner) ? rawWinner : sorted[0][0];
    const winnerValue = values.find(([sign]) => sign === winner)?.[1] || 0;
    const detail = `Pena: 1 ${Number(c.p1 || 0)}% | X ${Number(c.px || 0)}% | 2 ${Number(c.p2 || 0)}%`;
    return `<span class="pena-pick ${hitClass(winner, real, status)}" title="${escapeHtml(detail)}"><b>${escapeHtml(winner)}</b><small>${winnerValue}%</small></span>`;
}

function getPenaHiddenUserIds() {
    const visible = new Set(
        AI_COLUMNS.flatMap(([primary, fallback]) => [primary, fallback].filter(Boolean).map(id => String(id).toLowerCase()))
    );
    const ignored = new Set(["hermes", "momo", "jenova", "manu", "consenso", "programa", "v260_omnisciente", "consejo_ias"]);
    return Object.keys(state.data?.predicciones_actuales || {}).filter(uid => {
        const lower = String(uid).toLowerCase();
        if (visible.has(lower) || ignored.has(lower)) return false;
        if (state.user && String(state.user.id).toLowerCase() === lower) return false;
        return true;
    });
}

function bucketLabelForGoals(value) {
    if (!Number.isFinite(value) || value < 0) return null;
    return value >= 3 ? "M" : String(value);
}

function getPenaPlenoSummary(idx = 14) {
    const preds = state.data?.predicciones_actuales || {};
    const exactCounts = {};
    const homeBuckets = { "0": 0, "1": 0, "2": 0, "M": 0 };
    const awayBuckets = { "0": 0, "1": 0, "2": 0, "M": 0 };
    let valid = 0;
    let invalid = 0;

    getPenaHiddenUserIds().forEach(uid => {
        const sign = normalizeSign(preds?.[uid]?.signos?.[idx] || "-");
        const score = scoreOnly(sign);
        if (!score) {
            invalid += 1;
            return;
        }
        const match = score.match(/^(\d+)-(\d+)$/);
        if (!match) {
            invalid += 1;
            return;
        }
        valid += 1;
        exactCounts[score] = (exactCounts[score] || 0) + 1;
        const gl = Number.parseInt(match[1], 10);
        const gv = Number.parseInt(match[2], 10);
        const homeBucket = bucketLabelForGoals(gl);
        const awayBucket = bucketLabelForGoals(gv);
        if (homeBucket) homeBuckets[homeBucket] += 1;
        if (awayBucket) awayBuckets[awayBucket] += 1;
    });

    const topScore = Object.entries(exactCounts).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))[0] || null;
    return { valid, invalid, exactCounts, homeBuckets, awayBuckets, topScore };
}

function renderPenaPleno(summary, realScore, status) {
    if (!summary.topScore) {
        return `<span class="pena-pick pena-pick-pleno" title="La Pena todavia no tiene un pleno claro"><b>-</b><small>s/d</small></span>`;
    }
    const [topScore, count] = summary.topScore;
    const pct = summary.valid ? Math.round((count / summary.valid) * 100) : 0;
    const detail = [
        `Pena pleno: ${topScore} (${count}/${summary.valid})`,
        `Local 0:${summary.homeBuckets["0"]} 1:${summary.homeBuckets["1"]} 2:${summary.homeBuckets["2"]} M:${summary.homeBuckets["M"]}`,
        `Visit. 0:${summary.awayBuckets["0"]} 1:${summary.awayBuckets["1"]} 2:${summary.awayBuckets["2"]} M:${summary.awayBuckets["M"]}`,
        summary.invalid ? `Sin marcador valido: ${summary.invalid}` : ""
    ].filter(Boolean).join(" | ");
    return `<span class="pena-pick pena-pick-pleno ${hitClass(topScore, realScore, status, true)}" title="${escapeHtml(detail)}"><b>${escapeHtml(topScore)}</b><small>${pct}%</small></span>`;
}

function renderPenaPlenoDetail(idx = 14) {
    const summary = getPenaPlenoSummary(idx);
    if (!summary.topScore) {
        return `<strong>Sin pleno claro en la Pena</strong><small>Cuando tengan marcadores validos, aqui saldra el reparto 0 | 1 | 2 | M.</small>`;
    }
    const [topScore, count] = summary.topScore;
    const exactTop = Object.entries(summary.exactCounts)
        .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
        .slice(0, 3)
        .map(([score, qty]) => `${score} (${qty})`)
        .join(" | ");
    const bucketLine = (label, buckets) => `${label}: 0 ${buckets["0"]} | 1 ${buckets["1"]} | 2 ${buckets["2"]} | M ${buckets["M"]}`;
    return `
        <strong>${escapeHtml(topScore)} | ${count}/${summary.valid} Pena</strong>
        <small>${escapeHtml(bucketLine("Local", summary.homeBuckets))}</small>
        <small>${escapeHtml(bucketLine("Visit.", summary.awayBuckets))}</small>
        <small>${escapeHtml(`Marcadores: ${exactTop}${summary.invalid ? ` | sin valido ${summary.invalid}` : ""}`)}</small>`;
}

function renderMyCell(idx, mySign, real, status, canEdit, exactScore = false) {
    if (!state.user) return `<span class="empty-user-pick" title="Entra para guardar tu quiniela">-</span>`;
    if (!canEdit) return `<span class="ia-signo active ${hitClass(mySign, real, status, exactScore)}">${escapeHtml(mySign)}</span>`;
    if (hasSavedTicket() && !state.editMode && !state.draftDirty) {
        return `<span class="saved-ticket-sign ${hitClass(mySign, real, status, exactScore)}">${escapeHtml(mySign === "-" ? "—" : mySign)}</span>`;
    }
    if (idx === 14) {
        return `<button class="pleno-main-btn clickable" data-match-idx="${idx}" data-pleno="1">${escapeHtml(mySign === "-" ? "0-0" : mySign)}</button>`;
    }
    return `
        <div class="action-buttons" data-match-idx="${idx}">
            ${["1", "X", "2"].map(sign => `<button class="ia-signo clickable ${mySign === sign ? "active" : ""}" data-sign="${sign}" type="button">${sign}</button>`).join("")}
        </div>`;
}

function renderPrestigeRanking() {
    const container = qs("ranking-body");
    const ranking = state.data?.ranking_maestros;
    if (!container || !ranking) return;
    const hiddenIds = new Set(["hermes", "HERMES", "momo", "MOMO", "jenova", "JENOVA", "manu", "MANU", "consenso", "CONSENSO"]);

    const nameMap = {
        "v260_omnisciente": "TECNO",
        "programa": "PROGRAMA",
        "consejo_ias": "CONSEJO IA",
        "gemini": "GEMA",
        "claude": "CLAUDE",
        "chatgpt": "CHATGPT",
        "grok": "GROK",
        "copilot": "COPILOT",
        "chipi": "CHIPI",
        "deepseek": "CHIPI",
        "ernie": "ERNIE",
        "kimi": "KIMI",
        "pepe": "PEPE",
        "geli": "GELI",
        "profe": "PROFE",
        "fortu": "FORTU",
        "mrpurple": "MRPURPLE",
        "111242361526361637939": "MRPURPLE R.",
        "oraculo": "ORACULO"
    };

    const rows = Object.entries(ranking).filter(([id]) => !hiddenIds.has(id)).map(([id, stats]) => ({
        id,
        name: nameMap[id] || (state.user && id === state.user.id ? "YO" : id.length > 10 ? id.substring(0, 10) : id),
        total: stats.total || 0,
        jornada: stats.jornada || 0,
        isUser: state.user && id === state.user.id
    }));

    const total = [...rows].sort((a, b) => b.total - a.total || b.jornada - a.jornada).slice(0, 8);
    const today = [...rows].filter(item => Number(item.jornada || 0) > 0)
        .sort((a, b) => b.jornada - a.jornada || b.total - a.total)
        .slice(0, 5);
    const dailyBlock = today.length
        ? `<div class="rank-section-title" style="margin-top:10px;">Jornada actual</div>
           ${today.map((item, idx) => renderRankLine(item, idx, "jornada", "hoy")).join("")}`
        : "";

    container.innerHTML = `
        <div class="rank-section-title">Clasificación general</div>
        ${total.map((item, idx) => renderRankLine(item, idx, "total", "")).join("")}
        ${dailyBlock}`;
}

function renderRankLine(item, idx, field, label) {
    return `
        <div class="rank-line ${idx === 0 ? "is-leader" : ""} ${item.isUser ? "is-user" : ""}">
            <span class="rank-pos">${idx + 1}</span>
            <span class="rank-name">${escapeHtml(item.name)}</span>
            <small class="rank-label">${label ? escapeHtml(label) : ""}</small>
            <b class="rank-total">${item[field]}</b>
        </div>`;
}

function renderContestRows(rows = [], limit = 5) {
    return rows.slice(0, limit).map(item => `
        <div class="contest-row ${item.is_user ? "is-user" : ""}">
            <span class="contest-pos">${item.pos}</span>
            <span class="contest-name">${escapeHtml(item.name)}</span>
            <span class="contest-points">${item.points}</span>
        </div>`).join("") || `<div class="empty-state">Sin datos cerrados todavía.</div>`;
}

function renderContestPanel() {
    const container = qs("contest-body");
    const contest = state.contest;
    if (!container || !contest) return;
    const profile = contest.profile;
    const profileBlock = profile ? `
        <div class="contest-card">
            <div class="contest-title"><span>${escapeHtml(profile.name || "Perfil")}</span><small>perfil</small></div>
            <div class="profile-grid">
                <div class="profile-stat"><span>Posición</span><strong>${profile.position ?? "-"}</strong></div>
                <div class="profile-stat"><span>Aciertos</span><strong>${profile.hits ?? 0}</strong></div>
                <div class="profile-stat"><span>% acierto</span><strong>${profile.hit_rate ?? 0}%</strong></div>
                <div class="profile-stat"><span>Jornadas</span><strong>${profile.played ?? 0}</strong></div>
            </div>
        </div>` : "";

    const awards = (contest.galardones?.jornadas || []).slice(0, 5).map(item => `
        <div class="award-row">
            <span>J${item.jornada}</span>
            <b class="contest-name">${escapeHtml(item.winner)}</b>
            <strong class="contest-points">${item.points}</strong>
        </div>`).join("") || `<div class="empty-state">Sin galardones.</div>`;

    container.innerHTML = `
        <div class="contest-block">
            ${profileBlock}
            <div class="contest-card">
                <div class="contest-title"><span>General</span><small>temporada</small></div>
                ${renderContestRows(contest.general || [], 6)}
            </div>
            <div class="contest-card">
                <div class="contest-title"><span>Jornada ${contest.jornada?.jornada || ""}</span><small>clasificación</small></div>
                ${renderContestRows(contest.jornada?.rows || [], 6)}
            </div>
            <div class="contest-card">
                <div class="contest-title"><span>Mes ${escapeHtml(contest.monthly?.month || "-")}</span><small>mensual</small></div>
                ${renderContestRows(contest.monthly?.rows || [], 5)}
            </div>
            <div class="contest-card">
                <div class="contest-title"><span>Galardones</span><small>ganadores</small></div>
                ${awards}
            </div>
        </div>`;
}

function renderContestPage(view = "CONTEST_PROFILE") {
    const contest = state.contest;
    if (!contest) return `<div class="empty-state">No se pudo cargar La Peña.</div>`;
    const profile = contest.profile;
    const profileBlock = profile ? `
        <div class="contest-card">
            <div class="contest-title"><span>${escapeHtml(profile.name || "Perfil")}</span><small>perfil</small></div>
            <div class="profile-grid">
                <div class="profile-stat"><span>Posición</span><strong>${profile.position ?? "-"}</strong></div>
                <div class="profile-stat"><span>Pronósticos</span><strong>${profile.predictions ?? 0}</strong></div>
                <div class="profile-stat"><span>Aciertos</span><strong>${profile.hits ?? 0}</strong></div>
                <div class="profile-stat"><span>% acierto</span><strong>${profile.hit_rate ?? 0}%</strong></div>
                <div class="profile-stat"><span>Jornadas</span><strong>${profile.played ?? 0}</strong></div>
                <div class="profile-stat"><span>Mejor posición</span><strong>${profile.best_position ?? "-"}</strong></div>
            </div>
        </div>` : `
        <div class="contest-card">
            <div class="contest-title"><span>Perfil</span><small>sesión</small></div>
            <div class="empty-state">Entra con Google para ver tus estadísticas personales.</div>
        </div>`;

    const awards = (contest.galardones?.jornadas || []).slice(0, 10).map(item => `
        <div class="award-row">
            <span>J${item.jornada}</span>
            <b class="contest-name">${escapeHtml(item.winner)}</b>
            <strong class="contest-points">${item.points}</strong>
        </div>`).join("") || `<div class="empty-state">Sin galardones todavía.</div>`;

    const results = (profile?.results || []).slice().reverse().map(item => {
        const ticket = (item.ticket || []).map((sign, idx) => idx === 14 ? `[${sign}]` : sign).join(",");
        return `
            <div class="contest-row">
                <span class="contest-pos">J${item.jornada}</span>
                <span class="contest-ticket">${escapeHtml(ticket)}</span>
                <span class="contest-points">${item.points}</span>
            </div>`;
    }).join("") || `<div class="empty-state">Sin resultados personales.</div>`;

    if (view === "CONTEST_PROFILE") {
        if (!profile) {
            return `<section class="contest-page single"><div class="contest-card"><div class="contest-title"><span>Perfil</span><small>sesion</small></div><div class="empty-state">Entra con Google para ver tus estadisticas personales.</div></div></section>`;
        }
        return `
            <section class="contest-page single">
                <div class="contest-card">
                    <div class="contest-title"><span>Perfil y estadisticas de ${escapeHtml(profile.name || "Maestro")}</span><small>personal</small></div>
                    <div class="profile-grid">
                        <div class="profile-stat"><span>Posicion</span><strong>${profile.position ?? "-"}</strong></div>
                        <div class="profile-stat"><span>Pronosticos</span><strong>${profile.predictions ?? 0}</strong></div>
                        <div class="profile-stat"><span>Aciertos</span><strong>${profile.hits ?? 0}</strong></div>
                        <div class="profile-stat"><span>% acierto</span><strong>${profile.hit_rate ?? 0}%</strong></div>
                        <div class="profile-stat"><span>Jornadas jugadas</span><strong>${profile.played ?? 0}</strong></div>
                        <div class="profile-stat"><span>Aciertos/jornada</span><strong>${profile.hits_per_jornada ?? 0}</strong></div>
                        <div class="profile-stat"><span>Mejor posicion</span><strong>${profile.best_position ?? "-"}</strong></div>
                    </div>
                </div>
                <div class="contest-card">
                    <div class="contest-title"><span>Resultados</span><small>quiniela | aciertos | posicion</small></div>
                    ${results}
                </div>
            </section>`;
    }

    if (view === "CONTEST_GENERAL") {
        return `<section class="contest-page single"><div class="contest-card"><div class="contest-title"><span>La Peña general</span><small>temporada</small></div>${renderContestRows(contest.general || [], 80)}</div></section>`;
    }

    if (view === "CONTEST_MONTHLY") {
        return `<section class="contest-page single"><div class="contest-card"><div class="contest-title"><span>La Peña mensual</span><small>${escapeHtml(contest.monthly?.month || "-")}</small></div>${renderContestRows(contest.monthly?.rows || [], 80)}</div></section>`;
    }

    if (view === "CONTEST_JORNADA") {
        return `<section class="contest-page single"><div class="contest-card"><div class="contest-title"><span>La Peña jornada ${contest.jornada?.jornada || ""}</span><small>jornada actual</small></div>${renderContestRows(contest.jornada?.rows || [], 80)}</div></section>`;
    }

    if (view === "CONTEST_AWARDS") {
        const jornadaItems = contest.galardones?.jornadas || [];
        const monthItems = contest.galardones?.meses || [];
        const selectedJornada = String(state.selectedAwardJornada || jornadaItems[0]?.jornada || "");
        const selectedMonth = String(state.selectedAwardMonth || monthItems[0]?.month || "");
        const jornadaPick = jornadaItems.find(item => String(item.jornada) === selectedJornada) || jornadaItems[0];
        const monthPick = monthItems.find(item => String(item.month) === selectedMonth) || monthItems[0];
        const renderAwardChip = (item, idx, type = "jornada") => `
            <div class="award-chip">
                <span class="award-medal">${idx + 1}</span>
                <div><strong>${type === "mes" ? escapeHtml(item.month) : `J${escapeHtml(item.jornada)}`}</strong><small>${type === "mes" ? "mes" : escapeHtml(item.date || "jornada")}</small></div>
                <b>${escapeHtml(item.winner)}</b>
                <em>${item.points}</em>
            </div>`;
        const renderHistoryRow = (item, idx, type = "jornada") => `
            <div class="award-history-row">
                <span>${idx + 1}</span>
                <strong>${type === "mes" ? escapeHtml(item.month) : `J${escapeHtml(item.jornada)}`}</strong>
                <b>${escapeHtml(item.winner)}</b>
                <em>${item.points}</em>
            </div>`;
        const recentJornadas = jornadaItems.slice(0, 5).map((item, idx) => renderAwardChip(item, idx)).join("") || `<div class="empty-state">Sin ganadores de jornada.</div>`;
        const recentMonths = monthItems.slice(0, 5).map((item, idx) => renderAwardChip(item, idx, "mes")).join("") || `<div class="empty-state">Sin ganadores mensuales.</div>`;
        const jornadaHistory = jornadaItems.slice(0, 14).map((item, idx) => renderHistoryRow(item, idx)).join("") || `<div class="empty-state">Sin historico de jornadas.</div>`;
        const monthHistory = monthItems.slice(0, 10).map((item, idx) => renderHistoryRow(item, idx, "mes")).join("") || `<div class="empty-state">Sin historico mensual.</div>`;
        const jornadaOptions = jornadaItems.map(item => `<option value="${escapeHtml(item.jornada)}" ${String(item.jornada) === selectedJornada ? "selected" : ""}>Jornada ${escapeHtml(item.jornada)}</option>`).join("");
        const monthOptions = monthItems.map(item => `<option value="${escapeHtml(item.month)}" ${String(item.month) === selectedMonth ? "selected" : ""}>${escapeHtml(item.month)}</option>`).join("");
        return `
            <section class="contest-page awards-page">
                <div class="contest-card awards-head">
                    <div>
                        <span>Galardones</span>
                        <strong>Campeones de la Pena</strong>
                    </div>
                    <p>Ganadores por jornada y por mes, con consulta rapida del historico.</p>
                    <div class="awards-totals">
                        <b>${jornadaItems.length}</b><small>jornadas</small>
                        <b>${monthItems.length}</b><small>meses</small>
                    </div>
                </div>
                <div class="awards-grid">
                <div class="contest-card awards-card">
                    <div class="contest-title"><span>Ultimos campeones</span><small>jornada</small></div>
                    <div class="award-strip">${recentJornadas}</div>
                    <div class="award-picker">
                        <label>Consultar jornada</label>
                        <select onchange="changeAwardJornada(this.value)">${jornadaOptions}</select>
                    </div>
                    ${jornadaPick ? `<div class="award-feature">
                        <span>J${jornadaPick.jornada}</span>
                        <strong>${escapeHtml(jornadaPick.winner)}</strong>
                        <em>${jornadaPick.points} pts</em>
                    </div>` : ""}
                </div>
                <div class="contest-card awards-card">
                    <div class="contest-title"><span>Reyes del mes</span><small>ultimos 3</small></div>
                    <div class="award-strip">${recentMonths}</div>
                    <div class="award-picker">
                        <label>Consultar mes</label>
                        <select onchange="changeAwardMonth(this.value)">${monthOptions}</select>
                    </div>
                    ${monthPick ? `<div class="award-feature">
                        <span>${escapeHtml(monthPick.month)}</span>
                        <strong>${escapeHtml(monthPick.winner)}</strong>
                        <em>${monthPick.points} pts</em>
                    </div>` : ""}
                </div>
                <div class="contest-card awards-history-card">
                    <div class="contest-title"><span>Historico</span><small>consulta rapida</small></div>
                    <div class="awards-history-grid">
                        <div>
                            <h4>Jornadas</h4>
                            <div class="awards-history-list">${jornadaHistory}</div>
                        </div>
                        <div>
                            <h4>Meses</h4>
                            <div class="awards-history-list">${monthHistory}</div>
                        </div>
                    </div>
                </div>
                </div>
            </section>`;
    }

    return `
        <section class="contest-page">
            <div class="contest-card">
                <div class="contest-title"><span>La Peña general</span><small>temporada</small></div>
                ${renderContestRows(contest.general || [], 12)}
            </div>
            <div class="contest-grid-secondary">
                ${profileBlock}
                <div class="contest-card">
                    <div class="contest-title"><span>Jornada ${contest.jornada?.jornada || ""}</span><small>La Peña</small></div>
                    ${renderContestRows(contest.jornada?.rows || [], 8)}
                </div>
            </div>
            <div class="contest-card">
                <div class="contest-title"><span>Mensual ${escapeHtml(contest.monthly?.month || "-")}</span><small>mes actual</small></div>
                ${renderContestRows(contest.monthly?.rows || [], 10)}
            </div>
            <div class="contest-card">
                <div class="contest-title"><span>Galardones</span><small>ganadores de jornada</small></div>
                ${awards}
            </div>
            <div class="contest-card contest-wide">
                <div class="contest-title"><span>Tus resultados</span><small>quiniela · aciertos · posición</small></div>
                ${results}
            </div>
        </section>`;
}

function renderLiveStandings() {
    if (!state.data?.standings) return;
    const liveResults = getLiveStandingsResults();
    drawStandings(state.data.standings.primera || [], "standings-1-body", liveResults, "primera");
    drawStandings(state.data.standings.segunda || [], "standings-2-body", liveResults, "segunda");
}

function getLiveStandingsResults() {
    const liveResults = {};
    const allMatches = [...(state.data.partidos || [])];
    (state.data.all_league_matches || []).forEach(m => {
        const home = m.home_name || m.home?.name || m.local;
        const away = m.visitante || m.away_name || m.away?.name;
        const league = competitionLabel(m);
        if (!["LA LIGA", "SEGUNDA DIVISION"].includes(league)) return;
        const score = scoreOnly(m.score || m.scores?.score || m.marcador);
        if (home && away && score) allMatches.push({ local: home, visitante: away, marcador: score, status: isLiveMatch(m) ? "LIVE" : m.status });
    });
    allMatches.forEach(match => {
        if (!isLiveStatus(match.status)) return;
        const cleanScore = scoreOnly(match.marcador);
        if (!cleanScore) return;
        const [gl, gv] = cleanScore.split("-").map(n => Number.parseInt(n, 10));
        if (Number.isNaN(gl) || Number.isNaN(gv)) return;
        liveResults[normalizeName(match.local)] = { pts: gl > gv ? 3 : gl === gv ? 1 : 0, gf: gl, gc: gv, tag: `${gl}-${gv}`, status: match.status };
        liveResults[normalizeName(match.visitante)] = { pts: gv > gl ? 3 : gl === gv ? 1 : 0, gf: gv, gc: gl, tag: `${gv}-${gl}`, status: match.status };
    });
    return liveResults;
}

function findTeamLogo(name) {
    const target = normalizeName(name);
    const fixed = fixedTeamLogo(name);
    if (fixed) return fixed;
    const matches = [...(state.data?.partidos || []), ...(state.data?.all_league_matches || [])];
    for (const match of matches) {
        const home = match.local || match.home?.name || match.home_name;
        const away = match.visitante || match.away?.name || match.away_name;
        if (normalizeName(home) === target) return teamLogo(match, "home");
        if (normalizeName(away) === target) return teamLogo(match, "away");
    }
    return "";
}

function drawStandingsLegacyTable(teams, containerId, liveResults) {
    const container = qs(containerId);
    if (!container) return;
    const rows = buildLiveStandingsRows(teams, liveResults);
    container.innerHTML = `
        <table class="cls-table">
            <thead><tr><th style="text-align:center;">#</th><th style="text-align:left;">Equipo</th><th style="text-align:center;" title="Partidos jugados">PJ</th><th style="text-align:center;">Jor</th><th style="text-align:center;">Pts</th></tr></thead>
            <tbody>${rows.map((team, idx) => `
                <tr class="zone-${idx < 4 ? "champions" : idx < 6 ? "europe" : idx >= rows.length - 3 ? "danger" : "mid"}" title="G ${team.pgLive} / E ${team.peLive} / P ${team.ppLive} · GF ${team.gfLive} / GC ${team.gcLive} · Dif ${team.diffLive}">
                    <td class="cls-pos" style="text-align:center;">${idx + 1}</td>
                    <td class="cls-team"><span class="cls-team-main">${logoBadge(team.n, findTeamLogo(team.n))}<span>${escapeHtml(getShortName(team.n))}</span></span></td>
                    <td class="cls-pj" style="text-align:center;">${team.pjLive}</td>
                    <td class="cls-jor" style="text-align:center;">${team.live ? `<span class="cls-live-badge ${liveResultClass(team.live)}">${team.live.tag}</span>` : ""}</td>
                    <td class="cls-pts" style="text-align:center;">${team.ptsLive}</td>
                </tr>`).join("")}</tbody>
        </table>`;
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

function drawStandings(teams, containerId, liveResults, league = "primera") {
    const container = qs(containerId);
    if (!container) return;
    const rows = buildLiveStandingsRows(teams, liveResults);
    container.innerHTML = `
        <div class="side-standings-list">
            ${rows.map((team, idx) => `
                <div class="side-standing-row zone-${standingsZone(idx, rows.length, league)}" title="PJ ${team.pjLive} - G ${team.pgLive} / E ${team.peLive} / P ${team.ppLive} - GF ${team.gfLive} / GC ${team.gcLive} - Dif ${team.diffLive}">
                    <span class="side-standing-pos">${idx + 1}</span>
                    <span class="side-standing-team">${logoBadge(team.n, findTeamLogo(team.n))}<span class="side-standing-name">${escapeHtml(getShortName(team.n))}</span></span>
                    <span class="side-standing-meta">${team.live ? `<span class="cls-live-badge ${liveResultClass(team.live)}">${team.live.tag}</span>` : `PJ ${team.pjLive}`}</span>
                    <strong class="side-standing-pts">${team.ptsLive}</strong>
                </div>`).join("")}
        </div>`;
}

function buildLiveStandingsRows(teams, liveResults) {
    return teams.map(team => {
        const live = liveResults[normalizeName(team.n)];
        const pg = Number(team.pg ?? 0);
        const pe = Number(team.pe ?? 0);
        const pp = Number(team.pp ?? 0);
        const gf = Number(team.gf ?? 0);
        const gc = Number(team.gc ?? 0);
        const liveWin = live?.pts === 3 ? 1 : 0;
        const liveDraw = live?.pts === 1 ? 1 : 0;
        const liveLoss = live && live.pts === 0 ? 1 : 0;
        return {
            ...team,
            live,
            pjLive: Number(team.pj || 0) + (live ? 1 : 0),
            pgLive: pg + liveWin,
            peLive: pe + liveDraw,
            ppLive: pp + liveLoss,
            gfLive: gf + (live?.gf || 0),
            gcLive: gc + (live?.gc || 0),
            ptsLive: Number(team.pts || 0) + (live?.pts || 0)
        };
    }).map(team => ({ ...team, diffLive: team.gfLive - team.gcLive }))
      .sort((a, b) => b.ptsLive - a.ptsLive || b.diffLive - a.diffLive || b.gfLive - a.gfLive || (a.pos || 99) - (b.pos || 99));
}

function liveResultClass(live) {
    return live?.pts === 3 ? "cls-win" : live?.pts === 1 ? "cls-draw" : "cls-loss";
}

function renderFullStandingsPage() {
    const liveResults = getLiveStandingsResults();
    const showPrimera = state.currentFilter !== "STANDINGS_SEGUNDA";
    const showSegunda = state.currentFilter !== "STANDINGS_PRIMERA";
    return `
        <section class="full-standings-page">
            ${showPrimera ? `<div class="full-standings-card">
                <div class="full-standings-head">
                    <div>
                        <span class="section-kicker">Clasificacion</span>
                        <h2>Primera Division</h2>
                    </div>
                    <small>Tabla completa · directo integrado</small>
                </div>
                ${renderFullStandingsTable(state.data?.standings?.primera || [], liveResults, "primera")}
            </div>` : ""}
            ${showSegunda ? `<div class="full-standings-card">
                <div class="full-standings-head">
                    <div>
                        <span class="section-kicker">Clasificacion</span>
                        <h2>Segunda Division</h2>
                    </div>
                    <small>Tabla completa · directo integrado</small>
                </div>
                ${renderFullStandingsTable(state.data?.standings?.segunda || [], liveResults, "segunda")}
            </div>` : ""}
        </section>`;
}

function renderFullStandingsTable(teams, liveResults, league = "primera") {
    const rows = buildLiveStandingsRows(teams, liveResults);
    return `
        <table class="full-standings-table">
            <thead>
                <tr>
                    <th style="text-align:center;">#</th>
                    <th>Club</th>
                    <th>PJ</th>
                    <th>Jor</th>
                    <th>G</th>
                    <th>E</th>
                    <th>P</th>
                    <th>GF</th>
                    <th>GC</th>
                    <th>DG</th>
                    <th>Pts</th>
                    <th>Ultimos 5</th>
                </tr>
            </thead>
            <tbody>${rows.map((team, idx) => {
                const form = String(team.racha || "").trim();
                return `
                    <tr class="zone-${standingsZone(idx, rows.length, league)}">
                        <td class="full-pos">${idx + 1}</td>
                        <td class="full-club">${logoBadge(team.n, findTeamLogo(team.n))}<span>${escapeHtml(team.n)}</span></td>
                        <td>${team.pjLive}</td>
                        <td>${team.live ? `<span class="cls-live-badge ${liveResultClass(team.live)}">${team.live.tag}</span>` : ""}</td>
                        <td>${team.pgLive}</td>
                        <td>${team.peLive}</td>
                        <td>${team.ppLive}</td>
                        <td>${team.gfLive}</td>
                        <td>${team.gcLive}</td>
                        <td>${team.diffLive}</td>
                        <td class="full-points">${team.ptsLive}</td>
                        <td class="form-cell">${renderFormDots(form)}</td>
                    </tr>`;
            }).join("")}</tbody>
        </table>`;
}

function renderFormDots(form) {
    if (!form) return `<span class="form-muted">-</span>`;
    return form.split("").slice(-5).map(ch => {
        const value = ch.toUpperCase();
        const cls = value === "G" || value === "W" ? "form-win" : value === "E" || value === "D" ? "form-draw" : "form-loss";
        return `<span class="form-dot ${cls}">${escapeHtml(value === "W" ? "G" : value === "D" ? "E" : value)}</span>`;
    }).join("");
}

async function loadComments() {
    const body = qs("comments-body");
    const form = qs("comment-form");
    const text = qs("comment-text");
    const helper = qs("comment-helper");
    const submit = form?.querySelector("button[type='submit']");
    const count = qs("comment-count");
    const newCount = qs("comment-new-count");
    const summary = qs("comments-summary");
    if (!body || !state.data) return;

    if (form) form.classList.toggle("is-disabled", !state.user);
    if (submit) {
        submit.disabled = !state.user;
        submit.hidden = !state.user;
    }
    if (text) {
        text.disabled = !state.user;
        text.hidden = !state.user;
        text.placeholder = state.user ? "Comenta la jornada..." : "";
    }
    if (helper) {
        helper.innerHTML = state.user
            ? "Comentario de la jornada"
            : `<a class="comment-login-link" href="/login/google">Entra con Google para comentar</a>`;
    }

    try {
        const res = await fetch(`/api/comentarios?j=${encodeURIComponent(state.data.jornada)}`);
        const data = await res.json();
        const comments = data.comentarios || [];
        const latestId = comments.reduce((max, comment) => Math.max(max, Number(comment.id || 0)), 0);
        const seenId = readSeenCommentId(state.data.jornada);
        const freshCount = comments.filter(comment => Number(comment.id || 0) > seenId).length;
        body.dataset.latestCommentId = String(latestId);
        if (latestId) writeSeenCommentId(latestId, state.data.jornada);
        if (count) count.textContent = String(comments.length);
        if (newCount) newCount.textContent = String(freshCount);
        if (summary) {
            summary.textContent = `${comments.length} comentario${comments.length === 1 ? "" : "s"}${freshCount ? ` · ${freshCount} nuevo${freshCount === 1 ? "" : "s"}` : ""}`;
        }
        if (!comments.length) {
            body.innerHTML = `<div class="comments-empty">
                <strong style="display:block; margin-bottom:4px;">Sin comentarios todavía</strong>
                <span>${state.user ? "Deja el primero." : "Entra con Google y comenta."}</span>
            </div>`;
            return;
        }
        body.innerHTML = comments.map(comment => `
            <article class="comment-card">
                <div class="comment-meta">
                    <strong style="color:var(--accent);">${escapeHtml(comment.nombre || "Maestro")}</strong>
                    <span>${escapeHtml(formatCommentTime(comment.created_at))}</span>
                </div>
                <p>${escapeHtml(comment.texto)}</p>
            </article>
        `).join("");
        body.scrollTop = body.scrollHeight;
    } catch (error) {
        if (count) count.textContent = "!";
        if (newCount) newCount.textContent = "!";
        if (summary) summary.textContent = "No se pudieron cargar los comentarios.";
        body.innerHTML = `<div class="comments-empty">No se pudieron cargar los comentarios.</div>`;
    }
}

function formatCommentTime(value) {
    const date = new Date(String(value || "").replace(" ", "T"));
    if (Number.isNaN(date.getTime())) return "";
    const now = new Date();
    const sameDay = date.toDateString() === now.toDateString();
    return sameDay
        ? date.toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit" })
        : date.toLocaleDateString("es-ES", { day: "2-digit", month: "2-digit" });
}

async function submitComment(event) {
    event.preventDefault();
    if (!state.user) return showToast("Entra con Google para comentar.", "error");
    const text = qs("comment-text");
    const value = String(text?.value || "").trim();
    if (!value) return;

    try {
        const res = await fetch("/api/comentarios", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                jornada: state.data?.jornada || state.jornada,
                texto: value
            })
        });
        const result = await res.json();
        if (!res.ok || result.status !== "ok") throw new Error(result.message || "No se pudo comentar");
        text.value = "";
        await loadComments();
    } catch (error) {
        showToast(error.message, "error");
    }
}

async function renderEvolutionChart() {
    const canvas = qs("evolutionChart");
    const empty = qs("evolution-empty");
    if (!canvas || !window.Chart) return;
    if (!state.user) {
        const ctx = canvas.getContext("2d");
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        canvas.hidden = true;
        if (empty) empty.hidden = false;
        return;
    }
    canvas.hidden = false;
    if (empty) empty.hidden = true;
    try {
        const res = await fetch(`/api/user/evolution?uid=${encodeURIComponent(state.user.id)}`);
        const data = await res.json();
        if (state.evolutionChart) state.evolutionChart.destroy();
        state.evolutionChart = new Chart(canvas.getContext("2d"), {
            type: "line",
            data: {
                labels: data.labels || [],
                datasets: [
                    { label: "Mis aciertos", data: data.user || [], borderColor: "#38bdf8", backgroundColor: "rgba(56, 189, 248, 0.14)", borderWidth: 3, tension: 0.35, fill: true },
                    { label: "Programa", data: data.programa || data.ia || [], borderColor: "#fbbf24", borderWidth: 2, borderDash: [5, 5], tension: 0.35, fill: false },
                    { label: "Consenso IA", data: data.consenso || [], borderColor: "#a78bfa", borderWidth: 2, borderDash: [2, 4], tension: 0.35, fill: false }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: { beginAtZero: true, max: 15, grid: { color: "rgba(255,255,255,0.06)" }, ticks: { color: "#94a3b8" } },
                    x: { grid: { display: false }, ticks: { color: "#94a3b8", maxTicksLimit: 5 } }
                },
                plugins: { legend: { labels: { color: "#f8fafc", boxWidth: 10, font: { weight: "bold" } } } }
            }
        });
    } catch (error) {
        console.error(error);
    }
}

async function savePredictions() {
    if (!state.user) return showToast("Entra con Google para guardar.", "error");
    if (!state.data || String(state.data.jornada) !== String(state.data.max_jornada) || state.data.is_locked) {
        return showToast("Esta jornada ya esta cerrada.", "error");
    }
    if (hasSavedTicket() && !state.editMode && !state.draftDirty) {
        state.editMode = true;
        hydrateHero();
        renderArena();
        return showToast(`Puedes editar hasta ${state.data.edit_deadline || "el inicio del primer partido"}.`);
    }
    try {
        const res = await fetch("/api/predicciones/save", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ user_id: state.user.id, jornada: state.data.jornada, signos: state.my_signs })
        });
        const result = await res.json();
        if (!res.ok || result.status !== "ok") throw new Error(result.message || "No se pudo guardar");
        clearDraft();
        state.server_signs = [...state.my_signs];
        state.editMode = false;
        showToast("Quiniela guardada.");
        await refreshData();
    } catch (error) {
        showToast(error.message, "error");
    }
}

async function shareTicket() {
    if (!state.user) return showToast("Entra con Google para compartir.", "error");
    const matches = state.data?.partidos || [];
    if (!matches.length) return showToast("No hay jornada cargada para compartir.", "error");
    const lines = [
        `🏆 LIGA DE MAESTROS | Mis pronósticos J${state.data.jornada}`,
        ...matches.slice(0, 15).map((match, idx) => {
            const sign = state.my_signs[idx] && state.my_signs[idx] !== "-" ? state.my_signs[idx] : "sin marcar";
            const local = match.local || "Local";
            const away = match.visitante || "Visitante";
            const label = idx === 14 ? "Pleno al 15" : `${local} - ${away}`;
            return `${idx + 1}. ${label} -> ${sign}`;
        }),
        "🔥 Compite conmigo en la Liga de Maestros"
    ];
    const text = lines.join("\n");
    try {
        if (navigator.clipboard?.writeText) {
            await navigator.clipboard.writeText(text);
        } else {
            const area = document.createElement("textarea");
            area.value = text;
            area.setAttribute("readonly", "");
            area.style.position = "fixed";
            area.style.left = "-9999px";
            document.body.appendChild(area);
            area.select();
            document.execCommand("copy");
            area.remove();
        }
        showToast("Pronostico copiado.");
    } catch (error) {
        showToast("No se pudo copiar el pronostico.", "error");
    }
}

function bindEvents() {
    qs("warroom-btn")?.addEventListener("click", () => {
        filterLeague(state.currentFilter === "WAR_ROOM" ? "ALL" : "WAR_ROOM");
    });
    qs("refresh-btn")?.addEventListener("click", refreshData);
    qs("save-quiniela-btn")?.addEventListener("click", savePredictions);
    qs("share-ticket-btn")?.addEventListener("click", shareTicket);
    qs("comment-form")?.addEventListener("submit", submitComment);
    document.querySelector(".comments-panel-side .panel-head")?.addEventListener("click", () => {
        setCommentsOpen(!state.commentsOpen);
    });
    qs("matches-body")?.addEventListener("click", event => {
        const radarBtn = event.target.closest("[data-radar-match]");
        if (radarBtn) {
            const idx = Number.parseInt(radarBtn.dataset.radarMatch, 10);
            if (Number.isNaN(idx)) return;
            state.expandedMatch = state.expandedMatch === idx ? null : idx;
            renderArena();
            return;
        }
        const detailBtn = event.target.closest("[data-detail-toggle]");
        if (detailBtn) {
            const idx = Number.parseInt(detailBtn.dataset.matchIdx, 10);
            if (Number.isNaN(idx)) return;
            state.expandedMatch = state.expandedMatch === idx ? null : idx;
            renderArena();
            return;
        }
        const btn = event.target.closest(".clickable");
        if (!btn) return;
        if (!state.user) return showToast("Entra con Google para jugar.", "error");
        if (!state.data || String(state.data.jornada) !== String(state.data.max_jornada) || state.data.is_locked) {
            return showToast("Jornada bloqueada.", "error");
        }
        const idx = Number.parseInt(btn.dataset.matchIdx || btn.closest("[data-match-idx]")?.dataset.matchIdx, 10);
        if (Number.isNaN(idx)) return;
        if (btn.dataset.pleno) {
            const value = window.prompt("Resultado del pleno al 15", state.my_signs[idx] === "-" ? "0-0" : state.my_signs[idx]);
            if (value) state.my_signs[idx] = value.trim();
        } else {
            state.my_signs[idx] = state.my_signs[idx] === btn.dataset.sign ? "-" : btn.dataset.sign;
        }
        state.lastUserEdit = Date.now();
        state.draftDirty = true;
        persistDraft();
        hydrateHero();
        renderArena();
    });
    document.querySelectorAll(".tab-btn[data-standings]").forEach(button => {
        button.addEventListener("click", () => {
            document.querySelectorAll(".tab-btn[data-standings]").forEach(btn => btn.classList.remove("active"));
            document.querySelectorAll(".standings-pane").forEach(pane => pane.classList.remove("active"));
            button.classList.add("active");
            qs(button.dataset.standings)?.classList.add("active");
        });
    });
}

document.addEventListener("DOMContentLoaded", () => {
    hydrateCommentsPanel();
    bindEvents();
    refreshData();
    setInterval(() => {
        refreshData({ auto: true });
    }, 60000);
});

function renderLiveTicker() {
    const allMatches = getAllLeagueMatches();
    const matches = state.currentFilter === "ALL"
        ? (state.data?.partidos || [])
        : state.currentFilter === "LIVE"
            ? getLiveLeagueMatches()
            : state.currentFilter === "WAR_ROOM"
                ? getLiveLeagueMatches()
                : allMatches.filter(m => competitionLabel(m) === state.currentFilter.toUpperCase());
    const live = matches.filter(m => isLiveStatus(m.status) || isLiveMatch(m));
    const nextMatch = getNextLeagueMatch();
    const tickerItems = live.length
        ? live.map(m => {
            const home = m.local || m.home_name || m.home?.name;
            const away = m.visitante || m.away_name || m.away?.name;
            const score = scoreOnly(m.marcador || m.score || m.scores?.score) || m.marcador || m.score || "";
            return `<span><b>${escapeHtml(getShortName(home))}</b> ${escapeHtml(score)} <b>${escapeHtml(getShortName(away))}</b></span>`;
        }).join("")
        : `<span>${nextMatch ? `Próximo directo: <b>${escapeHtml(getShortName(nextMatch.local || nextMatch.home_name || nextMatch.home?.name || "-"))}</b> ${escapeHtml(formatKickoffShort(nextMatch.added || nextMatch.fecha_raw, nextMatch.scheduled || nextMatch.time || nextMatch.hora))}` : "Sin partidos en directo ahora mismo"}</span>`;
    return `
        <div class="live-ticker ${live.length ? "has-live" : ""} ${live.length > 1 ? "is-marquee" : "is-static"}">
            <div class="live-ticker-track">
                <div class="live-ticker-items">${live.length > 1 ? tickerItems + tickerItems : tickerItems}</div>
            </div>
        </div>`;
}

function updateTopbarLiveTicker() {
    const slot = qs("topbar-live-slot");
    if (!slot || !state.data) return;
    slot.innerHTML = renderLiveTicker();
}
