/* ==========================================================================
   ANALYTICS — Instrumentación mínima de embudo (privacy-first).
   Soporta Plausible / Umami / PostHog vía window.__LM_ANALYTICS__ o
   fallback a console en desarrollo. Sin cookies propias.
   ========================================================================== */

const LMAnalytics = {
    _queue: [],
    _ready: false,

    init() {
        this._ready = true;
        while (this._queue.length) {
            const item = this._queue.shift();
            this._send(item.event, item.props);
        }
        this.track("page_view", { path: location.pathname + location.search });
        document.addEventListener("click", (e) => {
            const el = e.target.closest?.["[data-analytics]"];
            if (!el) return;
            const event = el.getAttribute("data-analytics");
            if (event) this.track(event, { label: el.getAttribute("data-analytics-label") || el.textContent?.trim()?.slice(0, 40) });
        }, true);
    },

    track(event, props = {}) {
        if (!event) return;
        if (!this._ready) {
            this._queue.push({ event, props });
            return;
        }
        this._send(event, props);
    },

    _send(event, props) {
        const payload = { ...props, ts: Date.now() };
        try {
            if (typeof window.plausible === "function") {
                window.plausible(event, { props: payload });
                return;
            }
            if (window.umami && typeof window.umami.track === "function") {
                window.umami.track(event, payload);
                return;
            }
            if (window.posthog && typeof window.posthog.capture === "function") {
                window.posthog.capture(event, payload);
                return;
            }
            if (typeof window.__LM_ANALYTICS__ === "function") {
                window.__LM_ANALYTICS__(event, payload);
                return;
            }
            if (location.hostname === "localhost" || location.hostname === "127.0.0.1") {
                console.debug("[LM analytics]", event, payload);
            }
        } catch (err) {
        }
    },
};

window.LMAnalytics = LMAnalytics;
window.trackEvent = (event, props) => LMAnalytics.track(event, props);

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => LMAnalytics.init());
} else {
    LMAnalytics.init();
}
