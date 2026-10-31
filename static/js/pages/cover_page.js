/* Portada Liga de Maestros v19 — QUINIELA EN FORMATO TABLA
   Direccion: boleto de quiniela digital con paneles alrededor.
   - Centro: tabla de 14 partidos con una columna por Maestro (logo arriba,
     signo 1/X/2 normal, sin pastillas de color), más panel separado para el
     pleno con marcadores exactos de goles.
   - Ticker de goles arriba (banda fina animada) con directo y finalizados.
   - Paneles alrededor: LA PENA TOP 5, MAESTROS TOP 5, EN DIRECTO,
     RESULTADOS/PROXIMOS, PORRA +2, ULTIMA HORA.
   - Columna HORA / RES: horario si falta, marcador si el partido ya tiene resultado.
   - Header minimo: countdown + progreso + boton Firmar.
   Tipografia: Rajdhani (titular), Outfit (UI), JetBrains Mono (datos).
   Tokens: gold #fbbf24, cyan #38bdf8, surfaces oscuros.
*/

function loadSacramentoFont() {}
function hydrateCoverTypewriter() {}
function startCoverScorebar() {}
const _visibilitychange = "visibilitychange";

// La cuenta atras de la portada nace UNA sola vez: cada render la reutiliza en
// vez de sumar otro `setInterval`. Antes el propio render montaba el suyo sin
// clearInterval, y cada refresco (30-60 s en ventana de jornada) dejaba un tick
// huerfano escribiendo sobre un nodo ya desenganchado del DOM.
let _countdownStarted = false;
let _seasonCountdownStarted = false;
const SEASON_KICKOFF = new Date("2026-08-15T19:30:00");
function formatCountdownDigits(d, h, m, s) {
    return `${String(d).padStart(2, "0")}d ${String(h).padStart(2, "0")}h ${String(m).padStart(2, "0")}m ${String(s).padStart(2, "0")}s`;
}
function startCoverCountdown() {
    if (_countdownStarted) return;
    // Sin el nodo que deja el render no hay nada que pintar: se levanta la
    // bandera solo con el intervalo en marcha, de modo que la siguiente llamada
    // (u otro render) pueda reintentar en vez de quedarse apagada para siempre.
    if (!document.getElementById("cx-cd")) return;
    _countdownStarted = true;
    // El nodo se vuelve a buscar en cada tick: el render lo sustituye y una
    // referencia fija escribiria sobre un elemento fuera del DOM.
    const tick = () => {
        const el = document.getElementById("cx-cd");
        if (!el) return;
        const c = _diffParts(state.data?.edit_deadline || state.data?.kickoff_at);
        if (c.ms <= 0 || coverIsClosed()) { el.innerHTML = '<span class="cx-kpi-closed">CERRADA</span>'; return; }
        el.innerHTML = `<span class="cx-cd-block">${String(c.d).padStart(2, "0")}<i>d</i></span><span class="cx-cd-block">${String(c.h).padStart(2, "0")}<i>h</i></span><span class="cx-cd-block">${String(c.m).padStart(2, "0")}<i>m</i></span><span class="cx-cd-block">${String(c.s).padStart(2, "0")}<i>s</i></span>`;
        el.closest("[data-kpi]")?.classList.toggle("is-urgent", c.urgent);
    };
    tick();
    setInterval(tick, 1000);
}
function startSeasonCountdown() {
    if (_seasonCountdownStarted) return;
    _seasonCountdownStarted = true;
}
function updateCpScorebar() { startCoverScorebar(); }
function updateCpUrgency() {}
const _MAESTRO_LABEL = { programa: "Programa", claude: "Claude", grok: "Grok", chatgpt: "ChatGPT", copilot: "Copilot", gemini: "Gemini" };
const _MAESTRO_AVATAR = { programa: "∑", claude: "✦", grok: "✕", chatgpt: "◎", copilot: "▣", gemini: "✺" };
const _MAESTRO_TONE = { programa: "is-programa", claude: "is-claude", grok: "is-grok", chatgpt: "is-chatgpt", copilot: "is-copilot", gemini: "is-gemini" };
function triggerProgressPop() {}
function loadSeasonSummary() {}
/* El cierre de la quiniela llega del servidor en hora de Madrid
   ("2026-09-05 16:45"). Leerlo con `new Date()` lo interpretaba en la zona del
   navegador y la cuenta atras se descolocaba horas fuera de la peninsula. */
function _coverDeadlineMs(raw) {
    const text = String(raw || "").trim();
    if (!text) return null;
    if (typeof madridWallClockToMs === "function") {
        return madridWallClockToMs(text.slice(0, 10), text.slice(11, 16));
    }
    const parsed = Date.parse(text.replace(" ", "T"));
    return Number.isNaN(parsed) ? null : parsed;
}

function coverCloseLabel() {
    const raw = state?.data?.edit_deadline || state?.data?.kickoff_at || "";
    if (!raw) return state?.data?.is_locked ? "cerrada" : "abierta";
    const date = _coverDeadlineMs(raw);
    if (!date) return state?.data?.is_locked ? "cerrada" : "abierta";
    const diff = date - Date.now();
    if (diff <= 0 || state?.data?.is_locked) return "cerrada";
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(minutes / 60);
    const mins = minutes % 60;
    if (hours >= 24) return `${Math.floor(hours / 24)}d ${hours % 24}h`;
    if (hours > 0) return `${hours}h ${String(mins).padStart(2, "0")}m`;
    return `${Math.max(1, mins)}m`;
}
function coverIsClosed() { return Boolean(state?.data?.is_locked) || coverCloseLabel() === "cerrada"; }
function coverMasterColumns() {
    return (state.data?.participant_contract?.visible_ai_columns || []).map(col => ({
        id: Array.isArray(col) ? col[0] : col.id,
        label: Array.isArray(col) ? (col[2] || col[0]) : (col.name || col.label || col.id),
    })).filter(col => col.id);
}
function coverMasterNames() { return coverMasterColumns().filter(c => String(c.id).toLowerCase() !== "programa").map(c => c.label); }
function coverDisplayName(uid) {
    const names = state.data?.participant_contract?.names || {};
    const id = String(uid || "").toLowerCase();
    if (state.user && String(state.user.id).toLowerCase() === id) return state.user.name || "Tu";
    return names[id] || names[uid] || String(uid || "").split("@")[0];
}
function coverRankingRows() {
    const ranking = state.data?.ranking_maestros || {};
    const hidden = new Set((state.data?.participant_contract?.hidden_ids || []).map(id => String(id).toLowerCase()));
    return Object.entries(ranking).filter(([uid]) => !hidden.has(String(uid).toLowerCase()))
        .map(([uid, values]) => ({ uid, name: coverDisplayName(uid), total: Number(values?.total || 0), jornada: Number(values?.jornada_live ?? values?.jornada ?? 0) }))
        .sort((a, b) => b.total - a.total || b.jornada - a.jornada || a.name.localeCompare(b.name, "es"));
}
function coverPredictionSigns(e) { if (Array.isArray(e)) return e; return Array.isArray(e?.signos) ? e.signos : []; }
function coverPenaReading(row) {
    if (!row || !Number(row.total || 0)) return null;
    // Se comparan los PESOS crudos, no los porcentajes. Los porcentajes se
    // redondean y el resto siempre va a parar a la tercera casilla, asi que un
    // empate con un voto por signo dejaba ganadora sola a esa casilla: un
    // consenso fabricado con el reparto descentrado. Con pesos, el empate se ve
    // como empate.
    const { v1, vx, v2 } = coverPenaVoteWeights(row);
    const r = [{ s: "1", v: Number(v1) || 0 }, { s: "X", v: Number(vx) || 0 }, { s: "2", v: Number(v2) || 0 }];
    const max = Math.max(...r.map(x => x.v));
    // Sin votos no hay lectura, y un empate tampoco. Antes se fabricaba un
    // consenso que nadie habia expresado y se puntuaba como acierto:
    //   - con `total > 0` y sin votos, la columna afirmaba un consenso
    //     unanime (siempre "2", por el resto del redondeo);
    //   - un empate real devolvia "1X2", y como `isHitSign("1X2", real)` es true
    //     para cualquier resultado, la columna PEÑA se ponia en verde en todos los
    //     partidos, todos los dias.
    // Un empate es empate, no un acierto: se muestra "—" y no puntua.
    if (max <= 0) return null;
    const winners = r.filter(x => x.v === max).map(x => x.s);
    if (winners.length !== 1) return null;
    const share = coverPenaPercents(row);
    const percent = { 1: share.p1, X: share.px, 2: share.p2 }[winners[0]];
    return { sign: winners[0], percent, total: Number(row.total || 0) };
}

function coverPenaVoteWeights(row) {
    const votes = row?.votes;
    if (votes && typeof votes === "object") {
        return {
            v1: Number(votes["1"] || 0),
            vx: Number(votes.X ?? votes.x ?? 0),
            v2: Number(votes["2"] || 0),
        };
    }
    // Backend already sends p1/px/p2 as percentages and total as peñistas.
    const total = Number(row?.total || 0);
    return {
        v1: Number(row?.p1 || 0) * total / 100,
        vx: Number(row?.px || 0) * total / 100,
        v2: Number(row?.p2 || 0) * total / 100,
    };
}

function coverShareFromWeights(v1, vx, v2) {
    const weight = v1 + vx + v2;
    if (weight <= 0) return { p1: 0, px: 0, p2: 0 };
    const p1 = Math.round((v1 / weight) * 100);
    const px = Math.round((vx / weight) * 100);
    return { p1, px, p2: Math.max(0, 100 - p1 - px) };
}

function coverPenaPercents(row) {
    const { v1, vx, v2 } = coverPenaVoteWeights(row);
    const share = coverShareFromWeights(v1, vx, v2);
    if (v1 + vx + v2 > 0) return share;
    // Sin votos no hay reparto conocido. El resto a "2" fabricaba un consenso
    // (`p2 = 100`) que nadie habia expresado.
    return { p1: 0, px: 0, p2: 0 };
}

function coverAggregatePenaVote(consenso) {
    let w1 = 0, wx = 0, w2 = 0, penistas = 0, matches = 0;
    (Array.isArray(consenso) ? consenso : []).forEach(row => {
        const total = Number(row?.total || 0);
        const { v1, vx, v2 } = coverPenaVoteWeights(row);
        if (v1 + vx + v2 <= 0 && total <= 0) return;
        matches += 1;
        if (total > penistas) penistas = total;
        w1 += v1;
        wx += vx;
        w2 += v2;
    });
    return { ...coverShareFromWeights(w1, wx, w2), penistas, matches };
}
function coverCollectivePenaScore() { return { hits: 0, played: 0, totalMatches: 0 }; }
function coverDisagreementMatch() { return null; }
function coverTightPenaMatch() { return null; }
function coverFixtureHtml() { return ""; }
function updateCoverPorraStep() {}
function hydrateCoverPorra(data = {}) {
    // El panel LA PORRA de la portada no puede quedarse en "Cargando…".
    // `loadPorra()` ya pide `/api/porra` y entrega aquí su respuesta; esta
    // función pinta el resumen compacto con los mismos `data-*` que usan los
    // manejadores globales de la porra, sin duplicar la lógica de envío.
    const body = document.getElementById("cover-porra-content");
    if (!body) return false;
    const payload = data && typeof data === "object" ? data : {};
    const nombreCorto = (nombre, defecto) => {
        const texto = String(nombre ?? defecto ?? "").trim();
        if (!texto) return defecto;
        return typeof getShortName === "function" ? getShortName(texto) : texto;
    };
    const entero = (valor) => {
        const numero = Number(valor);
        return Number.isInteger(numero) && numero >= 0 && numero <= 15 ? String(numero) : "";
    };
    if (payload.status !== "ok" || payload.enabled === false) {
        body.innerHTML = `<div class="cx-empty">${escapeHtml(payload.message || "Sin porra disponible.")}</div>`;
        return true;
    }
    const match = payload.match && typeof payload.match === "object" ? payload.match : {};
    const mine = payload.mine && typeof payload.mine === "object" ? payload.mine : {};
    const local = nombreCorto(match.local, "Local");
    const visitante = nombreCorto(match.visitante, "Visitante");
    const titulo = String(payload.label || "Porra");
    const golesLocal = entero(mine.goles_local);
    const golesVisitante = entero(mine.goles_visitante);
    const guardada = golesLocal !== "" && golesVisitante !== "";
    const partidoId = Number(match.partido_id);
    const cabecera = `<div class="cx-porra-match"><strong>${escapeHtml(local)} vs ${escapeHtml(visitante)}</strong><span>${escapeHtml(titulo)}</span></div>`;
    if (guardada) {
        body.innerHTML = `${cabecera}<div class="cx-porra-saved"><span>Tu porra</span><b>${golesLocal}-${golesVisitante}</b></div>`;
        return true;
    }
    if (payload.locked) {
        body.innerHTML = `${cabecera}<div class="cx-porra-saved cx-porra-closed"><span>Porra cerrada</span></div>`;
        return true;
    }
    body.innerHTML = `${cabecera}
        <form class="cx-porra-form" data-porra-form data-partido-id="${Number.isFinite(partidoId) ? partidoId : ""}">
            <label class="cx-porra-form-label" for="cover-porra-home">Tu marcador exacto</label>
            <input id="cover-porra-home" data-porra-home type="number" min="0" max="15" inputmode="numeric" aria-label="Goles de ${escapeHtml(match.local || "local")}" value="${golesLocal}">
            <span aria-hidden="true">-</span>
            <input id="cover-porra-away" data-porra-away type="number" min="0" max="15" inputmode="numeric" aria-label="Goles de ${escapeHtml(match.visitante || "visitante")}" value="${golesVisitante}">
            <button type="button" data-porra-submit>${payload.auth ? "OK" : "Entrar"}</button>
            <small class="cx-porra-form-status" data-porra-status aria-live="polite"></small>
        </form>
        <p class="cx-porra-hint">Marcador exacto: <b>+2 puntos</b>.</p>`;
    return true;
}

function _abbr(name, max) {
    if (!name) return "—";
    const s = String(name).trim();
    const clean = s.replace(/[^A-Za-zÁÉÍÓÚÜÑáéíóúüñ\s]/g, "");
    const abbr = clean.split(/\s+/).map(w => w[0] || "").join("").slice(0, max || 3).toUpperCase();
    return abbr || s.slice(0, max || 3).toUpperCase();
}
function _fitName(name, maxLen) {
    if (!name) return "—";
    const s = String(name).trim();
    return s.length > maxLen ? s.slice(0, maxLen - 1) + "…" : s;
}
function _liveMinuteLabel(match) {
    const candidates = [match?.minuto_live, match?.minuto, match?.minute, match?.time];
    for (const raw of candidates) {
        const clean = String(raw ?? "").trim();
        if (!clean || clean === "-" || clean === "—") continue;
        if (/^(HT|DESC|DESCANSO|HALF)/i.test(clean)) return "Desc.";
        const parsed = clean.match(/\d{1,3}/);
        if (parsed) return `${parsed[0]}'`;
        return clean;
    }
    const numeric = typeof matchMinuteValue === "function" ? matchMinuteValue(match) : 0;
    if (numeric > 0) return `${numeric}'`;
    return (typeof liveStage === "function" && liveStage(match) === "HT") ? "Desc." : "LIVE";
}
function _liveScoreText(match) {
    if (typeof liveScoreDisplay === "function") {
        return liveScoreDisplay(match, match?.marcador_base || match?.score || match?.marcador || "—") || "—";
    }
    if (typeof scoreOnly === "function") return scoreOnly(match?.marcador || match?.score) || match?.marcador_base || "—";
    return match?.marcador_base || match?.score || match?.marcador || "—";
}
function _liveTeamLabel(name, maxLen) {
    const label = typeof getShortName === "function" ? getShortName(name) : name;
    return _fitName(label, maxLen || 12);
}
/* Los partidos del panel externo (Highlightly) llegan con home.name/away.name
   en lugar de local/visitante; sin esto su nombre se perdia en la portada. */
function _matchSideName(match, side) {
    if (!match) return "";
    if (side === "home") {
        return String(match.local || match.home_name || (match.home || {}).name || "").trim();
    }
    return String(match.visitante || match.away_name || (match.away || {}).name || "").trim();
}
function _matchPairKey(match) {
    const canonical = name => typeof normalizeName === "function"
        ? normalizeName(name)
        : String(name || "").trim().toLowerCase();
    return `${canonical(_matchSideName(match, "home"))}|${canonical(_matchSideName(match, "away"))}`;
}
function _liveCompLabel(match) {
    if (!match) return "";
    const raw = match.competition_name || (match.competition || {}).name || "";
    const label = String(raw).trim().toUpperCase();
    if (!label || label === "OTROS" || label === "FRIENDLIES") return "";
    const compact = {
        "LA LIGA": "LALIGA",
        "SEGUNDA DIVISION": "SEGUNDA",
        "LIGA F": "LIGA F",
        "LIGA F MOEVE": "LIGA F",
        "PRIMERA DIVISION FEMENINA": "LIGA F",
        "PREMIER LEAGUE": "PREMIER",
        "BUNDESLIGA": "BUNDES",
        "LIGUE 1": "LIGUE 1",
    };
    return compact[label] || label.split(/\s+/)[0].slice(0, 8);
}
/* Directos de hoy fuera de la quiniela (p. ej. un viernes con Racing - Elche):
   el backend los sirve en live_matches; sin este refuerzo el panel EN DIRECTO
   de la portada se queda a cero aunque haya futbol en juego. */
function _otherLiveMatchesToday(quinielaPairs) {
    const source = typeof getLiveLeagueMatches === "function" ? getLiveLeagueMatches() : [];
    return source.filter(m => m && !quinielaPairs.has(_matchPairKey(m)));
}
function _mtone(col) {
    if (!col) return "is-default";
    const id = String(col.id || col.label || "").toLowerCase();
    if (id.includes("claude")) return "is-claude";
    if (id.includes("chatgpt") || id.includes("gpt")) return "is-chatgpt";
    if (id.includes("gemini")) return "is-gemini";
    if (id.includes("grok")) return "is-grok";
    if (id.includes("copilot")) return "is-copilot";
    if (id.includes("programa")) return "is-programa";
    return "is-default";
}
function _mlogoKey(colOrUid) {
    const id = String(colOrUid?.id || colOrUid?.label || colOrUid || "").toLowerCase();
    if (id.includes("claude")) return "claude";
    if (id.includes("chatgpt") || (id.includes("gpt") && !id.includes("gemini"))) return "chatgpt";
    if (id.includes("gemini")) return "gemini";
    if (id.includes("grok")) return "grok";
    if (id.includes("copilot")) return "copilot";
    if (id.includes("programa")) return "programa";
    return "";
}
function _mlogoSrc(colOrUid) {
    const key = _mlogoKey(colOrUid);
    if (!key) return "";
    const assetsV = document.body?.dataset?.assetsV || "";
    return `/static/img/maestros/${key}.svg?v=${encodeURIComponent(assetsV)}`;
}
function _mlogoImg(colOrUid, size) {
    const src = _mlogoSrc(colOrUid);
    if (!src) return "";
    const px = Number(size || 12);
    const label = String(colOrUid?.label || colOrUid?.name || colOrUid?.id || colOrUid || "");
    return `<img class="cx-mi-logo" src="${src}" alt="" width="${px}" height="${px}" decoding="async" aria-hidden="true"${label ? ` title="${escapeHtml(label)}"` : ""}>`;
}
function _mshort(col) {
    const id = String(col?.id || col?.label || "").toLowerCase();
    if (id.includes("claude")) return "CLD";
    if (id.includes("chatgpt") || (id.includes("gpt") && !id.includes("gemini"))) return "GPT";
    if (id.includes("gemini")) return "GEM";
    if (id.includes("grok")) return "GRK";
    if (id.includes("copilot")) return "COP";
    if (id.includes("programa")) return "PRG";
    return String(col?.label || id || "?").slice(0, 3).toUpperCase();
}
function _visibleMasters(cols) {
    // Todas las columnas oficiales del contrato, incluido el Programa (PRG):
    // su boleto editorial debe verse en la quiniela igual que en la vista TICKET.
    return cols || [];
}
function _upick(i) {
    const s = state.my_signs || [];
    const r = s[i];
    if (!r || r === "-") return null;
    return String(r).toUpperCase();
}
function _live(m) {
    if (!m) return false;
    if (typeof isExpiredLiveMatch === "function" && isExpiredLiveMatch(m)) return false;
    if (typeof isMatchLiveNow === "function") return isMatchLiveNow(m);
    if (typeof isLiveStatus === "function" && isLiveStatus(m.status)) return true;
    if (typeof isLiveMatch === "function" && isLiveMatch(m)) return true;
    return false;
}
function _finished(m) {
    if (!m) return false;
    if (typeof isFinishedStatus === "function" && isFinishedStatus(m.status)) return true;
    if (typeof isImplicitlyFinished === "function" && isImplicitlyFinished(m)) return true;
    if (typeof isExpiredLiveMatch === "function" && isExpiredLiveMatch(m)) return true;
    return false;
}
function _hasScore(m) {
    if (!m) return false;
    if (m.goles_local != null && m.goles_visitante != null) return true;
    if (m.marcador_base && String(m.marcador_base).trim()) return true;
    if (typeof scoreOnly === "function") return Boolean(scoreOnly(m.marcador || m.score));
    return Boolean(String(m.marcador || m.score || "").match(/\d+\s*[-–]\s*\d+/));
}
function _whenKind(m) {
    if (!m) return "empty";
    const scheduled = typeof needsFixtureSchedule === "function"
        ? needsFixtureSchedule(m)
        : (!_hasScore(m) && !_live(m));
    if (_live(m) && !scheduled) return "live";
    if ((_finished(m) || _hasScore(m)) && !scheduled) return "finished";
    return "scheduled";
}
function _whenLabel(m) {
    const kind = _whenKind(m);
    if (kind === "live") {
        if (typeof liveScoreWithMinute === "function") {
            return liveScoreWithMinute(m, _liveScoreText(m));
        }
        const score = _liveScoreText(m);
        const minute = _liveMinuteLabel(m);
        return minute && minute !== "LIVE" ? `${score} · ${minute}` : score;
    }
    if (kind === "finished") return _liveScoreText(m);
    if (typeof fixtureScheduleDisplay === "function") return fixtureScheduleDisplay(m);
    return m?.hora || m?.kickoff || m?.marcador || "";
}
function _whenCell(m) {
    const kind = _whenKind(m);
    const label = _whenLabel(m) || "—";
    const kindClass = kind === "live" ? " is-live-score" : (kind === "finished" ? " is-ft-score" : " is-schedule");
    return `<td class="cx-r-when${kindClass}" data-cover-when="${kind}"><span class="cx-r-when-val">${escapeHtml(String(label))}</span></td>`;
}
function _closed(m) {
    if (!m) return false;
    if (_finished(m) && _hasScore(m)) return true;
    const r = String(m.signo_actual || "").toUpperCase();
    return ["1", "X", "2"].includes(r);
}
/* Un doble es un acierto si el signo real cae dentro del: "12" con resultado
   1 es ACIERTO, no fallo. La portada comparaba con igualdad estricta y
   marcaba como fallo justo los dobles del programa (12 en P1, 1X, X2...), que
   es lo que mas se rompia al contar aciertos y fallos. El pleno se compara
   por marcador exacto (3+ es "M"), igual que scoring.py en el backend. */
function _coverSignHit(sign, realSign, isPleno) {
    const prediction = String(sign || "-").trim().toUpperCase();
    const result = String(realSign || "-").trim().toUpperCase();
    if (!prediction || prediction === "-" || !result || result === "-") return false;
    if (typeof isHitSign === "function") return !!isHitSign(sign, realSign, !!isPleno);
    if (isPleno && typeof plenoScoreKey === "function") {
        const pick = plenoScoreKey(prediction);
        const actual = plenoScoreKey(result);
        return !!pick && !!actual && pick === actual;
    }
    return prediction.includes(result);
}
function _coverRealRef(match, isPleno) {
    // En el pleno la referencia es el marcador exacto, no el 1X2: el signo del
    // pleno es el resultado y con 1X2 la fila nunca podia acertar.
    if (!isPleno) return String(match?.signo_actual || "").toUpperCase();
    const score = String(match?.marcador_base || match?.marcador || "").trim();
    return score || String(match?.signo_actual || "").toUpperCase();
}
function _exactGoalScore(value) {
    const match = String(value || "").trim().match(/^(\d{1,2})\s*[-–]\s*(\d{1,2})$/);
    return match ? `${match[1]}-${match[2]}` : "—";
}
function _coverPlenoPanel(match, predictions, masters, consensus) {
    if (!match) return "";
    const home = typeof getShortName === "function" ? getShortName(match.local) : match.local;
    const away = typeof getShortName === "function" ? getShortName(match.visitante) : match.visitante;
    const score = _exactGoalScore(match.goles_local != null && match.goles_visitante != null
        ? `${match.goles_local}-${match.goles_visitante}`
        : (match.marcador_base || match.marcador || match.score));
    const predictionsHtml = masters.map(col => {
        const signs = coverPredictionSigns(predictions[col.id]);
        const value = _exactGoalScore(signs[14]);
        return `<div class="cx-pleno-prediction ${_mtone(col)}"><span>${escapeHtml(col.label)}</span><b>${escapeHtml(value)}</b></div>`;
    }).join("");
    const penaValue = _exactGoalScore(consensus?.topScore?.[0]);
    const userValue = _exactGoalScore(_upick(14));
    return `<section class="cx-pleno-panel" data-page-action="TICKET" data-match-id="${escapeHtml(match.id)}" aria-label="Pleno al quince, marcador de goles">
        <header class="cx-pleno-head"><span>PLENO AL QUINCE</span><b>${escapeHtml(_fitName(home, 18))} <i>–</i> ${escapeHtml(_fitName(away, 18))}</b><strong>${escapeHtml(score)}</strong></header>
        <div class="cx-pleno-predictions">${predictionsHtml}<div class="cx-pleno-prediction is-pena"><span>PEÑA</span><b>${escapeHtml(penaValue)}</b></div><div class="cx-pleno-prediction is-user"><span>TÚ</span><b>${escapeHtml(userValue)}</b></div></div>
    </section>`;
}
function _diffParts(deadline) {
    if (!deadline) return { d: 0, h: 0, m: 0, s: 0, ms: 0, urgent: false };
    const target = _coverDeadlineMs(deadline);
    if (!target) return { d: 0, h: 0, m: 0, s: 0, ms: 0, urgent: false };
    const ms = Math.max(0, target - Date.now());
    const s = Math.floor(ms / 1000);
    return {
        d: Math.floor(s / 86400),
        h: Math.floor((s % 86400) / 3600),
        m: Math.floor((s % 3600) / 60),
        s: s % 60,
        ms,
        urgent: ms < 3_600_000,
    };
}

function filasCubiertaAlineadas(idsFilas, idsPartidos) {
    // El parche incremental no puede emparejar filas por posicion. Esta regla es
    // deliberadamente estricta: ante una longitud, orden o identidad distintas,
    // el llamante tiene que hacer el render completo.
    if (!Array.isArray(idsFilas) || !Array.isArray(idsPartidos)) return false;
    if (idsFilas.length === 0 || idsFilas.length !== idsPartidos.length) return false;
    return idsFilas.every((idFila, idx) => {
        const idPartido = idsPartidos[idx];
        if (idFila === undefined || idFila === null || idPartido === undefined || idPartido === null) return false;
        if (String(idFila) === "" || String(idPartido) === "") return false;
        return String(idFila) === String(idPartido);
    });
}

/* ==========================================================================
   VISTA SIMPLE — la portada por defecto (Jornada 17 «en simple»)
   Una tabla por columnas, movil primero:
   Partido (fecha y hora) | Resultado | MrPurple | Programa | Tecnotron | Grok | Sonia.

   Reglas que NO viven aqui:
   - El acierto/fallo llega DECIDIDO desde el backend (payload `simple_view`,
     calculado con liga_maestros/scoring.py): en JS no se vuelve a puntuar, para
     que un doble o el pleno no se puedan contar distinto que en el ranking.
   - El marcador nunca se inventa: sin resultado verificado la casilla se queda
     en raya («—») y la fila aparece pendiente.
   - La portada fija y blanquea sus cinco columnas permitidas: aqui solo se
     pintan. Las demás líneas siguen en BD, pero no se muestran ni se puntúan.
   El resto de secciones de la portada no se borra: siguen debajo, plegadas en
   «Otras secciones», y el historico J1-J16 se ve con el selector #jornada-nav.
   ========================================================================== */

function simpleViewPayload() {
    return state?.data?.simple_view || null;
}

function simpleViewColumns(payload) {
    const incoming = Array.isArray(payload?.columns) ? payload.columns : [];
    const byId = new Map(incoming.filter(col => col?.id).map(col => [String(col.id).toLowerCase(), col]));
    // Orden/identidad cerrados incluso si llega un payload antiguo o parcial;
    // los ids ajenos se descartan y las columnas ausentes quedan pendientes.
    return [
        ["mrpurple", "MrPurple"],
        ["programa", "Programa"],
        ["tecnotron", "Tecnotron"],
        ["grok", "Grok"],
        ["sonia", "Sonia"],
    ].map(([id, name]) => {
        const source = byId.get(id);
        return { ...(source || {}), id, name, sin_linea: source ? Boolean(source.sin_linea) : true };
    });
}

/* Estados con marcador VERIFICADO. STALE (directo degradado) queda fuera a
   proposito: pintarlo seria inventar un resultado, igual que hace el backend. */
const _SV_LIVE_STATUSES = ["LIVE", "IN PLAY", "IN_PLAY", "HT", "HALF TIME", "HALF TIME BREAK", "EN JUEGO", "1H", "2H", "ET", "P", "PEN LIVE"];
const _SV_FINAL_STATUSES = ["FT", "FINISHED", "TERMINADO", "AET", "PEN", "AWARDED"];

function simpleViewVerifiedScore(match) {
    if (!match) return "";
    const gl = match.goles_local;
    const gv = match.goles_visitante;
    if (gl != null && gv != null && gl !== "" && gv !== "") return `${gl}-${gv}`;
    return (typeof scoreOnly === "function" && scoreOnly(match.marcador || match.score || "")) || "";
}

/* El payload ligero del poll (30 s) refresca `partidos` pero NO `simple_view`:
   sin este cruce la lista de la quiniela se quedaba con el marcador de la
   carga completa y el directo de cada casilla iba por detras. Solo se adopta
   lo que el partido diga de si mismo (mismo id) y solo en estados
   verificados: nunca se rellena una casilla con un resultado dudoso. */
function freshenSimpleViewRow(row) {
    if (!row) return row;
    const matches = Array.isArray(state?.data?.partidos) ? state.data.partidos : [];
    const source = matches
        .find(match => match && String(match.id ?? "") === String(row.id ?? ""));
    const sourceStatus = String(source?.status || "").toUpperCase();
    const sourceIsLive = _SV_LIVE_STATUSES.includes(sourceStatus)
        && !(typeof isExpiredLiveMatch === "function" && isExpiredLiveMatch(source));
    const sourceIsFinal = _SV_FINAL_STATUSES.includes(sourceStatus);
    let verifiedMatch = (sourceIsLive || sourceIsFinal) && simpleViewVerifiedScore(source) ? source : null;

    // El partido puede llegar primero al panel `live_matches` (con el minuto
    // y el marcador del proveedor) mientras la fila de `partidos` sigue NS.
    // Se cruza por equipos canonicos: Q15 puede decir «Rayo» / «Celta» y el
    // panel «Rayo Vallecano» / «Celta de Vigo».
    if (!verifiedMatch) {
        const panelMatches = [
            ...(Array.isArray(state?.data?.live_matches) ? state.data.live_matches : []),
            ...(typeof getLiveLeagueMatches === "function" ? getLiveLeagueMatches() : []),
        ];
        const rowPair = _matchPairKey(row);
        verifiedMatch = panelMatches.find(match => {
            if (!match || _matchPairKey(match) !== rowPair) return false;
            const status = String(match.status || "").toUpperCase();
            const live = _SV_LIVE_STATUSES.includes(status)
                && !(typeof isExpiredLiveMatch === "function" && isExpiredLiveMatch(match));
            return live && Boolean(simpleViewVerifiedScore(match));
        }) || null;
    }
    if (!verifiedMatch) return row;

    const status = String(verifiedMatch.status || "").toUpperCase();
    const live = _SV_LIVE_STATUSES.includes(status);
    const marcador = simpleViewVerifiedScore(verifiedMatch);
    const next = { ...row, status, en_juego: live };
    if (marcador) {
        next.resultado = marcador;
        next.has_result = true;
    }
    if (live) {
        const raw = String(verifiedMatch.minuto_live || verifiedMatch.minuto || verifiedMatch.minute || verifiedMatch.time || "").match(/\d{1,3}/);
        const minuto = raw ? `${raw[0]}'` : (typeof _liveMinuteLabel === "function" ? _liveMinuteLabel(verifiedMatch) : "");
        if (minuto && minuto !== "LIVE") next.minuto = minuto;
    }
    return next;
}

function simpleViewRows(payload) {
    const rows = Array.isArray(payload?.rows) ? payload.rows : [];
    if (rows.length) return rows.map(freshenSimpleViewRow);
    // Fallback para una respuesta antigua/parcial: solo acepta marcadores con
    // estado válido; STALE u otro estado degradado queda pendiente.
    return (state?.data?.partidos || []).slice(0, 15).map((match, index) => {
        const golesLocal = match.goles_local;
        const golesVisitante = match.goles_visitante;
        const status = String(match.status || "").toUpperCase();
        const verificado = _SV_FINAL_STATUSES.includes(status) || _SV_LIVE_STATUSES.includes(status);
        const hayMarcador = verificado && golesLocal != null && golesVisitante != null;
        const hora = String(match.hora || "").trim();
        const fecha = String(match.fecha_limpia || "").trim();
        const id = Number(match.id) || index + 1;
        return {
            id,
            local: String(match.local || ""),
            visitante: String(match.visitante || ""),
            cuando: [fecha, hora && hora !== "-" ? hora : ""].filter(Boolean).join(" "),
            is_pleno: id === 15,
            has_result: hayMarcador,
            resultado: hayMarcador ? `${golesLocal}-${golesVisitante}` : "",
            en_juego: _SV_LIVE_STATUSES.includes(status),
            minuto: String(match.minuto_live || match.minuto || ""),
            picks: {},
        };
    });
}

function simpleViewMark(pick) {
    if (!pick || pick.hit === null || pick.hit === undefined) return { glyph: "", state: "" };
    return pick.hit ? { glyph: "✓", state: "is-hit" } : { glyph: "✗", state: "is-miss" };
}

function simpleViewWhenText(row) {
    const cuando = String(row?.cuando || "").trim();
    // Casilla sin hora verificada (J17, la 14): se queda sin ella, sin rellenar.
    return cuando || "—";
}

function simpleViewResultText(row) {
    if (!row || !row.has_result) return "—";
    const marcador = String(row.resultado || "").trim();
    if (!marcador) return "—";
    if (!row.en_juego) return marcador;
    const minuto = String(row.minuto || "").trim();
    const digitos = minuto.match(/\d{1,3}/);
    if (digitos) return `${marcador} · ${digitos[0]}'`;
    if (minuto && minuto !== "-") return `${marcador} · ${minuto}`;
    return marcador;
}

function simpleViewDateText(fecha) {
    const texto = String(fecha || "").trim();
    const partes = texto.split("-");
    return partes.length === 3 ? `${partes[2]}/${partes[1]}/${partes[0]}` : texto;
}

function simpleViewMetaHtml(payload) {
    const boleto = payload?.boleto || {};
    const items = [["JORNADA", String(payload?.jornada || state?.data?.jornada || "")]];
    if (boleto.nombre) items.push(["BOLETO", boleto.nombre]);
    if (boleto.concurso) items.push(["CONCURSO", boleto.concurso]);
    if (boleto.fecha) items.push(["SE JUEGA", simpleViewDateText(boleto.fecha)]);
    if (boleto.cierre) items.push(["CIERRE", `${boleto.cierre}${boleto.cierre_estimado ? " (estimado)" : ""}`]);
    // Sin importe de bote: mientras no este confirmado, no se pinta ninguno.
    return `<dl class="cx-sv-meta">${items
        .map(([key, value]) => `<div class="cx-sv-meta-item"><dt>${escapeHtml(key)}</dt><dd>${escapeHtml(value)}</dd></div>`)
        .join("")}</dl>`;
}

function kawaiiCeldaEditable(col, row) {
    // Selector 1X2 de la columna propia, con el mismo contrato de eventos que
    // la vista de boleto: `.clickable` + `data-sign`/`data-pleno` + match-idx.
    const idx = Number(row.id) - 1;
    const signo = (state.my_signs || [])[idx] || "-";
    const pick = (row.picks || {})[col.id] || null;
    // El backend calcula el acierto. Conserva el color del boleto guardado
    // mientras se edita, siempre que siga visible el mismo signo puntuado.
    const sameScoredSign = pick && String(pick.signo || "-").localeCompare(String(signo)) === 0;
    const scoredState = sameScoredSign && pick.hit !== null && pick.hit !== undefined
        ? (pick.hit ? "is-hit" : "is-miss")
        : "";
    if (row.is_pleno) {
        const etiqueta = signo === "-" ? "Elegir" : signo;
        return `<td class="cx-sv-cell cx-sv-me is-editing${signo === "-" ? " is-empty" : ""}${scoredState ? ` ${scoredState}` : ""}">`
            + `<button type="button" class="kk-sign kk-sign-pleno clickable${signo !== "-" ? " is-active" : ""}${scoredState ? ` ${scoredState}` : ""}" data-pleno="true" data-match-idx="${idx}" aria-label="Elegir el marcador del Pleno al 15">${escapeHtml(etiqueta)}</button></td>`;
    }
    const botones = ["1", "X", "2"]
        .map(opcion => {
            const activo = signo === opcion;
            const resultado = activo ? scoredState : "";
            return `<button type="button" class="kk-sign clickable${activo ? " is-active" : ""}${resultado ? ` ${resultado}` : ""}" data-sign="${opcion}" data-match-idx="${idx}" aria-pressed="${activo ? "true" : "false"}" aria-label="Marcar ${opcion} en la casilla ${idx + 1}">${opcion}</button>`;
        })
        .join("");
    return `<td class="cx-sv-cell cx-sv-me is-editing" title="Tu columna: marca tu pronostico">${botones}</td>`;
}

function simpleViewCellHtml(col, row) {
    if (col && col.es_mia && kawaiiPuedeEditarLinea()) return kawaiiCeldaEditable(col, row);
    const pick = (row.picks || {})[col.id] || null;
    const signo = pick ? String(pick.signo || "-") : "-";
    const vacio = !signo || signo === "-";
    const mark = vacio ? { glyph: "", state: "" } : simpleViewMark(pick);
    const doble = Boolean(pick && pick.dobles && !row.is_pleno);
    const classes = ["cx-sv-cell", doble ? "is-double" : "", vacio ? "is-empty" : "", mark.state]
        .filter(Boolean)
        .join(" ");
    const estado = mark.glyph ? (pick.hit ? "acierto" : "fallo") : "pendiente";
    const etiqueta = `${col.name || col.id}: ${vacio ? "sin linea" : signo}, ${estado}`;
    return `<td class="${classes}" title="${escapeHtml(etiqueta)}">`
        + `<span class="cx-sv-sign">${vacio ? "—" : escapeHtml(signo)}</span>`
        + `<span class="cx-sv-mark" aria-hidden="true">${mark.glyph}</span></td>`;
}

function simpleViewRowHtml(row, columns) {
    const cells = columns.map(col => simpleViewCellHtml(col, row)).join("");
    const resultClass = row.has_result ? (row.en_juego ? " is-live" : " is-ft") : " is-pending";
    return `<tr class="cx-sv-row${row.is_pleno ? " is-pleno" : ""}" data-id="${escapeHtml(row.id)}">`
        + `<th scope="row" class="cx-sv-match">`
        + `<span class="cx-sv-idx" aria-hidden="true">${escapeHtml(row.id)}</span>`
        + `<span class="cx-sv-teams"><b>${escapeHtml(row.local)}</b><i>–</i><b>${escapeHtml(row.visitante)}</b></span>`
        + `<span class="cx-sv-when">${escapeHtml(simpleViewWhenText(row))}</span>`
        + `</th>`
        + `<td class="cx-sv-result${resultClass}">`
        + `<span class="cx-sv-result-val">${escapeHtml(simpleViewResultText(row))}</span></td>`
        + cells
        + `</tr>`;
}

function simpleViewColumnas(payload) {
    // El boleto «Tú» del usuario autenticado ocupa la columna MrPurple sin
    // cambiar el nombre ni el orden fijados para la portada.
    return simpleViewColumns(payload);
}

function kawaiiTablaHtml() {
    const payload = simpleViewPayload();
    const columns = simpleViewColumnas(payload);
    const rows = simpleViewRows(payload);
    const casillas = rows.filter(row => !row.is_pleno).slice(0, 14);
    const plenoRow = rows.find(row => row.is_pleno) || null;
    const totalCasillas = Number(payload?.total_casillas || 14);
    const spanCols = 2 + columns.length;

    const headCells = columns
        .map(col => `<th scope="col" class="cx-sv-col" data-col="${escapeHtml(col.id)}">`
            + `<span class="cx-sv-col-name">${escapeHtml(col.name || col.id)}</span>`
            + (col.sin_linea ? `<span class="cx-sv-col-flag">pendiente</span>` : "")
            + `</th>`)
        .join("");
    const footCells = columns
        .map(col => {
            const total = (payload?.totals || {})[col.id] || null;
            if (col.sin_linea || !total) {
                return `<td class="cx-sv-cell cx-sv-total is-empty" title="Sin linea para esta jornada">&mdash;</td>`;
            }
            const aciertos = Number(total.aciertos || 0);
            const jugados = Number(total.jugados || 0);
            const detalle = `${aciertos} aciertos en ${jugados} partidos con resultado, de ${totalCasillas} casillas`;
            return `<td class="cx-sv-cell cx-sv-total" title="${escapeHtml(detalle)}">`
                + `<b>${aciertos}/${totalCasillas}</b><small>${escapeHtml(col.name || col.id)}</small></td>`;
        })
        .join("");

    const plenoBody = plenoRow
        ? `<tbody class="cx-sv-pleno">`
            + `<tr class="cx-sv-pleno-head"><th colspan="${spanCols}" scope="colgroup">PLENO AL 15 · GOLES EXACTOS (fuera del total de ${totalCasillas})</th></tr>`
            + simpleViewRowHtml(plenoRow, columns)
            + `</tbody>`
        : "";

    return `<table class="cx-sv-table">
                <thead>
                    <tr>
                        <th scope="col" class="cx-sv-match-head">PARTIDO (fecha y hora)</th>
                        <th scope="col" class="cx-sv-result-head">RESULTADO</th>
                        ${headCells}
                    </tr>
                </thead>
                <tbody class="cx-sv-body">${casillas.map(row => simpleViewRowHtml(row, columns)).join("")}</tbody>
                ${plenoBody}
                <tfoot>
                    <tr>
                        <th colspan="2" scope="row" class="cx-sv-total-label">TOTAL · ${totalCasillas} CASILLAS SIN PLENO</th>
                        ${footCells}
                    </tr>
                </tfoot>
            </table>`;
}

function simpleViewHtml() {
    const payload = simpleViewPayload();
    const rows = simpleViewRows(payload);
    const casillas = rows.filter(row => !row.is_pleno).slice(0, 14);
    const plenoRow = rows.find(row => row.is_pleno) || null;
    const sinHora = casillas.concat(plenoRow ? [plenoRow] : []).filter(row => !String(row.cuando || "").trim());
    const notas = [
        "Sin resultado verificado la casilla se queda en —: nunca se inventa un marcador.",
    ];
    if (sinHora.length) {
        notas.push(`Casilla${sinHora.length > 1 ? "s" : ""} ${sinHora.map(row => row.id).join(", ")} sin hora verificada en la fuente oficial.`);
    }

    return `
        <div class="cx-sv-scroll" tabindex="0">${kawaiiTablaHtml()}</div>
        <footer class="cx-sv-note"><ul>${notas.map(nota => `<li>${escapeHtml(nota)}</li>`).join("")}</ul></footer>
    `;
}

/* ==========================================================================
   PAGINA UNICA KAWAII — «la quiniela ES la web».

   Una sola vista con todo lo de la jornada: cabecera, acceso con Google,
   franja de directo con datos reales, la tabla de la vista simple (✓/✗ por
   celda, signos simples, pleno aparte y totales al pie) y la clasificacion
   final. Fuera juegos, quiz, landing, trash-talk y consejo de IA.

   Reglas que NO viven aqui:
   - El acierto/fallo y los totales llegan decididos desde el backend (payload
     `simple_view`, puntuado una sola vez en liga_maestros/scoring.py).
   - Sin resultado verificado la casilla se queda en «—»: nunca se inventa.
   - La linea del registrado se guarda con el mecanismo existente
     (POST /api/predicciones/save) y solo mientras la jornada esta abierta.
   ========================================================================== */

const _KK_AVATARES = ["🦖", "🤖", "🔮", "👾", "🦊", "🐼", "🐸", "🐵", "🦄", "🐱"];

function kawaiiPuedeEditarLinea() {
    if (!state.user || !state.data) return false;
    if (coverIsClosed()) return false;
    if (String(state.data.jornada) !== String(state.data.max_jornada)) return false;
    // Mismas reglas que el boton del topbar: sin boleto guardado se edita ya;
    // con boleto guardado, solo al pulsar «Editar quiniela».
    return Boolean(state.editMode || state.draftDirty || !hasSavedTicket());
}

function kawaiiLoginHtml() {
    if (state.user) return "";
    if (state.data && state.data.auth_enabled === false) return "";
    return `<a class="kk-glogin" href="/login/google">
            <span class="kk-g" aria-hidden="true">G</span>
            Entrar con Google para dejar tu quiniela
        </a>`;
}

/* ---------- panel lateral con TODOS los directos ---------- */

/* Casilla de la quiniela que corresponde al partido (0 si no esta en el boleto). */
function kawaiiQuinielaSlot(match) {
    if (typeof quinielaSlotForMatch === "function") return quinielaSlotForMatch(match);
    if (!match) return 0;
    const key = _matchPairKey(match);
    const partidos = Array.isArray(state?.data?.partidos) ? state.data.partidos : [];
    const found = partidos.find(partido => {
        if (!partido) return false;
        if (match.id != null && String(partido.id ?? "") === String(match.id)) return true;
        return key && key !== "|" && _matchPairKey(partido) === key;
    });
    if (!found) return 0;
    const id = Number(found.id);
    return Number.isFinite(id) && id >= 1 && id <= 15 ? id : 0;
}

/* Todos los partidos en juego que ya sirve el backend (`live_matches`: las 5
   ligas + la quiniela, deduplicado en origen). La lista compartida se vuelve a
   deduplicar por pareja de equipos y se ordena por casilla del boleto. */
function kawaiiLiveMatches() {
    if (typeof getAllLiveMatches === "function") return getAllLiveMatches();
    const source = [
        ...(typeof getLiveLeagueMatches === "function" ? getLiveLeagueMatches() : []),
        ...(Array.isArray(state?.data?.partidos) ? state.data.partidos : []),
    ];
    const seen = new Set();
    const rows = [];
    source.forEach(match => {
        if (!match) return;
        const key = _matchPairKey(match);
        if (!key || key === "|" || seen.has(key)) return;
        if (!_live(match) || _finished(match)) return;
        if (typeof isExpiredLiveMatch === "function" && isExpiredLiveMatch(match)) return;
        seen.add(key);
        rows.push(match);
    });
    return rows;
}

function kawaiiLiveItemHtml(match) {
    const comp = _liveCompLabel(match);
    const home = _matchSideName(match, "home");
    const away = _matchSideName(match, "away");
    const marcador = _liveScoreText(match);
    const minuto = _liveMinuteLabel(match);
    const slot = kawaiiQuinielaSlot(match);
    return `<li class="kk-live-item${slot ? " is-quiniela" : ""}">
                <div class="kk-live-meta">
                    ${comp ? `<span class="kk-live-comp">${escapeHtml(comp)}</span>` : ""}
                    ${slot ? `<span class="kk-live-slot" title="Casilla ${slot} de la quiniela">Casilla ${slot}</span>` : ""}
                    <span class="kk-live-min">${escapeHtml(String(minuto || "EN JUEGO"))}</span>
                </div>
                <div class="kk-live-body">
                    <b>${escapeHtml(_fitName(home, 22))}</b><i aria-hidden="true">–</i><b>${escapeHtml(_fitName(away, 22))}</b>
                    <span class="kk-live-score">${escapeHtml(String(marcador || "—"))}</span>
                </div>
            </li>`;
}

function kawaiiLiveAsideHtml() {
    const matches = kawaiiLiveMatches();
    if (!matches.length) return "";
    const open = typeof livePanelShouldOpen === "function" ? livePanelShouldOpen() : true;
    return `<aside class="kk-live-aside" aria-label="Todos los partidos en directo">
            <details class="lm-live-fold"${open ? " open" : ""}>
                <summary class="kk-live-head">
                    <span class="kk-live-pulse" aria-hidden="true"></span>
                    <b>EN DIRECTO</b>
                    <span class="kk-live-count">${matches.length}</span>
                    <span class="kk-live-chevron" aria-hidden="true"></span>
                </summary>
                <ul class="kk-live-list">${matches.map(kawaiiLiveItemHtml).join("")}</ul>
                <p class="kk-live-note">Se actualiza solo, cada 30 segundos.</p>
            </details>
        </aside>`;
}

function kawaiiDirectoHtml() {
    // Con partidos en juego el panel lateral pinta TODOS los directos, asi que
    // la franja se calla. Sin directo se muestra el proximo de la quiniela y,
    // si no hay ninguno, no se pinta nada.
    try {
        if (kawaiiLiveMatches().length) return "";
        const proximo = typeof getNextLeagueMatch === "function" ? getNextLeagueMatch() : null;
        if (!proximo) return "";
        const home = typeof getShortName === "function" ? getShortName(proximo.local || "") : String(proximo.local || "");
        const away = typeof getShortName === "function" ? getShortName(proximo.visitante || "") : String(proximo.visitante || "");
        const cuando = _whenLabel(proximo) || "";
        return `<span class="kk-clock" aria-hidden="true">🕒</span>
            <div class="kk-live-body"><b>PRÓXIMO PARTIDO</b> — ${escapeHtml(home)} · ${escapeHtml(away)}</div>
            <span class="kk-min">${escapeHtml(String(cuando || "—"))}</span>`;
    } catch (error) {
        console.warn("[cover] no se pudo pintar la franja de directo:", error);
        return "";
    }
}

function kawaiiRankingListHtml() {
    let filas = [];
    try {
        filas = coverRankingRows();
    } catch (error) {
        console.warn("[cover] sin clasificacion pintable:", error);
        filas = [];
    }
    const yo = state.user ? String(state.user.id).toLowerCase() : "";
    const items = filas.map((fila, i) => {
        const mia = Boolean(yo) && String(fila.uid).toLowerCase() === yo;
        return `<div class="kk-rank${mia ? " is-you" : ""}">
                    <span class="kk-pos">${i + 1}</span>
                    <span class="kk-av" aria-hidden="true">${_KK_AVATARES[i % _KK_AVATARES.length]}</span>
                    <span class="kk-nm">${escapeHtml(_fitName(fila.name, 18))}${mia ? '<span class="kk-you-tag">tu columna</span>' : ""}</span>
                    <span class="kk-sc"><b>${Number(fila.total || 0)}</b> pts · ${Number(fila.jornada || 0)} en J</span>
                </div>`;
    }).join("");
    if (!items) {
        return `<p class="kk-empty">Todavía sin puntos: cada casilla se puntúa con su resultado verificado.</p>`;
    }
    return items;
}

function kawaiiCabeceraHtml(jornada, payload) {
    const cerrada = coverIsClosed();
    const abierto = coverCloseLabel();
    const chip = cerrada ? "Cerrada" : (abierto === "abierta" ? "Abierta" : `Cierra en ${abierto}`);
    return `<header class="kk-header">
            <span class="kk-logo" aria-hidden="true">🐾</span>
            <div class="kk-brand">
                <h1 class="kk-title">Liga de Maestros</h1>
                <p class="kk-sub">La Peña contra los Maestros IA &middot; 15 casillas, en directo y con aciertos y fallos</p>
            </div>
            <span class="kk-jbadge">J${escapeHtml(String(jornada))}</span>
        </header>
        <div class="kk-ticket">
            ${simpleViewMetaHtml(payload)}
            <span class="kk-pill kk-pill-state${cerrada ? " is-closed" : ""}">${escapeHtml(chip)}</span>
        </div>`;
}

function renderNewspaperCoverPageV3() {
    const payload = simpleViewPayload();
    const jornada = state.data?.jornada || state.jornada || "1";
    const editable = kawaiiPuedeEditarLinea();
    const aviso = state.user
        ? (editable
            ? `<p class="kk-hint">Marca tus signos en la columna <b>Tu</b> y guarda con el botón de arriba.</p>`
            : "")
        : "";

    const liveAside = kawaiiLiveAsideHtml();
    const franja = kawaiiDirectoHtml();

    return `<div class="cx kk-page${liveAside ? " has-live" : ""}">
        <div class="kk-wrap">
            ${kawaiiCabeceraHtml(jornada, payload)}
            ${kawaiiLoginHtml()}
            <div class="kk-layout">
                ${liveAside}
                <div class="kk-main">
                    ${franja ? `<div class="kk-live-wrap">${franja}</div>` : ""}
                    <section class="kk-card kk-table-card" aria-label="Quiniela de la jornada">
                        <h2 class="kk-card-title">📅 Jornada ${escapeHtml(String(jornada))} <span class="kk-tag">14 casillas + pleno al 15</span></h2>
                        ${aviso}
                        ${simpleViewHtml()}
                    </section>
                    <section class="kk-card kk-rank-card" aria-label="Clasificación">
                        <h2 class="kk-card-title">🏆 Clasificación <span class="kk-tag">total · jornada</span></h2>
                        <div class="kk-rank-list">${kawaiiRankingListHtml()}</div>
                    </section>
                </div>
            </div>
            <footer class="kk-foot">🐾 una sola página · resultados en directo, ✓ y ✗ por casilla · sin juegos ni quiz</footer>
        </div>
    </div>`;
}
