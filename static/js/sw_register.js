/* ==========================================================================
   SERVICE WORKER REGISTRATION
   Externalizado desde liga_index.html: la CSP del sitio usa
   `script-src 'self'` (sin 'unsafe-inline'), asi que un <script> inline
   quedaba bloqueado por el navegador y el SW nunca llegaba a registrarse.
   ========================================================================== */

(function registerServiceWorker() {
    if (!("serviceWorker" in navigator)) return;
    const swUrl = document.currentScript?.dataset.swUrl || "/static/sw.js";
    const register = () => {
        navigator.serviceWorker.register(swUrl, {
            scope: "/",
            updateViaCache: "none",
        }).catch(error => {
            console.warn("[SW] Registro fallido:", error);
        });
    };

    // late_assets.js injects this file during idle/interaction, often AFTER
    // window.load has already fired. Register immediately in that case instead
    // of waiting for an event that can never fire again.
    if (document.readyState === "complete") register();
    else window.addEventListener("load", register, { once: true });
})();
