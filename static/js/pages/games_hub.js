/* GAMES HUB — Selector de juegos arcade */

let activeGamesHubGame = null;
let snakeAssetsPromise = null;

function ensureSnakeAssets() {
    if (window.SnakeGol) return Promise.resolve();
    if (snakeAssetsPromise) return snakeAssetsPromise;

    snakeAssetsPromise = Promise.all([
        loadStylesheetOnce(
            "snake-gol-font",
            "https://fonts.googleapis.com/css2?family=Press+Start+2P&display=swap"
        ),
        loadStylesheetOnce(
            "snake-gol-styles",
            versionedAsset("/static/css/snake_gol_arcade.css", "snake-arcade-7")
        ),
        import(versionedAsset("/static/js/snake/index.js", "snake-modules-2"))
    ]).then(() => undefined).catch(error => {
        snakeAssetsPromise = null;
        throw error;
    });
    return snakeAssetsPromise;
}

function renderGamesHub() {
    return `
        <section class="games-hub-page">
            <div class="games-hub-header">
                <span class="section-kicker">Arcade</span>
                <h2>Juegos</h2>
                <small>Elige tu juego y compite por el mejor marcador</small>
            </div>
            <div class="games-grid">
                <button class="game-card" type="button" data-game="snake" aria-label="Jugar a Snake Gol">
                    <div class="game-card-icon">&#127922;</div>
                    <h3>Snake Gol</h3>
                    <p>Controla la serpiente, come balones y evita chocar. Ranking propio.</p>
                    ${renderArcadeTopFive("mundialSnake1x2.top10")}
                </button>
                <button class="game-card" type="button" data-game="arkanoid" aria-label="Jugar a Arkanoid Liga">
                    <div class="game-card-icon">&#9917;</div>
                    <h3>Arkanoid Liga</h3>
                    <p>Destruye los ladrillos de 20 equipos. Power-ups y niveles.</p>
                    ${renderArcadeTopFive("arkanoidLiga.topScores")}
                </button>
                <button class="game-card" type="button" data-game="invaders" aria-label="Jugar a Maestros Invaders">
                    <div class="game-card-icon">1X2</div>
                    <h3>Maestros Invaders</h3>
                    <p>Defiende el 1X2, supera oleadas de escudos y derrota a los jefes.</p>
                    ${renderArcadeTopFive("maestrosInvaders.topScores")}
                </button>
            </div>
            <div id="game-active-area"></div>
        </section>`;
}

function renderArcadeTopFive(storageKey) {
    try {
        const scores = JSON.parse(localStorage.getItem(storageKey) || "[]")
            .filter(entry => Number.isFinite(Number(entry?.score)))
            .sort((a, b) => Number(b.score) - Number(a.score))
            .slice(0, 5);
        if (!scores.length) return `<div class="game-card-empty">Sin marcas todav&iacute;a</div>`;
        return `<ol class="game-card-ranking">${scores.map((entry, index) => `
            <li><span>${index + 1}. ${escapeHtml(entry.name || "Jugador")}</span><strong>${Number(entry.score)} pts</strong></li>`).join("")}</ol>`;
    } catch (error) {
        return `<div class="game-card-empty">Sin marcas todav&iacute;a</div>`;
    }
}

function initGamesHub() {
    document.querySelectorAll(".game-card[data-game]").forEach(card => {
        card.addEventListener("click", () => {
            const game = card.dataset.game;
            if (game === "snake") launchSnakeGame();
            else if (game === "arkanoid") launchArkanoidGame();
            else if (game === "invaders") launchInvadersGame();
        });
    });
    if (activeGamesHubGame === "snake") launchSnakeGame();
    if (activeGamesHubGame === "arkanoid") showArkanoidGame();
    if (activeGamesHubGame === "invaders") showInvadersGame();
}

async function launchSnakeGame() {
    resetActiveGamePresentation();
    activeGamesHubGame = "snake";
    const area = qs("game-active-area");
    if (area) area.innerHTML = `<div class="empty-state">Cargando Snake Gol...</div>`;
    try {
        await ensureSnakeAssets();
        if (activeGamesHubGame === "snake") showSnakeGame();
    } catch (error) {
        console.error("No se pudo cargar Snake Gol", error);
        if (activeGamesHubGame === "snake" && area) {
            area.innerHTML = `<div class="empty-state">No se pudo iniciar Snake Gol.</div>`;
        }
    }
}

function showSnakeGame() {
    const area = qs("game-active-area");
    if (!area || !window.SnakeGol) return;
    area.innerHTML = `
        <div class="snake-game-view">
            <button class="game-back-btn" type="button" data-close-game>&#8592; Volver a Juegos</button>
            <div id="snake-game-mount"></div>
        </div>`;
    if (!window.SnakeGol.mount(qs("snake-game-mount"))) {
        area.innerHTML = `<div class="empty-state">No se pudo iniciar Snake Gol.</div>`;
        return;
    }
    document.body.classList.add("games-snake-open");
    setGamesHubTitle("Snake Gol");
}

function launchArkanoidGame() {
    resetActiveGamePresentation();
    activeGamesHubGame = "arkanoid";
    showArkanoidGame();
}

function showArkanoidGame() {
    const area = qs("game-active-area");
    if (!area) return;
    document.body.classList.add("games-arkanoid-open");
    setGamesHubTitle("Arkanoid Liga");
    area.innerHTML = `
        <div class="game-iframe-wrap">
            <button class="game-back-btn" type="button" data-close-game>&#8592; Volver a Juegos</button>
            <iframe src="/juegos/arkanoid.html" class="game-iframe" title="Arkanoid Liga" allowfullscreen></iframe>
        </div>`;
}

function launchInvadersGame() {
    resetActiveGamePresentation();
    activeGamesHubGame = "invaders";
    showInvadersGame();
}

function showInvadersGame() {
    const area = qs("game-active-area");
    if (!area) return;
    document.body.classList.add("games-invaders-open");
    setGamesHubTitle("Maestros Invaders");
    area.innerHTML = `
        <div class="game-iframe-wrap">
            <button class="game-back-btn" type="button" data-close-game>&#8592; Volver a Juegos</button>
            <iframe src="/juegos/maestros-invaders.html?v=5" class="game-iframe" title="Maestros Invaders" allow="autoplay" allowfullscreen></iframe>
        </div>`;
}

function closeActiveGame() {
    activeGamesHubGame = null;
    resetActiveGamePresentation();
    if (typeof hydrateHero === "function") hydrateHero();
}

function resetActiveGamePresentation() {
    window.SnakeGol?.unmount();
    document.body.classList.remove("games-snake-open", "games-arkanoid-open", "games-invaders-open");
    const area = qs("game-active-area");
    if (area) area.innerHTML = "";
}

function leaveGamesHub() {
    activeGamesHubGame = null;
    resetActiveGamePresentation();
}

function setGamesHubTitle(title) {
    const topbarTitle = qs("topbar-title");
    if (topbarTitle) topbarTitle.textContent = title;
}
