export function snakeView() {
  return `
    <section class="snake-gol-shell" id="mundial-snake-1x2">
      <div class="arcade-cabinet">
        <header class="arcade-header">
          <div class="arcade-kicker">LIGA DE MAESTROS - MINI ARCADE</div>
          <h1>MUNDIAL SNAKE 1X2</h1>
          <div class="arcade-lights" aria-hidden="true">
            <span>1</span><span>X</span><span>2</span>
          </div>
        </header>

        <div class="scoreboard">
          <div class="score-card"><span>PUNTOS</span><strong id="snakeScore">0000</strong></div>
          <div class="score-card"><span>MEJOR</span><strong id="snakeBest">0000</strong></div>
          <div class="score-card"><span>NIVEL</span><strong id="snakeLevel">01</strong></div>
          <div class="score-card"><span>ESTADO</span><strong id="snakeState">LISTO</strong></div>
        </div>

        <div class="game-layout">
          <div class="crt-frame">
            <canvas id="snakeGolCanvas" aria-label="Mundial Snake 1X2"></canvas>
            <div class="screen-overlay is-visible" id="snakeOverlay">
              <div class="overlay-card">
                <div class="overlay-small">INSERT COIN</div>
                <div class="overlay-title" id="snakeOverlayTitle">MUNDIAL SNAKE 1X2</div>
                <div class="overlay-text" id="snakeOverlayText">
                  Pulsa una flecha, WASD o START para comenzar
                </div>
              </div>
            </div>
          </div>

          <aside class="ranking-panel" aria-label="Ranking Top 10">
            <div class="ranking-title">TOP 10</div>
            <ol id="snakeRankBody" class="ranking-list"></ol>
          </aside>
        </div>

        <div class="controls-row">
          <div class="main-buttons">
            <button id="snakeStartBtn" class="arcade-button primary" type="button">START</button>
            <button id="snakePauseBtn" class="arcade-button" type="button">PAUSA</button>
            <button id="snakeResetBtn" class="arcade-button danger" type="button">RESET</button>
          </div>

          <div class="mobile-pad" aria-label="Controles moviles">
            <button class="pad-btn up" data-dir="up" aria-label="Arriba" type="button">&#9650;</button>
            <button class="pad-btn left" data-dir="left" aria-label="Izquierda" type="button">&#9664;</button>
            <button class="pad-btn right" data-dir="right" aria-label="Derecha" type="button">&#9654;</button>
            <button class="pad-btn down" data-dir="down" aria-label="Abajo" type="button">&#9660;</button>
          </div>
        </div>

        <footer class="arcade-help">
          Flechas / WASD para moverte - ESPACIO o P para pausar - En movil usa botones o desliza sobre el campo
        </footer>
      </div>
    </section>`;
}
