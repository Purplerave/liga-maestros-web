/**
 * 📊 LIGA DE LOS MAESTROS - MOTOR DEFINITIVO
 */

let state = { data: null, jornada: '59' };

async function refreshData() {
    const j = new URLSearchParams(window.location.search).get('j') || '59';
    try {
        const res = await fetch(`/api/liga/data?j=${j}`);
        state.data = await res.json();
        
        console.log("DEBUG: Datos recibidos:", state.data);
        
        renderMatches();
        renderStandings();
    } catch (e) {
        console.error("Error al refrescar datos:", e);
    }
}

function renderMatches() {
    const container = document.getElementById('matches-body');
    if (!container || !state.data.partidos) {
        console.error("No se encontró matches-body o no hay partidos");
        return;
    }

    container.innerHTML = state.data.partidos.map(m => `
        <tr>
            <td style="text-align:center;">${m.id}</td>
            <td style="text-align:right; font-weight:700;">${m.local}</td>
            <td style="text-align:center; font-weight:900;">${m.marcador}</td>
            <td style="text-align:left; font-weight:700;">${m.visitante}</td>
            <td style="text-align:center;">${m.signo_actual}</td>
            <td>-</td><td>-</td><td>-</td><td>-</td><td>-</td>
            <td style="text-align:center">1 X 2</td>
            <td style="text-align:center">-</td>
        </tr>
    `).join('');
}

function renderStandings() {
    const container = document.getElementById('real-liga-body');
    if (!container || !state.data.standings) {
        console.error("No se encontró real-liga-body o no hay standings");
        return;
    }
    
    const cls = state.data.standings;
    const draw = (title, teams) => {
        let html = `<div style="flex:1; padding:0 5px; font-size:0.55rem;">
            <div style="font-weight:900; color:#003a70; border-bottom:1px solid #ccc; margin-bottom:3px;">${title}</div>`;
        teams.forEach(e => {
            html += `<div style="display:flex; justify-content:space-between; padding:1px 0; border-bottom:1px solid #f1f5f9;">
                <span>${e.pos}. ${e.n}</span><span>${e.pts} pts</span>
            </div>`;
        });
        return html + '</div>';
    };
    
    container.innerHTML = draw("1ª DIV", cls.primera) + draw("2ª DIV", cls.segunda);
}

document.addEventListener('DOMContentLoaded', refreshData);
