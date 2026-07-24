/* ==========================================================================
   QUANTUM FINAL — Init, refreshData, y funciones unicas.
   Todos los modulos (utils, state, logos, navigation, live, standings,
   contest, quiz, arena, events) se cargan ANTES que este archivo.
   ========================================================================== */

// --- refreshData: orquestacion principal de datos y render ---
async function refreshData(options = {}) {
    if (options.auto && Date.now() - state.lastUserEdit < 12000) return;
    const preserveLocalTicket = Boolean(options.auto && (state.editMode || state.draftDirty));
    const scrollState = options.auto ? {
        x: window.scrollX,
        y: window.scrollY,
        tableX: qs("matches-body")?.querySelector(".arena-table-wrap")?.scrollLeft || 0
    } : null;
    try {
        const userRequest = options.auto
            ? Promise.resolve(null)
            : fetch("/api/user/status");
        const [userRes, dataRes] = await Promise.all([
            userRequest,
            fetch(`/api/liga/data?j=${encodeURIComponent(state.jornada)}`)
        ]);
        if (userRes) {
            const userPayload = await userRes.json();
            state.user = userPayload.user;
            state.csrfToken = userPayload.csrf_token || "";
        }
        state.data = await dataRes.json();
        logoAliasIndex = null;
        logoCache.clear();
        state.jornada = String(state.data.jornada || state.jornada);
        await ensureViewAssets(currentMainView());
        const patchedLiveView = Boolean(options.auto && state.currentFilter === "LIVE" && patchLiveArena());
        const patchedTicketView = Boolean(
            options.auto
            && state.currentFilter === "TICKET"
            && typeof patchTicketArena === "function"
            && patchTicketArena()
        );
        if (patchedLiveView || patchedTicketView) return;

        hydrateJornadaNav();
        hydrateUserSigns({ preserveLocalTicket });
        hydrateHero();
        updateAuthUI();
        renderArena();
        if (scrollState) {
            window.scrollTo(scrollState.x, scrollState.y);
            const table = qs("matches-body")?.querySelector(".arena-table-wrap");
            if (table) table.scrollLeft = scrollState.tableX;
        }
    } catch (error) {
        console.error(error);
        if (options.auto && state.data) {
            const now = Date.now();
            if (now - state.refreshErrorNotifiedAt > 60000) {
                showToast("No se pudo actualizar en segundo plano. Mantengo la ultima version cargada.", "error");
                state.refreshErrorNotifiedAt = now;
            }
            return;
        }
        const body = qs("matches-body");
        if (body) body.innerHTML = `<div class="empty-state">No se pudo cargar la Arena. Revisa que Flask y la base de datos esten activos.</div>`;
    }
}

async function ensureQ15Directo() {
    const jornada = String(state.data?.jornada || state.jornada || "");
    if (!jornada || state.q15DirectoJornada === jornada) return false;
    try {
        const response = await fetch(`/api/q15/directo?j=${encodeURIComponent(jornada)}`);
        state.q15Directo = response.ok ? await response.json() : {};
    } catch {
        state.q15Directo = {};
    }
    state.q15DirectoJornada = jornada;
    return true;
}

// --- Porra ---
async function loadPorra() {
    const bodies = [qs("porra-body"), qs("ticket-porra-body")].filter(Boolean);
    const summary = qs("porra-summary");
    const labels = document.querySelectorAll("[data-porra-label]");
    if (!state.data) return;
    if (!bodies.length && !qs("cover-porra-content")) return;
    try {
        const res = await fetch(`/api/porra?j=${encodeURIComponent(state.data.jornada)}`);
        const data = await res.json();
        if (typeof hydrateCoverPorra === "function") hydrateCoverPorra(data);
        if (!bodies.length) return;
        if (!res.ok || data.status !== "ok" || !data.enabled) {
            bodies.forEach(body => {
                body.innerHTML = `<div class="empty-state">${escapeHtml(data.message || "Sin porra disponible.")}</div>`;
            });
            return;
        }
        const match = data.match || {};
        labels.forEach(label => { label.textContent = data.label || "Porra"; });
        const mine = data.mine || {};
        const homeValue = mine.goles_local ?? "";
        const awayValue = mine.goles_visitante ?? "";
        const hasMine = mine.goles_local !== undefined && mine.goles_local !== null && mine.goles_visitante !== undefined && mine.goles_visitante !== null;
        if (summary) summary.textContent = data.locked ? "Cerrada" : "Marcador exacto";
        const totalEntries = Number(data.total_entries || 0);
        const distribution = data.distribution || [];
        const porraShare = distribution.slice(0, 3).map(item => {
            const score = `${Number(item.goles_local)}-${Number(item.goles_visitante)}`;
            const percent = Number(item.percent || 0);
            return `
                <span class="porra-share-pill">
                    <b>${escapeHtml(score)}</b>
                    <em>${totalEntries === 1 ? "&uacute;nico pron&oacute;stico" : `${percent.toLocaleString("es-ES", { maximumFractionDigits: 0 })}%`}</em>
                </span>`;
        }).join("");
        const shareBlock = totalEntries
            ? `<div class="porra-share">
                    <span class="porra-share-total">${totalEntries} participante${totalEntries === 1 ? "" : "s"}</span>
                    ${porraShare}
               </div>`
            : "";
        const renderBody = (body, index) => {
            const suffix = index ? "-ticket" : "";
            body.innerHTML = `
            <div class="porra-match">
                <strong>${escapeHtml(getShortName(match.local || "Local"))}</strong>
                <em>vs</em>
                <strong>${escapeHtml(getShortName(match.visitante || "Visitante"))}</strong>
            </div>
            ${hasMine
                ? `<div class="porra-saved">
                        <span>Tu porra</span>
                        <b>${Number(homeValue)}-${Number(awayValue)}</b>
                   </div>`
                : data.locked
                    ? `<div class="porra-saved porra-closed">
                            <span>Porra cerrada</span>
                       </div>`
                : `<form id="porra-form${suffix}" class="porra-form" data-porra-form>
                        <input id="porra-home${suffix}" data-porra-home type="number" min="0" max="15" inputmode="numeric" aria-label="Goles de ${escapeHtml(match.local || "local")}" value="${escapeHtml(homeValue)}">
                        <span>-</span>
                        <input id="porra-away${suffix}" data-porra-away type="number" min="0" max="15" inputmode="numeric" aria-label="Goles de ${escapeHtml(match.visitante || "visitante")}" value="${escapeHtml(awayValue)}">
                        <button type="button" data-porra-submit>${data.auth ? "OK" : "Entrar"}</button>
                        <small class="porra-form-status" data-porra-status aria-live="polite"></small>
                   </form>`}
            ${shareBlock}`;
        };
        bodies.forEach(renderBody);
    } catch (error) {
        if (typeof hydrateCoverPorra === "function") hydrateCoverPorra({ enabled: false, message: "No se pudo cargar la porra" });
        bodies.forEach(body => {
            body.innerHTML = `<div class="empty-state">No se pudo cargar la porra.</div>`;
        });
    }
}

async function submitPorra(event) {
    event.preventDefault();
    if (!state.user) {
        window.location.href = "/login/google";
        return;
    }
    const form = event.target.closest("[data-porra-form]");
    const homeInput = form?.querySelector("[data-porra-home]");
    const awayInput = form?.querySelector("[data-porra-away]");
    const submitButton = form?.querySelector("[data-porra-submit]");
    const formStatus = form?.querySelector("[data-porra-status]");
    if (!homeInput || !awayInput) return;
    if (submitButton?.disabled) return;
    if (submitButton) {
        submitButton.disabled = true;
        submitButton.textContent = "Guardando...";
    }
    if (formStatus) formStatus.textContent = "";
    try {
        const payload = {
                jornada: state.data.jornada || state.jornada,
                goles_local: homeInput.value,
                goles_visitante: awayInput.value
        };
        const sendPorra = async () => {
            const response = await fetch("/api/porra", {
                method: "POST",
                headers: authenticatedJsonHeaders(),
                body: JSON.stringify(payload)
            });
            return { response, data: await response.json() };
        };
        let { response: res, data } = await sendPorra();
        if (res.status === 403 && String(data.error || data.message || "").toLowerCase().includes("seguridad")) {
            const statusResponse = await fetch("/api/user/status", { cache: "no-store" });
            const statusPayload = await statusResponse.json();
            state.user = statusPayload.user || state.user;
            state.csrfToken = statusPayload.csrf_token || "";
            ({ response: res, data } = await sendPorra());
        }
        if (!res.ok || data.status !== "ok") throw new Error(data.message || data.error || "No se pudo guardar la porra.");
        await loadPorra();
        showToast("Porra guardada.");
    } catch (error) {
        if (submitButton) {
            submitButton.disabled = false;
            submitButton.textContent = state.user ? "OK" : "Entrar";
        }
        if (formStatus) formStatus.textContent = error.message;
        showToast(error.message, "error");
    }
}

// --- Guardar y compartir quiniela ---
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
            headers: authenticatedJsonHeaders(),
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
    const matches = state.data.partidos || [];
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
        if (navigator.clipboard.writeText) {
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
