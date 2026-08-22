/* ==========================================================================
   COMMAND PALETTE — Navegacion instantanea por teclado (Ctrl/Cmd + K).
   Mejora progresiva: si este modulo no carga, la app funciona igual.
   Dependencias: utils.js (qs, escapeHtml), state.js, navigation.js
   ========================================================================== */

const CommandPalette = {
    _root: null,
    _input: null,
    _list: null,
    _items: [],
    _filtered: [],
    _active: 0,
    _lastFocus: null,
    _open: false,

    init() {
        if (this._root) return;
        this._build();
        this._bindGlobalKeys();
    },

    /* ---------- Fuente de comandos ---------- */
    commands() {
        const pages = [
            ["ALL", "Portada", "Resumen de la jornada", "📰"],
            ["TICKET", "Quiniela", "Rellena y guarda tus 15 signos", "🎫"],
            ["LIVE", "Directo", "Marcadores en vivo", "🔴"],
            ["STANDINGS", "Ligas", "Clasificaciones Primera y Segunda", "📊"],
            ["SNAKE", "Juegos", "Snake Gol, Arkanoid e Invaders", "🎮"],
            ["CONTEST", "La Peña", "Rankings, premios y palmares", "🏆"],
            ["QUIZ", "Quiz", "Preguntas de la jornada", "❓"],
            ["NEWS", "Última hora", "Titulares del radar de prensa", "🗞️"],
        ];

        const list = pages.map(([page, title, desc, icon]) => ({
            id: `page:${page}`,
            group: "Ir a",
            title,
            desc,
            icon,
            run: () => openNewspaperPage(page),
        }));

        list.push({
            id: "action:profile",
            group: "Acciones",
            title: "Mi perfil",
            desc: "Evolucion, rachas y palmares personal",
            icon: "👤",
            run: () => openProfileView(),
        });
        list.push({
            id: "action:refresh",
            group: "Acciones",
            title: "Actualizar datos",
            desc: "Vuelve a pedir la jornada al servidor",
            icon: "🔄",
            shortcut: "R",
            run: () => (typeof refreshData === "function" ? refreshData() : null),
        });
        list.push({
            id: "action:save",
            group: "Acciones",
            title: "Guardar quiniela",
            desc: "Envia tus signos actuales",
            icon: "💾",
            shortcut: "S",
            run: () => (typeof savePredictions === "function" ? savePredictions() : null),
        });
        list.push({
            id: "action:share",
            group: "Acciones",
            title: "Compartir quiniela",
            desc: "Copia o comparte tu boleto",
            icon: "🔗",
            run: () => (typeof shareTicket === "function" ? shareTicket() : null),
        });
        list.push({
            id: "action:sound",
            group: "Acciones",
            title: "Alternar sonido",
            desc: "Activa o silencia los efectos",
            icon: "🔊",
            run: () => document.getElementById("sound-toggle-btn")?.click(),
        });
        list.push({
            id: "action:top",
            group: "Acciones",
            title: "Volver arriba",
            desc: "Scroll al inicio de la vista",
            icon: "⬆️",
            run: () => window.scrollTo({ top: 0, behavior: "smooth" }),
        });

        // Comando oculto de admin: fuerza la actualizacion completa del
        // servidor (clasificaciones, agenda del dia, directo y quiniela).
        if (
            state?.user?.is_admin
            || state?.data?.is_admin
        ) {
            list.push({
                id: "admin:refresh-all",
                group: "Admin",
                title: "Actualizar TODO (servidor)",
                desc: "Clasificaciones, agenda, directo y quiniela ahora mismo",
                icon: "⚡",
                run: () => (typeof adminRefreshAll === "function" ? adminRefreshAll() : null),
            });
        }

        const jornadas = Array.isArray(state?.data?.jornadas) ? state.data.jornadas : [];
        jornadas.slice(-12).reverse().forEach(jornada => {
            list.push({
                id: `jornada:${jornada}`,
                group: "Jornadas",
                title: `Jornada ${jornada}`,
                desc: String(jornada) === String(state?.data?.jornada || "") ? "Jornada actual" : "Cambiar de jornada",
                icon: "📅",
                run: () => (typeof changeJornada === "function" ? changeJornada(String(jornada)) : null),
            });
        });

        list.push({
            id: "legal:privacy",
            group: "Legal",
            title: "Privacidad",
            desc: "Como tratamos tus datos",
            icon: "🛡️",
            run: () => { window.location.href = "/privacidad"; },
        });
        list.push({
            id: "legal:cookies",
            group: "Legal",
            title: "Cookies",
            desc: "Politica de cookies",
            icon: "🍪",
            run: () => { window.location.href = "/cookies"; },
        });

        return list;
    },

    /* ---------- Construccion del DOM ---------- */
    _build() {
        const root = document.createElement("div");
        root.className = "cmdk-backdrop";
        root.hidden = true;
        root.innerHTML = `
            <div class="cmdk-panel" role="dialog" aria-modal="true" aria-label="Paleta de comandos">
                <div class="cmdk-search">
                    <span class="cmdk-search-icon" aria-hidden="true">⌘</span>
                    <input class="cmdk-input" type="text" role="combobox" aria-expanded="true"
                           aria-controls="cmdk-list" aria-autocomplete="list" autocomplete="off"
                           spellcheck="false" placeholder="Busca una vista, jornada o accion..." />
                    <span class="cmdk-hint"><span class="cmdk-kbd">Esc</span></span>
                </div>
                <ul class="cmdk-list" id="cmdk-list" role="listbox" aria-label="Resultados"></ul>
            </div>`;
        document.body.appendChild(root);

        this._root = root;
        this._input = root.querySelector(".cmdk-input");
        this._list = root.querySelector(".cmdk-list");

        root.addEventListener("mousedown", event => {
            if (event.target === root) this.close();
        });
        this._input.addEventListener("input", () => this._filter(this._input.value));
        this._input.addEventListener("keydown", event => this._onInputKey(event));
        this._list.addEventListener("click", event => {
            const item = event.target.closest("[data-cmdk-index]");
            if (!item) return;
            this._runIndex(Number.parseInt(item.dataset.cmdkIndex, 10));
        });
    },

    _bindGlobalKeys() {
        document.addEventListener("keydown", event => {
            const isPaletteKey = (event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k";
            if (isPaletteKey) {
                event.preventDefault();
                this.toggle();
                return;
            }
            if (event.key === "Escape" && this._open) {
                event.preventDefault();
                this.close();
            }
        });
    },

    _isTypingTarget(el) {
        if (!el) return false;
        return el.matches("input, textarea, select, [contenteditable='true']");
    },

    /* ---------- Estado abierto/cerrado ---------- */
    toggle() {
        this._open ? this.close() : this.open();
    },

    open() {
        this.init();
        if (this._open) return;
        this._open = true;
        this._lastFocus = document.activeElement;
        this._items = this.commands();
        this._root.hidden = false;
        // Forzar reflow para que la transicion se aplique
        void this._root.offsetWidth;
        this._root.classList.add("is-open");
        this._input.value = "";
        this._filter("");
        this._input.focus();
    },

    close() {
        if (!this._open) return;
        this._open = false;
        this._root.classList.remove("is-open");
        const finish = () => { if (!this._open) this._root.hidden = true; };
        setTimeout(finish, 160);
        if (this._lastFocus && typeof this._lastFocus.focus === "function") this._lastFocus.focus();
    },

    /* ---------- Filtro fuzzy ligero ---------- */
    _score(query, text) {
        const haystack = text.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");
        const needle = query.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");
        if (!needle) return 1;
        const direct = haystack.indexOf(needle);
        if (direct === 0) return 100;
        if (direct > 0) return 60 - Math.min(direct, 30);
        // subsecuencia
        let idx = 0;
        for (const char of needle) {
            idx = haystack.indexOf(char, idx);
            if (idx === -1) return 0;
            idx += 1;
        }
        return 20;
    },

    _filter(query) {
        const trimmed = String(query || "").trim();
        this._filtered = this._items
            .map(item => ({ item, score: this._score(trimmed, `${item.title} ${item.desc || ""}`) }))
            .filter(entry => entry.score > 0)
            .sort((a, b) => b.score - a.score)
            .map(entry => entry.item);
        this._active = 0;
        this._render(trimmed);
    },

    _highlight(text, query) {
        const safe = escapeHtml(text);
        if (!query) return safe;
        const pos = text.toLowerCase().indexOf(query.toLowerCase());
        if (pos === -1) return safe;
        const before = escapeHtml(text.slice(0, pos));
        const match = escapeHtml(text.slice(pos, pos + query.length));
        const after = escapeHtml(text.slice(pos + query.length));
        return `${before}<mark>${match}</mark>${after}`;
    },

    _render(query) {
        if (!this._filtered.length) {
            this._list.innerHTML = `<li class="cmdk-empty">Sin resultados para "${escapeHtml(query)}"</li>`;
            return;
        }
        let html = "";
        let lastGroup = "";
        this._filtered.forEach((item, index) => {
            if (item.group !== lastGroup) {
                lastGroup = item.group;
                html += `<li class="cmdk-group-label" role="presentation">${escapeHtml(item.group)}</li>`;
            }
            const shortcut = item.shortcut ? `<span class="cmdk-item-shortcut">${escapeHtml(item.shortcut)}</span>` : "<span></span>";
            html += `
                <li role="presentation">
                    <button type="button" role="option" class="cmdk-item${index === this._active ? " is-active" : ""}"
                            aria-selected="${index === this._active}" data-cmdk-index="${index}" data-no-ripple="true">
                        <span class="cmdk-item-icon" aria-hidden="true">${escapeHtml(item.icon || "•")}</span>
                        <span class="cmdk-item-body">
                            <span class="cmdk-item-title">${this._highlight(item.title, query)}</span>
                            ${item.desc ? `<span class="cmdk-item-desc">${escapeHtml(item.desc)}</span>` : ""}
                        </span>
                        ${shortcut}
                    </button>
                </li>`;
        });
        this._list.innerHTML = html;
    },

    _move(delta) {
        if (!this._filtered.length) return;
        this._active = (this._active + delta + this._filtered.length) % this._filtered.length;
        this._list.querySelectorAll(".cmdk-item").forEach((el, index) => {
            const active = index === this._active;
            el.classList.toggle("is-active", active);
            el.setAttribute("aria-selected", String(active));
            if (active) el.scrollIntoView({ block: "nearest" });
        });
    },

    _runIndex(index) {
        const item = this._filtered[index];
        if (!item) return;
        this.close();
        try {
            item.run();
        } catch (error) {
            console.warn("[cmdk] no se pudo ejecutar el comando", error);
        }
    },

    _onInputKey(event) {
        if (event.key === "ArrowDown") {
            event.preventDefault();
            this._move(1);
        } else if (event.key === "ArrowUp") {
            event.preventDefault();
            this._move(-1);
        } else if (event.key === "Enter") {
            event.preventDefault();
            this._runIndex(this._active);
        } else if (event.key === "Home") {
            event.preventDefault();
            this._active = 0;
            this._move(0);
        } else if (event.key === "End") {
            event.preventDefault();
            this._active = this._filtered.length - 1;
            this._move(0);
        }
    },
};

window.CommandPalette = CommandPalette;
