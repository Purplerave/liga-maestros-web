/* Directo: estado vacio de la pagina de resultados en vivo. */

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
    const nextHtml = nextMatch ? `
        <div class="direct-empty-next">
            <span>Proximo partido de la quiniela</span>
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
