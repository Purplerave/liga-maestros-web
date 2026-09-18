/* ==========================================================================
   LATE ASSETS — lo que la portada NO necesita para pintar.

   Frente 2 (Rendimiento/Portada): la portada servia 27 hojas de estilo y 17
   scripts antes de poder pintar. Nueve de esos scripts (analitica, confeti,
   imagen del boleto, sonidos, paleta de comandos, señales UX, post-jornada,
   onboarding y service worker) y dos hojas de estilo (onboarding y
   post-jornada) solo hacen falta cuando el usuario interactua o cuando su
   componente aparece: ninguno participa en el primer pintado.

   Aqui se cargan despues: cuando el hilo principal esta libre (idle), cuando
   la pagina termina de cargar o en cuanto el usuario toca algo (lo que llegue
   primero). Con `script.async = false` las descargas van en paralelo pero la
   ejecucion respeta el orden de la lista, igual que con etiquetas en el HTML.

   Contrato con el resto del shell:
   - Los modulos de aqui se consumen siempre con guarda
     (`window.CommandPalette?.init()`, `typeof SoundManager !== "undefined"`…),
     asi que cargarlos tarde nunca rompe la portada.
   - Al terminar se dispara `liga:late-ready` en `document`: events.js lo
     escucha para inicializar la paleta y las señales UX si aun no lo estaban.
   ========================================================================== */

(function registerLateAssets() {
    "use strict";

    /* La CSP del sitio es `script-src 'self'`: nada de codigo inline. La URL
       del service worker viaja como data-attribute de esta misma etiqueta. */
    const SW_URL = document.currentScript?.dataset.swUrl || "/static/sw.js";

    function versionedAsset(path, tag) {
        const version = (document.body && document.body.dataset.assetsV) || "dev";
        return `${path}?v=${encodeURIComponent(version)}-${tag}`;
    }

    // Estilos de componentes que no existen en el primer pintado.
    const LATE_STYLES = [
        ["late-onboarding-styles", versionedAsset("/static/css/onboarding.css", "onboarding-1")],
        ["late-post-jornada-styles", versionedAsset("/static/css/components/post_jornada.css", "pj-1")],
    ];

    // Scripts que la portada no necesita para ser util. El orden importa:
    // sw_register va al final porque registra el service worker al terminar.
    const LATE_SCRIPTS = [
        ["late-analytics-script", versionedAsset("/static/js/analytics.js", "analytics-1")],
        ["late-sound-script", versionedAsset("/static/js/sound_manager.js", "sound-1")],
        ["late-confetti-script", versionedAsset("/static/js/confetti.js", "confetti-1")],
        ["late-ticket-image-script", versionedAsset("/static/js/ticket_image.js", "ticket-image-1")],
        ["late-post-jornada-script", versionedAsset("/static/js/post_jornada.js", "pj-1")],
        ["late-onboarding-script", versionedAsset("/static/js/onboarding.js", "onboarding-1")],
        ["late-cmdk-script", versionedAsset("/static/js/command_palette.js", "cmdk-4")],
        ["late-ux-signals-script", versionedAsset("/static/js/ux_signals.js", "ux-signals-1")],
        ["late-sw-script", versionedAsset("/static/js/sw_register.js", "sw-register-2")],
    ];

    function injectStylesheet(id, href) {
        return new Promise(resolve => {
            if (document.getElementById(id)) return resolve();
            const link = document.createElement("link");
            link.id = id;
            link.rel = "stylesheet";
            link.href = href;
            link.addEventListener("load", resolve, { once: true });
            link.addEventListener("error", resolve, { once: true });
            document.head.appendChild(link);
        });
    }

    function injectScript(id, src) {
        return new Promise(resolve => {
            if (document.getElementById(id)) return resolve();
            const script = document.createElement("script");
            script.id = id;
            script.src = src;
            // Descarga en paralelo, ejecucion en orden de insercion.
            script.async = false;
            if (id === "late-sw-script") script.dataset.swUrl = SW_URL;
            script.addEventListener("load", () => {
                script.dataset.loaded = "true";
                resolve();
            }, { once: true });
            script.addEventListener("error", resolve, { once: true });
            document.body.appendChild(script);
        });
    }

    /* Las fuentes de Google llegaban como hoja de estilo bloqueante en el
       <head>: un DNS + TLS + ida y vuelta a un tercero antes del primer
       pintado. Ahora viajan como `preload` y se promocionan a hoja de estilo
       aqui, cuando el HTML ya esta parseado y la precarga esta en vuelo. Sin
       JS queda el <noscript> del template; sin red, el fallback del sistema
       (`display=swap` ya estaba en la URL). */
    function applyWebfonts() {
        const link = document.getElementById("lm-webfonts");
        if (link && link.rel === "preload") link.rel = "stylesheet";
    }

    async function loadLateAssets() {
        LATE_STYLES.forEach(([id, href]) => injectStylesheet(id, href));
        LATE_SCRIPTS.forEach(([id, src]) => injectScript(id, src));
        // Esperar a que el ultimo haya terminado para avisar al shell.
        const last = LATE_SCRIPTS[LATE_SCRIPTS.length - 1];
        const lastId = last && last[0];
        if (lastId) {
            await new Promise(resolve => {
                const node = document.getElementById(lastId);
                if (!node) return resolve();
                if (node.dataset.loaded === "true") return resolve();
                node.addEventListener("load", resolve, { once: true });
                node.addEventListener("error", resolve, { once: true });
            });
        }
        document.dispatchEvent(new CustomEvent("liga:late-ready"));
    }

    let started = false;
    const INTERACTION_EVENTS = ["pointerdown", "keydown", "touchstart", "wheel"];

    function start() {
        if (started) return;
        started = true;
        INTERACTION_EVENTS.forEach(type => window.removeEventListener(type, start));
        void loadLateAssets();
    }

    applyWebfonts();

    const scheduleIdle =
        window.requestIdleCallback ||
        function fallbackIdle(callback) {
            return window.setTimeout(() => callback({ timeRemaining: () => 0 }), 200);
        };

    // 1) en cuanto el hilo principal este libre (con tope de 3 s);
    scheduleIdle(start, { timeout: 3000 });
    // 2) si el usuario interactua antes, no esperamos: puede necesitarlos ya;
    INTERACTION_EVENTS.forEach(type =>
        window.addEventListener(type, start, { once: true, passive: true })
    );
    // 3) y como red de seguridad, al terminar de cargar la pagina.
    window.addEventListener("load", () => scheduleIdle(start, { timeout: 800 }));
})();
