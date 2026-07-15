/* ==========================================================================
   QUIZ — Reto 10 LaLiga: preguntas, envio, resultados, ranking.
   Dependencias: utils.js, state.js
   ========================================================================== */


function renderQuizNewspaperPage() {
    const jornada = state.data.jornada || state.jornada;
    if (!jornada) {
        return `<article class="newspaper-article-page"><div class="article-page-kicker">Pag. 7 - Reto 10</div><h2>Reto 10 LaLiga</h2><p>No hay jornada activa.</p></article>`;
    }
    return `
        <article class="quiz-feature-page">
            <header class="quiz-hero">
                <div>
                    <div class="quiz-kicker">Pag. 7 - Desafio de Maestros</div>
                    <h2>Reto 10</h2>
                    <p>Jornada ${escapeHtml(String(jornada))}: diez preguntas, puntos por acierto y ranking propio.</p>
                </div>
                <div class="quiz-hero-score" aria-hidden="true">
                    <span>1</span><span>X</span><span>2</span>
                </div>
            </header>
            <section class="quiz-stage">
                <div id="quiz-container" class="quiz-container">
                    <div class="empty-state">Cargando preguntas...</div>
                </div>
            </section>
        </article>`;
}

function initQuiz() {
    const container = document.getElementById("quiz-container");
    if (!container) return;
    const jornada = state.data.jornada || state.jornada;
    if (!jornada) { container.innerHTML = '<div class="empty-state">Sin jornada activa.</div>'; return; }

    fetch(`/api/quiz/preguntas?j=${jornada}`, { credentials: "same-origin" })
        .then(r => r.json())
        .then(data => {
            if (!data.disponible || !data.preguntas || data.preguntas.length === 0) {
                container.innerHTML = `
                    <div class="quiz-empty">
                        <div class="quiz-empty-icon"></div>
                        <h3>Reto 10 no disponible</h3>
                        <p>Aun no hay preguntas para la jornada ${escapeHtml(String(jornada))}. Vuelve mas tarde.</p>
                    </div>`;
                return;
            }
            renderQuizQuestions(container, data);
        })
        .catch(() => { container.innerHTML = '<div class="empty-state">Error al cargar el quiz.</div>'; });
}

function renderQuizQuestions(container, data) {
    const preguntas = data.preguntas;
    let currentQ = 0;
    const answers = [];
    const startTime = Date.now();
    const total = preguntas.length;

    function renderQuestion(idx) {
        const p = preguntas[idx];
        container.innerHTML = `
            <div class="quiz-progress">
                <div class="quiz-progress-bar"><div class="quiz-progress-fill" style="width:${((idx) / total) * 100}%"></div></div>
                <span>${idx + 1} / ${total}</span>
            </div>
            <div class="quiz-question-card">
                <div class="quiz-question-tema">${escapeHtml(p.tema || "")}</div>
                <h3 class="quiz-question-text">${escapeHtml(p.enunciado)}</h3>
                <div class="quiz-options">
                    <button class="quiz-option" data-q="${idx}" data-answer="A" type="button">
                        <span class="quiz-option-letter">A</span>
                        <span class="quiz-option-text">${escapeHtml(p.opcion_a)}</span>
                    </button>
                    <button class="quiz-option" data-q="${idx}" data-answer="B" type="button">
                        <span class="quiz-option-letter">B</span>
                        <span class="quiz-option-text">${escapeHtml(p.opcion_b)}</span>
                    </button>
                    <button class="quiz-option" data-q="${idx}" data-answer="C" type="button">
                        <span class="quiz-option-letter">C</span>
                        <span class="quiz-option-text">${escapeHtml(p.opcion_c)}</span>
                    </button>
                </div>
            </div>`;

        container.querySelectorAll(".quiz-option").forEach(btn => {
            btn.addEventListener("click", () => {
                answers[idx] = { pregunta_id: p.id, respuesta: btn.dataset.answer };
                currentQ++;
                if (currentQ < total) {
                    renderQuestion(currentQ);
                } else {
                    submitQuiz(container, answers, startTime, data.jornada);
                }
            });
        });
    }

    renderQuestion(0);
}

function submitQuiz(container, answers, startTime, jornada) {
    const tiempo = Date.now() - startTime;
    container.innerHTML = '<div class="empty-state">Enviando respuestas...</div>';

    fetch("/api/quiz/submit", {
        method: "POST",
        credentials: "same-origin",
        headers: authenticatedJsonHeaders(),
        body: JSON.stringify({ jornada, respuestas: answers, tiempo_total_ms: tiempo }),
    })
    .then(r => r.json())
    .then(result => {
        if (result.status !== "ok") {
            container.innerHTML = `<div class="quiz-result quiz-result-error"><h3>Error</h3><p>${escapeHtml(result.message || "No se pudo guardar.")}</p></div>`;
            return;
        }
        renderQuizResult(container, result, jornada);
    })
    .catch(() => { container.innerHTML = '<div class="empty-state">Error de conexion.</div>'; });
}

function renderQuizResult(container, result, jornada) {
    const minutes = Math.floor(result.total > 0 ? (result.tiempo_total_ms || 0) / 60000 : 0);
    const seconds = Math.floor(((result.tiempo_total_ms || 0) % 60000) / 1000);
    container.innerHTML = `
        <div class="quiz-result">
            <div class="quiz-result-score">
                <div class="quiz-result-big">${result.aciertos}/${result.total}</div>
                <div class="quiz-result-points">${result.puntos} puntos</div>
                <div class="quiz-result-time">${minutes}:${String(seconds).padStart(2, "0")}</div>
            </div>
            ${result.posicion_jornada ? `<div class="quiz-result-position">Estas ${result.posicion_jornada}Âº en esta jornada</div>` : ""}
            <div class="quiz-result-bonuses">
                ${result.bonus_perfecto ? `<span class="quiz-bonus">Perfecto +300</span>` : ""}
                ${result.bonus_rapidez ? `<span class="quiz-bonus">Rapidez +${result.bonus_rapidez}</span>` : ""}
                ${result.racha_max >= 3 ? `<span class="quiz-bonus">Racha ${result.racha_max} +${(result.racha_max >= 5 ? 50 : 0)}</span>` : ""}
            </div>
        </div>
        <div class="quiz-ranking-section">
            <h3>Ranking jornada ${escapeHtml(String(jornada))}</h3>
            <div id="quiz-ranking-list" class="quiz-ranking-list">Cargando...</div>
        </div>`;

    fetch(`/api/quiz/ranking?tipo=jornada&j=${jornada}`, { credentials: "same-origin" })
        .then(r => r.json())
        .then(data => {
            const list = document.getElementById("quiz-ranking-list");
            if (!list) return;
            if (!data.ranking || data.ranking.length === 0) {
                list.innerHTML = '<div class="empty-state">Sin ranking aun.</div>';
                return;
            }
            list.innerHTML = data.ranking.map((entry, idx) => `
                <div class="quiz-rank-row${entry.user_id === state.user.id ? " quiz-rank-mine" : ""}">
                    <span class="quiz-rank-pos">${idx + 1}Âº</span>
                    <span class="quiz-rank-name">${escapeHtml(entry.nombre)}</span>
                    <span class="quiz-rank-hits">${entry.aciertos}/${entry.total_preguntas}</span>
                    <span class="quiz-rank-pts">${entry.puntos} pts</span>
                </div>
            `).join("");
        })
        .catch(() => {});
}
