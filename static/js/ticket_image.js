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
        ctx.font = "600 34px 'Outfit', system-ui, sans-serif";
        ctx.fillText("LA PEÑA CONTRA LOS MAESTROS IA", W / 2, 120);

        ctx.fillStyle = COLORS.text;
        ctx.font = "700 96px 'Outfit', system-ui, sans-serif";
        ctx.shadowColor = COLORS.glow;
        ctx.shadowBlur = 30;
        ctx.fillText("LIGA DE MAESTROS", W / 2, 225);
        ctx.shadowBlur = 0;

        ctx.fillStyle = COLORS.gold;
        ctx.font = "700 52px 'Outfit', system-ui, sans-serif";
        ctx.fillText("MI QUINIELA · JORNADA " + (jornada || "?"), W / 2, 300);

        if (userName) {
            ctx.fillStyle = COLORS.soft;
            ctx.font = "500 34px 'Outfit', system-ui, sans-serif";
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
        ctx.font = "700 34px 'Outfit', system-ui, sans-serif";
        ctx.fillText(String(index + 1), x + 46, y + rowH / 2 + 12);

        // Teams
        ctx.textAlign = "left";
        ctx.fillStyle = COLORS.text;
        ctx.font = "600 32px 'Outfit', system-ui, sans-serif";
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
        ctx.font = "700 " + (String(sign).length > 3 ? 28 : 36) + "px 'Outfit', system-ui, sans-serif";
        ctx.fillText(hasSign ? String(sign) : "—", chipX + chipW / 2, y + rowH / 2 + 13);
    }

    function drawFooter(ctx, doneCount) {
        const y = H - 200;
        ctx.textAlign = "center";
        ctx.fillStyle = COLORS.text;
        ctx.font = "700 46px 'Outfit', system-ui, sans-serif";
        ctx.fillText(doneCount + "/15 FIRMADOS", W / 2, y);
        ctx.fillStyle = COLORS.neon;
        ctx.font = "600 40px 'Outfit', system-ui, sans-serif";
        ctx.shadowColor = COLORS.glow;
        ctx.shadowBlur = 18;
        ctx.fillText("¿Puedes ganar a la IA?", W / 2, y + 66);
        ctx.shadowBlur = 0;
        ctx.fillStyle = COLORS.muted;
        ctx.font = "500 30px 'Outfit', system-ui, sans-serif";
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

    // P1 2.1 — Tarjeta compartible Jornada: Tú vs IAs
    function getVsRows(state) {
        const ranking = state?.data?.ranking_maestros || {};
        const names = state?.data?.participant_contract?.names || {};
        const visibleCols = state?.data?.participant_contract?.visible_ai_columns || [];
        const aiIds = visibleCols.map(c => String(Array.isArray(c) ? c[0] : c.id).toLowerCase());
        const entries = Object.entries(ranking).map(([uid, v]) => {
            const name = names[String(uid).toLowerCase()] || names[uid] || String(uid).split("@")[0];
            const isAI = aiIds.includes(String(uid).toLowerCase());
            const pts = Number(v?.jornada ?? v?.total ?? 0);
            const isUser = state?.user && String(state.user.id).toLowerCase() === String(uid).toLowerCase();
            return { uid, name: isUser ? (state.user.name || "Tú") : name, pts, isAI, isUser };
        }).sort((a,b)=> b.pts - a.pts);
        // Ensure user appears even if not in ranking (fallback from signs)
        if (!entries.some(e=>e.isUser) && state?.user) {
            const done = (state.my_signs||[]).filter(s=>s&&s!=="-").length;
            entries.push({ uid: state.user.id, name: state.user.name||"Tú", pts: done, isAI:false, isUser:true });
            entries.sort((a,b)=> b.pts - a.pts);
        }
        // Take top 5 (user + 4 AIs) or first 5
        const top = entries.slice(0, 6);
        // Prioritize keeping user visible
        if (top.length>5 && !top.some(e=>e.isUser)) {
            const userEntry = entries.find(e=>e.isUser);
            if (userEntry) { top.pop(); top.push(userEntry); top.sort((a,b)=>b.pts-a.pts); }
        }
        return top.slice(0,5);
    }

    function drawVsHeader(ctx, jornada) {
        ctx.textAlign = "center";
        ctx.fillStyle = COLORS.neon;
        ctx.font = "600 30px 'Outfit', system-ui, sans-serif";
        ctx.fillText("JORNADA " + (jornada || "?") + " · HUMANO VS MÁQUINAS", W/2, 110);
        ctx.fillStyle = COLORS.text;
        ctx.font = "700 82px 'Outfit', system-ui, sans-serif";
        ctx.shadowColor = COLORS.glow; ctx.shadowBlur = 28;
        ctx.fillText("¿QUIÉN ACERTÓ MÁS?", W/2, 200);
        ctx.shadowBlur = 0;
    }

    function drawVsRows(ctx, rows) {
        const top = 280;
        const rowH = 110;
        const gap = 14;
        const x = 70, w = W-140;
        rows.forEach((row, i) => {
            const y = top + i*(rowH+gap);
            const medal = i===0 ? "🥇" : i===1 ? "🥈" : i===2 ? "🥉" : String(i+1);
            roundRect(ctx, x, y, w, rowH, 14);
            ctx.fillStyle = row.isUser ? "rgba(56,217,255,0.10)" : row.isAI ? "rgba(239,90,139,0.08)" : COLORS.panel;
            ctx.fill();
            ctx.strokeStyle = row.isUser ? "rgba(56,217,255,0.35)" : row.isAI ? "rgba(239,90,139,0.25)" : COLORS.panelBorder;
            ctx.lineWidth = 2; ctx.stroke();
            // medal
            ctx.textAlign = "center";
            ctx.fillStyle = COLORS.muted;
            ctx.font = "700 34px system-ui, sans-serif";
            ctx.fillText(medal, x+46, y+rowH/2+12);
            // name
            ctx.textAlign = "left";
            ctx.fillStyle = row.isUser ? "#7cc6ff" : row.isAI ? "#f472b6" : COLORS.text;
            ctx.font = "700 36px 'Outfit', system-ui, sans-serif";
            const label = (row.isUser ? "TÚ · " : row.isAI ? "IA · " : "") + row.name;
            ctx.fillText(fitText(ctx, label, w-240), x+90, y+rowH/2+12);
            // pts
            ctx.textAlign = "center";
            const ptsX = x+w-80, ptsY = y+rowH/2;
            roundRect(ctx, ptsX-70, ptsY-30, 140, 60, 10);
            ctx.fillStyle = i===0 ? "rgba(251,191,36,0.18)" : "rgba(255,255,255,0.06)";
            ctx.fill();
            ctx.fillStyle = i===0 ? COLORS.gold : COLORS.text;
            ctx.font = "800 40px 'Outfit', system-ui, sans-serif";
            ctx.fillText(row.pts + " pts", ptsX, ptsY+14);
        });
    }

    function drawVsFooter(ctx) {
        const y = H - 180;
        ctx.textAlign = "center";
        ctx.fillStyle = COLORS.neon;
        ctx.font = "700 38px 'Outfit', system-ui, sans-serif";
        ctx.shadowColor = COLORS.glow; ctx.shadowBlur = 16;
        ctx.fillText("LIGA DE MAESTROS", W/2, y);
        ctx.shadowBlur = 0;
        ctx.fillStyle = COLORS.muted;
        ctx.font = "500 28px 'Outfit', system-ui, sans-serif";
        ctx.fillText("Firma tu quiniela en ligademaestros", W/2, y+48);
    }

    function renderVs(state) {
        const canvas = document.createElement("canvas");
        canvas.width = W; canvas.height = H;
        const ctx = canvas.getContext("2d");
        const jornada = state?.data?.jornada || "?";
        const rows = getVsRows(state);
        drawBackground(ctx);
        drawVsHeader(ctx, jornada);
        if (rows.length) drawVsRows(ctx, rows);
        else {
            ctx.fillStyle = COLORS.muted; ctx.textAlign="center";
            ctx.font = "600 32px system-ui, sans-serif";
            ctx.fillText("Aún sin resultados — ¡sé el primero en firmar!", W/2, 500);
        }
        drawVsFooter(ctx);
        return canvas;
    }

    function generateVs(state) {
        return new Promise((resolve, reject) => {
            try { renderVs(state).toBlob(b=> b?resolve(b):reject(new Error("null")), "image/png"); }
            catch(e){ reject(e); }
        });
    }
    async function shareVs(state) {
        const blob = await generateVs(state);
        const jornada = state?.data?.jornada || "x";
        const file = new File([blob], `duelo-j${jornada}.png`, {type:"image/png"});
        if (navigator.canShare && navigator.canShare({files:[file]})) {
            try { await navigator.share({files:[file], title:"Liga de Maestros", text:`J${jornada} — ¿Humano o IA? Mi duelo en Liga de Maestros`}); return; } catch(e){ if(e&&e.name==="AbortError") return; }
        }
        download(blob, `duelo-j${jornada}.png`);
    }

    window.TicketImage = { generate, share, render, generateVs, shareVs, renderVs };
})();
