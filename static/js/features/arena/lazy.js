/** Lazy match rendering with IntersectionObserver. */

let _matchIntersectionObserver = null;

export function initLazyMatchRendering() {
    if (_matchIntersectionObserver) return;
    _matchIntersectionObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const el = entry.target;
                const matchData = el.dataset.matchJson;
                if (matchData) {
                    try {
                        const match = JSON.parse(matchData);
                        el.innerHTML = renderMatchCard(match);
                        el.classList.add("match-loaded");
                    } catch {}
                }
                _matchIntersectionObserver.unobserve(el);
            }
        });
    }, { rootMargin: "200px" });
}

export function lazyMatchPlaceholder(match) {
    const div = document.createElement("div");
    div.className = "match-card match-lazy";
    div.dataset.matchJson = JSON.stringify(match);
    div.style.minHeight = "120px";
    return div;
}

export function destroyLazyObserver() {
    if (_matchIntersectionObserver) {
        _matchIntersectionObserver.disconnect();
        _matchIntersectionObserver = null;
    }
}