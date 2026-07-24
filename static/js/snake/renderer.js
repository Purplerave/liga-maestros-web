import { COLS, ROWS } from "./config.js";

const FLAGS = Object.freeze([
  { type: "h", colors: ["#75aadb", "#ffffff", "#75aadb"] },
  { type: "h", colors: ["#aa151b", "#f1bf00", "#aa151b"] },
  { type: "v", colors: ["#0055a4", "#ffffff", "#ef4135"] },
  { type: "h", colors: ["#009b3a", "#f7d116", "#002776"] },
  { type: "v", colors: ["#006847", "#ffffff", "#ce1126"] },
  { type: "v", colors: ["#009246", "#ffffff", "#ce2b37"] },
  { type: "h", colors: ["#000000", "#dd0000", "#ffce00"] },
  { type: "h", colors: ["#ffffff", "#c8102e", "#ffffff"] }
]);

export class SnakeRenderer {
  constructor(canvas, getSnapshot) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d");
    this.getSnapshot = getSnapshot;
    this.view = {
      w: 960,
      h: 600,
      dpr: 1,
      cell: 24,
      ox: 0,
      oy: 0,
      boardW: 720,
      boardH: 480
    };
  }

  resize() {
    const frame = this.canvas.parentElement;
    const rect = frame?.getBoundingClientRect?.() || this.canvas.getBoundingClientRect();
    const width = Math.max(320, Math.floor(rect.width || this.canvas.clientWidth || 960));
    const availableHeight = Math.max(260, Math.floor(window.innerHeight - (rect.top || 0) - 18));
    const height = Math.max(260, Math.min(Math.floor(width / (COLS / ROWS)), availableHeight));
    const view = this.view;

    view.dpr = Math.max(1, Math.min(2, window.devicePixelRatio || 1));
    view.w = width;
    view.h = height;
    this.canvas.width = Math.floor(width * view.dpr);
    this.canvas.height = Math.floor(height * view.dpr);
    this.canvas.style.height = `${height}px`;
    this.ctx.setTransform(view.dpr, 0, 0, view.dpr, 0, 0);

    view.cell = Math.floor(Math.min(view.w / COLS, view.h / ROWS));
    view.boardW = view.cell * COLS;
    view.boardH = view.cell * ROWS;
    view.ox = Math.floor((view.w - view.boardW) / 2);
    view.oy = Math.floor((view.h - view.boardH) / 2);
    this.draw(0);
  }

  draw(alpha = 0) {
    const state = this.getSnapshot();
    this.ctx.clearRect(0, 0, this.view.w, this.view.h);
    this.drawBackdrop();
    this.drawField();
    this.drawObstacles(state.obstacles);
    this.drawFood(state.food);
    this.drawSnake(state.snake, state.prevSnake, alpha);
    this.drawCollisionBorder();
    this.drawFx();
  }

  cellCenter(cell) {
    return {
      x: this.view.ox + cell.x * this.view.cell + this.view.cell / 2,
      y: this.view.oy + cell.y * this.view.cell + this.view.cell / 2
    };
  }

  drawBackdrop() {
    const { ctx, view } = this;
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

  drawField() {
    const { ctx, view } = this;
    const { ox, oy, boardW, boardH, cell } = view;
    ctx.save();

    const turf = ctx.createLinearGradient(ox, oy, ox + boardW, oy + boardH);
    turf.addColorStop(0, "#09341f");
    turf.addColorStop(0.5, "#0c5d37");
    turf.addColorStop(1, "#082d1f");
    this.roundedRect(ox, oy, boardW, boardH, 18);
    ctx.fillStyle = turf;
    ctx.fill();

    for (let x = 0; x < COLS; x += 1) {
      ctx.fillStyle = x % 2 === 0 ? "rgba(255,255,255,0.028)" : "rgba(0,0,0,0.05)";
      ctx.fillRect(ox + x * cell, oy, cell, boardH);
    }

    ctx.strokeStyle = "rgba(248,251,255,0.42)";
    ctx.lineWidth = Math.max(1, cell * 0.055);
    this.roundedRect(ox + cell * 0.5, oy + cell * 0.5, boardW - cell, boardH - cell, 14);
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

  drawFood(food) {
    if (!food) return;
    const center = this.cellCenter(food);
    const pulse = 1 + Math.sin(performance.now() / 145) * 0.07;
    this.drawBall(center.x, center.y, this.view.cell * 0.45 * pulse);
  }

  drawBall(x, y, radius) {
    const { ctx } = this;
    ctx.save();
    ctx.shadowColor = "#ffffff";
    ctx.shadowBlur = radius * 0.65;
    ctx.beginPath();
    ctx.arc(x, y, radius, 0, Math.PI * 2);
    const fill = ctx.createRadialGradient(
      x - radius * 0.35,
      y - radius * 0.45,
      radius * 0.12,
      x,
      y,
      radius
    );
    fill.addColorStop(0, "#ffffff");
    fill.addColorStop(0.55, "#f2f6ff");
    fill.addColorStop(1, "#bac5d5");
    ctx.fillStyle = fill;
    ctx.fill();
    ctx.lineWidth = Math.max(1.2, radius * 0.08);
    ctx.strokeStyle = "#08101b";
    ctx.stroke();

    this.drawPentagon(x, y, radius * 0.34, -Math.PI / 2, "#08101b");
    for (let index = 0; index < 5; index += 1) {
      const angle = -Math.PI / 2 + index * (Math.PI * 2 / 5);
      const px = x + Math.cos(angle) * radius * 0.64;
      const py = y + Math.sin(angle) * radius * 0.64;
      this.drawPentagon(px, py, radius * 0.16, angle, "#08101b");
      ctx.beginPath();
      ctx.moveTo(
        x + Math.cos(angle) * radius * 0.32,
        y + Math.sin(angle) * radius * 0.32
      );
      ctx.lineTo(
        px - Math.cos(angle) * radius * 0.14,
        py - Math.sin(angle) * radius * 0.14
      );
      ctx.lineWidth = Math.max(1, radius * 0.055);
      ctx.stroke();
    }

    ctx.beginPath();
    ctx.arc(x - radius * 0.28, y - radius * 0.33, radius * 0.18, 0, Math.PI * 2);
    ctx.fillStyle = "rgba(255,255,255,0.55)";
    ctx.fill();
    ctx.restore();
  }

  drawPentagon(x, y, radius, rotation, color) {
    const { ctx } = this;
    ctx.beginPath();
    for (let index = 0; index < 5; index += 1) {
      const angle = rotation + index * (Math.PI * 2 / 5);
      const px = x + Math.cos(angle) * radius;
      const py = y + Math.sin(angle) * radius;
      if (index === 0) ctx.moveTo(px, py);
      else ctx.lineTo(px, py);
    }
    ctx.closePath();
    ctx.fillStyle = color;
    ctx.fill();
  }

  drawObstacles(obstacles) {
    obstacles.forEach((obstacle) => {
      const center = this.cellCenter(obstacle);
      const size = this.view.cell * 0.68;
      if (obstacle.type === "cup") this.drawCup(center.x, center.y, size);
      else if (obstacle.type === "defender") this.drawDefender(center.x, center.y, size);
      else this.drawCard(center.x, center.y, size, obstacle.type === "red" ? "#ff365f" : "#ffe75a");
    });
  }

  drawCard(x, y, size, color) {
    const { ctx } = this;
    ctx.save();
    ctx.translate(x, y);
    ctx.rotate(-0.16);
    ctx.shadowColor = color;
    ctx.shadowBlur = 14;
    this.roundedRect(-size * 0.33, -size * 0.48, size * 0.66, size * 0.96, size * 0.08);
    ctx.fillStyle = color;
    ctx.fill();
    ctx.globalAlpha = 0.22;
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(-size * 0.22, -size * 0.35, size * 0.44, size * 0.12);
    ctx.restore();
  }

  drawCup(x, y, size) {
    const { ctx } = this;
    ctx.save();
    ctx.translate(x, y);
    ctx.shadowColor = "#ffe75a";
    ctx.shadowBlur = 16;
    ctx.fillStyle = "#ffe75a";
    ctx.strokeStyle = "#3a2500";
    ctx.lineWidth = Math.max(1, size * 0.06);
    ctx.beginPath();
    ctx.moveTo(-size * 0.28, -size * 0.34);
    ctx.lineTo(size * 0.28, -size * 0.34);
    ctx.lineTo(size * 0.2, size * 0.16);
    ctx.quadraticCurveTo(0, size * 0.28, -size * 0.2, size * 0.16);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();
    ctx.beginPath();
    ctx.arc(-size * 0.32, -size * 0.1, size * 0.2, Math.PI * 0.5, Math.PI * 1.55);
    ctx.arc(size * 0.32, -size * 0.1, size * 0.2, Math.PI * 1.45, Math.PI * 0.5);
    ctx.stroke();
    ctx.fillRect(-size * 0.06, size * 0.2, size * 0.12, size * 0.22);
    ctx.fillRect(-size * 0.26, size * 0.42, size * 0.52, size * 0.1);
    ctx.restore();
  }

  drawDefender(x, y, size) {
    const { ctx } = this;
    const bodyW = size * 0.54;
    const bodyH = size * 0.62;
    const headR = size * 0.15;
    ctx.save();
    ctx.translate(x, y);
    ctx.shadowColor = "#ff365f";
    ctx.shadowBlur = 10;
    ctx.beginPath();
    ctx.ellipse(0, size * 0.42, size * 0.3, size * 0.08, 0, 0, Math.PI * 2);
    ctx.fillStyle = "rgba(0,0,0,0.28)";
    ctx.fill();
    ctx.beginPath();
    ctx.arc(0, -size * 0.31, headR, 0, Math.PI * 2);
    ctx.fillStyle = "#ffd0a8";
    ctx.fill();
    this.roundedRect(-bodyW / 2, -size * 0.15, bodyW, bodyH, size * 0.12);
    ctx.fillStyle = "#ff365f";
    ctx.fill();
    ctx.lineWidth = Math.max(1, size * 0.04);
    ctx.strokeStyle = "#ffffff";
    ctx.stroke();
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(-bodyW * 0.08, -size * 0.11, bodyW * 0.16, bodyH * 0.72);
    ctx.fillStyle = "#111827";
    ctx.fillRect(-bodyW * 0.38, size * 0.38, bodyW * 0.27, size * 0.09);
    ctx.fillRect(bodyW * 0.11, size * 0.38, bodyW * 0.27, size * 0.09);
    ctx.beginPath();
    ctx.arc(-headR * 0.34, -size * 0.33, Math.max(1, size * 0.025), 0, Math.PI * 2);
    ctx.arc(headR * 0.34, -size * 0.33, Math.max(1, size * 0.025), 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
  }

  drawSnake(snake, previousSnake, alpha) {
    for (let index = snake.length - 1; index >= 0; index -= 1) {
      const current = snake[index] || snake[snake.length - 1];
      const previous = previousSnake[index] || current;
      const cell = {
        x: previous.x + (current.x - previous.x) * alpha,
        y: previous.y + (current.y - previous.y) * alpha
      };
      this.drawPlayerSegment(
        this.view.ox + cell.x * this.view.cell + this.view.cell / 2,
        this.view.oy + cell.y * this.view.cell + this.view.cell / 2,
        index,
        index === 0
      );
    }
  }

  drawPlayerSegment(x, y, index, isHead) {
    const { ctx, view } = this;
    const scale = isHead ? 1.05 : 0.95;
    const width = view.cell * 0.78 * scale;
    const height = view.cell * 0.58 * scale;
    const flag = FLAGS[index % FLAGS.length];

    ctx.save();
    ctx.translate(x, y);
    ctx.shadowColor = isHead ? "#ffe75a" : "#27f7ff";
    ctx.shadowBlur = isHead ? 14 : 7;
    ctx.beginPath();
    ctx.ellipse(0, view.cell * 0.3, view.cell * 0.34, view.cell * 0.1, 0, 0, Math.PI * 2);
    ctx.fillStyle = "rgba(0,0,0,0.24)";
    ctx.fill();
    this.roundedRect(-width / 2, -height / 2, width, height, view.cell * 0.12);
    ctx.clip();
    flag.colors.forEach((color, stripe) => {
      ctx.fillStyle = color;
      if (flag.type === "v") {
        ctx.fillRect(-width / 2 + stripe * width / 3, -height / 2, width / 3 + 1, height);
      } else {
        ctx.fillRect(-width / 2, -height / 2 + stripe * height / 3, width, height / 3 + 1);
      }
    });
    ctx.restore();

    ctx.save();
    ctx.translate(x, y);
    ctx.lineWidth = Math.max(1, view.cell * 0.045);
    ctx.strokeStyle = isHead ? "#ffe75a" : "rgba(255,255,255,0.5)";
    this.roundedRect(-width / 2, -height / 2, width, height, view.cell * 0.12);
    ctx.stroke();
    if (isHead) {
      ctx.fillStyle = "#05020c";
      ctx.beginPath();
      ctx.arc(-width * 0.16, -height * 0.07, Math.max(1.4, view.cell * 0.055), 0, Math.PI * 2);
      ctx.arc(width * 0.16, -height * 0.07, Math.max(1.4, view.cell * 0.055), 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = "#05020c";
      ctx.beginPath();
      ctx.arc(0, height * 0.05, width * 0.16, 0.12 * Math.PI, 0.88 * Math.PI);
      ctx.stroke();
    }
    ctx.restore();
  }

  drawCollisionBorder() {
    const { ctx, view } = this;
    const { ox, oy, boardW, boardH, cell } = view;
    ctx.save();
    ctx.lineWidth = Math.max(3, cell * 0.16);
    ctx.strokeStyle = "#ffe75a";
    ctx.shadowColor = "#ffe75a";
    ctx.shadowBlur = 10;
    this.roundedRect(ox, oy, boardW, boardH, 18);
    ctx.stroke();
    ctx.setLineDash([Math.max(7, cell * 0.45), Math.max(5, cell * 0.28)]);
    ctx.lineWidth = Math.max(1, cell * 0.055);
    ctx.strokeStyle = "rgba(5,2,12,0.78)";
    ctx.shadowBlur = 0;
    this.roundedRect(ox + cell * 0.18, oy + cell * 0.18, boardW - cell * 0.36, boardH - cell * 0.36, 15);
    ctx.stroke();
    ctx.restore();
  }

  drawFx() {
    const { ctx, view } = this;
    ctx.save();
    ctx.globalAlpha = 0.13 + Math.sin(performance.now() / 500) * 0.035;
    ctx.strokeStyle = "#27f7ff";
    ctx.lineWidth = 2;
    this.roundedRect(view.ox - 2, view.oy - 2, view.boardW + 4, view.boardH + 4, 18);
    ctx.stroke();
    ctx.restore();
  }

  roundedRect(x, y, width, height, radius) {
    const ctx = this.ctx;
    const safeRadius = Math.min(radius, width / 2, height / 2);
    ctx.beginPath();
    ctx.moveTo(x + safeRadius, y);
    ctx.arcTo(x + width, y, x + width, y + height, safeRadius);
    ctx.arcTo(x + width, y + height, x, y + height, safeRadius);
    ctx.arcTo(x, y + height, x, y, safeRadius);
    ctx.arcTo(x, y, x + width, y, safeRadius);
    ctx.closePath();
  }
}
