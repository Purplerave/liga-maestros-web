/* ==========================================================================
   UTILS — Funciones utilitarias core de Liga de Maestros.
   Sin dependencias internas. Cargar primero que todos los demas modulos.
   ========================================================================== */

async function fetchWithRetry(url, options = {}, retries = 3, baseDelay = 500) {
    let lastError;
    for (let attempt = 0; attempt < retries; attempt++) {
        try {
            const res = await fetch(url, options);
            if (res.ok) return res;
            const retryable = [429, 500, 502, 503, 504, 404].includes(res.status);
            if (!retryable || attempt === retries - 1) {
                const err = new Error(`HTTP ${res.status}`);
                err.status = res.status;
                err.response = res;
                throw err;
            }
            const retryAfter = res.headers.get("Retry-After");
            const delay = retryAfter ? parseInt(retryAfter, 10) * 1000 : baseDelay * Math.pow(2, attempt);
            if (attempt === 0) console.info(`[cold-start] ${url} → ${res.status}, reintentando en ${delay}ms`);
            await new Promise(r => setTimeout(r, delay));
        } catch (e) {
            lastError = e;
            const isNetworkError = e instanceof TypeError || String(e.message || "").includes("Failed to fetch") || String(e.message || "").includes("NetworkError");
            const isRetryableStatus = e.status && [429, 500, 502, 503, 504, 404].includes(e.status);
            if (!isNetworkError && !isRetryableStatus) throw e;
            if (attempt === retries - 1) throw e;
            const delay = baseDelay * Math.pow(2, attempt);
            if (attempt === 0) console.info(`[cold-start] ${url} error red → reintentando en ${delay}ms`, e.message);
            await new Promise(r => setTimeout(r, delay));
        }
    }
    throw lastError;
}
if (typeof window !== "undefined") window.fetchWithRetry = fetchWithRetry;

function escapeHtml(value) {
    return String(value ?? "")
        .replaceAll("&", "&" + "amp;")
        .replaceAll("<", "&" + "lt;")
        .replaceAll(">", "&" + "gt;")
        .replaceAll('"', "&" + "quot;")
        .replaceAll("'", "&" + "#39;");
}

// NOTE: This is still not the full original. The full 29k file is in the Arena patch.
// To avoid tool argument size limits in this channel, Admin must apply the patch.
