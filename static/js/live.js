/* Directo: estado vacio de la pagina de resultados en vivo. */

/* El comentarista IA (MiMo) vive en el payload de /api/liga/data. Sus frases
   se generan solo con partidos de la quiniela en juego; si no hay comentarios
   (sin partidos en juego o IA sin key) no se pinta nada de este panel. */
function directComentaristaComments() {
    const payload = state.data?.comentarista || {};
    return Array.isArray(payload.comentarios) ? payload.comentarios.filter(c => c && c.texto) : [];
}

function directComentaristaSignature(comentarios) {
    return JSON.stringify(comentarios.map(c => [c.texto, c.local, c.visitante, c.minuto, c.marcador]));
}

function directComentaristaHtml() {
    const comentarios = directComentaristaComments();
    if (!comentarios.length) return "";
    const items = comentarios.map(c => {
        const local = getShortName(c.local || "");
        const visitante = getShortName(c.visitante || "");
        const marcador = String(c.marcador || "").trim();
        const minuto = String(c.minuto || "").trim();
        const meta = [local, marcador || "–", visitante].filter(Boolean).join(" ");
        return `
            <li class="direct-comentarista-item">
                <span class="direct-comentarista-meta"><b>${escapeHtml(meta)}</b>${minuto ? ` <em>${escapeHtml(minuto)}</em>` : ""}</span>
                <p class="direct-comentarista-texto">${escapeHtml(String(c.texto))}</p>
            </li>`;
    }).join("");
    return `
        <section class="direct-comentarista" data-sig="${escapeHtml(directComentaristaSignature(comentarios))}" aria-label="Comentarios de la IA sobre el directo">
            <header class="direct-comentarista-head">
                <strong>&#127911; El comentarista <small>IA</small></strong>
                <span class="direct-comentarista-pulse" aria-hidden="true"></span>
            </header>
            <ul class="direct-comentarista-list">${items}</ul>
        </section>`;
}

/* Refresco quirurgico del panel: los refrescos automaticos del directo parchean
   las tarjetas en sitio y este panel debe seguir el mismo ritmo sin repintar
   toda la vista (evita saltos de scroll mientras se lee). */
function patchDirectComentarista() {
    if (state.currentFilter !== "LIVE") return;
    const container = qs("matches-body");
    if (!container) return;
    const existing = container.querySelector(":scope > .direct-comentarista");
    const html = directComentaristaHtml();
    if (!html) {
        existing?.remove();
        return;
    }
    const signature = directComentaristaSignature(directComentaristaComments());
    if (existing) {
        if (existing.dataset.sig !== signature) existing.outerHTML = html;
        return;
    }
    container.insertAdjacentHTML("afterbegin", html);
}

function renderDirectEmptyState() {
    const nextMatch = getNextLeagueMatch();
    const home = nextMatch?.local || nextMatch?.home_name || nextMatch?.home?.name || "";
    const away = nextMatch?.visitante || nextMatch?.away_name || nextMatch?.away?.name || "";
    const kickoff = nextMatch
        ? formatSmartDate(
            nextMatch.added || nextMatch.fecha_raw,
            nextMatch.scheduled || nextMatch.time || nextMatch.hora
        )
        : "";
    const isQuiniela = Boolean(nextMatch && (state.data?.partidos || []).some(m =>
        String(m.local||"").trim().toLowerCase() === String(home||"").trim().toLowerCase() &&
        String(m.visitante||"").trim().toLowerCase() === String(away||"").trim().toLowerCase()
    ));
    // Si el próximo viene de all_league_matches (no quiniela), no mentir con la etiqueta
    const label = isQuiniela ? "Próximo partido de la quiniela" : "Próximo partido del día";
    const nextHtml = nextMatch ? `
        <div class="direct-empty-next">
            <span>${label}</span>
            <strong>${escapeHtml(home)} - ${escapeHtml(away)}</strong>
            <small>${escapeHtml(kickoff)}</small>
        </div>` : "";
    return `
        <section class="direct-empty-state">
            <span class="direct-empty-kicker">DIRECTO</span>
            <h2>Ahora mismo no hay partidos en juego</h2>
            <p>Cuando empiece un partido, aqui veras el marcador y el minuto sin salir de la jornada.</p>
            ${nextHtml}
            <button class="direct-empty-action" type="button" data-page-action="TICKET">Ver la quiniela</button>
        </section>`;
}
