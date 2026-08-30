/* ==========================================================================
   SERVICE WORKER REGISTRATION
   Externalizado desde liga_index.html: la CSP del sitio usa
   `script-src 'self'` (sin 'unsafe-inline'), asi que un <script> inline
   quedaba bloqueado por el navegador y el SW nunca llegaba a registrarse.
   ========================================================================== */

(function registerServiceWorker() {
    if (!("serviceWorker" in navigator)) return;
    const swUrl = document.currentScript?.dataset.swUrl || "/static/sw.js";
    window.addEventListener("load", () => {
        navigator.serviceWorker.register(swUrl).catch(error => {
            console.warn("[SW] Registro fallido:", error);
        });
    });
})();
