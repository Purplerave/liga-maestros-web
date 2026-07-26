/* ==========================================================================
   UX SIGNALS — Señales de sistema del frontend.
   - Skip link accesible
   - Barra de progreso al cambiar de vista
   - Aviso de conexion perdida / recuperada
   - Aviso de nueva version disponible (service worker)
   - Atajos de teclado globales
   Todo es mejora progresiva: si falla, la app sigue funcionando.
   ========================================================================== */

const UXSignals = {
    _pill: null,
    _pillTimer: null,
    _progress: null,
    _progressTimer: null,
    _pending: 0,

    init() {
        this._mountSkipLink();
        this._mountProgress();
        this._mountPill();
        this._watchNetwork();
        this._watchServiceWorker();
        this._bindShortcuts();
        this._enhanceRouting();
        this._prefetchOnIntent();
    },

    /* ---------- Prefetch de vistas al mostrar intencion ---------- */
    _prefetchOnIntent() {
        if (typeof ensureViewStyles !== "function") return;
        const warmed = new Set();
        const warm = page => {
            if (!page || warmed.has(page)) return;
            warmed.add(page);
            // Solo el CSS: es idempotente, cacheable y no ejecuta logica de vista.
            Promise.resolve(ensureViewStyles(page)).catch(() => {});
        };
        const onIntent = event => {
            const button = event.target.closest?.("[data-page-action]");
            if (button) warm(button.dataset.pageAction);
        };
        document.addEventListener("pointerenter", onIntent, true);
        document.addEventListener("focusin", onIntent);
    },

    /* ---------- Skip link ---------- */
    _mountSkipLink() {
        if (document.querySelector(".skip-link")) return;
        const main = document.querySelector(".main-arena");
        if (main && !main.id) main.id = "contenido-principal";
        const link = document.createElement("a");
        link.className = "skip-link";
        link.href = `#${main?.id || "contenido-principal"}`;
        link.textContent = "Saltar al contenido";
        document.body.insertBefore(link, document.body.firstChild);
    },

    /* ---------- Barra de progreso ---------- */
    _mountProgress() {
        const bar = document.createElement("div");
        bar.className = "route-progress";
        bar.setAttribute("role", "presentation");
        document.body.appendChild(bar);
        this._progress = bar;
    },

    startProgress() {
        this._pending += 1;
        if (!this._progress) return;
        this._progress.classList.add("is-active");
        this._progress.style.setProperty("--route-progress", "18%");
        clearTimeout(this._progressTimer);
        this._progressTimer = setTimeout(() => {
            this._progress?.style.setProperty("--route-progress", "72%");
        }, 180);
    },

    endProgress() {
        this._pending = Math.max(0, this._pending - 1);
        if (this._pending > 0 || !this._progress) return;
        clearTimeout(this._progressTimer);
        this._progress.style.setProperty("--route-progress", "100%");
        setTimeout(() => {
            this._progress?.classList.remove("is-active");
            setTimeout(() => this._progress?.style.setProperty("--route-progress", "0%"), 200);
        }, 220);
    },

    /* ---------- Pildora de sistema ---------- */
    _mountPill() {
        const pill = document.createElement("div");
        pill.className = "system-pill";
        pill.setAttribute("role", "status");
        pill.setAttribute("aria-live", "polite");
        pill.hidden = true;
        document.body.appendChild(pill);
        this._pill = pill;
    },

    showPill(message, { variant = "", action = null, timeout = 4000 } = {}) {
        if (!this._pill) return;
        const pill = this._pill;
        pill.className = `system-pill${variant ? ` is-${variant}` : ""}`;
        pill.hidden = false;
        pill.innerHTML = `<span class="pill-dot" aria-hidden="true"></span><span>${escapeHtml(message)}</span>`;
        if (action) {
            const button = document.createElement("button");
            button.type = "button";
            button.textContent = action.label;
            button.addEventListener("click", action.run, { once: true });
            pill.appendChild(button);
        }
        void pill.offsetWidth;
        pill.classList.add("is-visible");
        clearTimeout(this._pillTimer);
        if (timeout) {
            this._pillTimer = setTimeout(() => this.hidePill(), timeout);
        }
    },

    hidePill() {
        if (!this._pill) return;
        this._pill.classList.remove("is-visible");
        setTimeout(() => { if (this._pill && !this._pill.classList.contains("is-visible")) this._pill.hidden = true; }, 240);
    },

    /* ---------- Red ---------- */
    _watchNetwork() {
        window.addEventListener("offline", () => {
            document.body.classList.add("is-offline");
            this.showPill("Sin conexion — viendo la ultima version guardada", { variant: "offline", timeout: 0 });
        });
        window.addEventListener("online", () => {
            document.body.classList.remove("is-offline");
            this.showPill("Conexion recuperada", { variant: "online", timeout: 2600 });
            if (typeof refreshData === "function") refreshData({ auto: true });
        });
        if (!navigator.onLine) {
            document.body.classList.add("is-offline");
            this.showPill("Sin conexion — viendo la ultima version guardada", { variant: "offline", timeout: 0 });
        }
    },

    /* ---------- Nueva version ---------- */
    _watchServiceWorker() {
        if (!("serviceWorker" in navigator)) return;
        navigator.serviceWorker.ready.then(registration => {
            registration.addEventListener("updatefound", () => {
                const worker = registration.installing;
                if (!worker) return;
                worker.addEventListener("statechange", () => {
                    if (worker.state === "installed" && navigator.serviceWorker.controller) {
                        this.showPill("Hay una version nueva de la web", {
                            variant: "update",
                            timeout: 0,
                            action: { label: "Recargar", run: () => window.location.reload() },
                        });
                    }
                });
            });
        }).catch(() => {});
    },

    /* ---------- Atajos globales ---------- */
    _bindShortcuts() {
        document.addEventListener("keydown", event => {
            if (event.ctrlKey || event.metaKey || event.altKey) return;
            const target = event.target;
            if (target && target.matches?.("input, textarea, select, [contenteditable='true']")) return;
            const key = event.key.toLowerCase();
            const pages = { p: "ALL", q: "TICKET", d: "LIVE", l: "STANDINGS", j: "SNAKE", n: "CONTEST" };
            if (pages[key] && typeof openNewspaperPage === "function") {
                event.preventDefault();
                openNewspaperPage(pages[key]);
                return;
            }
            if (key === "r" && typeof refreshData === "function") {
                event.preventDefault();
                refreshData();
                return;
            }
            if (key === "s" && typeof savePredictions === "function") {
                event.preventDefault();
                savePredictions();
                return;
            }
            if (key === "?" || (event.shiftKey && key === "/")) {
                event.preventDefault();
                window.CommandPalette?.open();
            }
        });
    },

    /* ---------- Progreso + View Transitions al cambiar de vista ---------- */
    _enhanceRouting() {
        if (typeof window.openNewspaperPage !== "function") return;
        const original = window.openNewspaperPage;
        const self = this;
        const prefersReducedMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        window.openNewspaperPage = async function wrappedOpenNewspaperPage(page) {
            self.startProgress();
            const run = () => original.call(this, page);
            try {
                // View Transitions API donde exista; fallback silencioso donde no.
                if (typeof document.startViewTransition === "function" && !prefersReducedMotion()) {
                    return await document.startViewTransition(run).finished.catch(() => {});
                }
                return await run();
            } finally {
                self.endProgress();
            }
        };
    },
};

window.UXSignals = UXSignals;
