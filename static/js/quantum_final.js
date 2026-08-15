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
            if (!userRes.ok) throw new Error(`User API ${userRes.status}`);
            const userPayload = await userRes.json();
            state.user = userPayload.user;
            state.csrfToken = userPayload.csrf_token || "";
        }
        if (!dataRes.ok) throw new Error(`Data API ${dataRes.status}`);
        state.data = await dataRes.json();
        logoAliasIndex = null;
        logoCache.clear();
        state.jornada = String(state.data.jornada || state.jornada);
        if (typeof startLiveUpdates === "function") startLiveUpdates();

        // 🎊 Welcome-back celebration for returning users
        if (!options.auto && state.user && hasSavedTicket() && state.draftDirty === false) {
            const done = state.my_signs.filter(s => s !== "-").length;
            if (done === 15 && typeof window.launchConfetti === "function") {
                setTimeout(() => {
                    window.launchConfetti({ count: 30, spread: 50, duration: 2000, origin: { x: 0.5, y: 0.15 } });
                }, 400);
            }
        }

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
// The selected match belongs to the user: never let the API's automatic
// fallback decide where an exact-score prediction is saved.
let porraSelectedMatchId = null;

async function loadPorra(partidoId = porraSelectedMatchId) {
    const bodies = [qs("porra-body"), qs("ticket-porra-body")].filter(Boolean);
    const summary = qs("porra-summary");
    const labels = document.querySelectorAll("[data-porra-label]");
    if (!state.data) return;
    if (!bodies.length && !qs("cover-porra-content")) return;
    try {
        const requestedMatch = partidoId ? `&pid=${encodeURIComponent(partidoId)}` : "";
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 8000);
        const res = await fetch(`/api/porra?j=${encodeURIComponent(state.data.jornada)}${requestedMatch}`, { signal: controller.signal });
        clearTimeout(timeout);
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
        porraSelectedMatchId = Number(match.partido_id) || null;
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
        const matchOptions = (data.available || []).map(item => {
            const id = Number(item.partido_id);
            const selected = id === Number(match.partido_id) ? " selected" : "";
            return `<option value="${id}"${selected}>${id}. ${escapeHtml(getShortName(item.local || "Local"))} - ${escapeHtml(getShortName(item.visitante || "Visitante"))}</option>`;
        }).join("");
        const selector = matchOptions
            ? `<label class="porra-selector-label">
                    <select class="porra-selector" data-porra-match aria-label="Elige el partido para tu porra — +2 puntos extra si aciertas el marcador exacto">${matchOptions}</select>
                    <small class="porra-hint" style="display:block;color:#94a3b8;font-size:0.56rem;margin-top:3px;line-height:1.3;">Marcador exacto: <b style="color:#f5b53f;">+2 puntos</b>.</small>
               </label>`
            : "";
        const renderBody = (body, index) => {
            const suffix = index ? "-ticket" : "";
            const matchLabel = `${escapeHtml(getShortName(match.local || "Local"))} vs ${escapeHtml(getShortName(match.visitante || "Visitante"))}`;

            // Show change status
            let changeStatus = "";
            if (hasMine && !data.jornada_locked) {
                const changes = data.my_changes || 0;
                if (changes === 0) {
                    changeStatus = `<small class="porra-change-info">Puedes cambiar 1 vez</small>`;
                } else {
                    changeStatus = `<small class="porra-change-info locked">Ya no puedes cambiar</small>`;
                }
            }

            body.innerHTML = `
            <div class="porra-match-header">
                <strong>${matchLabel}</strong>
                ${selector}
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
                : `<form id="porra-form${suffix}" class="porra-form" data-porra-form data-partido-id="${Number(match.partido_id)}">
                        <input id="porra-home${suffix}" data-porra-home type="number" min="0" max="15" inputmode="numeric" aria-label="Goles de ${escapeHtml(match.local || "local")}" value="${escapeHtml(homeValue)}">
                        <span>-</span>
                        <input id="porra-away${suffix}" data-porra-away type="number" min="0" max="15" inputmode="numeric" aria-label="Goles de ${escapeHtml(match.visitante || "visitante")}" value="${escapeHtml(awayValue)}">
                        <button type="button" data-porra-submit>${data.auth ? "OK" : "Entrar"}</button>
                        <small class="porra-form-status" data-porra-status aria-live="polite"></small>
                   </form>`}
            ${changeStatus}
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
                partido_id: form?.dataset.partidoId || porraSelectedMatchId,
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
        // 🎊 Mini celebracion por participar en la porra
        if (typeof window.launchConfetti === "function") {
            window.launchConfetti({ count: 15, spread: 30, duration: 1200 });
        }
        if (typeof SoundManager !== "undefined" && SoundManager.playSave) {
            SoundManager.playSave();
        }
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
function showWelcomeOnboarding() {
    // El onboarding multi-paso vive en onboarding.js para no duplicar el modal.
}

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

    const signs = Array.isArray(state.my_signs) ? state.my_signs.slice(0, 15) : [];
    const missingMatches = Array.from({ length: 15 }, (_, index) => index)
        .filter(index => !signs[index] || signs[index] === "-");
    if (missingMatches.length) {
        const missingLabel = missingMatches.map(index => index + 1).join(", ");
        return showToast(`Completa la quiniela. Falta${missingMatches.length === 1 ? "" : "n"}: ${missingLabel}.`, "error");
    }

    const saveButton = qs("save-quiniela-btn");
    if (saveButton?.disabled) return;
    if (saveButton) {
        saveButton.disabled = true;
        saveButton.setAttribute("aria-busy", "true");
        saveButton.textContent = "Guardando...";
    }

    const payload = { user_id: state.user.id, jornada: state.data.jornada, signos: signs };
    const sendPredictions = async () => {
        const response = await fetch("/api/predicciones/save", {
            method: "POST",
            headers: authenticatedJsonHeaders(),
            body: JSON.stringify(payload)
        });
        const contentType = response.headers.get("content-type") || "";
        const result = contentType.includes("application/json") ? await response.json() : {};
        return { response, result };
    };

    try {
        let { response: res, result } = await sendPredictions();
        const securityExpired = res.status === 403
            && String(result.error || result.message || "").toLowerCase().includes("seguridad");
        if (securityExpired) {
            const statusResponse = await fetch("/api/user/status", { cache: "no-store" });
            if (!statusResponse.ok) throw new Error("La sesion ha caducado. Recarga la pagina e inicia sesion de nuevo.");
            const statusPayload = await statusResponse.json();
            if (!statusPayload.user || !statusPayload.csrf_token) {
                throw new Error("La sesion ha caducado. Inicia sesion de nuevo.");
            }
            state.user = statusPayload.user;
            state.csrfToken = statusPayload.csrf_token;
            payload.user_id = state.user.id;
            ({ response: res, result } = await sendPredictions());
        }
        if (!res.ok || result.status !== "ok") {
            throw new Error(result.message || result.error || `No se pudo guardar (error ${res.status}).`);
        }
        const savedSigns = Array.isArray(result.signos) && result.signos.length === 15
            ? result.signos.map(sign => sign || "-")
            : signs;
        clearDraft();
        state.my_signs = [...savedSigns];
        state.server_signs = [...savedSigns];
        state.editMode = false;
        hydrateHero();
        renderArena();

        showToast("Quiniela guardada correctamente.");
        try {
            if (typeof window.launchBigConfetti === "function") {
                window.launchBigConfetti();
            } else if (typeof window.launchConfetti === "function") {
                window.launchConfetti({ count: 50, spread: 80, duration: 2500 });
            }
            if (typeof SoundManager !== "undefined" && SoundManager.playSave) SoundManager.playSave();
        } catch (effectError) {
            console.warn("No se pudo mostrar la celebracion del guardado", effectError);
        }
        await refreshData();
    } catch (error) {
        const message = error instanceof Error && error.message
            ? error.message
            : "No se pudo guardar la quiniela. Comprueba tu conexion e intentalo de nuevo.";
        showToast(message, "error");
        if (typeof SoundManager !== "undefined" && SoundManager.playError) SoundManager.playError();
    } finally {
        if (saveButton) {
            saveButton.removeAttribute("aria-busy");
            hydrateHero();
        }
    }
}

function buildShareText() {
    const matches = state.data?.partidos || [];
    const done = (state.my_signs || []).filter(sign => sign && sign !== "-").length;
    return [
        "🏆 LIGA DE MAESTROS | Mis pronosticos J" + (state.data?.jornada || ""),
        done + "/15 marcados · Humanos vs IA",
        ...matches.slice(0, 15).map((match, idx) => {
            const sign = state.my_signs[idx] && state.my_signs[idx] !== "-" ? state.my_signs[idx] : "sin marcar";
            const local = match.local || "Local";
            const away = match.visitante || "Visitante";
            const label = idx === 14 ? "Pleno al 15" : local + " - " + away;
            return (idx + 1) + ". " + label + " -> " + sign;
        }),
        "🔥 ¿Puedes ganar a la IA? ligademaestros",
    ].join("\n");
}

function sharePageUrl() {
    try {
        const url = new URL(window.location.href);
        url.searchParams.delete("contest");
        return url.toString();
    } catch {
        return window.location.origin + "/";
    }
}

function closeShareSheet() {
    const sheet = qs("share-sheet");
    if (!sheet) return;
    sheet.hidden = true;
    sheet.classList.remove("is-open");
}

function openShareSheet() {
    const sheet = qs("share-sheet");
    const preview = qs("share-sheet-preview");
    if (!sheet || !preview) return false;
    preview.textContent = buildShareText();
    const nativeBtn = sheet.querySelector("[data-share-action='native']");
    if (nativeBtn) nativeBtn.hidden = !navigator.share;
    sheet.hidden = false;
    requestAnimationFrame(() => sheet.classList.add("is-open"));
    sheet.querySelector(".share-sheet-close")?.focus();
    return true;
}

function copyShareText(text) {
    if (navigator.clipboard?.writeText) return navigator.clipboard.writeText(text);
    const area = document.createElement("textarea");
    area.value = text;
    area.setAttribute("readonly", "");
    area.style.position = "fixed";
    area.style.left = "-9999px";
    document.body.appendChild(area);
    area.select();
    document.execCommand("copy");
    area.remove();
    return Promise.resolve();
}

function runShareAction(action) {
    const text = qs("share-sheet-preview")?.textContent || buildShareText();
    const shareUrl = sharePageUrl();
    const payload = text + "\n" + shareUrl;
    if (action === "copy") {
        copyShareText(payload).then(() => {
            showToast("Pronostico copiado.");
            if (typeof SoundManager !== "undefined" && SoundManager.playSave) SoundManager.playSave();
            closeShareSheet();
        }).catch(() => showToast("No se pudo copiar el pronostico.", "error"));
        return;
    }
    if (action === "twitter") {
        window.open(
            "https://twitter.com/intent/tweet?text=" + encodeURIComponent(text) + "&url=" + encodeURIComponent(shareUrl),
            "_blank",
            "noopener,noreferrer"
        );
        showToast("Abriendo X...");
        return;
    }
    if (action === "whatsapp") {
        window.open("https://wa.me/?text=" + encodeURIComponent(payload), "_blank", "noopener,noreferrer");
        showToast("Abriendo WhatsApp...");
        return;
    }
    if (action === "image" && window.TicketImage) {
        showToast("Generando imagen del boleto...");
        window.TicketImage.share(state).then(() => {
            if (typeof SoundManager !== "undefined" && SoundManager.playSave) SoundManager.playSave();
            closeShareSheet();
        }).catch(() => showToast("No se pudo generar la imagen.", "error"));
        return;
    }
    if (action === "native" && navigator.share) {
        navigator.share({ title: "Liga de Maestros", text, url: shareUrl }).catch(error => {
            if (error && error.name === "AbortError") return;
            showToast("No se pudo abrir el panel nativo.", "error");
        });
    }
}

function shareTicket() {
    if (!state.user) return showToast("Entra con Google para compartir.", "error");
    const matches = state.data.partidos || [];
    if (!matches.length) return showToast("No hay jornada cargada para compartir.", "error");
    if (typeof window.launchConfetti === "function") {
        window.launchConfetti({ count: 30, spread: 70, duration: 2000 });
    }
    if (openShareSheet()) return;
    copyShareText(buildShareText() + "\n" + sharePageUrl()).then(() => {
        showToast("Pronostico copiado.");
    }).catch(() => showToast("No se pudo copiar el pronostico.", "error"));
}

async function loadNewsBriefing() {
    const target = qs("cover-news-content");
    if (!target) return;
    try {
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 8000);
        const res = await fetch("/api/noticias/radar", { signal: controller.signal });
        clearTimeout(timeout);
        if (!res.ok) { target.innerHTML = '<span class="cp-empty">Sin novedades</span>'; return; }
        const data = await res.json();
        const novedades = Array.isArray(data.novedades) ? data.novedades : [];
        const bajas = Array.isArray(data.bajas) ? data.bajas : [];
        if (!novedades.length && !bajas.length) {
            target.innerHTML = '<span class="cp-empty">Sin novedades de momento</span>';
            return;
        }
        const newsHtml = novedades.map(item => {
            const category = escapeHtml(String(item.categoria || "noticia").toUpperCase());
            const text = escapeHtml(item.texto || "");
            const source = escapeHtml(item.source || "");
            const link = escapeHtml(item.link || "#");
            return `<a class="cp-news-row" href="${link}" target="_blank" rel="noopener noreferrer"><span class="cp-news-category">${category}</span><strong>${text}</strong><small>${source}</small></a>`;
        }).join("");
        const injuriesHtml = bajas.slice(0, 3).map(item => {
            const status = escapeHtml(String(item.estado || "baja").toUpperCase());
            const player = escapeHtml(item.jugador || "");
            const team = escapeHtml(item.equipo || "");
            const note = escapeHtml(item.nota || "");
            return `<div class="cp-news-row is-availability"><span class="cp-news-category">${status}</span><strong>${player} · ${team}</strong><small>${note}</small></div>`;
        }).join("");
        target.innerHTML = newsHtml + injuriesHtml;
    } catch (error) {
        target.innerHTML = '<span class="cp-empty">Sin novedades de momento</span>';
    }
}
