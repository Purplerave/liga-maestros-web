/* ==========================================================================
   PEÑA VOTE — Formulario de voto de La Peña (14 signos + pleno)
   Llama a GET /api/pena/mis-votos y POST /api/pena/votar.
   Un boleto por cuenta de Google y jornada, editable hasta el cierre.
   ========================================================================== */

const PENA_VOTE_COOLDOWN_MS = 2000;
let _lastPenaVoteTs = 0;

function qsPena(id) {
    return document.getElementById(id);
}

function escapeHtml(value) {
    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

function escapeHtmlAttr(value) {
    return String(value ?? "").replaceAll('"', "&quot;").replaceAll("'", "&#039;");
}

/* Renderiza el encabezado del formulario: estado, jornada, número de votantes. */
function renderPenaVoteHeader(jornada, totalVotantes, puedeVotar, motivoCerrado) {
    const el = qsPena("pena-vote-header");
    if (!el) return;
    const votantesTxt = totalVotantes === 0
        ? "Sé el primero en votar"
        : totalVotantes === 1
            ? "1 de la peña ha votado"
            : `${totalVotantes} de la peña han votado`;
    if (!puedeVotar) {
        el.innerHTML = `
            <div class="pena-vote-state is-closed">
                <span class="pena-vote-dot"></span>
                <strong>${escapeHtml(motivoCerrado || "Jornada cerrada")}</strong>
            </div>
            <p class="pena-vote-caption">${escapeHtml(votantesTxt)}</p>
        `;
        return;
    }
    el.innerHTML = `
        <div class="pena-vote-state is-open">
            <span class="pena-vote-dot"></span>
            <strong>Jornada ${escapeHtml(jornada)} — vota tu boleto</strong>
        </div>
        <p class="pena-vote-caption">${escapeHtml(votantesTxt)}</p>
    `;
}

/* Renderiza el formulario de 14 signos + pleno con botones grandes (pulgar-friendly). */
function renderPenaVoteForm(signos, puedeEditar, jornada, onSignChange, onSave) {
    const el = qsPena("pena-vote-form");
    if (!el) return;
    if (!puedeEditar) {
        el.innerHTML = `<div class="pena-vote-empty">No hay boleto guardado todavía. Rellena las 14 casillas y el pleno.</div>`;
        return;
    }
    const filas = [];
    for (let i = 0; i < 15; i += 1) {
        const esPleno = i === 14;
        const valor = signos[i] || "-";
        let opciones;
        if (esPleno) {
            opciones = [
                { label: "0-0", valor: "0-0" },
                { label: "1-0", valor: "1-0" },
                { label: "1-1", valor: "1-1" },
                { label: "2-0", valor: "2-0" },
                { label: "2-1", valor: "2-1" },
                { label: "2-2", valor: "2-2" },
                { label: "3-0", valor: "3-0" },
                { label: "3-1", valor: "3-1" },
                { label: "3-2", valor: "3-2" },
                { label: "M", valor: "M" },
            ];
        } else {
            opciones = [
                { label: "1", valor: "1" },
                { label: "X", valor: "X" },
                { label: "2", valor: "2" },
            ];
        }
        const btnsHtml = opciones.map(o => {
            const presionado = valor === o.valor ? " aria-pressed=\"true\"" : "";
            return `<button type="button" class="pena-vote-btn${activo && valor === o.valor ? " active" : ""}" data-pena-sign="${escapeHtml(o.valor)}" data-pena-idx="${i}"${presionado}>${escapeHtml(o.label)}</button>`;
        }).join("");
        filas.push(`
            <div class="pena-vote-row${esPleno ? " is-pleno" : ""}">
                <label class="pena-vote-match">${esPleno ? "Pleno 15" : `Partido ${i + 1}`}</label>
                <div class="pena-vote-options" role="group" aria-label="${escapeHtml(esPleno ? "Pleno al 15" : `Partido ${i + 1}`)}">${btnsHtml}</div>
                <input type="hidden" class="pena-vote-value" data-pena-idx="${i}" value="${escapeHtml(valor)}">
            </div>
        `);
    }
    el.innerHTML = `
        <div class="pena-vote-grid">${filas.join("")}</div>
        <div class="pena-vote-actions">
            <button type="button" class="pena-vote-btn-save primary-btn" id="pena-vote-save-btn" disabled>Guardar boleto</button>
            <button type="button" class="pena-vote-btn-clear" id="pena-vote-clear-btn">Limpiar</button>
        </div>
    `;

    // Bind de botones de signo
    el.querySelectorAll("[data-pena-sign]").forEach(btn => {
        btn.addEventListener("click", () => {
            const idx = Number(btn.dataset.penaIdx);
            const valor = btn.dataset.penaSign;
            onSignChange(idx, valor);
        });
    });

    // Guardar
    const saveBtn = qsPena("pena-vote-save-btn");
    if (saveBtn) {
        saveBtn.addEventListener("click", async () => {
            const valores = Array.from(el.querySelectorAll(".pena-vote-value")).map(i => i.value || "-");
            if (valores.some(v => v === "-")) {
                showToast("Completa las 15 casillas antes de guardar.", "error");
                return;
            }
            await onSave(valores);
        });
    }

    // Limpiar
    const clearBtn = qsPena("pena-vote-clear-btn");
    if (clearBtn) {
        clearBtn.addEventListener("click", () => {
            el.querySelectorAll("[data-pena-sign]").forEach(b => b.classList.remove("active"));
            el.querySelectorAll(".pena-vote-value").forEach(i => { i.value = "-"; });
            const saveBtn = qsPena("pena-vote-save-btn");
            if (saveBtn) saveBtn.disabled = true;
            showToast("Boleto limpiado.", "info");
        });
    }
}

/* Habilita/deshabilita el botón guardar según si todas las casillas están rellenas. */
function updatePenaSaveButton(signos) {
    const btn = qsPena("pena-vote-save-btn");
    if (!btn) return;
    const completo = signos.every(s => s && s !== "-");
    btn.disabled = !completo;
}

/* Carga los votos ya guardados del usuario para la jornada. */
async function loadPenaVotos(jornada) {
    const resp = await fetch(`/api/pena/mis-votos?j=${encodeURIComponent(jornada)}`, {
        headers: authenticatedJsonHeaders(),
        cache: "no-store",
    });
    if (!resp.ok) return null;
    const data = await resp.json();
    return data && data.votos ? data.votos : null;
}

/* Guarda (o reemplaza) el boleto de la Peña. */
async function savePenaVoto(jornada, signos) {
    if (Date.now() - _lastPenaVoteTs < PENA_VOTE_COOLDOWN_MS) {
        showToast("Espera un momento antes de volver a guardar.", "error");
        return { ok: false };
    }
    const resp = await fetch("/api/pena/votar", {
        method: "POST",
        headers: authenticatedJsonHeaders(),
        body: JSON.stringify({ jornada, signos }),
    });
    _lastPenaVoteTs = Date.now();
    const data = await resp.json();
    return { ok: resp.ok && data.status === "ok", ...data };
}

/* Inicializa el formulario de voto de La Peña. Se llama desde renderArenaTicket
   cuando la vista es TICKET y hay jornada activa. */
function initPenaVote() {
    const formEl = qsPena("pena-vote-form");
    if (!formEl) return;

    const jornada = state.data && state.data.jornada ? String(state.data.jornada) : "";
    if (!jornada) {
        qsPena("pena-vote-header").innerHTML = `<div class="pena-vote-state is-closed"><strong>Sin jornada abierta</strong></div>`;
        return;
    }

    const puedeVotar = Boolean(state.user)
        && String(state.data.jornada) === String(state.data.max_jornada)
        && !state.data.is_locked;

    // Contador de votantes (público, sin login)
    fetch(`/api/pena/consenso?j=${encodeURIComponent(jornada)}`, { cache: "no-store" })
        .then(r => r.ok ? r.json() : { total_votantes: 0 })
        .then(data => {
            renderPenaVoteHeader(jornada, Number(data?.total_votantes || 0), puedeVotar, data?.message);
        })
        .catch(() => renderPenaVoteHeader(jornada, 0, puedeVotar, "No se pudo cargar el estado"));

    if (!state.user) {
        qsPena("pena-vote-form").innerHTML = `
            <div class="pena-vote-empty">
                <p>Entra con Google para votar.</p>
                <a href="/login/google" class="primary-btn">Entrar con Google</a>
            </div>
        `;
        return;
    }

    if (!puedeVotar) {
        qsPena("pena-vote-form").innerHTML = `<div class="pena-vote-empty">Esta jornada no acepta votos (cerrada o inexistente).</div>`;
        return;
    }

    // Precarga los votos guardados
    loadPenaVotos(jornada).then(votosGuardados => {
        const signos = votosGuardados ? votosGuardados.slice() : Array(15).fill("-");
        renderPenaVoteForm(signos, true, jornada,
            (idx, valor) => {
                const input = qsPena("pena-vote-form").querySelector(`.pena-vote-value[data-pena-idx="${idx}"]`);
                if (input) input.value = valor;
                const row = qsPena("pena-vote-form").querySelector(`.pena-vote-row:nth-child(${idx + 1})`);
                row.querySelectorAll("[data-pena-sign]").forEach(b => b.classList.remove("active"));
                const btn = row.querySelector(`[data-pena-sign="${escapeHtmlAttr(valor)}"]`);
                if (btn) btn.classList.add("active");
                const nuevos = signos.map((s, i) => i === idx ? valor : s);
                updatePenaSaveButton(nuevos);
            },
            async (valores) => {
                const resultado = await savePenaVoto(jornada, valores);
                if (resultado.ok) {
                    showToast("Boleto guardado. Puedes cambiarlo hasta el cierre.", "success");
                    if (typeof renderArena === "function") renderArena();
                } else {
                    showToast(resultado.message || "No se pudo guardar el boleto.", "error");
                }
            });
    }).catch(() => {
        renderPenaVoteForm(Array(15).fill("-"), true, jornada,
            () => {},
            async () => { showToast("Error guardando el boleto.", "error"); });
    });
}