/* ═══════════════════════════════════════════════════════════════
   ANIMATED COUNTERS — Contadores que dan vida a las estadisticas
   
   Cuando un numero aparece en pantalla, cuenta desde 0 hasta su
   valor con una animacion fluida. Engagement instantaneo.
   ═══════════════════════════════════════════════════════════════ */

function animateCounter(el, target, { duration = 800, prefix = '', suffix = '', decimals = 0 } = {}) {
    if (!el) return;
    
    // Si ya hay una animacion en curso, cancelarla
    if (el._counterAnim) {
        cancelAnimationFrame(el._counterAnim);
    }

    const start = performance.now();
    const startValue = 0;
    const diff = target - startValue;

    function update(now) {
        const elapsed = now - start;
        const progress = Math.min(elapsed / duration, 1);
        
        // Ease out cubic
        const eased = 1 - Math.pow(1 - progress, 3);
        const current = startValue + diff * eased;
        
        el.textContent = prefix + current.toFixed(decimals) + suffix;
        
        if (progress < 1) {
            el._counterAnim = requestAnimationFrame(update);
        } else {
            el.textContent = prefix + target.toLocaleString('es-ES', {
                minimumFractionDigits: decimals,
                maximumFractionDigits: decimals
            }) + suffix;
            el._counterAnim = null;
        }
    }

    el._counterAnim = requestAnimationFrame(update);
}

// Observador de interseccion para animar cuando el elemento es visible
function initAnimatedCounters(container = document) {
    const counters = container.querySelectorAll('[data-animate-count]');
    if (!counters.length) return;

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const el = entry.target;
                const target = parseFloat(el.dataset.animateCount);
                const duration = parseInt(el.dataset.animateDuration || '800', 10);
                const prefix = el.dataset.animatePrefix || '';
                const suffix = el.dataset.animateSuffix || '';
                const decimals = parseInt(el.dataset.animateDecimals || '0', 10);

                if (!isNaN(target)) {
                    animateCounter(el, target, { duration, prefix, suffix, decimals });
                }
                observer.unobserve(el);
            }
        });
    }, { threshold: 0.3 });

    counters.forEach(el => observer.observe(el));
}

// Aplicar a elementos que se renderizan dinamicamente
document.addEventListener('DOMContentLoaded', () => {
    initAnimatedCounters();
    
    // Observar cambios en el DOM para nuevos contadores
    const observer = new MutationObserver(() => {
        initAnimatedCounters();
    });
    const targetNode = document.getElementById('matches-body') || document.body;
    if (targetNode) {
        observer.observe(targetNode, { childList: true, subtree: true });
    }
});

if (typeof window !== 'undefined') {
    window.animateCounter = animateCounter;
    window.initAnimatedCounters = initAnimatedCounters;
}
