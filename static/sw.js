/* ═══════════════════════════════════════════════════════════════
   SERVICE WORKER — Liga de Maestros
   
   Estrategia: Cache-First para estaticos, red directa para API.
   Offline: muestra la ultima version cargada de la pagina.
   ═══════════════════════════════════════════════════════════════ */

const CACHE = 'liga-maestros-v9';
const STATIC_CACHE = 'liga-maestros-static-v9';

const PRECACHE_URLS = [
    '/',
    '/static/manifest.webmanifest',
    '/static/css/base/tokens.css',
    '/static/css/layout/app_shell.css',
    '/static/css/visual_unification.css',
    '/static/css/cover_hero.css',
    '/static/css/base/typography.css',
    '/static/css/themes/newspaper/shell.css',
    '/static/css/themes/newspaper/page_foundations.css',
    '/static/css/themes/newspaper/components.css',
    '/static/css/themes/newspaper/masthead.css',
    '/static/js/utils.js',
    '/static/js/state.js',
    '/static/js/logos.js',
    '/static/js/navigation.js',
    '/static/js/live.js',
    '/static/js/arena.js',
    '/static/js/events.js',
    '/static/js/quantum_final.js',
    '/static/js/confetti.js',
    '/static/css/themes/newspaper/animations.css',
    '/static/css/components/command_palette.css',
    '/static/css/components/ux_signals.css',
    '/static/js/command_palette.js',
    '/static/js/ux_signals.js',
    '/static/img/ligademaestroslogo_trans.png'
];

// Instalacion — precachear recursos criticos
self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(STATIC_CACHE).then(cache => {
            return cache.addAll(PRECACHE_URLS).catch(err => {
                console.warn('[SW] Precaching parcial:', err);
            });
        }).then(() => self.skipWaiting())
    );
});

// Activacion — limpiar caches viejos
self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys().then(keys => {
            return Promise.all(
                keys.filter(key => key !== CACHE && key !== STATIC_CACHE)
                    .map(key => caches.delete(key))
            );
        }).then(() => self.clients.claim())
    );
});

// Interceptar peticiones
self.addEventListener('fetch', event => {
    const { request } = event;
    const url = new URL(request.url);

    // Solo interceptar nuestro propio origen
    if (url.origin !== self.location.origin) return;

    const path = url.pathname;

    // La API contiene datos dinámicos y privados. Nunca se almacena en Cache Storage.
    if (path.startsWith('/api/')) {
        if (request.method !== 'GET') {
            event.respondWith(fetch(request));
            return;
        }
        event.respondWith(networkWithTimeout(request, 4000));
        return;
    }

    // Archivos estaticos versionados — Cache First (inmutables)
    if (path.startsWith('/static/') && url.searchParams.has('v')) {
        event.respondWith(cacheFirst(request));
        return;
    }

    // HTML principal — Network First
    if (path === '/') {
        event.respondWith(
            networkFirst(request).catch(() => {
                return caches.match(request).then(cached => {
                    return cached || new Response(
                        `<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Liga de Maestros</title><style>body{background:#06090f;color:#f0f4f8;font-family:system-ui;display:grid;place-items:center;min-height:100vh;text-align:center;padding:20px}h1{font-size:2rem;color:#fbbf24}a{color:#38bdf8}</style></head><body><h1>🏆 Liga de Maestros</h1><p>Parece que no tienes conexion a internet.</p><p>Vuelve a intentarlo cuando tengas conexion.</p><a href="/">Reintentar</a></body></html>`,
                        { headers: { 'Content-Type': 'text/html;charset=UTF-8' } }
                    );
                });
            })
        );
        return;
    }

    // Otros estaticos — Cache First
    if (path.startsWith('/static/') || path.startsWith('/juegos/')) {
        event.respondWith(cacheFirst(request));
        return;
    }

    // Por defecto — Network First
    event.respondWith(networkFirst(request));
});

/* ──────────────────────────────────────────
   ESTRATEGIAS DE CACHE
   ────────────────────────────────────────── */

async function cacheFirst(request) {
    const cached = await caches.match(request);
    if (cached) return cached;
    try {
        const response = await fetch(request);
        if (response.ok) {
            const cache = await caches.open(STATIC_CACHE);
            cache.put(request, response.clone());
        }
        return response;
    } catch (error) {
        return new Response('Recurso no disponible offline', { status: 408 });
    }
}

async function networkFirst(request) {
    try {
        const response = await fetch(request);
        if (response.ok) {
            const cache = await caches.open(CACHE);
            cache.put(request, response.clone());
        }
        return response;
    } catch {
        const cached = await caches.match(request);
        if (cached) return cached;
        throw new Error('Offline');
    }
}

async function networkWithTimeout(request, timeoutMs = 4000) {
    const timeout = new Promise((_, reject) =>
        setTimeout(() => reject(new Error('Timeout')), timeoutMs)
    );
    try {
        return await Promise.race([fetch(request), timeout]);
    } catch {
        return new Response(JSON.stringify({ status: 'error', message: 'Offline' }), {
            status: 503,
            headers: {
                'Content-Type': 'application/json',
                'Cache-Control': 'no-store'
            }
        });
    }
}
