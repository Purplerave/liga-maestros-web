/* Selector accesible del marcador del Pleno al 15. */

function openPlenoModal(idx) {
    const match = (state.data?.partidos || [])[idx];
    if (!match) return;

    const validGoals = ["0", "1", "2", "M"];
    const current = String(state.my_signs[idx] || "0-0").toUpperCase();
    const parts = current.split("-");
    let homeGoals = validGoals.includes(parts[0]) ? parts[0] : "0";
    let awayGoals = validGoals.includes(parts[1]) ? parts[1] : "0";
    const trigger = document.activeElement;

    document.getElementById("pleno-modal-overlay")?.remove();

    const localName = match.local || "Local";
    const visitorName = match.visitante || "Visitante";
    const overlay = document.createElement("div");
    overlay.className = "pleno-modal-overlay";
    overlay.id = "pleno-modal-overlay";
    overlay.innerHTML = `
        <div class="pleno-modal" role="dialog" aria-modal="true" aria-labelledby="pleno-modal-title">
            <header class="pleno-modal-header">
                <h3 id="pleno-modal-title">Pleno al 15</h3>
                <div class="pleno-modal-teams">
                    <div class="pleno-modal-team">
                        ${logoBadge(localName, teamLogo(match, "home"))}
                        <span>${escapeHtml(getShortName(localName))}</span>
                    </div>
                    <span class="pleno-modal-vs" aria-hidden="true">VS</span>
                    <div class="pleno-modal-team">
                        ${logoBadge(visitorName, teamLogo(match, "away"))}
                        <span>${escapeHtml(getShortName(visitorName))}</span>
                    </div>
                </div>
            </header>
            <div class="pleno-modal-body">
                ${renderPlenoGoalGroup("local", localName, homeGoals, validGoals)}
                ${renderPlenoGoalGroup("visitante", visitorName, awayGoals, validGoals)}
                <div class="pleno-modal-preview" aria-live="polite">
                    <span>Pronostico</span>
                    <strong id="pleno-preview">${homeGoals}-${awayGoals}</strong>
                </div>
            </div>
            <footer class="pleno-modal-actions">
                <button class="pleno-modal-cancel" type="button">Cancelar</button>
                <button class="pleno-modal-save" type="button">Confirmar</button>
            </footer>
        </div>`;
    document.body.appendChild(overlay);

    const updatePreview = () => {
        const preview = overlay.querySelector("#pleno-preview");
        if (preview) preview.textContent = `${homeGoals}-${awayGoals}`;
    };
    const selectGoal = event => {
        const button = event.target.closest("[data-pleno-side]");
        if (!button) return;
        const side = button.dataset.plenoSide;
        overlay.querySelectorAll(`[data-pleno-side="${side}"]`).forEach(item => {
            item.classList.toggle("active", item === button);
            item.setAttribute("aria-pressed", item === button ? "true" : "false");
        });
        if (side === "local") homeGoals = button.dataset.goal;
        else awayGoals = button.dataset.goal;
        updatePreview();
    };
    const close = () => {
        document.removeEventListener("keydown", onKeydown);
        overlay.classList.remove("is-active");
        window.setTimeout(() => overlay.remove(), 160);
        if (trigger instanceof HTMLElement) trigger.focus();
    };
    const onKeydown = event => {
        if (event.key === "Escape") close();
    };

    overlay.addEventListener("click", event => {
        if (event.target === overlay) close();
        else selectGoal(event);
    });
    overlay.querySelector(".pleno-modal-cancel")?.addEventListener("click", close);
    overlay.querySelector(".pleno-modal-save")?.addEventListener("click", () => {
        state.my_signs[idx] = `${homeGoals}-${awayGoals}`;
        state.lastUserEdit = Date.now();
        state.draftDirty = true;
        persistDraft();
        hydrateHero();
        renderArena();
        close();
    });
    document.addEventListener("keydown", onKeydown);
    window.requestAnimationFrame(() => {
        overlay.classList.add("is-active");
        overlay.querySelector(".pleno-goal-btn.active")?.focus();
    });
}

function renderPlenoGoalGroup(side, teamName, selected, values) {
    const label = `Goles de ${getShortName(teamName)}`;
    return `
        <fieldset class="pleno-goals-group">
            <legend>${escapeHtml(label)}</legend>
            <div class="pleno-goals-grid">
                ${values.map(value => `
                    <button class="pleno-goal-btn ${value === selected ? "active" : ""}"
                            type="button" data-pleno-side="${side}" data-goal="${value}"
                            aria-pressed="${value === selected ? "true" : "false"}"
                            aria-label="${escapeHtml(label)}: ${value}">${value}</button>
                `).join("")}
            </div>
        </fieldset>`;
}
