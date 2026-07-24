/* ==========================================================================
   STATE — Objeto de estado global, hidratacion, draft, auth, page checks.
   Dependencias: utils.js, logos.js (logoLookupKey)
   ========================================================================== */

const state = {
    data: null,
    contest: null,
    contestJornada: "",
    jornada: new URLSearchParams(window.location.search).get("j") || "",
    user: null,
    csrfToken: "",
    my_signs: Array(15).fill("-"),
    server_signs: Array(15).fill("-"),
    draftDirty: false,
    editMode: false,
    lastUserEdit: 0,
    currentFilter: "ALL",
    contestView: "MATCHES",
    expandedMatch: null,
    q15Directo: {},
    q15DirectoJornada: "",
    selectedAwardJornada: "",
    selectedAwardMonth: "",
    newspaperPage: "ALL",
    refreshErrorNotifiedAt: 0,
    snake: {
        running: false,
        over: false,
        score: 0,
        best: 0,
        savedScore: 0,
        timer: null,
        dir: { x: 1, y: 0 },
        nextDir: { x: 1, y: 0 },
        dirQueue: [],
        snake: [],
        food: null,
        cards: [],
        reason: ""
    }
};

const initialView = new URLSearchParams(window.location.search).get("view");
if (initialView) state.currentFilter = ["MATCHES", "PANEL"].includes(initialView) ? "ALL" : initialView;
const initialContest = new URLSearchParams(window.location.search).get("contest");
if (initialContest) state.contestView = initialContest;
if (state.currentFilter === "CONTEST") {
    state.currentFilter = "ALL";
    state.contestView = "CONTEST_GENERAL";
}
document.body.classList.toggle("newspaper-cover-active", state.contestView === "MATCHES" && state.currentFilter === "ALL");
document.body.classList.toggle("newspaper-ticket-active", state.contestView === "MATCHES" && state.currentFilter === "TICKET");

const AI_COLUMNS = [
    ["programa", "v260_omnisciente", "Programa"],
    ["gemini", null, "Gemini"],
    ["grok", null, "GROK"],
    ["claude", null, "Claude"],
    ["copilot", null, "Copilot"],
    ["chatgpt", null, "ChatGPT"]
];

const COUNCIL_STYLE_JORNADAS = new Set(["67"]);
const logoCache = new Map();
let logoAliasIndex = null;
let standingContextCache = new Map();

function isCouncilStyleJornada() {
    return COUNCIL_STYLE_JORNADAS.has(String(state.data?.jornada || state.jornada || ""));
}

function getOfficialAIColumns() {
    const columns = state.data?.participant_contract?.visible_ai_columns;
    if (!Array.isArray(columns) || !columns.length) return AI_COLUMNS;
    return columns
        .map(column => [
            String(column.id || "").trim(),
            column.fallback ? String(column.fallback).trim() : null,
            String(column.name || column.label || column.id || "").trim()
        ])
        .filter(([id, , label]) => id && label);
}

function hydrateJornadaNav() {
    const nav = qs("jornada-nav");
    if (!nav || !state.data) return;
    const jornadas = (Array.isArray(state.data.jornadas_disponibles) && state.data.jornadas_disponibles.length
        ? state.data.jornadas_disponibles
        : [state.data.jornada || state.data.max_jornada])
        .map(value => Number(value))
        .filter(value => Number.isFinite(value))
        .filter((value, index, list) => list.indexOf(value) === index)
        .sort((a, b) => b - a);
    nav.innerHTML = "";
    jornadas.forEach(jornada => {
        const opt = document.createElement("option");
        opt.value = String(jornada);
        opt.textContent = `Jornada ${jornada}`;
        opt.selected = String(jornada) === String(state.data.jornada);
        nav.appendChild(opt);
    });
}

function hydrateHero() {
    if (!state.data) return;
    const title = state.contestView !== "MATCHES"
        ? contestViewTitle(state.contestView)
        : state.currentFilter === "ALL"
            ? "Portada"
            : state.currentFilter === "TICKET"
                ? "Quiniela oficial"
                : state.currentFilter === "SNAKE_PAGE"
                    ? "Juegos"
                    : state.currentFilter === "QUIZ_PAGE"
                        ? "Quiz"
                : state.currentFilter === "LIVE"
                    ? "Partidos en directo"
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
    if (document.body.classList.contains("newspaper-ui")) {
        if (topbarKicker) topbarKicker.textContent = `Jornada ${state.data.jornada} - La Peña vs Maestros IA`;
        if (topbarTitle) topbarTitle.textContent = currentMainView() === "ALL" ? "Portada de la jornada" : title;
    } else {
        if (topbarTitle) topbarTitle.textContent = title;
        if (topbarKicker) topbarKicker.textContent = `Jornada ${state.data.jornada}`;
    }
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
        if (!canSave) {
            save.hidden = true;
            save.textContent = "Guardar quiniela";
        }
    }
    const share = qs("share-ticket-btn");
    if (share) {
        share.hidden = !state.user;
        share.disabled = !state.data.partidos.length;
    }
    updatePicksProgress();
    updateHeroStrip();
}

function contestViewTitle(value) {
    return {
        CONTEST_PROFILE: "Mi perfil",
        CONTEST_GENERAL: "La Peña general",
        CONTEST_MONTHLY: "La Peña mensual",
        CONTEST_JORNADA: "La Peña jornada",
        CONTEST_HISTORY: "Histórico",
        CONTEST_AWARDS: "Galardones"
    }[value] || "La Peña";
}

function getAllLeagueMatches() {
    return state.data?.all_league_matches || [];
}

function getBrowsableLeagueMatches() {
    const blockedTokens = [
        "FRIENDL",
        "UEFA",
        "CHAMPIONS",
        "EUROPA LEAGUE",
        "CONFERENCE LEAGUE",
        "SUPER CUP",
        "SUPERCUP"
    ];
    return getAllLeagueMatches().filter(match => {
        const competition = competitionLabel(match);
        return !blockedTokens.some(token => competition.includes(token));
    });
}

function isLiveMatch(match) {
    const status = String(match.status || "").toUpperCase();
    if (isImplicitlyFinished(match)) return false;
    if (status.includes("LIVE") || status === "IN PLAY" || status === "HT" || status === "EN JUEGO") return true;
    const score = scoreOnly(match.score || match.marcador || "");
    if (score && !isFinishedStatus(status)) return true;
    const dateText = String(match.added || match.fecha_raw || "").slice(0, 10);
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
    if (!state.user) {
        if (navAuth) navAuth.innerHTML = state.data.auth_enabled === false
            ? `<span class="login-btn topbar-login-btn is-disabled" title="Google OAuth pendiente de configurar">Login off</span>`
            : `<a class="login-btn topbar-login-btn" href="/login/google">Entrar</a>`;
        return;
    }
    const stats = state.data?.ranking_maestros?.[state.user.id] || { total: 0, jornada: 0 };
    const profile = state.contest?.profile || {};
    const points = Number(stats.total ?? profile.hits ?? 0);
    const rank = profile.position ?? getUserRankingPosition();
    const rankText = rank ? `#${rank}` : "-";
    const firstName = String(state.user.name || "Maestro").split(" ")[0];
    if (navAuth) navAuth.innerHTML = `
        <div class="topbar-user-summary" title="${escapeHtml(`${stats.jornada || 0} aciertos en la jornada actual`)}">
            <button class="topbar-user-name profile-link" type="button" data-open-profile>${escapeHtml(firstName)}</button>
            <span class="topbar-user-score topbar-user-points"><b>${points}</b> pts</span>
            <span class="topbar-user-score topbar-user-rank"><b>${escapeHtml(rankText)}</b> ranking</span>
            <button class="topbar-mini-link" type="button" data-open-profile>Perfil</button>
        </div>
        <a class="logout-link compact-logout" href="/logout">Salir</a>`;
}

function getUserRankingPosition() {
    if (!state.user) return null;
    const uid = String(state.user.id);
    const ranking = state.data.ranking_maestros || {};
    const rows = Object.entries(ranking)
        .map(([id, stats]) => ({
            id,
            total: Number(stats.total || 0),
            jornada: Number(stats.jornada || 0)
        }))
        .sort((a, b) => b.total - a.total || b.jornada - a.jornada || a.id.localeCompare(b.id));
    const idx = rows.findIndex(row => String(row.id) === uid);
    if (idx >= 0) return idx + 1;
    const contestRow = (state.contest?.general || []).find(row => String(row.id) === uid || row.is_user);
    return contestRow?.pos || null;
}

function isTicketPage() {
    return state.contestView === "MATCHES" && state.currentFilter === "TICKET";
}

function isCoverPage() {
    return state.contestView === "MATCHES" && state.currentFilter === "ALL";
}

function isProfilePage() {
    return state.contestView === "CONTEST_PROFILE";
}

function isStandingsPage() {
    return state.contestView === "MATCHES" && String(state.currentFilter || "").startsWith("STANDINGS_");
}

function isSnakePage() {
    return state.contestView === "MATCHES" && state.currentFilter === "SNAKE_PAGE";
}

function isQuizPage() {
    return state.contestView === "MATCHES" && state.currentFilter === "QUIZ_PAGE";
}

function isContestPage() {
    return state.contestView !== "MATCHES";
}

function isLiveOrLeaguePage() {
    return state.contestView === "MATCHES" && (
        state.currentFilter === "LIVE" ||
        (state.currentFilter && !["ALL", "TICKET", "SNAKE_PAGE", "QUIZ_PAGE"].includes(state.currentFilter) && !String(state.currentFilter).startsWith("STANDINGS_"))
    );
}
