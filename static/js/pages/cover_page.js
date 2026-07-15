/* Portada — LA LIGA DE MAESTROS */

function hydrateCoverTypewriter() {}

function coverCloseLabel() {
    const raw = state.data.edit_deadline || state.data.kickoff_at || "";
    if (!raw) return state.data.is_locked ? "cerrada" : "abierta";
    const date = new Date(String(raw).replace(" ", "T"));
    if (Number.isNaN(date.getTime())) return state.data.is_locked ? "cerrada" : "abierta";
    const diff = date.getTime() - Date.now();
    if (diff <= 0 || state.data.is_locked) return "cerrada";
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(minutes / 60);
    const mins = minutes % 60;
    if (hours >= 24) return `${Math.floor(hours / 24)}d ${hours % 24}h`;
    if (hours > 0) return `${hours}h ${String(mins).padStart(2, "0")}m`;
    return `${Math.max(1, mins)}m`;
}

function coverIsClosed() {
    return Boolean(state.data.is_locked) || coverCloseLabel() === "cerrada";
}

function coverMasterNames() {
    const cols = (state.data?.participant_contract?.visible_ai_columns || []);
    return cols
        .map(col => {
            if (Array.isArray(col)) return col[2] || col[0];
            return col.name || col.label || col.id || "";
        })
        .filter(name => name && String(name).toLowerCase() !== "programa");
}

function renderNewspaperCoverPageV3() {
    const matches = state.data.partidos || [];
    const closed = coverIsClosed();
    const jornada = state.data.jornada || state.jornada || "";
    const liveCount = matches.filter(m => isLiveStatus(m.status) || isLiveMatch(m)).length;
    const saved = hasSavedTicket();
    const names = coverMasterNames();
    const namesStr = names.length
        ? names.slice(0, 3).join(", ") + (names.length > 3 ? " y el resto" : "")
        : "las IAs";
    const numPlayers = Object.keys(state.data.ranking_maestros || {}).length || 0;

    const ctaLabel = closed
        ? (saved ? "Ver mi quiniela" : "Ver resultados")
        : (saved ? "Ver o modificar mi quiniela" : "Hacer mi quiniela");

    return `
        <div class="cp">
            <div class="cp-hero">
                <img class="cp-hero-logo" src="/static/img/ligademaestroslogo_trans.png" alt="Liga de Maestros">
                <h1 class="cp-hero-title">&iexcl;Haz tu quiniela!</h1>
                <p class="cp-hero-desc">
                    Cada jornada te la juegas contra los Maestros IA y la Pe&ntilde;a.
                    &iquest;Pleno al 15? Ese es tu trono. &iexcl;Ve a por &eacute;l!
                </p>
                <p class="cp-hero-tagline">&iexcl;Demu&eacute;stralo! &iexcl;Sube en el ranking! &iexcl;S&eacute; el mejor!</p>
                <div class="cp-hero-actions">
                    <button type="button" class="cp-hero-btn" data-page-action="TICKET">${escapeHtml(ctaLabel)}</button>
                    ${!closed && !saved ? `<span class="cp-hero-deadline">Cierre en ${escapeHtml(coverCloseLabel())}</span>` : ""}
                </div>
                <div class="cp-hero-proof"><b>${numPlayers}</b> jugadores esta temporada</div>
            </div>
            <div class="cp-features">
                <button type="button" class="cp-feat" data-page-action="TICKET">
                    <span class="cp-feat-icon">&#9917;</span>
                    <div class="cp-feat-text">
                        <b>Quiniela</b>
                        <p>Haz tu pron&oacute;stico para esta jornada.</p>
                    </div>
                </button>
                <button type="button" class="cp-feat" data-page-action="LIVE">
                    <span class="cp-feat-icon">&#9200;</span>
                    <div class="cp-feat-text">
                        <b>Directo Mundial</b>
                        <p>Resultados en tiempo real de todas las ligas.</p>
                    </div>
                </button>
                <button type="button" class="cp-feat" data-page-action="STANDINGS">
                    <span class="cp-feat-icon">&#128200;</span>
                    <div class="cp-feat-text">
                        <b>Ligas</b>
                        <p>Clasificaciones de Primera y Segunda.</p>
                    </div>
                </button>
                <button type="button" class="cp-feat" data-page-action="SNAKE">
                    <span class="cp-feat-icon">&#127922;</span>
                    <div class="cp-feat-text">
                        <b>Juegos</b>
                        <p>Snake Gol, Quiz y m&aacute;s.</p>
                    </div>
                </button>
            </div>
            ${liveCount ? `<div class="cp-live-banner"><span class="cp-live-dot"></span> ${liveCount} partido${liveCount > 1 ? "s" : ""} en directo &mdash; <button type="button" data-page-action="LIVE">Ver directo</button></div>` : ""}
        </div>`;
}
