import { DIRECTIONS } from "./config.js";

function keyDirection(key) {
  const normalized = key.toLowerCase();
  if (normalized === "arrowup" || normalized === "w") return DIRECTIONS.up;
  if (normalized === "arrowdown" || normalized === "s") return DIRECTIONS.down;
  if (normalized === "arrowleft" || normalized === "a") return DIRECTIONS.left;
  if (normalized === "arrowright" || normalized === "d") return DIRECTIONS.right;
  return null;
}

function arcadeIsVisible(canvas) {
  return Boolean(canvas.offsetParent)
    && document.body.classList.contains("newspaper-snake-active");
}

export function bindSnakeControls({ engine, renderer, elements }) {
  let swipeStart = null;

  const handleKeydown = (event) => {
    if (event.target?.matches?.("input, textarea, select")) return;
    if (!arcadeIsVisible(elements.canvas)) return;

    const direction = keyDirection(event.key);
    if (direction) {
      event.preventDefault();
      engine.setDirection(direction);
      return;
    }
    if (event.key === " " || event.key.toLowerCase() === "p") {
      event.preventDefault();
      engine.pause();
    }
  };

  const handleStart = () => engine.start();
  const handlePause = () => engine.pause();
  const handleReset = () => engine.reset();
  const handleDirection = (event) => {
    event.preventDefault();
    engine.setDirection(DIRECTIONS[event.currentTarget.dataset.dir]);
  };
  const handlePointerDown = (event) => {
    if (event.pointerType === "mouse") return;
    swipeStart = { x: event.clientX, y: event.clientY };
  };
  const handlePointerUp = (event) => {
    if (!swipeStart || event.pointerType === "mouse") return;
    const dx = event.clientX - swipeStart.x;
    const dy = event.clientY - swipeStart.y;
    swipeStart = null;
    if (Math.max(Math.abs(dx), Math.abs(dy)) < 24) return;
    engine.setDirection(
      Math.abs(dx) > Math.abs(dy)
        ? (dx > 0 ? DIRECTIONS.right : DIRECTIONS.left)
        : (dy > 0 ? DIRECTIONS.down : DIRECTIONS.up)
    );
  };
  const handleOrientationChange = () => {
    window.setTimeout(() => renderer.resize(), 150);
  };

  window.addEventListener("keydown", handleKeydown);
  elements.start.addEventListener("click", handleStart);
  elements.pause.addEventListener("click", handlePause);
  elements.reset.addEventListener("click", handleReset);

  const directionButtons = [...elements.canvas.closest(".snake-gol-shell").querySelectorAll("[data-dir]")];
  directionButtons.forEach((button) => {
    button.addEventListener("pointerdown", handleDirection);
  });

  elements.canvas.addEventListener("pointerdown", handlePointerDown);
  elements.canvas.addEventListener("pointerup", handlePointerUp);

  const resizeObserver = new ResizeObserver(() => renderer.resize());
  resizeObserver.observe(elements.canvas.parentElement);
  window.addEventListener("orientationchange", handleOrientationChange);

  return () => {
    window.removeEventListener("keydown", handleKeydown);
    window.removeEventListener("orientationchange", handleOrientationChange);
    elements.start.removeEventListener("click", handleStart);
    elements.pause.removeEventListener("click", handlePause);
    elements.reset.removeEventListener("click", handleReset);
    directionButtons.forEach((button) => {
      button.removeEventListener("pointerdown", handleDirection);
    });
    elements.canvas.removeEventListener("pointerdown", handlePointerDown);
    elements.canvas.removeEventListener("pointerup", handlePointerUp);
    resizeObserver.disconnect();
  };
}
