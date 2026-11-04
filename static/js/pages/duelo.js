/* ==========================================================================
   DUELO — Marcador Maestros vs Peña + cuenta atrás del cierre.
   Se actualiza con cada payload completo o slim: lo llaman refreshData,
   patchTicketArena/patchLiveArena/patchCoverPage y el poll del directo.
   ========================================================================== */

let _dueloCountdownInterval = null;

/* Aciertos de las columnas oficiales en la jornada que está en juego.
   El marcador del duelo NO suma todos los maestros (eso daba 41-9 en la J17).
   Usa el mejor maestro de la jornada: si la Peña gana al mejor máquina,
   queda escrito. */
function dueloMaestrosHits() {
    const ranking = state.data?.ranking_maestros || {};
    let mejor = 0;
    for (const stats of Object.values(ranking)) {
        const h = Number(stats?.jornada_live ?? stats?.jornada ?? 0) || 0;
        if (h > mejor) mejor = h;
    }
    return mejor;
}

/* Aciertos del consenso de la Peña: un signo mayoritario por partido.
   Un empate (`ganador === "-"`) no es una lectura y no puntúa; el marcador
   del pleno solo cuenta si las 14 previas del consenso están acertadas,
   igual que la regla del backend (si no, el 15 nunca vale nada). */
function dueloPenaScore() {
    const consenso = Array.isArray(state.data?.consenso_pena) ? state.data.consenso_pena : [];
    const partidos = Array.isArray(state.data?.partidos) ? state.data.partidos : [];
    const lectura = new Map();
    consenso.forEach(row => {
        const ganador = String(row?.ganador || "-").toUpperCase();
        if (!ganador || ganador === "-") return;
        if (!Number(row?.total || 0)) return;
        lectura.set(Number(row?.id), ganador);
    });

    let hits = 0;
    let previas = 0;
    let previasResueltas = 0;
    let ultimaResuelta = true;
    const total = Math.min(14, partidos.length);
    for (let i = 0; i < total; i += 1) {
        const match = partidos[i];
        const ganador = lectura.get(Number(match?.id ?? i + 1));
        const real = String(match?.signo_actual || "").trim().toUpperCase();
        const decidido = Boolean(real) && real !== "-" && ganador;
        if (decidido) {
            previasResueltas += 1;
            ultimaResuelta = true;
            if (real.includes(ganador)) {
                previas += 1;
                hits += 1;
            } else {
                ultimaResuelta = false;
            }
        } else {
            // Un partido sin resultado todavía no rompe el pleno: solo lo deja
            // pendiente. Si ya hay una previa fallada, el 15 no puede pagar.
            ultimaResuelta = false;
        }
    }

    const pleno = partidos.length > 14 ? partidos[14] : null;
    const plenoGanador = lectura.get(Number(pleno?.id ?? 15));
    const marcador = String(pleno?.marcador || pleno?.score || "").trim();
    const plenoDecidido = Boolean(marcador) && /^\d+\s*[-–]\s*\d+$/.test(marcador);
    if (previasResueltas === 14 && previas === 14 && ultimaResuelta && plenoDecidido && plenoGanador) {
        if (marcador.replace(/\s|–/g, "-") === plenoGanador.replace(/\s|–/g, "-")) hits += 1;
    }
    return hits;
}

function updateDueloScore() {
    const maestrosEl = document.getElementById("duelo-maestros");
    const penaEl = document.getElementById("duelo-pena");
    if (!maestrosEl || !penaEl) return;
    maestrosEl.textContent = String(dueloMaestrosHits());
    penaEl.textContent = String(dueloPenaScore());
}

function startDueloCountdown() {
    const el = document.getElementById("duelo-countdown");
    if (!el) return;
    if (_dueloCountdownInterval) clearInterval(_dueloCountdownInterval);
    const tick = () => {
        // El deadline es una hora de pared de Madrid ("2026-08-22 17:00").
        const raw = state.data?.edit_deadline || state.data?.kickoff_at || "";
        const text = String(raw).trim();
        if (!text) { el.textContent = "—"; el.classList.remove("urgent"); return; }
        let target = null;
        if (typeof madridWallClockToMs === "function") {
            target = madridWallClockToMs(text.slice(0, 10), text.slice(11, 16));
        } else {
            const parsed = Date.parse(text.replace(" ", "T"));
            target = Number.isNaN(parsed) ? null : parsed;
        }
        if (!target) { el.textContent = "—"; el.classList.remove("urgent"); return; }
        const diff = target - Date.now();
        if (diff <= 0 || state.data?.is_locked) {
            el.textContent = "CERRADA";
            el.classList.remove("urgent");
            return;
        }
        const totalSec = Math.floor(diff / 1000);
        const d = Math.floor(totalSec / 86400);
        const h = Math.floor((totalSec % 86400) / 3600);
        const m = Math.floor((totalSec % 3600) / 60);
        const s = totalSec % 60;
        let label;
        if (d > 0) label = `${d}d ${String(h).padStart(2, "0")}h`;
        else if (h > 0) label = `${h}h ${String(m).padStart(2, "0")}m`;
        else label = `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
        el.textContent = `Cierra en ${label}`;
        el.classList.toggle("urgent", diff < 3_600_000);
    };
    tick();
    _dueloCountdownInterval = setInterval(tick, 1000);
}

function hydrateDuelo() {
    updateDueloScore();
    startDueloCountdown();
}
