/* Portada — Sidebar con perfil, navegación y ranking */

function coverDisplayName(uid) {
    const names = state.data?.participant_contract?.names || {};
    const n = String(uid || "").toLowerCase();
    if (state.user && String(state.user.id).toLowerCase() === n) return state.user.name || "Tu";
    return names[n] || names[uid] || String(uid || "").split("@")[0];
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

function coverProfileCardHtml() {
    if (!state.user) {
        return `
            <div class="cp-profile-card">
                <div class="cp-profile-avatar">?</div>
                <div class="cp-profile-info">
                    <div class="cp-profile-name">Invitado</div>
                    <div class="cp-profile-stats">Entra para jugar</div>
                </div>
            </div>`;
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
    const initials = (state.user.name || "?").split(" ").map(w => w[0]).join("").toUpperCase().slice(0, 2);

    return `
        <div class="cp-profile-card" onclick="openProfileView()" role="button" tabindex="0">
            <div class="cp-profile-avatar">${escapeHtml(initials)}</div>
            <div class="cp-profile-info">
                <div class="cp-profile-name">${escapeHtml(state.user.name || "Jugador")}</div>
                <div class="cp-profile-stats">
                    <span class="cp-profile-pos">#${position || "?"}</span>
                    <span>&middot;</span>
                    <span>${total} pts</span>
                    ${numPlayers ? `<span>&middot;</span><span>${numPlayers} jug.</span>` : ""}
                </div>
            </div>
        </div>`;
}

function coverNavButtonsHtml() {
    const matches = state.data.partidos || [];
    const liveCount = matches.filter(m => isLiveStatus(m.status) || isLiveMatch(m)).length;

    const buttons = [
        { action: "TICKET", icon: "&#9917;", label: "Quiniela" },
        { action: "LIVE", icon: "&#9200;", label: "Directo", badge: liveCount || null },
        { action: "CONTEST", icon: "&#127942;", label: "La Pe&ntilde;a" },
        { action: "STANDINGS", icon: "&#128200;", label: "Ligas" },
        { action: "SNAKE", icon: "&#127922;", label: "Juegos" },
    ];

    return `
        <div class="cp-nav-buttons">
            ${buttons.map(b => `
                <button type="button" class="cp-nav-btn" data-page-action="${b.action}">
                    <span class="cp-nav-icon">${b.icon}</span>
                    <span class="cp-nav-label">${b.label}</span>
                    ${b.badge ? `<span class="cp-nav-badge">${b.badge}</span>` : ""}
                </button>`).join("")}
        </div>`;
}

function coverLeaderboardHtml() {
    const ranking = state.data.ranking_maestros || {};
    const hidden = new Set((state.data?.participant_contract?.hidden_ids || []).map(id => String(id).toLowerCase()));
    const rows = Object.entries(ranking)
        .filter(([uid]) => !hidden.has(String(uid).toLowerCase()))
        .map(([uid, s]) => ({
            uid, name: coverDisplayName(uid), total: Number(s.total || 0),
            isUser: Boolean(state.user && String(state.user.id).toLowerCase() === String(uid).toLowerCase())
        }));
    if (!rows.length) return "";
    const sorted = rows.sort((a, b) => b.total - a.total || a.name.localeCompare(b.name, "es"));
    const userIdx = state.user ? sorted.findIndex(r => r.isUser) : -1;
    const top = sorted.slice(0, 8);
    const userOutside = userIdx >= 8 && state.user ? sorted[userIdx] : null;

    return `
        <div class="cp-rank">
            <div class="cp-rank-title">Clasificacion</div>
            ${top.map((r, i) => `
                <div class="cp-rank-row ${r.isUser ? "is-user" : ""} ${i === 0 ? "is-leader" : ""}">
                    <span class="cp-rank-pos">${i + 1}</span>
                    <span class="cp-rank-name">${escapeHtml(r.name)}</span>
                    <span class="cp-rank-pts">${r.total}</span>
                </div>`).join("")}
            ${userOutside ? `<div class="cp-rank-dots">&middot;&middot;&middot;</div>
            <div class="cp-rank-row is-user">
                <span class="cp-rank-pos">${userIdx + 1}</span>
                <span class="cp-rank-name">${escapeHtml(userOutside.name)}</span>
                <span class="cp-rank-pts">${userOutside.total}</span>
            </div>` : ""}
        </div>`;
}
