/* ==========================================================================
   POST-JORNADA — Banner de resumen emocional al entrar tras una jornada.
   Cierra el loop: "¿le gané a Claude?" sin que el usuario tenga que buscarlo.
   Mejora progresiva: si falla, la app sigue igual.
   ========================================================================== */

const PostJornada = {
    _storageKey(jornada) {
        return `lm_pj_seen_j${jornada}`;
    },

    async init() {
        try {
            await this._waitForUser(4000);
            if (!state?.user?.id) return;

            const res = await fetch("/api/user/post-jornada-summary", {
                credentials: "same-origin",
                headers: { Accept: "application/json" },
            });
            if (!res.ok) return;
            const data = await res.json();
            if (!data || !data.jornada) return;

            const key = this._storageKey(data.jornada);
            if (localStorage.getItem(key) === "1") return;

            this._show(data);
            if (typeof trackEvent === "function") {
                trackEvent("result_view", { jornada: data.jornada, beaten: data.beaten_ais });
            }
        } catch (_) {
        }
    },

    _waitForUser(timeoutMs) {
        return new Promise((resolve) => {
            if (typeof state !== "undefined" && state?.user?.id) {
                resolve();
                return;
            }
            const start = Date.now();
            const tick = () => {
                if (typeof state !== "undefined" && state?.user?.id) {
                    resolve();
                    return;
                }
                if (Date.now() - start > timeoutMs) {
                    resolve();
                    return;
                }
                setTimeout(tick, 150);
            };
            tick();
        });
    },

    _show(data) {
        if (document.getElementById("pj-banner")) return;

        const racha = data.racha || {};
        const scores = data.ai_scores || {};
        const aiRows = Object.entries(scores)
            .map(([id, hits]) => {
                const label = id === "chatgpt" ? "GPT" : id.charAt(0).toUpperCase() + id.slice(1);
                const diff = (data.human_hits || 0) - hits;
                const cls = diff > 0 ? "pj-win" : diff < 0 ? "pj-loss" : "pj-draw";
                const sign = diff > 0 ? `+${diff}` : String(diff);
                return `<li class="${cls}"><span>${label}</span><b>${hits}</b><em>${sign}</em></li>`;
            })
            .join("");

        const banner = document.createElement("aside");
        banner.id = "pj-banner";
        banner.className = "pj-banner";
        banner.setAttribute("role", "dialog");
        banner.setAttribute("aria-label", "Resumen de la jornada");
        banner.innerHTML = `
            <div class="pj-banner-inner">
                <button type="button" class="pj-close" aria-label="Cerrar" data-pj-close>&times;</button>
                <div class="pj-kicker">Jornada ${data.jornada} · resultado</div>
                <h2 class="pj-headline">${this._esc(data.headline || "Resumen de la jornada")}</h2>
                <div class="pj-scoreline">
                    <div class="pj-you">
                        <span>Tú</span>
                        <strong>${data.human_hits ?? 0}</strong>
                        <small>aciertos</small>
                    </div>
                    <ul class="pj-ais">${aiRows}</ul>
                </div>
                <div class="pj-meta">
                    <span>Racha: <b>${racha.racha_actual ?? 0}</b></span>
                    <span>Mejor: <b>${racha.racha_max ?? 0}</b></span>
                    <span>Jornadas: <b>${racha.jornadas_jugadas ?? 0}</b></span>
                </div>
                <div class="pj-actions">
                    <button type="button" class="pj-btn pj-btn-primary" data-pj-share>Compartir resultado</button>
                    <button type="button" class="pj-btn" data-pj-close>Seguir</button>
                </div>
            </div>
        `;
        document.body.appendChild(banner);
        requestAnimationFrame(() => banner.classList.add("pj-visible"));

        banner.querySelectorAll("[data-pj-close]").forEach((btn) => {
            btn.addEventListener("click", () => this._dismiss(data.jornada));
        });
        banner.querySelector("[data-pj-share]")?.addEventListener("click", () => {
            this._share(data);
        });
    },

    _dismiss(jornada) {
        try {
            localStorage.setItem(this._storageKey(jornada), "1");
        } catch (_) {}
        const banner = document.getElementById("pj-banner");
        if (!banner) return;
        banner.classList.remove("pj-visible");
        setTimeout(() => banner.remove(), 280);
    },

    async _share(data) {
        if (typeof trackEvent === "function") {
            trackEvent("share_click", { channel: "post_jornada", jornada: data.jornada });
        }
        const text = data.share_text || `Jornada ${data.jornada}: ${data.human_hits} aciertos. #LigaDeMaestros`;
        const url = location.origin + "/";
        try {
            if (navigator.share) {
                await navigator.share({ title: "Liga de Maestros", text, url });
                return;
            }
        } catch (_) {}
        try {
            await navigator.clipboard.writeText(text + "\n" + url);
            if (typeof showToast === "function") showToast("Resultado copiado. ¡Pégalo donde quieras!");
        } catch (_) {
            if (typeof showToast === "function") showToast(text, "success");
        }
    },

    _esc(value) {
        return String(value ?? "")
            .replaceAll("&", "&amp;")
            .replaceAll("<", "&lt;")
            .replaceAll(">", "&gt;")
            .replaceAll('"', "&quot;");
    },
};

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => PostJornada.init());
} else {
    PostJornada.init();
}
