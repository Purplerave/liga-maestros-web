/* ==========================================================================
   UTILS — Funciones utilitarias core de Liga de Maestros.
   Sin dependencias internas. Cargar primero que todos los demas modulos.
   ========================================================================== */

async function fetchWithRetry(url, options = {}, retries = 3, baseDelay = 500) {
    let lastError;
    for (let attempt = 0; attempt <= retries; attempt++) {
        try {
            const res = await fetch(url, options);
            if (res.ok) return res;
            const retryable = [429, 500, 502, 503, 504, 404].includes(res.status);
            if (!retryable || attempt === retries) return res;
            const retryAfter = res.headers.get("Retry-After");
            const delay = retryAfter ? parseInt(retryAfter, 10) * 1000 : baseDelay * Math.pow(2, attempt);
            await new Promise(r => setTimeout(r, delay));
            continue;
        } catch (err) {
            lastError = err;
            const isNetwork = err instanceof TypeError && (err.message.includes("Failed to fetch") || err.message.includes("NetworkError") || err.message.includes("network"));
            if (!isNetwork || attempt === retries) throw err;
            await new Promise(r => setTimeout(r, baseDelay * Math.pow(2, attempt)));
        }
    }
    if (lastError) throw lastError;
}

if (typeof window !== "undefined") window.fetchWithRetry = fetchWithRetry;

// NOTE: This is a temporary incomplete version. Full content being restored in next commits.
