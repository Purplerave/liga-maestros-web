/* ==========================================================================
   DUELO — Marcador Maestros vs Peña + cuenta atrás del cierre.
   Se actualiza con cada payload completo o slim.
   ========================================================================== */

let _dueloCountdownInterval = null;

function startDueloCountdown() {
    const el = document.getElementById("duelo-countdown");
    if (!el) return;
    if (_dueloCountdownInterval) clearInterval(_dueloCountdownInterval);
    const tick = () => {
        const raw = state.data?.edit_deadline || state.data?.kickoff_at || "";
        if (!raw) { el.textContent = "—"; return; }
        const text = String(raw).trim();
        let target;
        if (typeof madridWallClockToMs === "function") {
            target = madridWallClockToMs(text.slice(0, 10), text.slice(11, 16));
        } else {
            const parsed = Date.parse(text.replace(" ", "T"));
            target = Number.isNaN(parsed) ? null : parsed;
        }
        if (!target) { el.textContent = "—"; return; }
        const diff = Math.max(0, target - Date.now());
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
        else label = `${String(m).padStart(2, "0")}m ${String(s).padStart(2, "0")}s`;
        el.textContent = `Cierra en ${label}`;
        el.classList.toggle("urgent", diff < 3_600_000);
    };
    tick();
    _dueloCountdownInterval = setInterval(tick, 1000);
}

function updateDueloScore() {
    const maestrosEl = document.getElementById("duelo-maestros");
    const penaEl = document.getElementById("duelo-pena");
    if (!maestrosEl || !penaEl) return;
    const ranking = state.data?.ranking_maestros || {};
    const consenso = state.data?.consenso_pena || [];
    // Puntuación de la Peña: signos mayoritarios, uno por partido
    let penaHits = 0;
    let penaltyPlayed = 0;
    const partidos = state.data?.partidos || [];
    for (let i = 0; i < Math.min(14, partidos.length); i++) {
        const m = partidos[i];
        const c = consenso.find(item => Number(item.id) === Number(m.id));
        if (!c || !c.ganador || c.ganador === "-") continue;
        const real = String(m.signo_actual || "").toUpperCase();
        if (!real || real === "-") continue;
        penaltyPlayed += 1;
        if (real.includes(c.ganador)) penaltyHits += 1;
    }
    // Puntuación de los Maestros: suma de aciertos de la jornada
    let maestrosHits = 0;
    for (const [uid, stats] of Object.entries(ranking)) {
        maestrosHits += Number(stats.jornada_live ?? stats.jornada ?? 0);
    }
    maestrosEl.textContent = String(maestrosHits);
    penaEl.textContent = String(penaltyHits);
}

function hydrateDuelo() {
    updateDueloScore();
    startDueloCountdown();
}