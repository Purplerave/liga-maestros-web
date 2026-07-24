import { bindSnakeControls } from "./controls.js";
import { SnakeEngine } from "./engine.js";
import { SnakeRanking } from "./ranking.js";
import { SnakeRenderer } from "./renderer.js";
import { snakeView } from "./view.js";

function getElements() {
  const elements = {
    canvas: document.getElementById("snakeGolCanvas"),
    score: document.getElementById("snakeScore"),
    best: document.getElementById("snakeBest"),
    level: document.getElementById("snakeLevel"),
    state: document.getElementById("snakeState"),
    rank: document.getElementById("snakeRankBody"),
    overlay: document.getElementById("snakeOverlay"),
    overlayTitle: document.getElementById("snakeOverlayTitle"),
    overlayText: document.getElementById("snakeOverlayText"),
    start: document.getElementById("snakeStartBtn"),
    pause: document.getElementById("snakePauseBtn"),
    reset: document.getElementById("snakeResetBtn")
  };
  elements.overlaySmall = elements.overlay?.querySelector(".overlay-small");
  return elements;
}

let activeGame = null;

function mount(container) {
  if (!(container instanceof HTMLElement)) return false;
  unmount();
  container.innerHTML = snakeView();
  const elements = getElements();
  if (!Object.values(elements).every(Boolean)) {
    container.replaceChildren();
    return false;
  }

  const ranking = new SnakeRanking(elements.rank, elements.best);
  let engine;
  const renderer = new SnakeRenderer(elements.canvas, () => engine.snapshot());
  engine = new SnakeEngine({ renderer, ranking, elements });

  const unbindControls = bindSnakeControls({ engine, renderer, elements });
  renderer.resize();
  engine.reset();
  engine.run();
  activeGame = { container, engine, ranking, unbindControls };
  return true;
}

function unmount() {
  if (!activeGame) return;
  activeGame.unbindControls();
  activeGame.engine.destroy();
  activeGame.container.replaceChildren();
  activeGame = null;
}

window.SnakeGol = Object.freeze({
  mount,
  unmount,
  start: () => activeGame?.engine.start(),
  reset: () => activeGame?.engine.reset(),
  pause: () => activeGame?.engine.pause(),
  getScore: () => activeGame?.engine.getScore() ?? 0,
  getRunStats: () => activeGame?.engine.getRunStats() ?? null,
  onGameOver: (callback) => activeGame?.engine.onGameOver(callback),
  saveScore: (score, name = "") => activeGame?.ranking.save(
    score,
    name,
    activeGame.engine.level
  ) ?? [],
  loadScores: () => activeGame?.ranking.load() ?? []
});
