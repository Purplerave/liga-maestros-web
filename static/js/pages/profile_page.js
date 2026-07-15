/* ==========================================================================
   PROFILE PAGE — Vista completa del perfil del jugador
   ========================================================================== */

function renderProfilePage() {
    if (!state.user) {
        return `<div class="profile-page"><div class="profile-empty">Inicia sesion para ver tu perfil.</div></div>`;
    }

    const ranking = state.data.ranking_maestros || {};
    const uid = String(state.user.id).toLowerCase();
    const entry = ranking[uid] || {};
    const total = Number(entry.total || 0);
    const allRows = Object.entries(ranking)
        .map(([k, v]) => ({ uid: k, total: Number(v.total || 0) }))
        .sort((a, b) => b.total - a.total);
    const position = allRows.findIndex(r => r.uid === uid) + 1;
    const numPlayers = allRows.length;
    const aciertos = Number(entry.aciertos || entry.hits || 0);
    const jornadasPlayed = Number(entry.jornadas || entry.played || 0);
    const bestPos = entry.best_position || entry.best_pos || position;
    const initials = (state.user.name || "?").split(" ").map(w => w[0]).join("").toUpperCase().slice(0, 2);

    const jornadas = state.data.historial_jornadas || state.data.user_jornadas || [];
    const maxJ = Number(state.data.max_jornada || state.data.jornada || 0);

    return `
        <div class="profile-page">
            <button type="button" class="profile-back" data-page-action="ALL">&larr; Volver a portada</button>

            <div class="profile-header">
                <div class="profile-avatar-lg">${escapeHtml(initials)}</div>
                <div class="profile-header-info">
                    <h2 class="profile-name">${escapeHtml(state.user.name || "Jugador")}</h2>
                    <div class="profile-sub">
                        <span class="profile-position">#${position || "?"} de ${numPlayers}</span>
                        <span class="profile-sep">&middot;</span>
                        <span>${total} puntos</span>
                    </div>
                </div>
            </div>

            <div class="profile-stats-grid">
                <div class="profile-stat-card">
                    <span class="profile-stat-value">#${position || "-"}</span>
                    <span class="profile-stat-label">Posicion actual</span>
                </div>
                <div class="profile-stat-card">
                    <span class="profile-stat-value">${total}</span>
                    <span class="profile-stat-label">Puntos totales</span>
                </div>
                <div class="profile-stat-card">
                    <span class="profile-stat-value">${aciertos}</span>
                    <span class="profile-stat-label">Aciertos totales</span>
                </div>
                <div class="profile-stat-card">
                    <span class="profile-stat-value">${jornadasPlayed || jornadas.length || "-"}</span>
                    <span class="profile-stat-label">Jornadas jugadas</span>
                </div>
                <div class="profile-stat-card">
                    <span class="profile-stat-value">#${bestPos || "-"}</span>
                    <span class="profile-stat-label">Mejor posicion</span>
                </div>
                <div class="profile-stat-card">
                    <span class="profile-stat-value">${jornadasPlayed && aciertos ? Math.round((aciertos / (jornadasPlayed * 14)) * 100) : "-"}%</span>
                    <span class="profile-stat-label">Acierto medio</span>
                </div>
            </div>

            <div class="profile-history">
                <h3 class="profile-history-title">Historial jornada a jornada</h3>
                ${jornadas.length ? `
                    <div class="profile-history-list">
                        ${jornadas.map(j => {
                            const num = j.jornada || j.num || "?";
                            const pts = j.puntos || j.points || j.total || 0;
                            const hits = j.aciertos || j.hits || 0;
                            const signos = j.signos || j.picks || [];
                            return `
                                <div class="profile-history-row">
                                    <span class="profile-history-num">J${escapeHtml(String(num))}</span>
                                    <span class="profile-history-hits">${hits} aciertos</span>
                                    <span class="profile-history-pts">${pts} pts</span>
                                    <span class="profile-history-signos">${Array.isArray(signos) ? signos.join(" ") : ""}</span>
                                </div>`;
                        }).join("")}
                    </div>
                ` : `
                    <div class="profile-empty">Aun no hay historial de jornadas.</div>
                `}
            </div>
        </div>`;
}
