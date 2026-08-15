/* Ticket image generator: renders the signed quiniela as a shareable PNG
 * (1080x1920, Stories-friendly) using an offscreen canvas. No server work,
 * no external dependencies, CSP-safe (external file, no inline JS).
 *
 * Public API:
 *   TicketImage.generate(state) -> Promise<Blob>
 *   TicketImage.share(state)    -> Promise<void> (native share w/ files, else download)
 */
(function () {
    "use strict";

    const W = 1080;
    const H = 1920;

    const COLORS = {
        bg: "#060a0f",
        panel: "#0b1119",
        panelBorder: "#1a2530",
        neon: "#00FF66",
        glow: "rgba(0,255,102,.35)",
        text: "#ffffff",
        muted: "#5a6a7a",
        soft: "#8fa1b3",
        gold: "#fbbf24",
        signBg: "#0f1722",
        red: "#ff4444",
    };

    function roundRect(ctx, x, y, w, h, r) {
        ctx.beginPath();
        ctx.moveTo(x + r, y);
        ctx.arcTo(x + w, y, x + w, y + h, r);
        ctx.arcTo(x + w, y + h, x, y + h, r);
        ctx.arcTo(x, y + h, x, y, r);
        ctx.arcTo(x, y, x + w, y, r);
        ctx.closePath();
    }

    function fitText(ctx, text, maxWidth) {
        let out = String(text || "");
        while (out.length > 3 && ctx.measureText(out).width > maxWidth) {
            out = out.slice(0, -2);
        }
        return out === String(text || "") ? out : out + "…";
    }

    function drawBackground(ctx) {
        ctx.fillStyle = COLORS.bg;
        ctx.fillRect(0, 0, W, H);
        const gradient = ctx.createRadialGradient(W / 2, 0, 80, W / 2, 0, H * 0.7);
        gradient.addColorStop(0, "rgba(13,21,32,.95)");
        gradient.addColorStop(1, "rgba(13,21,32,0)");
        ctx.fillStyle = gradient;
        ctx.fillRect(0, 0, W, H);
        ctx.strokeStyle = "rgba(255,255,255,.025)";
        ctx.lineWidth = 1;
        for (let x = 0; x <= W; x += 40) {
            ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke();
        }
        for (let y = 0; y <= H; y += 40) {
            ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke();
        }
    }

    function drawHeader(ctx, jornada, userName) {
        ctx.textAlign = "center";
        ctx.fillStyle = COLORS.neon;
        ctx.font = "600 34px 'Space Grotesk', system-ui, sans-serif";
        ctx.fillText("LA PEÑA CONTRA LOS MAESTROS IA", W / 2, 120);

        ctx.fillStyle = COLORS.text;
        ctx.font = "700 96px 'Bebas Neue', 'Space Grotesk', system-ui, sans-serif";
        ctx.shadowColor = COLORS.glow;
        ctx.shadowBlur = 30;
        ctx.fillText("LIGA DE MAESTROS", W / 2, 225);
        ctx.shadowBlur = 0;

        ctx.fillStyle = COLORS.gold;
        ctx.font = "700 52px 'Bebas Neue', 'Space Grotesk', system-ui, sans-serif";
        ctx.fillText("MI QUINIELA · JORNADA " + (jornada || "?"), W / 2, 300);

        if (userName) {
            ctx.fillStyle = COLORS.soft;
            ctx.font = "500 34px 'Space Grotesk', system-ui, sans-serif";
            ctx.fillText(fitText(ctx, userName, W - 200), W / 2, 352);
        }
    }

    function drawMatchRow(ctx, y, index, match, sign) {
        const x = 70;
        const rowW = W - 140;
        const rowH = 86;
        const isPleno = index === 14;

        roundRect(ctx, x, y, rowW, rowH, 12);
        ctx.fillStyle = COLORS.panel;
        ctx.fill();
        ctx.strokeStyle = COLORS.panelBorder;
        ctx.lineWidth = 2;
        ctx.stroke();

        // Number badge
        ctx.textAlign = "center";
        ctx.fillStyle = COLORS.muted;
        ctx.font = "700 34px 'Bebas Neue', 'Space Grotesk', system-ui, sans-serif";
        ctx.fillText(String(index + 1), x + 46, y + rowH / 2 + 12);

        // Teams
        ctx.textAlign = "left";
        ctx.fillStyle = COLORS.text;
        ctx.font = "600 32px 'Space Grotesk', system-ui, sans-serif";
        const local = match?.local || "Local";
        const away = match?.visitante || "Visitante";
        const label = isPleno ? "PLENO AL 15 · " + local + " - " + away : local + " - " + away;
        ctx.fillText(fitText(ctx, label, rowW - 260), x + 90, y + rowH / 2 + 11);

        // Sign chip
        const chipW = 132;
        const chipX = x + rowW - chipW - 16;
        const chipY = y + 14;
        const chipH = rowH - 28;
        roundRect(ctx, chipX, chipY, chipW, chipH, 10);
        const hasSign = sign && sign !== "-";
        ctx.fillStyle = hasSign ? COLORS.signBg : "rgba(255,68,68,.08)";
        ctx.fill();
        ctx.strokeStyle = hasSign ? COLORS.neon : COLORS.red;
        ctx.lineWidth = 2;
        ctx.stroke();
        ctx.textAlign = "center";
        ctx.fillStyle = hasSign ? COLORS.neon : COLORS.red;
        ctx.font = "700 " + (String(sign).length > 3 ? 28 : 36) + "px 'Bebas Neue', 'Space Grotesk', system-ui, sans-serif";
        ctx.fillText(hasSign ? String(sign) : "—", chipX + chipW / 2, y + rowH / 2 + 13);
    }

    function drawFooter(ctx, doneCount) {
        const y = H - 200;
        ctx.textAlign = "center";
        ctx.fillStyle = COLORS.text;
        ctx.font = "700 46px 'Bebas Neue', 'Space Grotesk', system-ui, sans-serif";
        ctx.fillText(doneCount + "/15 FIRMADOS", W / 2, y);
        ctx.fillStyle = COLORS.neon;
        ctx.font = "600 40px 'Space Grotesk', system-ui, sans-serif";
        ctx.shadowColor = COLORS.glow;
        ctx.shadowBlur = 18;
        ctx.fillText("¿Puedes ganar a la IA?", W / 2, y + 66);
        ctx.shadowBlur = 0;
        ctx.fillStyle = COLORS.muted;
        ctx.font = "500 30px 'Space Grotesk', system-ui, sans-serif";
        ctx.fillText(window.location.host || "ligademaestros", W / 2, y + 126);
    }

    function render(state) {
        const canvas = document.createElement("canvas");
        canvas.width = W;
        canvas.height = H;
        const ctx = canvas.getContext("2d");

        const matches = (state?.data?.partidos || []).slice(0, 15);
        const signs = state?.my_signs || [];
        const jornada = state?.data?.jornada;
        const userName = state?.user?.name || "";
        const done = signs.filter((sign) => sign && sign !== "-").length;

        drawBackground(ctx);
        drawHeader(ctx, jornada, userName);

        const top = 410;
        const gap = 8;
        for (let i = 0; i < 15; i++) {
            drawMatchRow(ctx, top + i * (86 + gap), i, matches[i], signs[i]);
        }
        drawFooter(ctx, done);
        return canvas;
    }

    function generate(state) {
        return new Promise((resolve, reject) => {
            try {
                render(state).toBlob((blob) => {
                    if (blob) resolve(blob);
                    else reject(new Error("canvas.toBlob returned null"));
                }, "image/png");
            } catch (error) {
                reject(error);
            }
        });
    }

    function download(blob, filename) {
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        link.remove();
        setTimeout(() => URL.revokeObjectURL(url), 4000);
    }

    async function share(state) {
        const blob = await generate(state);
        const jornada = state?.data?.jornada || "x";
        const filename = "quiniela-j" + jornada + ".png";
        const file = new File([blob], filename, { type: "image/png" });
        if (navigator.canShare && navigator.canShare({ files: [file] })) {
            try {
                await navigator.share({
                    files: [file],
                    title: "Liga de Maestros",
                    text: "Mi quiniela de la J" + jornada + " · ¿Puedes ganar a la IA?",
                });
                return;
            } catch (error) {
                if (error && error.name === "AbortError") return;
                // Fall through to download on any other share failure.
            }
        }
        download(blob, filename);
    }

    window.TicketImage = { generate, share, render };
})();
