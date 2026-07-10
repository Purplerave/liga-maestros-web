(() => {
  "use strict";

  const STORAGE_KEY = "mundialSnake1x2.top10";
  const COLS = 30;
  const ROWS = 20;
  const START_SPEED = 154;
  const MIN_SPEED = 68;
  const MAX_OBSTACLES = 14;

  const canvas = document.getElementById("snakeGolCanvas");
  const ctx = canvas.getContext("2d");

  const elScore = document.getElementById("snakeScore");
  const elBest = document.getElementById("snakeBest");
  const elLevel = document.getElementById("snakeLevel");
  const elState = document.getElementById("snakeState");
  const elRank = document.getElementById("snakeRankBody");

  const overlay = document.getElementById("snakeOverlay");
  const overlayTitle = document.getElementById("snakeOverlayTitle");
  const overlayText = document.getElementById("snakeOverlayText");

  const startBtn = document.getElementById("snakeStartBtn");
  const pauseBtn = document.getElementById("snakePauseBtn");
  const resetBtn = document.getElementById("snakeResetBtn");

  const dirs = {
    up: { x: 0, y: -1 },
    down: { x: 0, y: 1 },
    left: { x: -1, y: 0 },
    right: { x: 1, y: 0 }
  };

  let snake = [];
  let prevSnake = [];
  let direction = { ...dirs.right };
  let nextDirection = { ...dirs.right };
  let food = null;
  let obstacles = [];

  let score = 0;
  let level = 1;
  let best = 0;
  let eaten = 0;
  let stepMs = START_SPEED;
  let pendingRecordScore = 0;

  let status = "ready";
  let lastTime = 0;
  let accumulator = 0;
  let callbacks = [];
  let runStartedAt = 0;

  let view = {
    w: 960,
    h: 600,
    dpr: 1,
    cell: 24,
    ox: 0,
    oy: 0,
    boardW: 720,
    boardH: 480
  };

  let swipeStart = null;

  function cloneCells(cells) {
    return cells.map((cell) => ({ x: cell.x, y: cell.y }));
  }

  function padScore(value) {
    return String(Math.max(0, value)).padStart(4, "0");
  }

  function padLevel(value) {
    return String(value).padStart(2, "0");
  }

  function loadScores() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      const parsed = raw ? JSON.parse(raw) : [];
      return Array.isArray(parsed)
        ? parsed
            .filter((item) => Number.isFinite(item.score))
            .sort((a, b) => b.score - a.score)
            .slice(0, 10)
        : [];
    } catch {
      return [];
    }
  }

  function recordQualifies(finalScore) {
    const scores = loadScores();
    return Number.isFinite(finalScore) && finalScore > 0 && (scores.length < 10 || finalScore > scores[scores.length - 1].score);
  }

  function saveScore(finalScore, playerName = "") {
    if (!Number.isFinite(finalScore) || finalScore <= 0) return loadScores();

    const scores = loadScores();
    const qualifies = scores.length < 10 || finalScore > scores[scores.length - 1].score;

    if (!qualifies) return scores;

    const cleanName = String(playerName || localStorage.getItem("mundialSnake1x2.playerName") || "")
      .trim()
      .toUpperCase()
      .replace(/[^A-Z0-9 Ñ.-]/g, "")
      .slice(0, 12);

    if (!cleanName) return scores;
    localStorage.setItem("mundialSnake1x2.playerName", cleanName);

    const entry = {
      name: cleanName,
      score: finalScore,
      level,
      date: new Date().toISOString()
    };

    const next = [...scores, entry]
      .sort((a, b) => b.score - a.score)
      .slice(0, 10);

    localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    return next;
  }

  function renderRanking() {
    const scores = loadScores();
    elRank.innerHTML = "";

    for (let i = 0; i < 10; i += 1) {
      const li = document.createElement("li");

      if (scores[i]) {
        li.innerHTML = `
          <div class="rank-row">
            <span class="rank-name">${escapeHtml(scores[i].name || "---")}</span>
            <span class="rank-score">${padScore(scores[i].score)}</span>
          </div>
        `;
      } else {
        li.innerHTML = `<span class="empty-rank">---</span>`;
      }

      elRank.appendChild(li);
    }

    best = scores.length ? scores[0].score : 0;
    elBest.textContent = padScore(best);
  }

  function escapeHtml(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function rebuildSnake(dir = dirs.right) {
    const head = { x: Math.floor(COLS / 2), y: Math.floor(ROWS / 2) };
    snake = [];

    for (let i = 0; i < 5; i += 1) {
      snake.push({
        x: head.x - dir.x * i,
        y: head.y - dir.y * i
      });
    }

    prevSnake = cloneCells(snake);
  }

  function reset() {
    direction = { ...dirs.right };
    nextDirection = { ...dirs.right };
    score = 0;
    level = 1;
    eaten = 0;
    stepMs = START_SPEED;
    obstacles = [];
    status = "ready";
    accumulator = 0;
    lastTime = performance.now();
    runStartedAt = 0;

    rebuildSnake(direction);
    spawnFood();
    updateHud();
    showOverlay(
      "MUNDIAL SNAKE 1X2",
      "Pulsa una flecha, WASD o START para comenzar",
      "INSERT COIN"
    );
    renderRanking();
    draw(0);
  }

  function start() {
    if (status === "gameover") reset();
    if (status === "running") return;

    status = "running";
    lastTime = performance.now();
    if (!runStartedAt) runStartedAt = lastTime;
    accumulator = 0;
    hideOverlay();
    updateHud();
  }

  function pause() {
    if (status === "ready") return;

    if (status === "gameover") {
      reset();
      return;
    }

    if (status === "paused") {
      status = "running";
      lastTime = performance.now();
      hideOverlay();
    } else if (status === "running") {
      status = "paused";
      showOverlay("PAUSA", "Pulsa ESPACIO, P o PAUSA para volver al partido", "TIEMPO MUERTO");
    }

    updateHud();
  }

  function getScore() {
    return score;
  }

  function getRunStats(reason = "") {
    const now = performance.now();
    return {
      score,
      level,
      eaten,
      reason,
      duration_ms: runStartedAt ? Math.max(0, Math.round(now - runStartedAt)) : 0
    };
  }

  function onGameOver(callback) {
    if (typeof callback === "function") callbacks.push(callback);
  }

  function updateHud() {
    elScore.textContent = padScore(score);
    elBest.textContent = padScore(Math.max(best, score));
    elLevel.textContent = padLevel(level);

    const label = {
      ready: "LISTO",
      running: "JUGANDO",
      paused: "PAUSA",
      gameover: "FINAL"
    };

    elState.textContent = label[status] || "LISTO";
  }

  function showOverlay(title, text, small = "INSERT COIN", extraHtml = "") {
    overlay.classList.add("is-visible");
    overlay.querySelector(".overlay-small").textContent = small;
    overlayTitle.textContent = title;
    overlayText.innerHTML = `${escapeHtml(text)}${extraHtml}`;
  }

  function hideOverlay() {
    overlay.classList.remove("is-visible");
  }

  function isReverse(a, b) {
    return a.x + b.x === 0 && a.y + b.y === 0;
  }

  function setDirection(dir) {
    if (!dir) return;

    if (status === "ready") {
      direction = { ...dir };
      nextDirection = { ...dir };
      rebuildSnake(dir);
      start();
      return;
    }

    if (status === "gameover") {
      reset();
      direction = { ...dir };
      nextDirection = { ...dir };
      rebuildSnake(dir);
      start();
      return;
    }

    if (status !== "running") return;

    if (!isReverse(dir, direction)) {
      nextDirection = { ...dir };
    }
  }

  function cellsEqual(a, b) {
    return a && b && a.x === b.x && a.y === b.y;
  }

  function isOccupied(cell, includeObstacles = true) {
    const onSnake = snake.some((part) => cellsEqual(part, cell));
    const onObstacle = includeObstacles && obstacles.some((obs) => cellsEqual(obs, cell));
    return onSnake || onObstacle;
  }

  function isNearSnake(cell, radius = 1) {
    return snake.some((part) => Math.abs(part.x - cell.x) + Math.abs(part.y - cell.y) <= radius);
  }

  function isEdgeCell(cell) {
    return cell.x <= 0 || cell.x >= COLS - 1 || cell.y <= 0 || cell.y >= ROWS - 1;
  }

  function randomFreeCell(options = {}) {
    let cell;
    let guard = 0;

    do {
      cell = {
        x: Math.floor(Math.random() * COLS),
        y: Math.floor(Math.random() * ROWS)
      };
      guard += 1;
    } while (
      (
        isOccupied(cell) ||
        (options.avoidFood && cellsEqual(cell, food)) ||
        (options.avoidEdges && isEdgeCell(cell)) ||
        (options.avoidNearSnake && isNearSnake(cell, options.safeRadius || 1))
      ) && guard < 2000
    );

    return cell;
  }

  function spawnFood() {
    food = randomFreeCell();
  }

  function spawnObstacle() {
    if (obstacles.length >= MAX_OBSTACLES) return;

    const cell = randomFreeCell({
      avoidFood: true,
      avoidEdges: true,
      avoidNearSnake: true,
      safeRadius: 2
    });

    if (cellsEqual(cell, food) || isOccupied(cell) || isEdgeCell(cell) || isNearSnake(cell, 2)) return;

    const roll = Math.random();
    obstacles.push({
      x: cell.x,
      y: cell.y,
      type: roll > 0.86 ? "cup" : roll > 0.72 ? "red" : roll > 0.58 ? "yellow" : "defender"
    });
  }

  function spawnObstacleWave() {
    const targetMax = Math.min(MAX_OBSTACLES, 4 + Math.floor(level * 1.35));
    if (obstacles.length >= targetMax) return;

    const amount = Math.min(targetMax - obstacles.length, level >= 5 && Math.random() > 0.55 ? 2 : 1);
    for (let i = 0; i < amount; i += 1) {
      spawnObstacle();
    }
  }

  function updateGame() {
    direction = { ...nextDirection };
    prevSnake = cloneCells(snake);

    const head = snake[0];
    const newHead = {
      x: head.x + direction.x,
      y: head.y + direction.y
    };

    if (
      newHead.x < 0 ||
      newHead.x >= COLS ||
      newHead.y < 0 ||
      newHead.y >= ROWS
    ) {
      finishGame("MURO");
      return;
    }

    const willEat = cellsEqual(newHead, food);
    const bodyToCheck = willEat ? snake : snake.slice(0, -1);

    if (bodyToCheck.some((part) => cellsEqual(part, newHead))) {
      finishGame("PROPIA DEFENSA");
      return;
    }

    if (obstacles.some((obs) => cellsEqual(obs, newHead))) {
      finishGame("TARJETA");
      return;
    }

    snake.unshift(newHead);

    if (willEat) {
      eaten += 1;
      score += 10 + level * 2;

      level = Math.floor(score / 72) + 1;
      stepMs = Math.max(MIN_SPEED, START_SPEED - (level - 1) * 7);

      spawnFood();
      spawnObstacleWave();
    } else {
      snake.pop();
    }

    updateHud();
  }

  function endGame(reason) {
    status = "gameover";
    saveScore(score);
    renderRanking();
    updateHud();

    const message =
      reason === "TARJETA"
        ? "Has chocado con una tarjeta/obstáculo. Puntuación final: " + padScore(score)
        : reason === "MURO"
          ? "Te has ido contra la banda. Puntuación final: " + padScore(score)
          : "Choque contigo mismo. Puntuación final: " + padScore(score);

    showOverlay("TARJETA ROJA", message, "FINAL DEL PARTIDO");

    callbacks.forEach((cb) => {
      try {
        cb({ score, level, reason });
      } catch (error) {
        console.warn("SnakeGol onGameOver callback error:", error);
      }
    });
  }

  function finishGame(reason) {
    status = "gameover";
    pendingRecordScore = recordQualifies(score) ? score : 0;
    if (!pendingRecordScore) saveScore(score);
    renderRanking();
    updateHud();

    const message =
      reason === "TARJETA"
        ? "Has chocado con una tarjeta/obstaculo. Puntuacion final: " + padScore(score)
        : reason === "MURO"
          ? "Te has ido contra la banda. Puntuacion final: " + padScore(score)
          : "Choque contigo mismo. Puntuacion final: " + padScore(score);

    const recordForm = pendingRecordScore
      ? `
        <form class="record-form" id="snakeRecordForm">
          <label for="snakeRecordName">Entras en el TOP 10. Escribe tu nombre:</label>
          <div>
            <input id="snakeRecordName" maxlength="12" autocomplete="off" placeholder="TU NOMBRE" />
            <button type="submit">OK</button>
          </div>
        </form>`
      : "";

    showOverlay("TARJETA ROJA", message, "FINAL DEL PARTIDO", recordForm);

    if (pendingRecordScore) {
      const input = document.getElementById("snakeRecordName");
      const form = document.getElementById("snakeRecordForm");
      input?.focus();
      form?.addEventListener("submit", (event) => {
        event.preventDefault();
        const nextScores = saveScore(pendingRecordScore, input.value);
        if (nextScores.some((item) => item.score === pendingRecordScore)) {
          pendingRecordScore = 0;
          renderRanking();
          showOverlay("RECORD GUARDADO", "Pulsa una flecha, WASD o START para volver a jugar", "TOP 10");
        }
      });
    }

    callbacks.forEach((cb) => {
      try {
        cb(getRunStats(reason));
      } catch (error) {
        console.warn("SnakeGol onGameOver callback error:", error);
      }
    });
  }

  function resizeCanvas() {
    const rect = canvas.getBoundingClientRect();
    const width = Math.max(320, Math.floor(rect.width || 960));
    const height = Math.max(260, Math.floor(width / 1.6));

    view.dpr = Math.max(1, Math.min(2, window.devicePixelRatio || 1));
    view.w = width;
    view.h = height;

    canvas.width = Math.floor(width * view.dpr);
    canvas.height = Math.floor(height * view.dpr);
    canvas.style.height = `${height}px`;

    ctx.setTransform(view.dpr, 0, 0, view.dpr, 0, 0);

    view.cell = Math.floor(Math.min(view.w / COLS, view.h / ROWS));
    view.boardW = view.cell * COLS;
    view.boardH = view.cell * ROWS;
    view.ox = Math.floor((view.w - view.boardW) / 2);
    view.oy = Math.floor((view.h - view.boardH) / 2);

    draw(0);
  }

  function cellCenter(cell) {
    return {
      x: view.ox + cell.x * view.cell + view.cell / 2,
      y: view.oy + cell.y * view.cell + view.cell / 2
    };
  }

  function interpolatedCell(index, alpha) {
    const current = snake[index] || snake[snake.length - 1];
    const previous = prevSnake[index] || current;

    return {
      x: previous.x + (current.x - previous.x) * alpha,
      y: previous.y + (current.y - previous.y) * alpha
    };
  }

  function loop(time) {
    requestAnimationFrame(loop);

    if (status === "running") {
      const delta = Math.min(80, time - lastTime);
      lastTime = time;
      accumulator += delta;

      while (accumulator >= stepMs) {
        updateGame();
        accumulator -= stepMs;

        if (status !== "running") {
          accumulator = 0;
          break;
        }
      }
    } else {
      lastTime = time;
    }

    const alpha = status === "running" ? accumulator / stepMs : 0;
    draw(alpha);
  }

  function draw(alpha) {
    ctx.clearRect(0, 0, view.w, view.h);

    drawBackdrop();
    drawField();
    drawObstacles();
    drawFood();
    drawSnake(alpha);
    drawCollisionBorder();
    drawFx();
  }

  function drawBackdrop() {
    const gradient = ctx.createLinearGradient(0, 0, view.w, view.h);
    gradient.addColorStop(0, "#09051f");
    gradient.addColorStop(0.48, "#02050f");
    gradient.addColorStop(1, "#120622");

    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, view.w, view.h);

    ctx.save();
    ctx.globalAlpha = 0.12;
    ctx.fillStyle = "#27f7ff";
    ctx.font = `${Math.max(9, view.cell * 0.36)}px "Press Start 2P", monospace`;
    ctx.fillText("1X2", view.ox + 12, view.oy - 10);
    ctx.fillStyle = "#ff3df2";
    ctx.fillText("MUNDIAL", view.ox + view.boardW - 138, view.oy - 10);
    ctx.restore();
  }

  function drawField() {
    const { ox, oy, boardW, boardH, cell } = view;

    ctx.save();

    const turf = ctx.createLinearGradient(ox, oy, ox + boardW, oy + boardH);
    turf.addColorStop(0, "#09341f");
    turf.addColorStop(0.5, "#0c5d37");
    turf.addColorStop(1, "#082d1f");

    roundedRect(ox, oy, boardW, boardH, 18);
    ctx.fillStyle = turf;
    ctx.fill();

    for (let x = 0; x < COLS; x += 1) {
      ctx.fillStyle = x % 2 === 0 ? "rgba(255,255,255,0.028)" : "rgba(0,0,0,0.05)";
      ctx.fillRect(ox + x * cell, oy, cell, boardH);
    }

    ctx.strokeStyle = "rgba(248,251,255,0.42)";
    ctx.lineWidth = Math.max(1, cell * 0.055);

    roundedRect(ox + cell * 0.5, oy + cell * 0.5, boardW - cell, boardH - cell, 14);
    ctx.stroke();

    ctx.beginPath();
    ctx.moveTo(ox + boardW / 2, oy + cell * 0.5);
    ctx.lineTo(ox + boardW / 2, oy + boardH - cell * 0.5);
    ctx.stroke();

    ctx.beginPath();
    ctx.arc(ox + boardW / 2, oy + boardH / 2, cell * 2.25, 0, Math.PI * 2);
    ctx.stroke();

    ctx.beginPath();
    ctx.arc(ox + boardW / 2, oy + boardH / 2, Math.max(3, cell * 0.18), 0, Math.PI * 2);
    ctx.fillStyle = "rgba(248,251,255,0.72)";
    ctx.fill();

    ctx.strokeStyle = "rgba(248,251,255,0.48)";
    ctx.strokeRect(ox + cell * 0.5, oy + boardH * 0.28, cell * 3.6, boardH * 0.44);
    ctx.strokeRect(ox + boardW - cell * 4.1, oy + boardH * 0.28, cell * 3.6, boardH * 0.44);

    ctx.restore();
  }

  function drawGoals() {
    const { ox, oy, boardW, boardH, cell } = view;
    const goalH = cell * 4.5;
    const goalW = Math.max(8, cell * 0.45);
    const y = oy + boardH / 2 - goalH / 2;

    ctx.save();
    ctx.lineWidth = 2;
    ctx.strokeStyle = "rgba(39,247,255,0.88)";
    ctx.fillStyle = "rgba(39,247,255,0.1)";
    ctx.shadowColor = "#27f7ff";
    ctx.shadowBlur = 14;

    ctx.fillRect(ox - goalW, y, goalW, goalH);
    ctx.strokeRect(ox - goalW, y, goalW, goalH);

    ctx.fillRect(ox + boardW, y, goalW, goalH);
    ctx.strokeRect(ox + boardW, y, goalW, goalH);

    ctx.restore();
  }

  function drawFood() {
    if (!food) return;

    const c = cellCenter(food);
    const pulse = 1 + Math.sin(performance.now() / 145) * 0.07;
    drawSoccerBall(c.x, c.y, view.cell * 0.45 * pulse);
  }

  function drawSoccerBall(x, y, r) {
    ctx.save();
    ctx.shadowColor = "rgba(255,255,255,0.85)";
    ctx.shadowBlur = r * 0.55;
    ctx.font = `${r * 2.15}px "Segoe UI Emoji", "Apple Color Emoji", "Noto Color Emoji", sans-serif`;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText("⚽", x, y + r * 0.03);
    ctx.restore();
  }

  function drawClassicBall(x, y, r) {
    ctx.save();
    ctx.shadowColor = "#ffffff";
    ctx.shadowBlur = r * 0.65;

    ctx.beginPath();
    ctx.arc(x, y, r, 0, Math.PI * 2);
    const ball = ctx.createRadialGradient(x - r * 0.35, y - r * 0.45, r * 0.12, x, y, r);
    ball.addColorStop(0, "#ffffff");
    ball.addColorStop(0.55, "#f2f6ff");
    ball.addColorStop(1, "#bac5d5");
    ctx.fillStyle = ball;
    ctx.fill();

    ctx.lineWidth = Math.max(1.2, r * 0.08);
    ctx.strokeStyle = "#08101b";
    ctx.stroke();

    drawPentagon(x, y, r * 0.34, -Math.PI / 2, "#08101b");

    const points = 5;
    for (let i = 0; i < points; i += 1) {
      const a = -Math.PI / 2 + i * (Math.PI * 2 / points);
      const px = x + Math.cos(a) * r * 0.64;
      const py = y + Math.sin(a) * r * 0.64;

      drawPentagon(px, py, r * 0.16, a, "#08101b");

      ctx.beginPath();
      ctx.moveTo(x + Math.cos(a) * r * 0.32, y + Math.sin(a) * r * 0.32);
      ctx.lineTo(px - Math.cos(a) * r * 0.14, py - Math.sin(a) * r * 0.14);
      ctx.strokeStyle = "#08101b";
      ctx.lineWidth = Math.max(1, r * 0.055);
      ctx.stroke();
    }

    ctx.beginPath();
    ctx.arc(x - r * 0.28, y - r * 0.33, r * 0.18, 0, Math.PI * 2);
    ctx.fillStyle = "rgba(255,255,255,0.55)";
    ctx.fill();

    ctx.restore();
  }

  function drawPentagon(x, y, r, rot, color) {
    ctx.beginPath();

    for (let i = 0; i < 5; i += 1) {
      const a = rot + i * (Math.PI * 2 / 5);
      const px = x + Math.cos(a) * r;
      const py = y + Math.sin(a) * r;

      if (i === 0) ctx.moveTo(px, py);
      else ctx.lineTo(px, py);
    }

    ctx.closePath();
    ctx.fillStyle = color;
    ctx.fill();
  }

  function drawObstacles() {
    obstacles.forEach((obs) => {
      const c = cellCenter(obs);
      const s = view.cell * 0.68;

      if (obs.type === "cup") {
        drawCup(c.x, c.y, s);
      } else if (obs.type === "defender") {
        drawDefender(c.x, c.y, s);
      } else {
        drawCard(c.x, c.y, s, obs.type === "red" ? "#ff365f" : "#ffe75a");
      }
    });
  }

  function drawCard(x, y, s, color) {
    ctx.save();
    ctx.translate(x, y);
    ctx.rotate(-0.16);

    ctx.shadowColor = color;
    ctx.shadowBlur = 14;

    roundedRect(-s * 0.33, -s * 0.48, s * 0.66, s * 0.96, s * 0.08);
    ctx.fillStyle = color;
    ctx.fill();

    ctx.globalAlpha = 0.22;
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(-s * 0.22, -s * 0.35, s * 0.44, s * 0.12);

    ctx.restore();
  }

  function drawCup(x, y, s) {
    ctx.save();
    ctx.translate(x, y);

    ctx.shadowColor = "#ffe75a";
    ctx.shadowBlur = 16;
    ctx.fillStyle = "#ffe75a";
    ctx.strokeStyle = "#3a2500";
    ctx.lineWidth = Math.max(1, s * 0.06);

    ctx.beginPath();
    ctx.moveTo(-s * 0.28, -s * 0.34);
    ctx.lineTo(s * 0.28, -s * 0.34);
    ctx.lineTo(s * 0.2, s * 0.16);
    ctx.quadraticCurveTo(0, s * 0.28, -s * 0.2, s * 0.16);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();

    ctx.beginPath();
    ctx.arc(-s * 0.32, -s * 0.1, s * 0.2, Math.PI * 0.5, Math.PI * 1.55);
    ctx.arc(s * 0.32, -s * 0.1, s * 0.2, Math.PI * 1.45, Math.PI * 0.5);
    ctx.stroke();

    ctx.fillRect(-s * 0.06, s * 0.2, s * 0.12, s * 0.22);
    ctx.fillRect(-s * 0.26, s * 0.42, s * 0.52, s * 0.1);

    ctx.restore();
  }

  function drawDefender(x, y, s) {
    ctx.save();
    ctx.translate(x, y);

    const bodyW = s * 0.54;
    const bodyH = s * 0.62;
    const headR = s * 0.15;

    ctx.shadowColor = "#ff365f";
    ctx.shadowBlur = 10;

    ctx.beginPath();
    ctx.ellipse(0, s * 0.42, s * 0.3, s * 0.08, 0, 0, Math.PI * 2);
    ctx.fillStyle = "rgba(0,0,0,0.28)";
    ctx.fill();

    ctx.beginPath();
    ctx.arc(0, -s * 0.31, headR, 0, Math.PI * 2);
    ctx.fillStyle = "#ffd0a8";
    ctx.fill();

    roundedRect(-bodyW / 2, -s * 0.15, bodyW, bodyH, s * 0.12);
    ctx.fillStyle = "#ff365f";
    ctx.fill();
    ctx.lineWidth = Math.max(1, s * 0.04);
    ctx.strokeStyle = "#ffffff";
    ctx.stroke();

    ctx.fillStyle = "#ffffff";
    ctx.fillRect(-bodyW * 0.08, -s * 0.11, bodyW * 0.16, bodyH * 0.72);

    ctx.fillStyle = "#111827";
    ctx.fillRect(-bodyW * 0.38, s * 0.38, bodyW * 0.27, s * 0.09);
    ctx.fillRect(bodyW * 0.11, s * 0.38, bodyW * 0.27, s * 0.09);

    ctx.fillStyle = "#111827";
    ctx.beginPath();
    ctx.arc(-headR * 0.34, -s * 0.33, Math.max(1, s * 0.025), 0, Math.PI * 2);
    ctx.arc(headR * 0.34, -s * 0.33, Math.max(1, s * 0.025), 0, Math.PI * 2);
    ctx.fill();

    ctx.restore();
  }

  function drawSnake(alpha) {
    for (let i = snake.length - 1; i >= 0; i -= 1) {
      const cell = interpolatedCell(i, alpha);
      const x = view.ox + cell.x * view.cell + view.cell / 2;
      const y = view.oy + cell.y * view.cell + view.cell / 2;

      drawPlayerSegment(x, y, view.cell, i, i === 0);
    }
  }

  function drawPlayerSegment(x, y, cell, index, isHead) {
    const scale = isHead ? 1.05 : 0.95;
    const flagW = cell * 0.78 * scale;
    const flagH = cell * 0.58 * scale;

    const flags = [
      { type: "h", colors: ["#75aadb", "#ffffff", "#75aadb"] },
      { type: "h", colors: ["#aa151b", "#f1bf00", "#aa151b"] },
      { type: "v", colors: ["#0055a4", "#ffffff", "#ef4135"] },
      { type: "h", colors: ["#009b3a", "#f7d116", "#002776"] },
      { type: "v", colors: ["#006847", "#ffffff", "#ce1126"] },
      { type: "v", colors: ["#009246", "#ffffff", "#ce2b37"] },
      { type: "h", colors: ["#000000", "#dd0000", "#ffce00"] },
      { type: "h", colors: ["#ffffff", "#c8102e", "#ffffff"] }
    ];

    const flag = flags[index % flags.length];

    ctx.save();
    ctx.translate(x, y);

    ctx.shadowColor = isHead ? "#ffe75a" : "#27f7ff";
    ctx.shadowBlur = isHead ? 14 : 7;

    ctx.beginPath();
    ctx.ellipse(0, cell * 0.3, cell * 0.34, cell * 0.1, 0, 0, Math.PI * 2);
    ctx.fillStyle = "rgba(0,0,0,0.24)";
    ctx.fill();

    roundedRect(-flagW / 2, -flagH / 2, flagW, flagH, cell * 0.12);
    ctx.clip();

    if (flag.type === "v") {
      flag.colors.forEach((color, idx) => {
        ctx.fillStyle = color;
        ctx.fillRect(-flagW / 2 + idx * flagW / 3, -flagH / 2, flagW / 3 + 1, flagH);
      });
    } else {
      flag.colors.forEach((color, idx) => {
        ctx.fillStyle = color;
        ctx.fillRect(-flagW / 2, -flagH / 2 + idx * flagH / 3, flagW, flagH / 3 + 1);
      });
    }

    ctx.restore();

    ctx.save();
    ctx.translate(x, y);
    ctx.lineWidth = Math.max(1, cell * 0.045);
    ctx.strokeStyle = isHead ? "#ffe75a" : "rgba(255,255,255,0.5)";
    roundedRect(-flagW / 2, -flagH / 2, flagW, flagH, cell * 0.12);
    ctx.stroke();

    if (isHead) {
      ctx.fillStyle = "#05020c";
      ctx.beginPath();
      ctx.arc(-flagW * 0.16, -flagH * 0.07, Math.max(1.4, cell * 0.055), 0, Math.PI * 2);
      ctx.arc(flagW * 0.16, -flagH * 0.07, Math.max(1.4, cell * 0.055), 0, Math.PI * 2);
      ctx.fill();

      ctx.strokeStyle = "#05020c";
      ctx.lineWidth = Math.max(1, cell * 0.045);
      ctx.beginPath();
      ctx.arc(0, flagH * 0.05, flagW * 0.16, 0.12 * Math.PI, 0.88 * Math.PI);
      ctx.stroke();
    }

    ctx.restore();
  }

  function drawFx() {
    const t = performance.now() / 1000;

    ctx.save();
    ctx.globalAlpha = 0.13 + Math.sin(t * 2) * 0.035;
    ctx.strokeStyle = "#27f7ff";
    ctx.lineWidth = 2;
    roundedRect(view.ox - 2, view.oy - 2, view.boardW + 4, view.boardH + 4, 18);
    ctx.stroke();
    ctx.restore();
  }

  function drawCollisionBorder() {
    const { ox, oy, boardW, boardH, cell } = view;

    ctx.save();
    ctx.lineWidth = Math.max(3, cell * 0.16);
    ctx.strokeStyle = "#ffe75a";
    ctx.shadowColor = "#ffe75a";
    ctx.shadowBlur = 10;
    roundedRect(ox, oy, boardW, boardH, 18);
    ctx.stroke();

    ctx.setLineDash([Math.max(7, cell * 0.45), Math.max(5, cell * 0.28)]);
    ctx.lineWidth = Math.max(1, cell * 0.055);
    ctx.strokeStyle = "rgba(5,2,12,0.78)";
    ctx.shadowBlur = 0;
    roundedRect(ox + cell * 0.18, oy + cell * 0.18, boardW - cell * 0.36, boardH - cell * 0.36, 15);
    ctx.stroke();
    ctx.restore();
  }

  function roundedRect(x, y, w, h, r) {
    const radius = Math.min(r, w / 2, h / 2);

    ctx.beginPath();
    ctx.moveTo(x + radius, y);
    ctx.arcTo(x + w, y, x + w, y + h, radius);
    ctx.arcTo(x + w, y + h, x, y + h, radius);
    ctx.arcTo(x, y + h, x, y, radius);
    ctx.arcTo(x, y, x + w, y, radius);
    ctx.closePath();
  }

  function keyToDirection(key) {
    const k = key.toLowerCase();

    if (k === "arrowup" || k === "w") return dirs.up;
    if (k === "arrowdown" || k === "s") return dirs.down;
    if (k === "arrowleft" || k === "a") return dirs.left;
    if (k === "arrowright" || k === "d") return dirs.right;

    return null;
  }

  function isArcadeVisible() {
    return Boolean(canvas?.offsetParent) && document.body.classList.contains("newspaper-snake-active");
  }

  function bindEvents() {
    window.addEventListener("keydown", (event) => {
      if (event.target?.matches?.("input, textarea, select")) return;
      if (!isArcadeVisible()) return;

      const dir = keyToDirection(event.key);

      if (dir) {
        event.preventDefault();
        setDirection(dir);
        return;
      }

      if (event.key === " " || event.key.toLowerCase() === "p") {
        event.preventDefault();
        pause();
      }
    });

    startBtn.addEventListener("click", start);
    pauseBtn.addEventListener("click", pause);
    resetBtn.addEventListener("click", reset);

    document.querySelectorAll("[data-dir]").forEach((button) => {
      button.addEventListener("pointerdown", (event) => {
        event.preventDefault();
        setDirection(dirs[button.dataset.dir]);
      });
    });

    canvas.addEventListener("pointerdown", (event) => {
      if (event.pointerType === "mouse") return;

      swipeStart = {
        x: event.clientX,
        y: event.clientY
      };
    });

    canvas.addEventListener("pointerup", (event) => {
      if (!swipeStart || event.pointerType === "mouse") return;

      const dx = event.clientX - swipeStart.x;
      const dy = event.clientY - swipeStart.y;
      const absX = Math.abs(dx);
      const absY = Math.abs(dy);

      swipeStart = null;

      if (Math.max(absX, absY) < 24) return;

      if (absX > absY) {
        setDirection(dx > 0 ? dirs.right : dirs.left);
      } else {
        setDirection(dy > 0 ? dirs.down : dirs.up);
      }
    });

    const resizeObserver = new ResizeObserver(resizeCanvas);
    resizeObserver.observe(canvas.parentElement);

    window.addEventListener("orientationchange", () => {
      setTimeout(resizeCanvas, 150);
    });
  }

  window.SnakeGol = {
    start,
    reset,
    pause,
    getScore,
    getRunStats,
    onGameOver,

    // Preparadas para cambiar localStorage por API cuando lo conectes a Flask.
    saveScore,
    loadScores
  };

  bindEvents();
  resizeCanvas();
  reset();
  requestAnimationFrame(loop);
})();
