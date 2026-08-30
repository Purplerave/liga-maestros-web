/* ═══════════════════════════════════════════════════════════════
   SOUND MANAGER — Sistema de sonido opcional para la Liga de Maestros
   
   "El sonido es la mitad de la experiencia" — pero siempre
   respetamos al usuario: OFF por defecto, control total.
   ═══════════════════════════════════════════════════════════════ */

const SoundManager = {
    _enabled: false,
    _volume: 0.3,
    _initialized: false,
    _context: null,

    _storageKey: 'liga_maestros_sound',

    init() {
        if (this._initialized) return;
        this._initialized = true;

        // Leer preferencia guardada
        try {
            const saved = JSON.parse(localStorage.getItem(this._storageKey) || '{}');
            this._enabled = saved.enabled || false;
            this._volume = saved.volume || 0.3;
        } catch { this._enabled = false; }

        // Crear boton de control de sonido en la UI
        this._createToggleButton();
    },

    _createToggleButton() {
        const existing = document.getElementById('sound-toggle-btn');
        if (existing) return;

        const btn = document.createElement('button');
        btn.id = 'sound-toggle-btn';
        btn.type = 'button';
        btn.title = this._enabled ? 'Silenciar sonidos' : 'Activar sonidos';
        btn.setAttribute('aria-label', btn.title);
        btn.innerHTML = this._enabled ? '🔊' : '🔇';
        btn.style.cssText = `
            position: fixed;
            bottom: 16px;
            right: 16px;
            z-index: 999;
            width: 40px;
            height: 40px;
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 50%;
            background: rgba(6, 9, 15, 0.85);
            backdrop-filter: blur(12px);
            color: #94a3b8;
            font-size: 1.1rem;
            cursor: pointer;
            transition: all 0.2s ease;
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
        `;

        btn.addEventListener('mouseenter', () => {
            btn.style.transform = 'translateY(-2px)';
            btn.style.borderColor = 'rgba(56, 189, 248, 0.3)';
        });
        btn.addEventListener('mouseleave', () => {
            btn.style.transform = 'none';
            btn.style.borderColor = 'rgba(255, 255, 255, 0.1)';
        });

        btn.addEventListener('click', () => this.toggle());

        document.body.appendChild(btn);
    },

    _updateToggleButton() {
        const btn = document.getElementById('sound-toggle-btn');
        if (!btn) return;
        btn.innerHTML = this._enabled ? '🔊' : '🔇';
        btn.title = this._enabled ? 'Silenciar sonidos' : 'Activar sonidos';
        btn.setAttribute('aria-label', btn.title);
    },

    toggle() {
        this._enabled = !this._enabled;
        this._save();
        this._updateToggleButton();

        if (this._enabled) {
            // Reproducir un pequeño sonido de prueba
            this._beep(880, 0.1);
            this._showToast('🔊 Sonido activado');
        } else {
            this._showToast('🔇 Sonido desactivado');
        }
    },

    _save() {
        try {
            localStorage.setItem(this._storageKey, JSON.stringify({
                enabled: this._enabled,
                volume: this._volume
            }));
        } catch {}
    },

    _showToast(msg) {
        if (typeof showToast === 'function') {
            showToast(msg);
        }
    },

    // Generar tonos con Web Audio API (no requiere archivos)
    _beep(frequency = 520, duration = 0.15, type = 'sine') {
        if (!this._enabled) return;
        try {
            if (!this._context) {
                this._context = new (window.AudioContext || window.webkitAudioContext)();
            }
            if (this._context.state === 'suspended') {
                this._context.resume();
            }

            const osc = this._context.createOscillator();
            const gain = this._context.createGain();

            osc.type = type;
            osc.frequency.setValueAtTime(frequency, this._context.currentTime);

            gain.gain.setValueAtTime(this._volume, this._context.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.001, this._context.currentTime + duration);

            osc.connect(gain);
            gain.connect(this._context.destination);

            osc.start(this._context.currentTime);
            osc.stop(this._context.currentTime + duration);
        } catch { /* Silently fail — audio no es critico */ }
    },

    // Sonidos especificos
    playHit() { this._beep(880, 0.12, 'sine'); },

    playMiss() { this._beep(220, 0.2, 'sawtooth'); },

    playSave() {
        this._beep(660, 0.1, 'sine');
        setTimeout(() => this._beep(880, 0.15, 'sine'), 80);
    },

    playError() {
        this._beep(330, 0.15, 'square');
        setTimeout(() => this._beep(260, 0.2, 'square'), 120);
    },

    playTick() { this._beep(1200, 0.05, 'sine'); },

    playCountComplete() {
        this._beep(523, 0.1, 'sine');
        setTimeout(() => this._beep(659, 0.1, 'sine'), 80);
        setTimeout(() => this._beep(784, 0.15, 'sine'), 160);
    },

    playNotification() {
        this._beep(800, 0.08, 'sine');
        setTimeout(() => this._beep(1000, 0.1, 'sine'), 100);
    },

    playPageEnter() { this._beep(600, 0.05, 'sine'); },

    playCelebration() {
        [523, 587, 659, 784, 880, 1047].forEach((freq, i) => {
            setTimeout(() => this._beep(freq, 0.12, 'sine'), i * 60);
        });
    },

    isEnabled() { return this._enabled; }
};

// Inicializar automaticamente cuando el DOM este listo
document.addEventListener('DOMContentLoaded', () => {
    SoundManager.init();
});

if (typeof window !== 'undefined') {
    window.SoundManager = SoundManager;
}
