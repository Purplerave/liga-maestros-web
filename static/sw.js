/* ═══════════════════════════════════════════════════════════════
   SERVICE WORKER — Liga de Maestros

   Estrategia:
     - API .................... red directa, con tope de espera. Nunca se cachea.
     - Estaticos con ?v= ...... cache first (la URL cambia al desplegar).
     - Estaticos sin ?v= ...... red, respetando no-store. Sin cache.
     - Navegacion ............. red primero, conCaducidad y sin cachear
                               jamas paginas legales ni la cuenta del usuario.
     - POST / PUT / DELETE .... no se interceptan en absoluto.

   Offline: se muestra la ultima version cacheada de la portada.

   Sobre el ambito: este SW se sirve en /static/sw.js pero se registra con
   scope "/", asi que controla TODO el origen (tambien /api/*, /cuenta y las
   paginas legales). Antes seOwned que su ambito era /static/ y por eso no
   hacía falta proteger esas rutas. Ahora que si las atraviesa, cachearlas sin
   caducidad servia la politica de privacidad y cookies de hace semanas.
   ═══════════════════════════════════════════════════════════════ */

const CACHE = 'liga-maestros-v14';
const STATIC_CACHE = 'liga-maestros-static-v14';
const CACHE_PREFIX = 'liga-maestros-';

/* Cuanto tiempo se considera aceptable una entrada de la cache de navegacion.
   Sin esto, /privacidad se servia desde Cache Storage indefinidamente. */
const NAV_TTL_MS = 24 * 60 * 60 * 1000; // 24 h

/* Rutas que jamas se cachean: contienen datos del usuario o texto legal que
   debe ser siempre el vigente. */
const NEVER_CACHE_PATHS = [
    '/cuenta',
    '/privacidad',
    '/cookies',
    '/aviso-legal',
    '/ayuda',
];

/* Tope de espera para la API. Era de 4000 ms, y con ese tope cualquier
   respuesta por encima de 4 s se convertía en un 503 inventado con el servidor
   vivo: en producción /api/liga/data medía 1,31 s de media y /api/noticias/radar
   4,28 s (/metrics, 13/09 con la J6 en juego).

   30 s es una red de seguridad contra cuelgues reales, no un filtro de
   rendimiento. */
const API_TIMEOUT_MS = 30000;

const PRECACHE_URLS = [
    '/',
    '/static/manifest.webmanifest',
    '/static/css/base/tokens.css',
    '/static/css/layout/app_shell.css',
    '/static/css/visual_unification.css',
    '/static/css/cover_hero.css',
    '/static/css/mobile_v2.css',
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

/* Instalacion — precachear recursos criticos.
   `cache.addAll` es todo-o-nada: un unico 404 cancelaba los 25 precacheos y
   solo dejaba un console.warn mientras `skipWaiting()` seguia adelante. */
self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(STATIC_CACHE)
            .then(cache => Promise.allSettled(PRECACHE_URLS.map(url => cache.add(url))))
            .then(() => self.skipWaiting())
    );
});

/* Activacion — borrar nuestras propias caches antiguas.
   Antes se borraba TODO lo del origen cuyo nombre no fuera el nuestro, lo que
   se comia las caches de cualquier otra app servida en el mismo dominio. */
self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys()
            .then(keys => Promise.all(
                keys
                    .filter(key => key.startsWith(CACHE_PREFIX))
                    .filter(key => key !== CACHE && key !== STATIC_CACHE)
                    .map(key => caches.delete(key))
            ))
            .then(() => self.clients.claim())
    );
});

// Interceptar peticiones
self.addEventListener('fetch', event => {
    const { request } = event;
    const url = new URL(request.url);

    // Solo interceptar nuestro propio origen
    if (url.origin !== self.location.origin) return;

    /* Solo GET. Antes esta regla solo estaba en la rama de /api/, asi que un
       POST caia en el `networkFirst` por defecto: `cache.put()` con un request
       no-GET lanza TypeError, se comia el catch y acababa en
       `throw new Error('Offline')`. Eso rompia, entre otros,
       POST /cuenta/eliminar y todos los formularios. */
    if (request.method !== 'GET') return;

    const path = url.pathname;

    // La API contiene datos dinamicos y privados. Nunca se almacena en Cache Storage.
    if (path.startsWith('/api/')) {
        event.respondWith(networkWithTimeout(request, API_TIMEOUT_MS));
        return;
    }

    // Rutas con datos del usuario o texto legal: red directa, sin cache.
    if (NEVER_CACHE_PATHS.includes(path)) return;

    // Archivos estaticos versionados — Cache First (inmutables por definicion:
    // el ?v= cambia cuando el contenido cambia, asi que no necesitan caducidad).
    if (path.startsWith('/static/') && url.searchParams.has('v')) {
        event.respondWith(cacheFirst(request));
        return;
    }

    // HTML principal — Network First, con repliegue offline.
    if (path === '/') {
        event.respondWith(
            networkFirst(request, CACHE, NAV_TTL_MS).catch(() => {
                return caches.match(request).then(cached => {
                    return cached || new Response(OFFLINE_HTML, {
                        headers: { 'Content-Type': 'text/html;charset=UTF-8' }
                    });
                });
            })
        );
        return;
    }

    /* Estaticos sin versionar: el servidor los manda con
       `no-store, no-cache, must-revalidate`, asi que cachearlos era.cachear
       basura. Se respeta la cabecera y, si aun asi arrives cacheado, se
       revalida contra la red. */
    if (path.startsWith('/static/') || path.startsWith('/juegos/')) {
        event.respondWith(staticNoStore(request));
        return;
    }

    // Resto de navegacion (landing, 404, etc.): red primero, con caducidad.
    event.respondWith(
        networkFirst(request, CACHE, NAV_TTL_MS).catch(() => caches.match(request))
    );
});

/* ──────────────────────────────────────────
   HELPERS
   ────────────────────────────────────────── */

const OFFLINE_HTML = `<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Liga de Maestros</title><style>body{background:#06090f;color:#f0f4f8;font-family:system-ui;display:grid;place-items:center;min-height:100vh;text-align:center;padding:20px}h1{font-size:2rem;color:#fbbf24}a{color:#38bdf8}</style></head><body><h1>🏆 Liga de Maestros</h1><p>Parece que no tienes conexion a internet.</p><p>Vuelve a intentarlo cuando tengas conexion.</p><a href="/">Reintentar</a></body></html>`;

/* El servidor es la autoridad sobre su Cache-Control. Si dice no-store o
   private, no se guarda: /cuenta llega con `no-store, private` y contiene el
   nombre y el email del usuario. */
function isCacheable(response) {
    if (!response || !response.ok) return false;
    const cc = (response.headers.get('Cache-Control') || '').toLowerCase();
    return !cc.includes('no-store') && !cc.includes('private') && !cc.includes('no-cache');
}

async function putWithTtl(cache, request, response, ttlMs) {
    if (!isCacheable(response)) return;
    const body = await response.clone().blob();
    const stamped = new Response(body, {
        status: response.status,
        statusText: response.statusText,
        headers: response.headers
    });
    stamped.headers.set('X-SW-Cached-At', String(Date.now()));
    await cache.put(request, stamped);
    void ttlMs;
}

/* Devuelve la entrada si no ha caducado; si ha caducado, la borra y devuelve
   null para que el llamante vaya a la red. */
async function matchFresh(request, ttlMs) {
    const cache = await caches.open(CACHE);
    const cached = await cache.match(request);
    if (!cached) return null;

    if (!ttlMs) return cached;

    const cachedAt = Number(cached.headers.get('X-SW-Cached-At') || 0);
    if (cachedAt && Date.now() - cachedAt > ttlMs) {
        await cache.delete(request);
        return null;
    }
    return cached;
}

/* ──────────────────────────────────────────
   ESTRATEGIAS DE CACHE
   ────────────────────────────────────────── */

async function cacheFirst(request) {
    const cached = await caches.match(request);
    if (cached) return cached;
    try {
        const response = await fetch(request);
        if (isCacheable(response)) {
            const cache = await caches.open(STATIC_CACHE);
            await putWithTtl(cache, request, response, null);
        }
        return response;
    } catch (error) {
        return new Response('Recurso no disponible offline', { status: 408 });
    }
}

/* Estatico sin ?v=: se sirve de red siempre que se pueda. Si el servidor dice
   no-store (que es lo normal aqui), no queda nada en la cache y la proxima vez
   se vuelve a pedir. Si la red falla, se sirve lo que hubiera. */
async function staticNoStore(request) {
    try {
        return await fetch(request);
    } catch (error) {
        const cached = await caches.match(request);
        if (cached) return cached;
        return new Response('Recurso no disponible offline', { status: 408 });
    }
}

async function networkFirst(request, cacheName = CACHE, ttlMs = null) {
    try {
        const response = await fetch(request);
        if (isCacheable(response)) {
            const cache = await caches.open(cacheName);
            await putWithTtl(cache, request, response, ttlMs);
        }
        return response;
    } catch {
        const cached = await matchFresh(request, ttlMs);
        if (cached) return cached;
        throw new Error('Offline');
    }
}

async function networkWithTimeout(request, timeoutMs = API_TIMEOUT_MS) {
    const timeout = new Promise((_, reject) =>
        setTimeout(() => reject(new Error('Timeout')), timeoutMs)
    );
    try {
        return await Promise.race([fetch(request), timeout]);
    } catch {
        /* Respuesta sintetica: solo se fabrica cuando la red falla de verdad o
           cuando el servidor lleva 30 s sin responder. Se marca como
           reintentable (504 + status network_error) para que la web vuelva a
           pedirlo en vez de dar la pagina por muerta, y nunca confunde con el
           503 cold_start que emite el backend al arrancar. */
        return new Response(JSON.stringify({
            status: 'network_error',
            message: 'Sin respuesta del servidor',
            retryable: true
        }), {
            status: 504,
            headers: {
                'Content-Type': 'application/json',
                'Cache-Control': 'no-store'
            }
        });
    }
}
