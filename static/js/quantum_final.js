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
        const [userRes, dataRes, syncRes, contestRes] = await Promise.all([
            fetch("/api/user/status"),
            fetch(`/api/liga/data?j=${encodeURIComponent(state.jornada)}`),
            fetch(`/api/sync/status?j=${encodeURIComponent(state.jornada)}`),
            fetch(`/api/concurso?j=${encodeURIComponent(state.jornada)}`)
        ]);
        const userPayload = await userRes.json();
        state.user = userPayload.user;
        state.csrfToken = userPayload.csrf_token || "";
        state.data = await dataRes.json();
        logoAliasIndex = null;
        logoDataIndex = null;
        logoCache.clear();
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

        const patchedLiveView = Boolean(options.auto && state.currentFilter === "LIVE" && patchLiveArena());
        const patchedTicketView = Boolean(options.auto && state.currentFilter === "TICKET" && patchTicketArena());
        if (patchedLiveView || patchedTicketView) return;

        hydrateJornadaNav();
        hydrateUserSigns({ preserveLocalTicket });
        hydrateStatus(sync);
        hydrateHero();
        updateAuthUI();
        updateWarRoomButton();
        renderArena();
        if (scrollState) {
            window.scrollTo(scrollState.x, scrollState.y);
            const table = qs("matches-body")?.querySelector(".arena-table-wrap");
            if (table) table.scrollLeft = scrollState.tableX;
        }
        if (shouldRefreshSideModules()) {
            renderLiveStandings();
        }
        loadPorra();
        loadComments();
        renderEvolutionChart();
        loadLeagueNav();
        hydrateContestNav();
        hydrateStandingsNav();
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

// --- Comentarios ---
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
            : state.data.auth_enabled === false
                ? "Login pendiente de configurar"
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
                <strong style="display:block; margin-bottom:4px;">Sin comentarios todavia</strong>
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
    const value = String(text.value || "").trim();
    if (!value) return;

    try {
        const res = await fetch("/api/comentarios", {
            method: "POST",
            headers: authenticatedJsonHeaders(),
            body: JSON.stringify({
                jornada: state.data.jornada || state.jornada,
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

// --- Porra ---
async function loadPorra() {
    const bodies = [qs("porra-body"), qs("ticket-porra-body")].filter(Boolean);
    const summary = qs("porra-summary");
    const labels = document.querySelectorAll("[data-porra-label]");
    if (!state.data) return;
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

// --- Grafico de evolucion ---
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
