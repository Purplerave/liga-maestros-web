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

        // 🎊 Celebrate save
        const done = state.my_signs.filter(s => s !== "-").length;
        if (typeof window.launchConfetti === "function") {
            if (done === 15) {
                window.launchBigConfetti();
            } else if (done >= 10) {
                window.launchMilestoneConfetti(done);
            } else {
                window.launchConfetti({ count: 20, spread: 40, duration: 1500 });
            }
        }
        if (typeof SoundManager !== "undefined" && SoundManager.playSave) {
            SoundManager.playSave();
        }

        showToast("Quiniela guardada.");
        await refreshData();
    } catch (error) {
        showToast(error.message, "error");
        if (typeof SoundManager !== "undefined" && SoundManager.playError) {
            SoundManager.playError();
        }
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

    // 🎊 Celebracion al compartir
    if (typeof window.launchConfetti === "function") {
        window.launchConfetti({ count: 30, spread: 70, duration: 2000 });
    }

    // En móviles con Web Share API, abrir la hoja nativa de compartir
    // (WhatsApp, Telegram, X...). Fallback: portapapeles.
    if (navigator.share) {
        try {
            await navigator.share({ title: "Liga de Maestros", text });
            if (typeof SoundManager !== "undefined" && SoundManager.playCelebration) {
                SoundManager.playCelebration();
            }
            showToast("Pronostico compartido.");
            return;
        } catch (shareError) {
            if (shareError && shareError.name === "AbortError") return;
        }
    }
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
        if (typeof SoundManager !== "undefined" && SoundManager.playSave) {
            SoundManager.playSave();
        }
        showToast("Pronostico copiado.");
    } catch (error) {
        showToast("No se pudo copiar el pronostico.", "error");
        if (typeof SoundManager !== "undefined" && SoundManager.playError) {
            SoundManager.playError();
        }
    }
}

/* ═══════════════════════════════════════════════════════════════
   IN-APP NOTIFICATIONS — Notificaciones nativas dentro de la web
   ═══════════════════════════════════════════════════════════════ */

const _inAppNotifs = new Set();

function showInAppNotification({ icon = '⚽', title, message, duration = 5000, onClick } = {}) {
    const id = Date.now() + Math.random();
    if (_inAppNotifs.size >= 3) return; // Max 3 visibles
    _inAppNotifs.add(id);

    const notif = document.createElement('div');
    notif.className = 'in-app-notification';
    notif.id = `notif-${id}`;
    notif.innerHTML = `
        <span class="notif-icon">${icon}</span>
        <div>
            <strong>${escapeHtml(title)}</strong>
            ${message ? `<br><small>${escapeHtml(message)}</small>` : ''}
        </div>
        <button class="notif-close" type="button" aria-label="Cerrar notificación">&times;</button>
    `;

    notif.addEventListener('click', (e) => {
        if (e.target.closest('.notif-close')) {
            notif.remove();
            _inAppNotifs.delete(id);
            return;
        }
        if (typeof onClick === 'function') onClick();
        notif.remove();
        _inAppNotifs.delete(id);
    });

    document.body.appendChild(notif);

    if (duration > 0) {
        setTimeout(() => {
            if (notif.parentNode) {
                notif.style.opacity = '0';
                notif.style.transform = 'translateX(100%) scale(0.9)';
                setTimeout(() => {
                    if (notif.parentNode) notif.remove();
                    _inAppNotifs.delete(id);
                }, 300);
            }
        }, duration);
    }
}

// Detectar cambios en directo y mostrar notificaciones
let _lastLiveNotified = new Map();

function checkLiveNotifications() {
    if (document.hidden) return;
    const matches = getLiveLeagueMatches();
    const now = Date.now();

    matches.forEach(match => {
        const key = liveMatchDomKey(match);
        const last = _lastLiveNotified.get(key);
        const score = scoreOnly(match.marcador || match.score || match.scores?.score || '');

        if (!last) {
            // Nuevo partido en directo
            const home = match.local || match.home_name || '';
            const away = match.visitante || match.away_name || '';
            if (home && away) {
                setTimeout(() => {
                    showInAppNotification({
                        icon: '🔴',
                        title: `¡${home} vs ${away} en juego!`,
                        message: `Minuto ${match.minuto || match.time || ''}`,
                        duration: 6000,
                        onClick: () => {
                            state.currentFilter = 'LIVE';
                            syncUrlState();
                            renderArena();
                        }
                    });
                }, 800);
            }
        } else if (last.score !== score && score !== '-' && score !== '') {
            // ¡GOL! Ha cambiado el marcador
            const home = match.local || match.home_name || '';
            const away = match.visitante || match.away_name || '';
            setTimeout(() => {
                showInAppNotification({
                    icon: '⚡',
                    title: `¡GOL! ${home} ${score} ${away}`,
                    message: `Minuto ${match.minuto || match.time || ''}`,
                    duration: 5000,
                    onClick: () => {
                        state.currentFilter = 'LIVE';
                        syncUrlState();
                        renderArena();
                    }
                });
                if (typeof SoundManager !== "undefined" && SoundManager.playNotification) {
                    SoundManager.playNotification();
                }
            }, 500);
        }

        _lastLiveNotified.set(key, { score, time: now });
    });

    // Limpiar partidos antiguos (mas de 3 horas)
    const threeHours = 3 * 60 * 60 * 1000;
    for (const [key, data] of _lastLiveNotified) {
        if (now - data.time > threeHours) _lastLiveNotified.delete(key);
    }
}

// Hook en refreshLiveSnapshot
const _origRefreshLive = refreshLiveSnapshot;
refreshLiveSnapshot = async function() {
    await _origRefreshLive.call(this);
    if (state.currentFilter === 'LIVE' || state.currentFilter === 'ALL') {
        checkLiveNotifications();
    }
};

// Export global para in-app notifications
window.showInAppNotification = showInAppNotification;

async function loadNewsBriefing() {
    const target = qs("cover-news-content");
    if (!target) return;
    try {
        const res = await fetch("/api/noticias/radar");
        if (!res.ok) return;
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
