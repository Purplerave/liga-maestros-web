/* ═══════════════════════════════════════════════════════════════
   CONFETTI — Sistema de celebraciones para la Liga de Maestros
   
   Version: Golden Edition — cada acierto merece su fiesta.
   ═══════════════════════════════════════════════════════════════ */

const CONFETTI_COLORS = [
    '#fbbf24', '#f59e0b', '#38bdf8', '#22c55e',
    '#ef4444', '#a78bfa', '#f472b6', '#34d399',
    '#fb923c', '#e879f9', '#2dd4bf', '#facc15'
];

const CONFETTI_SHAPES = ['square', 'circle', 'triangle'];

let confettiQueue = [];
let confettiRunning = false;

function launchConfetti({
    count = 60,
    spread = 80,
    origin = { x: 0.5, y: 0.3 },
    colors = CONFETTI_COLORS,
    duration = 3000,
    particleSize = 10,
    burst = false
} = {}) {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

    const container = document.createElement('div');
    container.className = 'confetti-container';
    container.style.pointerEvents = 'none';
    document.body.appendChild(container);

    const particles = burst ? count * 3 : count;
    const centerX = origin.x * window.innerWidth;
    const centerY = origin.y * window.innerHeight;

    for (let i = 0; i < particles; i++) {
        const piece = document.createElement('div');
        const color = colors[Math.floor(Math.random() * colors.length)];
        const shape = CONFETTI_SHAPES[Math.floor(Math.random() * CONFETTI_SHAPES.length)];
        const size = particleSize * (0.5 + Math.random() * 1);
        const angle = (Math.random() - 0.5) * spread * 2;
        const velocity = 300 + Math.random() * 600;
        const delay = Math.random() * 0.5;
        const rotation = Math.random() * 720;

        piece.className = `confetti-piece ${shape}`;
        piece.style.cssText = `
            left: ${centerX}px;
            top: ${centerY}px;
            width: ${shape === 'triangle' ? '0' : size}px;
            height: ${shape === 'triangle' ? '0' : size}px;
            background: ${shape !== 'triangle' ? color : 'transparent'};
            color: ${color};
            border-bottom-color: ${color};
            animation-delay: ${delay}s;
            animation-duration: ${duration / 1000 + Math.random()}s;
            transform: rotate(${rotation}deg);
        `;

        // Custom drift via CSS custom property
        piece.style.setProperty('--drift-x', `${Math.sin(angle * Math.PI / 180) * 150}px`);
        container.appendChild(piece);
    }

    // Limpiar despues de la animacion
    setTimeout(() => {
        if (container.parentNode) container.remove();
    }, duration + 1000);
}

function launchBigConfetti() {
    launchConfetti({
        count: 120,
        spread: 120,
        duration: 4000,
        burst: true
    });
}

function launchHitConfetti() {
    launchConfetti({
        count: 40,
        spread: 60,
        origin: { x: 0.5, y: 0.4 },
        duration: 2000,
        particleSize: 8
    });
}

function launchMilestoneConfetti(milestone) {
    const intensity = milestone >= 15 ? 150 : milestone >= 10 ? 100 : 60;
    launchConfetti({
        count: intensity,
        spread: 100,
        duration: 3500,
        burst: true,
        colors: ['#fbbf24', '#f59e0b', '#38bdf8', '#22c55e', '#a78bfa']
    });
}

/* ──────────────────────────────────────────
   ESTRELLAS SEGUIDORAS EN HOVER (mini confetti)
   ────────────────────────────────────────── */

function sparkleAt(x, y, color = '#fbbf24') {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

    const sparkles = 6;
    for (let i = 0; i < sparkles; i++) {
        const spark = document.createElement('div');
        const size = 4 + Math.random() * 4;
        const angle = (Math.PI * 2 * i) / sparkles + (Math.random() - 0.5) * 0.5;
        const dist = 20 + Math.random() * 30;

        spark.style.cssText = `
            position: fixed;
            left: ${x}px;
            top: ${y}px;
            width: ${size}px;
            height: ${size}px;
            border-radius: 50%;
            background: ${color};
            pointer-events: none;
            z-index: 9999;
            opacity: 1;
            transition: all 0.6s cubic-bezier(0.16, 1, 0.3, 1);
            transform: translate(0, 0) scale(1);
        `;

        document.body.appendChild(spark);

        requestAnimationFrame(() => {
            spark.style.transform = `translate(${Math.cos(angle) * dist}px, ${Math.sin(angle) * dist}px) scale(0)`;
            spark.style.opacity = '0';
        });

        setTimeout(() => {
            if (spark.parentNode) spark.remove();
        }, 700);
    }
}

/* ──────────────────────────────────────────
   EXPORT
   ────────────────────────────────────────── */

if (typeof window !== 'undefined') {
    window.launchConfetti = launchConfetti;
    window.launchBigConfetti = launchBigConfetti;
    window.launchHitConfetti = launchHitConfetti;
    window.launchMilestoneConfetti = launchMilestoneConfetti;
    window.sparkleAt = sparkleAt;
}
