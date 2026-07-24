export const COLS = 30;
export const ROWS = 20;
export const START_SPEED = 154;
export const MIN_SPEED = 68;
export const MAX_OBSTACLES = 14;
export const STORAGE_KEY = "mundialSnake1x2.top10";
export const PLAYER_KEY = "mundialSnake1x2.playerName";

export const DIRECTIONS = Object.freeze({
  up: Object.freeze({ x: 0, y: -1 }),
  down: Object.freeze({ x: 0, y: 1 }),
  left: Object.freeze({ x: -1, y: 0 }),
  right: Object.freeze({ x: 1, y: 0 })
});

export function cloneCells(cells) {
  return cells.map((cell) => ({ x: cell.x, y: cell.y }));
}

export function cellsEqual(a, b) {
  return Boolean(a && b && a.x === b.x && a.y === b.y);
}

export function padScore(value) {
  return String(Math.max(0, Number(value) || 0)).padStart(4, "0");
}

export function padLevel(value) {
  return String(Math.max(1, Number(value) || 1)).padStart(2, "0");
}

export function isReverse(a, b) {
  return a.x + b.x === 0 && a.y + b.y === 0;
}
