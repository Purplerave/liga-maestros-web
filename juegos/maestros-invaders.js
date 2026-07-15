"use strict";

const canvas = document.getElementById("game");
const ctx = canvas.getContext("2d");
const ui = {
  score: document.getElementById("score"), wave: document.getElementById("wave"),
  lives: document.getElementById("lives"), best: document.getElementById("best"),
  overlay: document.getElementById("overlay"), kicker: document.getElementById("overlayKicker"),
  title: document.getElementById("overlayTitle"), text: document.getElementById("overlayText"),
  button: document.getElementById("primaryButton"), nameRow: document.getElementById("nameRow"),
  name: document.getElementById("playerName"), ranking: document.getElementById("ranking")
};

const SCORE_KEY = "maestrosInvaders.topScores";
const PLAYER_KEY = "maestrosInvaders.playerName";
const W = canvas.width;
const H = canvas.height;
const TEAM_NAMES = [
  "BARCELONA", "REAL_MADRID", "VILLARREAL", "VALENCIA", "OSASUNA", "GETAFE", "GIRONA",
  "ESPANYOL", "MALLORCA", "RAYO", "ALAVES", "LEVANTE", "ELCHE", "LAS_PALMAS",
  "ALMERIA", "MALAGA", "ZARAGOZA", "BURGOS", "EIBAR", "CORDOBA", "HUESCA",
  "CADIZ", "GRANADA", "VALLADOLID", "OVIEDO", "ALBACETE", "CEUTA"
];
const TEAM_LOGOS = TEAM_NAMES.map(name => {
  const image = new Image();
  image.src = `/static/img/team_logos/${name}.png`;
  return { name, image };
});

const keys = { left: false, right: false, fire: false };
let state = "ready";
let score = 0;
let wave = 1;
let lives = 3;
let best = 0;
let lastTime = 0;
let fireCooldown = 0;
let enemyFireCooldown = 1;
let diveCooldown = 3;
let shake = 0;
let flash = 0;
let formation = { direction: 1, speed: 35, drop: 20 };
let player;
let enemies = [];
let shots = [];
let enemyShots = [];
let particles = [];
let powerups = [];
let stars = [];
let audioContext = null;

const FORMATION_NAMES = ["Bloque clásico", "Cuña ofensiva", "Diamante", "Doble ala"];

function formationPoints(style) {
  const points = [];
  if (style === 0) {
    for (let row = 0; row < 4; row++) for (let col = 0; col < 7; col++) points.push({ x: 132 + col * 102, y: 72 + row * 66, row, col });
  } else if (style === 1) {
    for (let row = 0; row < 3; row++) for (let col = 0; col < 8; col++) points.push({ x: 92 + col * 105, y: 62 + row * 62 + Math.abs(col - 3.5) * 22, row, col });
  } else if (style === 2) {
    [3, 5, 7, 5, 3].forEach((count, row) => {
      const start = W / 2 - ((count - 1) * 92 + 42) / 2;
      for (let col = 0; col < count; col++) points.push({ x: start + col * 92, y: 55 + row * 57, row, col });
    });
  } else {
    for (let row = 0; row < 4; row++) {
      for (let col = 0; col < 3; col++) {
        points.push({ x: 105 + col * 86 + row * 12, y: 65 + row * 62, row, col });
        points.push({ x: W - 147 - col * 86 - row * 12, y: 65 + row * 62, row, col: col + 4 });
      }
    }
  }
  return points;
}

function resetPlayer() {
  player = { x: W / 2, y: H - 52, width: 48, height: 28, speed: 330, shield: 0, triple: 0, invulnerable: 0 };
}

function makeStars() {
  stars = Array.from({ length: 95 }, () => ({ x: Math.random() * W, y: Math.random() * H, z: .25 + Math.random() * 1.4 }));
}

function buildWave() {
  enemies = [];
  shots = [];
  enemyShots = [];
  powerups = [];
  const bossWave = wave % 4 === 0;
  if (bossWave) {
    enemies.push({ x: W / 2 - 70, y: 92, width: 140, height: 76, hp: 18 + wave * 2, maxHp: 18 + wave * 2, boss: true, bossKind: (wave / 4 - 1) % 3, team: null, phase: 0 });
  } else {
    const style = (wave - 1) % FORMATION_NAMES.length;
    formationPoints(style).forEach((point, index) => {
      const team = TEAM_LOGOS[(index + (wave - 1) * 5) % TEAM_LOGOS.length];
      const role = point.row === 0 && wave >= 3 ? "keeper" : point.row < 2 ? "elite" : "scout";
      const hp = role === "keeper" ? 3 : role === "elite" ? 2 : 1;
      enemies.push({
        x: point.x, y: point.y, width: role === "keeper" ? 46 : 42, height: role === "keeper" ? 46 : 42,
        hp, maxHp: hp, role, boss: false, team, phase: Math.random() * Math.PI * 2,
        diving: false, diveT: 0
      });
    });
  }
  formation = { direction: 1, speed: 32 + wave * 6, drop: 18, style: bossWave ? -1 : (wave - 1) % FORMATION_NAMES.length };
  enemyFireCooldown = Math.max(.25, 1.25 - wave * .06);
  diveCooldown = Math.max(3.2, 6.8 - wave * .16);
  resetPlayer();
  syncHud();
}

function startGame() {
  score = 0; wave = 1; lives = 3; particles = []; flash = 0; shake = 0;
  buildWave();
  state = "playing";
  ui.overlay.hidden = true;
  lastTime = performance.now();
  beep(220, .06, "square", .035);
}

function nextWave() {
  score += 500 * wave;
  wave++;
  keys.left = keys.right = keys.fire = false;
  buildWave();
  state = "playing";
  ui.overlay.hidden = true;
}

function completeWave() {
  if (state !== "playing") return;
  state = "between";
  keys.left = keys.right = keys.fire = false;
  enemyShots = [];
  powerups = [];
  showOverlay(
    "Oleada superada",
    `Has limpiado la oleada ${wave}. Bonificación: ${500 * wave} puntos.`,
    "Siguiente oleada",
    false,
    nextWave,
    "Sector seguro"
  );
}

function update(dt) {
  stars.forEach(star => { star.y += (16 + wave * 1.5) * star.z * dt; if (star.y > H) { star.y = 0; star.x = Math.random() * W; } });
  particles.forEach(p => { p.x += p.vx * dt; p.y += p.vy * dt; p.life -= dt; p.vy += 34 * dt; });
  particles = particles.filter(p => p.life > 0);
  if (state !== "playing") return;

  player.invulnerable = Math.max(0, player.invulnerable - dt);
  player.shield = Math.max(0, player.shield - dt);
  player.triple = Math.max(0, player.triple - dt);
  if (keys.left) player.x -= player.speed * dt;
  if (keys.right) player.x += player.speed * dt;
  player.x = Math.max(26, Math.min(W - 26, player.x));

  fireCooldown -= dt;
  if (keys.fire && fireCooldown <= 0) {
    fireCooldown = player.triple > 0 ? .13 : .22;
    firePlayerShot();
  }

  shots.forEach(s => { s.y -= s.speed * dt; s.x += s.vx * dt; });
  enemyShots.forEach(s => { s.y += s.speed * dt; s.x += s.vx * dt; });
  shots = shots.filter(s => s.y > -20);
  enemyShots = enemyShots.filter(s => s.y < H + 30);

  updateEnemies(dt);
  updatePowerups(dt);
  handleCollisions();
  shake = Math.max(0, shake - dt * 18);
  flash = Math.max(0, flash - dt * 2.5);
}

function updateEnemies(dt) {
  if (!enemies.length) {
    completeWave();
    return;
  }
  const boss = enemies.find(e => e.boss);
  if (boss) {
    boss.phase += dt;
    boss.x = W / 2 - boss.width / 2 + Math.sin(boss.phase * .85) * 280;
    enemyFireCooldown -= dt;
    if (enemyFireCooldown <= 0) {
      enemyFireCooldown = Math.max(.22, .65 - wave * .025);
      const spreads = boss.bossKind === 0 ? [-.55, 0, .55] : boss.bossKind === 1 ? [-.9, -.45, 0, .45, .9] : [-.7, -.2, .2, .7];
      spreads.forEach(vx => enemyShots.push({ x: boss.x + boss.width / 2, y: boss.y + boss.height, width: 8, height: 18, speed: 220 + wave * 8, vx: vx * 105, type: boss.bossKind === 2 ? "yellow" : "red" }));
    }
    return;
  }

  const formationEnemies = enemies.filter(e => !e.diving);
  const divingEnemies = enemies.filter(e => e.diving);
  let minX = Infinity;
  let maxX = -Infinity;
  formationEnemies.forEach(e => { minX = Math.min(minX, e.x); maxX = Math.max(maxX, e.x + e.width); });
  if ((formation.direction > 0 && maxX >= W - 26) || (formation.direction < 0 && minX <= 26)) {
    formation.direction *= -1;
    formationEnemies.forEach(e => e.y += formation.drop);
    divingEnemies.forEach(e => e.diveOriginY += formation.drop);
    formation.speed += 4;
  }
  const formationDx = formation.direction * formation.speed * dt;
  formationEnemies.forEach(e => { e.x += formationDx; e.phase += dt; });
  divingEnemies.forEach(e => { e.diveOriginX += formationDx; });

  divingEnemies.forEach(e => {
    e.diveWarning = Math.max(0, e.diveWarning - dt);
    e.phase += dt * 4;
    if (e.diveWarning > 0) {
      e.x = e.diveOriginX;
      e.y = e.diveOriginY;
      return;
    }
    e.diveT += dt;
    const progress = Math.min(1, e.diveT / 3.2);
    e.x = e.diveOriginX + Math.sin(Math.PI * progress) * (e.diveTargetX - e.diveOriginX) + Math.sin(Math.PI * 2 * progress) * 75;
    e.y = e.diveOriginY + Math.sin(Math.PI * progress) * 380;
    if (progress >= 1) { e.diving = false; e.x = e.diveOriginX; e.y = e.diveOriginY; }
  });

  diveCooldown -= dt;
  if (wave >= 2 && diveCooldown <= 0 && formationEnemies.length > 3) {
    const divers = formationEnemies.filter(e => e.role !== "keeper" && e.y < 300);
    const diver = divers[Math.floor(Math.random() * divers.length)];
    if (diver) {
      const missOffset = Math.random() < .5 ? -105 : 105;
      diver.diving = true; diver.diveWarning = .8; diver.diveT = 0; diver.diveOriginX = diver.x; diver.diveOriginY = diver.y;
      diver.diveTargetX = Math.max(70, Math.min(W - 70, player.x + missOffset));
      diveCooldown = Math.max(3.1, 6.6 - wave * .15) * (.9 + Math.random() * .35);
      beep(360, .08, "sawtooth", .02);
    }
  }

  enemyFireCooldown -= dt;
  if (enemyFireCooldown <= 0) {
    enemyFireCooldown = Math.max(.22, 1.2 - wave * .055) * (.75 + Math.random() * .55);
    const candidates = formationEnemies.filter(e => !formationEnemies.some(other => Math.abs(other.x - e.x) < 22 && other.y > e.y));
    const shooter = candidates[Math.floor(Math.random() * candidates.length)] || enemies[0];
    enemyShots.push({ x: shooter.x + shooter.width / 2, y: shooter.y + shooter.height, width: 7, height: 16, speed: 190 + wave * 8, vx: 0, type: Math.random() < .28 ? "yellow" : "red" });
  }
  if (formationEnemies.some(e => e.y + e.height > player.y - 8)) loseLife();
}

function updatePowerups(dt) {
  powerups.forEach(p => { p.y += 125 * dt; p.spin += dt * 4; });
  powerups = powerups.filter(p => p.y < H + 30);
}

function firePlayerShot() {
  const angles = player.triple > 0 ? [-.17, 0, .17] : [0];
  angles.forEach(angle => shots.push({ x: player.x, y: player.y - 20, width: 6, height: 14, speed: 520, vx: angle * 240 }));
  beep(640, .035, "square", .018);
}

function handleCollisions() {
  for (let si = shots.length - 1; si >= 0; si--) {
    const shot = shots[si];
    const ei = enemies.findIndex(enemy => hit(shot, enemy));
    if (ei < 0) continue;
    const enemy = enemies[ei];
    shots.splice(si, 1);
    enemy.hp--;
    burst(shot.x, shot.y, enemy.boss ? "#ffc83d" : "#32d5ff", enemy.boss ? 8 : 4);
    beep(enemy.hp <= 0 ? 125 : 180, .04, "sawtooth", .025);
    if (enemy.hp <= 0) destroyEnemy(ei, enemy);
  }

  for (let i = enemyShots.length - 1; i >= 0; i--) {
    if (hit(enemyShots[i], { x: player.x - player.width / 2, y: player.y - player.height / 2, width: player.width, height: player.height })) {
      enemyShots.splice(i, 1);
      if (player.shield > 0) { player.shield = 0; burst(player.x, player.y, "#38e48f", 12); beep(310, .12, "triangle", .04); }
      else loseLife();
    }
  }

  if (player.invulnerable <= 0 && enemies.some(enemy => enemy.diving && enemy.diveWarning <= 0 && enemy.diveT > .45 && hit({ x: player.x, y: player.y, width: player.width * .72, height: player.height * .72 }, enemy))) loseLife();

  for (let i = powerups.length - 1; i >= 0; i--) {
    if (hit(powerups[i], { x: player.x - player.width / 2, y: player.y - player.height / 2, width: player.width, height: player.height })) {
      const power = powerups.splice(i, 1)[0];
      if (power.type === "shield") player.shield = 9;
      else player.triple = 9;
      score += 150;
      beep(880, .16, "sine", .045);
    }
  }
  syncHud();
}

function destroyEnemy(index, enemy) {
  enemies.splice(index, 1);
  score += enemy.boss ? 2500 : enemy.diving ? 260 : enemy.maxHp === 3 ? 260 : enemy.maxHp === 2 ? 180 : 100;
  burst(enemy.x + enemy.width / 2, enemy.y + enemy.height / 2, enemy.boss ? "#ffc83d" : "#ff5570", enemy.boss ? 34 : 14);
  shake = enemy.boss ? 9 : 3;
  flash = enemy.boss ? .7 : .18;
  if (!enemy.boss && Math.random() < .085) powerups.push({ x: enemy.x + enemy.width / 2, y: enemy.y, width: 25, height: 25, spin: 0, type: Math.random() < .5 ? "shield" : "triple" });
  if (!enemies.length) completeWave();
}

function loseLife() {
  if (player.invulnerable > 0 || state !== "playing") return;
  lives--;
  player.invulnerable = 2;
  player.shield = 0;
  enemyShots = [];
  player.x = W / 2;
  burst(player.x, player.y, "#ff5570", 28);
  shake = 12; flash = .65;
  beep(75, .35, "sawtooth", .055);
  syncHud();
  if (lives <= 0) finishGame();
}

function finishGame() {
  state = "over";
  const qualifies = qualifiesForTopTen(score);
  if (qualifies) {
    ui.name.value = localStorage.getItem(PLAYER_KEY) || "";
    showOverlay("¡Top 10!", `Has conseguido ${score} puntos. Escribe tu nombre para guardar la marca.`, "Guardar marca", true, saveQualifiedScore, "Nueva marca");
    setTimeout(() => ui.name.focus(), 0);
  } else {
    showOverlay("Fin de la temporada", `Has conseguido ${score} puntos. No has entrado en el Top 10.`, "Volver a jugar", false, startGame, "Clasificación cerrada");
  }
}

function saveQualifiedScore() {
  const name = cleanName(ui.name.value);
  if (!name) {
    ui.text.textContent = "Escribe un nombre para guardar tu marca en el Top 10.";
    ui.name.focus();
    return;
  }
  localStorage.setItem(PLAYER_KEY, name);
  const scores = loadScores();
  scores.push({ name, score, wave, date: new Date().toISOString() });
  scores.sort((a, b) => b.score - a.score || a.date.localeCompare(b.date));
  localStorage.setItem(SCORE_KEY, JSON.stringify(scores.slice(0, 10)));
  renderRanking();
  syncHud();
  showOverlay("Marca guardada", `${name}: ${score} puntos, oleada ${wave}.`, "Volver a jugar", false, startGame, "Salón de la fama");
}

function qualifiesForTopTen(value) {
  if (value <= 0) return false;
  const scores = loadScores();
  return scores.length < 10 || value > Number(scores[scores.length - 1]?.score || 0);
}

function loadScores() {
  try {
    const parsed = JSON.parse(localStorage.getItem(SCORE_KEY) || "[]");
    return Array.isArray(parsed) ? parsed.filter(item => Number.isFinite(Number(item.score))).sort((a, b) => Number(b.score) - Number(a.score)).slice(0, 10) : [];
  } catch (_) { return []; }
}

function renderRanking() {
  const scores = loadScores();
  best = scores.length ? Number(scores[0].score) : 0;
  ui.ranking.innerHTML = scores.length
    ? scores.map((entry, index) => `<li><span>${index + 1}</span><b>${escapeHtml(entry.name || "Jugador")}</b><strong>${Number(entry.score)}</strong></li>`).join("")
    : `<li class="ranking-empty"><span>-</span><b>Sin marcas</b><strong>0</strong></li>`;
}

function showOverlay(title, text, button, askName, action, kicker) {
  ui.title.textContent = title;
  ui.text.textContent = text;
  ui.button.textContent = button;
  ui.kicker.textContent = kicker;
  ui.nameRow.hidden = !askName;
  ui.overlay.hidden = false;
  ui.button.onclick = action;
}

function syncHud() {
  const scores = loadScores();
  best = Math.max(score, scores.length ? Number(scores[0].score) : 0);
  ui.score.textContent = String(score).padStart(6, "0");
  ui.wave.textContent = String(wave).padStart(2, "0");
  ui.lives.textContent = String(Math.max(0, lives));
  ui.best.textContent = String(best).padStart(6, "0");
}

function draw() {
  ctx.save();
  if (shake > 0) ctx.translate((Math.random() - .5) * shake, (Math.random() - .5) * shake);
  ctx.fillStyle = "#02060d";
  ctx.fillRect(0, 0, W, H);
  drawBackground();
  drawEnemies();
  drawShots();
  drawPowerups();
  drawPlayer();
  drawParticles();
  if (flash > 0) { ctx.fillStyle = `rgba(255,255,255,${Math.min(.22, flash * .2)})`; ctx.fillRect(0, 0, W, H); }
  if (state === "paused") { ctx.fillStyle = "rgba(2,6,13,.64)"; ctx.fillRect(0,0,W,H); ctx.fillStyle = "#f5f7fb"; ctx.font = "700 30px system-ui"; ctx.textAlign = "center"; ctx.fillText("PAUSA", W / 2, H / 2); }
  ctx.restore();
}

function drawBackground() {
  stars.forEach(star => { ctx.fillStyle = `rgba(103,228,255,${.18 + star.z * .35})`; ctx.fillRect(star.x, star.y, star.z > 1 ? 2 : 1, star.z > 1 ? 2 : 1); });
  const gradient = ctx.createLinearGradient(0, H * .55, 0, H);
  gradient.addColorStop(0, "rgba(10,48,67,0)");
  gradient.addColorStop(1, "rgba(10,48,67,.22)");
  ctx.fillStyle = gradient; ctx.fillRect(0, 0, W, H);
  ctx.strokeStyle = "rgba(50,213,255,.055)";
  for (let y = 320; y < H; y += 28) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke(); }
  if (formation.style >= 0) {
    ctx.fillStyle = "rgba(142,162,184,.62)";
    ctx.font = "700 12px system-ui";
    ctx.textAlign = "left";
    ctx.fillText(`${FORMATION_NAMES[formation.style]} · Oleada ${wave}`, 18, 24);
  }
}

function drawEnemies() {
  enemies.forEach(enemy => {
    if (enemy.boss) { drawBoss(enemy); return; }
    const cx = enemy.x + enemy.width / 2;
    const cy = enemy.y + enemy.height / 2 + Math.sin(enemy.phase * 2) * 2;
    ctx.save();
    ctx.translate(cx, cy);
    if (enemy.diveWarning > 0) {
      ctx.strokeStyle = `rgba(255,85,112,${.35 + Math.sin(enemy.phase * 9) * .3})`;
      ctx.lineWidth = 3;
      ctx.beginPath(); ctx.arc(0, 0, 32, 0, Math.PI * 2); ctx.stroke();
    }
    ctx.fillStyle = enemy.hp < enemy.maxHp ? "rgba(255,85,112,.22)" : "rgba(18,36,54,.9)";
    ctx.beginPath(); ctx.arc(0, 0, 25, 0, Math.PI * 2); ctx.fill();
    ctx.strokeStyle = enemy.role === "keeper" ? "#ff5570" : enemy.maxHp > 1 ? "#ffc83d" : "#31506e"; ctx.lineWidth = enemy.diving ? 4 : 2; ctx.stroke();
    if (enemy.team.image.complete && enemy.team.image.naturalWidth) ctx.drawImage(enemy.team.image, -18, -18, 36, 36);
    else { ctx.fillStyle = "#f5f7fb"; ctx.font = "700 10px system-ui"; ctx.textAlign = "center"; ctx.textBaseline = "middle"; ctx.fillText(enemy.team.name.slice(0, 2), 0, 0); }
    ctx.restore();
  });
}

function drawBoss(enemy) {
  const cx = enemy.x + enemy.width / 2;
  const cy = enemy.y + enemy.height / 2;
  ctx.save(); ctx.translate(cx, cy);
  ctx.shadowBlur = 22; ctx.shadowColor = "#ffc83d";
  ctx.fillStyle = "#ffc83d";
  ctx.beginPath(); ctx.moveTo(-50,-26); ctx.lineTo(-30,22); ctx.lineTo(30,22); ctx.lineTo(50,-26); ctx.lineTo(18,-8); ctx.lineTo(0,-34); ctx.lineTo(-18,-8); ctx.closePath(); ctx.fill();
  ctx.fillRect(-36, 24, 72, 10);
  ctx.shadowBlur = 0;
  ctx.fillStyle = "#07111d"; ctx.font = "900 20px system-ui"; ctx.textAlign = "center"; ctx.fillText("LM", 0, 12);
  ctx.restore();
  ctx.fillStyle = "#17283c"; ctx.fillRect(enemy.x, enemy.y - 14, enemy.width, 6);
  ctx.fillStyle = "#ff5570"; ctx.fillRect(enemy.x, enemy.y - 14, enemy.width * enemy.hp / enemy.maxHp, 6);
}

function drawPlayer() {
  if (!player || (player.invulnerable > 0 && Math.floor(player.invulnerable * 12) % 2)) return;
  ctx.save(); ctx.translate(player.x, player.y);
  if (player.shield > 0) { ctx.strokeStyle = "#38e48f"; ctx.lineWidth = 3; ctx.beginPath(); ctx.arc(0,0,34,0,Math.PI*2); ctx.stroke(); }
  ctx.fillStyle = "#32d5ff"; ctx.beginPath(); ctx.moveTo(0,-20); ctx.lineTo(24,14); ctx.lineTo(8,10); ctx.lineTo(0,20); ctx.lineTo(-8,10); ctx.lineTo(-24,14); ctx.closePath(); ctx.fill();
  ctx.fillStyle = "#07111d"; ctx.fillRect(-8,-2,16,13);
  ctx.fillStyle = "#ffc83d"; ctx.font = "900 9px system-ui"; ctx.textAlign = "center"; ctx.fillText("LM", 0, 8);
  ctx.fillStyle = "#ff5570"; ctx.fillRect(-12,17,7,7); ctx.fillRect(5,17,7,7);
  ctx.restore();
}

function drawShots() {
  ctx.fillStyle = "#f5f7fb";
  shots.forEach(s => { ctx.fillRect(s.x - s.width / 2, s.y, s.width, s.height); ctx.fillStyle = "#32d5ff"; ctx.fillRect(s.x - 1, s.y - 5, 2, 5); });
  enemyShots.forEach(s => { ctx.fillStyle = s.type === "yellow" ? "#ffc83d" : "#ff5570"; ctx.fillRect(s.x - s.width / 2, s.y, s.width, s.height); ctx.fillStyle = "#07111d"; ctx.fillRect(s.x - 2, s.y + 4, 4, 3); });
}

function drawPowerups() {
  powerups.forEach(p => { ctx.save(); ctx.translate(p.x, p.y); ctx.rotate(p.spin); ctx.fillStyle = p.type === "shield" ? "#38e48f" : "#ffc83d"; ctx.fillRect(-12,-12,24,24); ctx.fillStyle="#07111d"; ctx.font="900 12px system-ui"; ctx.textAlign="center"; ctx.textBaseline="middle"; ctx.fillText(p.type === "shield" ? "S" : "3",0,1); ctx.restore(); });
}

function burst(x, y, color, amount) {
  for (let i = 0; i < amount; i++) particles.push({ x, y, vx: (Math.random() - .5) * 220, vy: (Math.random() - .5) * 220, life: .35 + Math.random() * .55, color, size: 2 + Math.random() * 4 });
}

function drawParticles() {
  particles.forEach(p => { ctx.globalAlpha = Math.max(0, p.life * 1.8); ctx.fillStyle = p.color; ctx.fillRect(p.x, p.y, p.size, p.size); });
  ctx.globalAlpha = 1;
}

function hit(a, b) {
  const ax = a.x - (a.width || 0) / 2;
  return ax < b.x + b.width && ax + (a.width || 0) > b.x && a.y < b.y + b.height && a.y + (a.height || 0) > b.y;
}

function cleanName(value) { return String(value || "").trim().replace(/[^a-zA-Z0-9ÁÉÍÓÚÜÑáéíóúüñ _-]/g, "").slice(0, 12); }
function escapeHtml(value) { return String(value).replace(/[&<>'"]/g, char => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[char])); }

function beep(frequency, duration, type, volume) {
  try {
    audioContext ||= new (window.AudioContext || window.webkitAudioContext)();
    const oscillator = audioContext.createOscillator();
    const gain = audioContext.createGain();
    oscillator.type = type; oscillator.frequency.value = frequency;
    gain.gain.setValueAtTime(volume, audioContext.currentTime);
    gain.gain.exponentialRampToValueAtTime(.0001, audioContext.currentTime + duration);
    oscillator.connect(gain); gain.connect(audioContext.destination);
    oscillator.start(); oscillator.stop(audioContext.currentTime + duration);
  } catch (_) { /* Audio is optional. */ }
}

function togglePause() {
  if (state === "playing") state = "paused";
  else if (state === "paused") { state = "playing"; lastTime = performance.now(); }
}

function movePlayerToPointer(event) {
  if (state !== "playing" || !player) return;
  const rect = canvas.getBoundingClientRect();
  const scale = Math.min(rect.width / W, rect.height / H);
  const renderedWidth = W * scale;
  const offsetX = (rect.width - renderedWidth) / 2;
  const canvasX = (event.clientX - rect.left - offsetX) / scale;
  player.x = Math.max(26, Math.min(W - 26, canvasX));
}

function frame(time) {
  const dt = Math.min(.034, Math.max(0, (time - lastTime) / 1000 || 0));
  lastTime = time;
  update(dt);
  draw();
  requestAnimationFrame(frame);
}

window.addEventListener("keydown", event => {
  if (["ArrowLeft", "ArrowRight", "Space"].includes(event.code)) event.preventDefault();
  if (event.code === "ArrowLeft" || event.code === "KeyA") keys.left = true;
  if (event.code === "ArrowRight" || event.code === "KeyD") keys.right = true;
  if (event.code === "Space") keys.fire = true;
  if (event.code === "KeyP") togglePause();
});
window.addEventListener("keyup", event => {
  if (event.code === "ArrowLeft" || event.code === "KeyA") keys.left = false;
  if (event.code === "ArrowRight" || event.code === "KeyD") keys.right = false;
  if (event.code === "Space") keys.fire = false;
});
window.addEventListener("blur", () => { keys.left = keys.right = keys.fire = false; if (state === "playing") state = "paused"; });
ui.name.addEventListener("keydown", event => { if (event.key === "Enter") ui.button.click(); });

canvas.addEventListener("pointermove", movePlayerToPointer);
canvas.addEventListener("pointerdown", event => {
  if (event.pointerType === "mouse" && event.button !== 0) return;
  event.preventDefault();
  movePlayerToPointer(event);
  if (state === "playing" && fireCooldown <= 0) {
    fireCooldown = player.triple > 0 ? .13 : .22;
    firePlayerShot();
  }
  keys.fire = true;
  canvas.setPointerCapture?.(event.pointerId);
});
canvas.addEventListener("pointerup", event => {
  keys.fire = false;
  canvas.releasePointerCapture?.(event.pointerId);
});
canvas.addEventListener("pointercancel", () => { keys.fire = false; });

document.querySelectorAll("[data-control]").forEach(button => {
  const control = button.dataset.control;
  const down = event => { event.preventDefault(); if (control === "fire") keys.fire = true; else keys[control] = true; };
  const up = event => { event.preventDefault(); if (control === "fire") keys.fire = false; else keys[control] = false; };
  button.addEventListener("pointerdown", down);
  button.addEventListener("pointerup", up);
  button.addEventListener("pointercancel", up);
  button.addEventListener("pointerleave", up);
});

makeStars();
resetPlayer();
renderRanking();
syncHud();
ui.button.onclick = startGame;
requestAnimationFrame(frame);
