import { PLAYER_KEY, STORAGE_KEY, padScore } from "./config.js";

function normalizedName(value) {
  return String(value || "")
    .trim()
    .toUpperCase()
    .replace(/[^A-Z0-9 Ñ.-]/g, "")
    .slice(0, 12);
}

export class SnakeRanking {
  constructor(listElement, bestElement) {
    this.listElement = listElement;
    this.bestElement = bestElement;
    this.best = 0;
  }

  load() {
    try {
      const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
      return Array.isArray(parsed)
        ? parsed
            .filter((item) => Number.isFinite(Number(item?.score)))
            .map((item) => ({ ...item, score: Number(item.score) }))
            .sort((a, b) => b.score - a.score)
            .slice(0, 10)
        : [];
    } catch {
      return [];
    }
  }

  qualifies(score) {
    const scores = this.load();
    return Number.isFinite(score) && score > 0
      && (scores.length < 10 || score > scores[scores.length - 1].score);
  }

  save(score, playerName = "", level = 1) {
    if (!Number.isFinite(score) || score <= 0) return this.load();

    const scores = this.load();
    if (scores.length >= 10 && score <= scores[scores.length - 1].score) return scores;

    const name = normalizedName(playerName || localStorage.getItem(PLAYER_KEY));
    if (!name) return scores;

    localStorage.setItem(PLAYER_KEY, name);
    const next = [...scores, {
      name,
      score,
      level,
      date: new Date().toISOString()
    }]
      .sort((a, b) => b.score - a.score)
      .slice(0, 10);

    localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    return next;
  }

  render(currentScore = 0) {
    const scores = this.load();
    this.listElement.replaceChildren();

    for (let index = 0; index < 10; index += 1) {
      const item = document.createElement("li");
      const score = scores[index];
      if (score) {
        const row = document.createElement("div");
        row.className = "rank-row";

        const name = document.createElement("span");
        name.className = "rank-name";
        name.textContent = score.name || "---";

        const value = document.createElement("span");
        value.className = "rank-score";
        value.textContent = padScore(score.score);

        row.append(name, value);
        item.append(row);
      } else {
        const empty = document.createElement("span");
        empty.className = "empty-rank";
        empty.textContent = "---";
        item.append(empty);
      }
      this.listElement.append(item);
    }

    this.best = scores[0]?.score || 0;
    this.bestElement.textContent = padScore(Math.max(this.best, currentScore));
    return this.best;
  }
}
