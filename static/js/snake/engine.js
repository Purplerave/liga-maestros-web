import {
  COLS,
  ROWS,
  START_SPEED,
  MIN_SPEED,
  MAX_OBSTACLES,
  DIRECTIONS,
  cellsEqual,
  cloneCells,
  isReverse,
  padLevel,
  padScore
} from "./config.js";

const STATUS_LABELS = Object.freeze({
  ready: "LISTO",
  running: "JUGANDO",
  paused: "PAUSA",
  gameover: "FINAL"
});

export class SnakeEngine {
  constructor({ renderer, ranking, elements }) {
    this.renderer = renderer;
    this.ranking = ranking;
    this.elements = elements;
    this.snake = [];
    this.prevSnake = [];
    this.direction = { ...DIRECTIONS.right };
    this.directionQueue = [];
    this.food = null;
    this.obstacles = [];
    this.score = 0;
    this.level = 1;
    this.eaten = 0;
    this.stepMs = START_SPEED;
    this.pendingRecordScore = 0;
    this.status = "ready";
    this.lastTime = 0;
    this.accumulator = 0;
    this.callbacks = [];
    this.runStartedAt = 0;
    this.frame = 0;
  }

  snapshot() {
    return {
      snake: this.snake,
      prevSnake: this.prevSnake,
      food: this.food,
      obstacles: this.obstacles
    };
  }

  reset() {
    this.direction = { ...DIRECTIONS.right };
    this.directionQueue = [];
    this.score = 0;
    this.level = 1;
    this.eaten = 0;
    this.stepMs = START_SPEED;
    this.obstacles = [];
    this.status = "ready";
    this.accumulator = 0;
    this.lastTime = performance.now();
    this.runStartedAt = 0;
    this.pendingRecordScore = 0;
    this.rebuildSnake(this.direction);
    this.spawnFood();
    this.updateHud();
    this.showOverlay(
      "MUNDIAL SNAKE 1X2",
      "Pulsa una flecha, WASD o START para comenzar",
      "INSERT COIN"
    );
    this.ranking.render();
    this.renderer.draw(0);
  }

  start() {
    if (this.status === "gameover") this.reset();
    if (this.status === "running") return;
    this.status = "running";
    this.lastTime = performance.now();
    if (!this.runStartedAt) this.runStartedAt = this.lastTime;
    this.accumulator = 0;
    this.hideOverlay();
    this.updateHud();
  }

  pause() {
    if (this.status === "ready") return;
    if (this.status === "gameover") {
      this.reset();
      return;
    }

    if (this.status === "paused") {
      this.status = "running";
      this.lastTime = performance.now();
      this.hideOverlay();
    } else if (this.status === "running") {
      this.status = "paused";
      this.showOverlay(
        "PAUSA",
        "Pulsa ESPACIO, P o PAUSA para volver al partido",
        "TIEMPO MUERTO"
      );
    }
    this.updateHud();
  }

  setDirection(next) {
    if (!next) return;
    if (this.status === "ready" || this.status === "gameover") {
      if (this.status === "gameover") this.reset();
      this.direction = { ...next };
      this.directionQueue = [];
      this.rebuildSnake(next);
      this.start();
      return;
    }
    if (this.status !== "running") return;

    const reference = this.directionQueue.at(-1) || this.direction;
    if (
      this.directionQueue.length < 2
      && !isReverse(next, reference)
      && !cellsEqual(next, reference)
    ) {
      this.directionQueue.push({ ...next });
    }
  }

  rebuildSnake(direction) {
    const head = { x: Math.floor(COLS / 2), y: Math.floor(ROWS / 2) };
    this.snake = Array.from({ length: 5 }, (_, index) => ({
      x: head.x - direction.x * index,
      y: head.y - direction.y * index
    }));
    this.prevSnake = cloneCells(this.snake);
  }

  isOccupied(cell, includeObstacles = true) {
    return this.snake.some((part) => cellsEqual(part, cell))
      || (includeObstacles && this.obstacles.some((obstacle) => cellsEqual(obstacle, cell)));
  }

  isNearSnake(cell, radius = 1) {
    return this.snake.some(
      (part) => Math.abs(part.x - cell.x) + Math.abs(part.y - cell.y) <= radius
    );
  }

  isEdgeCell(cell) {
    return cell.x <= 0 || cell.x >= COLS - 1 || cell.y <= 0 || cell.y >= ROWS - 1;
  }

  cellIsAllowed(cell, options) {
    return !this.isOccupied(cell)
      && !(options.avoidFood && cellsEqual(cell, this.food))
      && !(options.avoidEdges && this.isEdgeCell(cell))
      && !(options.avoidNearSnake && this.isNearSnake(cell, options.safeRadius || 1));
  }

  randomFreeCell(options = {}) {
    for (let attempt = 0; attempt < 800; attempt += 1) {
      const cell = {
        x: Math.floor(Math.random() * COLS),
        y: Math.floor(Math.random() * ROWS)
      };
      if (this.cellIsAllowed(cell, options)) return cell;
    }

    const candidates = [];
    for (let y = 0; y < ROWS; y += 1) {
      for (let x = 0; x < COLS; x += 1) {
        const cell = { x, y };
        if (this.cellIsAllowed(cell, options)) candidates.push(cell);
      }
    }
    return candidates.length
      ? candidates[Math.floor(Math.random() * candidates.length)]
      : null;
  }

  spawnFood() {
    this.food = this.randomFreeCell({
      avoidEdges: true,
      avoidNearSnake: true,
      safeRadius: 1
    });
    if (!this.food) this.finish("CAMPO COMPLETO");
  }

  spawnObstacle() {
    if (this.obstacles.length >= MAX_OBSTACLES) return;
    const cell = this.randomFreeCell({
      avoidFood: true,
      avoidEdges: true,
      avoidNearSnake: true,
      safeRadius: 2
    });
    if (!cell) return;
    const roll = Math.random();
    this.obstacles.push({
      ...cell,
      type: roll > 0.86
        ? "cup"
        : roll > 0.72
          ? "red"
          : roll > 0.58
            ? "yellow"
            : "defender"
    });
  }

  spawnObstacleWave() {
    const target = Math.min(MAX_OBSTACLES, 4 + Math.floor(this.level * 1.35));
    const amount = Math.min(
      target - this.obstacles.length,
      this.level >= 5 && Math.random() > 0.55 ? 2 : 1
    );
    for (let index = 0; index < Math.max(0, amount); index += 1) {
      this.spawnObstacle();
    }
  }

  update() {
    if (this.directionQueue.length) this.direction = this.directionQueue.shift();
    this.prevSnake = cloneCells(this.snake);
    const head = this.snake[0];
    const nextHead = {
      x: head.x + this.direction.x,
      y: head.y + this.direction.y
    };

    if (
      nextHead.x < 0
      || nextHead.x >= COLS
      || nextHead.y < 0
      || nextHead.y >= ROWS
    ) {
      this.finish("MURO");
      return;
    }

    const willEat = cellsEqual(nextHead, this.food);
    const body = willEat ? this.snake : this.snake.slice(0, -1);
    if (body.some((part) => cellsEqual(part, nextHead))) {
      this.finish("PROPIA DEFENSA");
      return;
    }
    if (this.obstacles.some((obstacle) => cellsEqual(obstacle, nextHead))) {
      this.finish("TARJETA");
      return;
    }

    this.snake.unshift(nextHead);
    if (willEat) {
      this.eaten += 1;
      this.score += 10 + this.level * 2;
      this.level = Math.floor(this.score / 72) + 1;
      this.stepMs = Math.max(MIN_SPEED, START_SPEED - (this.level - 1) * 7);
      this.spawnFood();
      if (this.status === "running") this.spawnObstacleWave();
    } else {
      this.snake.pop();
    }
    this.updateHud();
  }

  finish(reason) {
    this.status = "gameover";
    this.pendingRecordScore = this.ranking.qualifies(this.score) ? this.score : 0;
    this.ranking.render(this.score);
    this.updateHud();

    const message = reason === "TARJETA"
      ? `Has chocado con un obstáculo. Puntuación final: ${padScore(this.score)}`
      : reason === "MURO"
        ? `Te has ido contra la banda. Puntuación final: ${padScore(this.score)}`
        : `Choque contigo mismo. Puntuación final: ${padScore(this.score)}`;

    if (this.pendingRecordScore) this.showRecordOverlay(message);
    else this.showOverlay("TARJETA ROJA", message, "FINAL DEL PARTIDO");

    const stats = this.getRunStats(reason);
    this.callbacks.forEach((callback) => {
      try {
        callback(stats);
      } catch (error) {
        console.warn("SnakeGol onGameOver callback error:", error);
      }
    });
  }

  showRecordOverlay(message) {
    this.showOverlay("TARJETA ROJA", message, "FINAL DEL PARTIDO");
    const form = document.createElement("form");
    form.className = "record-form";
    const label = document.createElement("label");
    label.htmlFor = "snakeRecordName";
    label.textContent = "Entras en el TOP 10. Escribe tu nombre:";
    const controls = document.createElement("div");
    const input = document.createElement("input");
    input.id = "snakeRecordName";
    input.maxLength = 12;
    input.autocomplete = "off";
    input.placeholder = "TU NOMBRE";
    const button = document.createElement("button");
    button.type = "submit";
    button.textContent = "OK";
    controls.append(input, button);
    form.append(label, controls);
    this.elements.overlayText.append(form);
    input.focus();

    form.addEventListener("submit", (event) => {
      event.preventDefault();
      const score = this.pendingRecordScore;
      const scores = this.ranking.save(score, input.value, this.level);
      if (!scores.some((entry) => entry.score === score)) return;
      this.pendingRecordScore = 0;
      this.ranking.render();
      this.showOverlay(
        "RÉCORD GUARDADO",
        "Pulsa una flecha, WASD o START para volver a jugar",
        "TOP 10"
      );
    });
  }

  showOverlay(title, text, small = "INSERT COIN") {
    this.elements.overlay.classList.add("is-visible");
    this.elements.overlaySmall.textContent = small;
    this.elements.overlayTitle.textContent = title;
    this.elements.overlayText.replaceChildren(document.createTextNode(text));
  }

  hideOverlay() {
    this.elements.overlay.classList.remove("is-visible");
  }

  updateHud() {
    this.elements.score.textContent = padScore(this.score);
    this.ranking.bestElement.textContent = padScore(
      Math.max(this.ranking.best, this.score)
    );
    this.elements.level.textContent = padLevel(this.level);
    this.elements.state.textContent = STATUS_LABELS[this.status] || "LISTO";
  }

  getScore() {
    return this.score;
  }

  getRunStats(reason = "") {
    return {
      score: this.score,
      level: this.level,
      eaten: this.eaten,
      reason,
      duration_ms: this.runStartedAt
        ? Math.max(0, Math.round(performance.now() - this.runStartedAt))
        : 0
    };
  }

  onGameOver(callback) {
    if (typeof callback === "function") this.callbacks.push(callback);
  }

  run() {
    const loop = (time) => {
      this.frame = requestAnimationFrame(loop);
      if (this.status === "running") {
        const delta = Math.min(80, time - this.lastTime);
        this.lastTime = time;
        this.accumulator += delta;
        while (this.accumulator >= this.stepMs) {
          this.update();
          this.accumulator -= this.stepMs;
          if (this.status !== "running") {
            this.accumulator = 0;
            break;
          }
        }
      } else {
        this.lastTime = time;
      }
      const alpha = this.status === "running" ? this.accumulator / this.stepMs : 0;
      this.renderer.draw(alpha);
    };
    this.frame = requestAnimationFrame(loop);
  }

  destroy() {
    cancelAnimationFrame(this.frame);
    this.frame = 0;
    this.status = "paused";
    this.callbacks = [];
  }
}
