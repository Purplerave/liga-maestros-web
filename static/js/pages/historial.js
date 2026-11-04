/* ==========================================================================
   HISTORIAL — Vista del duelo Maestros vs Peña jornada a jornada.
   Consume GET /api/liga/historial y pinta la tabla de estadísticas.
   ========================================================================== */

function qsHistorial(id) {
    return document.getElementById(id);
}

async function loadHistorial() {
    const body = qsHistorial("historial-duelo-body");
    if (!body) return;

    try {
        const resp = await fetch("/api/liga/historial", { cache: "no-store" });
        if (!resp.ok) throw new Error("No se pudo cargar el historial");
        const data = await resp.json();
        if (data.status !== "ok" || !Array.isArray(data.historial)) {
            throw new Error(data.message || "Error cargando historial");
        }
        renderHistorial(data.historial);
    } catch (err) {
        body.innerHTML = `<div class="empty-state">${escapeHtml(err.message || "Error cargando historial")}</div>`;
    }
}

function renderHistorial(historial) {
    const body = qsHistorial("historial-duelo-body");
    if (!body) return;

    if (!historial.length) {
        body.innerHTML = `<div class="empty-state">Sin jornadas jugadas todavía.</div>`;
        return;
    }

    const rows = historial.map(h => {
        const ganaMaestros = h.maestros > h.pena;
        const ganaPena = h.pena > h.maestros;
        const empate = h.maestros === h.pena;
        const clase = ganaMaestros ? "maestros-win" : ganaPena ? "pena-win" : "draw";
        return `
            <tr class="${clase}">
                <td class="hist-jornada">J${h.jornada}</td>
                <td class="hist-maestros">${h.maestros}</td>
                <td class="hist-pena">${h.pena}</td>
                <td class="hist-votantes">${h.votantes}</td>
                <td class="hist-acum-m">${h.acumulado_maestros}</td>
                <td class="hist-acum-p">${h.acumulado_pena}</td>
            </tr>
        `;
    }).join("");

    body.innerHTML = `
        <table class="historial-duelo-table">
            <thead>
                <tr>
                    <th>Jornada</th>
                    <th>Maestros</th>
                    <th>Peña</th>
                    <th>Votantes</th>
                    <th>Acum. M</th>
                    <th>Acum. P</th>
                </tr>
            </thead>
            <tbody>${rows}</tbody>
        </table>
    `;
}

// Carga el historial cuando el DOM esté listo
document.addEventListener("DOMContentLoaded", () => {
    loadHistorial();
});