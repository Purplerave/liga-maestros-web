/* Onboarding modal — shows once on first visit, then remembers via localStorage */
(function () {
    "use strict";

    var STORAGE_KEY = "lm_onboarding_done";

    function shouldShow() {
        try {
            return !localStorage.getItem(STORAGE_KEY);
        } catch (e) {
            return true;
        }
    }

    function dismiss() {
        try {
            localStorage.setItem(STORAGE_KEY, "1");
        } catch (e) { /* ignore */ }
        var overlay = document.querySelector(".onboarding-overlay");
        if (overlay) {
            overlay.classList.add("onboarding-fade-out");
            setTimeout(function () {
                overlay.remove();
            }, 300);
        }
    }

    var steps = [
        {
            icon: "\u26bd",
            title: "\u00bfPuedes ganar a la IA?",
            body: "15 partidos. La Pe\u00f1a contra GPT, Claude, Gemini y Grok. Firma tu 1X2 y demuestra que los humanos todav\u00eda podemos ganar."
        },
        {
            icon: "\ud83d\udcdd",
            title: "Firma tu quiniela",
            body: "Elige 1, X o 2 para cada partido de la jornada. Una quiniela simple y ya. Guarda antes de que empiecen los partidos \u2014 \u00a1no se puede cambiar despu\u00e9s!"
        },
        {
            icon: "\ud83c\udfc6",
            title: "Compite y sube en el ranking",
            body: "Cada acierto te da puntos. Compite contra los Maestros IA, contra la media de La Pe\u00f1a, y contra tus amigos. Comparte tus resultados y mira qui\u00e9n acierta m\u00e1s."
        }
    ];

    var currentStep = 0;

    function renderStep() {
        var step = steps[currentStep];
        var modal = document.querySelector(".onboarding-modal");
        if (!modal) return;

        var progressDots = "";
        for (var i = 0; i < steps.length; i++) {
            progressDots += '<span class="onboarding-dot' + (i === currentStep ? " active" : "") + '"></span>';
        }

        modal.innerHTML =
            '<div class="onboarding-icon">' + step.icon + '</div>' +
            '<h2>' + step.title + '</h2>' +
            '<p>' + step.body + '</p>' +
            '<div class="onboarding-progress">' + progressDots + '</div>' +
            '<div class="onboarding-actions">' +
                (currentStep > 0
                    ? '<button class="onboarding-back" type="button">Atr\u00e1s</button>'
                    : '<span></span>') +
                (currentStep < steps.length - 1
                    ? '<button class="onboarding-next primary-btn" type="button">Siguiente</button>'
                    : '<button class="onboarding-next primary-btn" type="button">\u00a1Empezar!</button>') +
            '</div>' +
            '<button class="onboarding-skip" type="button">Saltar</button>';

        // Bind events
        var nextBtn = modal.querySelector(".onboarding-next");
        var backBtn = modal.querySelector(".onboarding-back");
        var skipBtn = modal.querySelector(".onboarding-skip");

        if (nextBtn) {
            nextBtn.addEventListener("click", function () {
                if (currentStep < steps.length - 1) {
                    currentStep++;
                    renderStep();
                } else {
                    dismiss();
                }
            });
        }
        if (backBtn) {
            backBtn.addEventListener("click", function () {
                if (currentStep > 0) {
                    currentStep--;
                    renderStep();
                }
            });
        }
        if (skipBtn) {
            skipBtn.addEventListener("click", dismiss);
        }

        // Focus the primary button for accessibility
        var focusTarget = nextBtn || skipBtn;
        if (focusTarget) focusTarget.focus();
    }

    function show() {
        var overlay = document.createElement("div");
        overlay.className = "onboarding-overlay";
        overlay.setAttribute("role", "dialog");
        overlay.setAttribute("aria-label", "Bienvenido a Liga de Maestros");
        overlay.innerHTML = '<div class="onboarding-modal"></div>';
        document.body.appendChild(overlay);

        // Close on overlay click (outside modal)
        overlay.addEventListener("click", function (e) {
            if (e.target === overlay) dismiss();
        });

        // Close on Escape
        overlay.addEventListener("keydown", function (e) {
            if (e.key === "Escape") dismiss();
        });

        renderStep();
    }

    // Init after DOM is ready
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", function () {
            if (shouldShow()) show();
        });
    } else {
        if (shouldShow()) show();
    }
})();
