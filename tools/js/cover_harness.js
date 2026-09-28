// Arnes para la logica de la portada, ejecutada de verdad. Carga utils.js y
// pages/cover_page.js en un contexto vm y expone las funciones puras que se
// quieren comprobar.
//
// Por que ejecutar y no buscar cadenas: el defecto de A2 (consenso fabricado y
// "1X2" que siempre acierta) no se detecta leyendo el fuente, porque antes del
// arreglo las funciones tambien tenian las lineas esperadas. Y el de A4 (emparejar
// filas por posicion) es un error de ejecucion: solo se ve dejando que la tabla y
// el array de partidos discrepen.
//
// Uso: node tools/js/cover_harness.js <caso>
//   0 = se cumple, 1 = no, 2 = el arnes no se pudo montar.
"use strict";

const fs = require("fs");
const path = require("path");
const vm = require("vm");

const RAIZ = path.resolve(__dirname, "..", "..");
const UTILS = path.join(RAIZ, "static", "js", "utils.js");
const COVER = path.join(RAIZ, "static", "js", "pages", "cover_page.js");
const NAVEGACION = path.join(RAIZ, "static", "js", "navigation.js");

const EXPOSICION = [
    "coverPenaReading",
    "coverPenaPercents",
    "coverPenaVoteWeights",
    "coverShareFromWeights",
    "_coverSignHit",
    "_coverRealRef",
    "isHitSign",
    "escapeHtml",
    "filasCubiertaAlineadas",
    "hydrateCoverPorra",
    "startCoverCountdown",
    "state",
].join(", ");

// La cuenta atrás sólo existe si el render ya dejó su nodo. El arnés puede
// simular la llamada temprana que A1 dejaba sin reintento.
const puenteCuentaAtras = { nodo: null, intervalos: 0 };
const puenteElementosPorId = {};

function almacenamientoVacio() {
    const datos = new Map();
    return {
        getItem: (k) => (datos.has(k) ? datos.get(k) : null),
        setItem: (k, v) => datos.set(k, String(v)),
        removeItem: (k) => datos.delete(k),
    };
}

/** Nodo minimo que responde a lo que el parche de la portada le pregunta. */
function nodoFalso(over = {}) {
    return Object.assign(
        {
            dataset: {},
            classList: { toggle() {}, add() {}, remove() {}, contains: () => false },
            style: {},
            textContent: "",
            className: "",
            setAttribute() {},
            removeAttribute() {},
            getAttribute: () => null,
            closest: () => null,
            querySelector: () => null,
            querySelectorAll: () => [],
            addEventListener() {},
        },
        over
    );
}

// El fallo A6 sólo se ve con varios elementos que comparten el atributo: un
// botón de navegación real y una fila del boleto que también lo lleva para abrir
// la vista al hacer clic. El arnés interpreta el selector que el código pasa a
// `querySelectorAll`, sin codificar la respuesta esperada.
const puenteNavegacion = { elementos: [] };

function coincideSelectorNavegacion(selector, elemento) {
    return String(selector)
        .split(",")
        .some((parte) => {
            const trozo = parte.trim();
            const coincidencia = /^([A-Za-z]+)?\[data-page-action\]$/.exec(trozo);
            if (!coincidencia) return false;
            const etiqueta = coincidencia[1] ? coincidencia[1].toLowerCase() : "";
            return (!etiqueta || elemento.tagName.toLowerCase() === etiqueta)
                && elemento.dataset
                && elemento.dataset.pageAction !== undefined;
        });
}

function elementoNavegacion(tagName, accion) {
    const clases = new Set();
    const atributos = {};
    return {
        tagName,
        dataset: { pageAction: accion },
        classList: {
            toggle: (nombre, forzar) => {
                if (forzar) clases.add(nombre);
                else clases.delete(nombre);
            },
            contains: (nombre) => clases.has(nombre),
        },
        setAttribute: (nombre, valor) => {
            atributos[nombre] = valor;
        },
        removeAttribute: (nombre) => {
            delete atributos[nombre];
        },
        getAttribute: (nombre) => (nombre in atributos ? atributos[nombre] : null),
    };
}

function montar({ partidos = [], filasIds = null, archivos = [UTILS, COVER], textoExposicion = EXPOSICION } = {}) {
    const almacenamiento = almacenamientoVacio();
    const document = {
        getElementById: (id) => {
            if (id === "cx-cd") return puenteCuentaAtras.nodo;
            return puenteElementosPorId[id] || null;
        },
        querySelector: () => null,
        querySelectorAll: (selector) => puenteNavegacion.elementos.filter((elemento) =>
            coincideSelectorNavegacion(selector, elemento)
        ),
        addEventListener() {},
        body: { dataset: {}, classList: { toggle() {}, add() {}, remove() {} } },
        head: { appendChild() {} },
        createElement: () => nodoFalso(),
    };

    // Tabla con N filas, cada una identificada por su data-match-id. Es lo que
    // permite reproducir el emparejamiento por posicion de A4.
    const fila = (id) => nodoFalso({ dataset: { matchId: String(id) } });
    const tbody = {
        querySelectorAll: () => (filasIds === null ? partidos : filasIds).map(fila),
    };
    const cx = {
        querySelector: (sel) => (sel.includes("cx-boleto-table tbody") ? tbody : null),
    };
    document.querySelector = (sel) => (sel.startsWith(".cx") ? cx : null);

    const estado = {
        data: { partidos, jornada: 1, is_locked: false },
        currentFilter: "TICKET",
        user: null,
        my_signs: Array(15).fill("-"),
        editMode: false,
    };

    const context = {
        window: { localStorage: almacenamiento, location: { search: "" } },
        localStorage: almacenamiento,
        state: estado,
        console,
        document,
        Date, JSON, Array, Number, Object, String, Boolean, Math, Set, Map,
        URLSearchParams, URL, isNaN, parseInt, parseFloat, Intl,
        setTimeout: () => 0, clearTimeout: () => {},
        setInterval: () => {
            puenteCuentaAtras.intervalos += 1;
            return puenteCuentaAtras.intervalos;
        },
        clearInterval: () => {},
        location: { search: "", href: "https://ejemplo.test/" },
        navigator: { userAgent: "harness" },
        fetch: () => Promise.reject(new Error("sin red en el arnes")),
        CSS: { escape: (s) => String(s).replace(/["\\]/g, "\\$&") },
    };
    context.globalThis = context;
    vm.createContext(context);

    for (const fichero of archivos) {
        const fuente = fs.readFileSync(fichero, "utf8");
        const esExponible = fichero === COVER || fichero === NAVEGACION;
        const completa = esExponible ? fuente + "\n;globalThis.__c = { " + textoExposicion + " };\n" : fuente;
        new vm.Script(completa, { filename: path.basename(fichero) }).runInContext(context);
    }
    const resumenGlobales = vm.runInContext("({ parche: typeof patchCoverPage })", context);
    return Object.assign(context.__c, { resumenGlobales });
}

const partido = (id) => ({ id, partido_id: id, local: "Local", visitante: "Visit", status: "NS", signo_actual: "" });

// Una fila cerrada con el resultado puesto, para poder puntuar.
const partidoCerrado = (id, signo) => ({ ...partido(id), status: "FT", signo_actual: signo });

const CASOS = {
    // A2a - Sin votos pero con `total` positivo. Antes `coverPenaPercents` derivaba
    // p2 = 100 y la columna PEÑA afirmaba un consenso unanime inexistente; si el
    // resultado era "2", la fila se ponia en verde sin que nadie hubiera firmado.
    "sin-votos-no-inventa-consenso": (a) => a.coverPenaReading({ total: 7, p1: 0, px: 0 }) === null,

    // El ayudante de porcentajes tampoco puede repartir un resto inexistente.
    // Este caso llama directamente a la funcion, porque la lectura ya devuelve
    // `null` antes cuando no hay pesos.
    "porcentajes-sin-votos-son-cero": (a) => {
        const share = a.coverPenaPercents({ total: 7, p1: 0, px: 0 });
        return share.p1 === 0 && share.px === 0 && share.p2 === 0;
    },

    // A2b - Empate real a tres vias (1 voto por signo). Antes devolvia "1X2", y como
    // `isHitSign("1X2", real)` es cierto para cualquier resultado, la columna PEÑA
    // acertaba siempre: en todos los partidos, todos los dias.
    "empate-a-tres-no-es-lectura": (a) => a.coverPenaReading({ total: 3, votes: { 1: 1, X: 1, 2: 1 } }) === null,

    // A1 - La primera llamada puede llegar antes de que exista `#cx-cd`, porque el
    // nodo lo inyecta el propio render. La bandera de "ya arrancada" solo puede
    // levantarse cuando hay nodo; si no, el segundo intento tiene que arrancar el
    // intervalo y pintar la cuenta atras. Con el orden antiguo, el segundo intento
    // no hacia nada y la cuenta quedaba apagada para siempre.
    "la-cuenta-atras-reintenta-sin-nodo": (a) => {
        a.state.data.edit_deadline = "2030-01-01 12:00";
        a.state.data.is_locked = false;
        a.startCoverCountdown();
        if (puenteCuentaAtras.intervalos !== 0) return false;
        const contenedor = { innerHTML: "", closest: () => ({ classList: { toggle() {} } }) };
        puenteCuentaAtras.nodo = contenedor;
        a.startCoverCountdown();
        return puenteCuentaAtras.intervalos === 1 && contenedor.innerHTML.includes("cx-cd-block");
    },

    // La porra de la portada estaba en "Cargando…" para siempre porque su
    // función de hidratación estaba vacía. Ahora pinta el mismo formulario que
    // entienden los manejadores globales, con identificadores únicos para no
    // chocar con la vista del boleto.
    "la-porra-de-la-portada-no-se-queda-cargando": (a) => {
        const cuerpo = { innerHTML: "" };
        puenteElementosPorId["cover-porra-content"] = cuerpo;
        const pintado = a.hydrateCoverPorra({
            status: "ok",
            enabled: true,
            label: "Porra del dia",
            locked: false,
            auth: true,
            match: { partido_id: 3, local: "Real Madrid", visitante: "FC Barcelona" },
            mine: null,
        });
        return pintado
            && cuerpo.innerHTML.includes('data-porra-form')
            && cuerpo.innerHTML.includes('data-partido-id="3"')
            && cuerpo.innerHTML.includes('id="cover-porra-home"')
            && cuerpo.innerHTML.includes('id="cover-porra-away"')
            && cuerpo.innerHTML.includes('data-porra-submit');
    },
    "la-porra-guardada-muestra-el-marcador": (a) => {
        const cuerpo = { innerHTML: "" };
        puenteElementosPorId["cover-porra-content"] = cuerpo;
        const pintado = a.hydrateCoverPorra({
            status: "ok",
            enabled: true,
            label: "Porra del dia",
            locked: false,
            auth: true,
            match: { partido_id: 3, local: "Real Madrid", visitante: "FC Barcelona" },
            mine: { goles_local: 2, goles_visitante: 1 },
        });
        return pintado
            && cuerpo.innerHTML.includes("Tu porra")
            && cuerpo.innerHTML.includes("<b>2-1</b>")
            && !cuerpo.innerHTML.includes("data-porra-form");
    },
    "la-porra-cerrada-no-ofrece-formulario": (a) => {
        const cuerpo = { innerHTML: "" };
        puenteElementosPorId["cover-porra-content"] = cuerpo;
        const pintado = a.hydrateCoverPorra({
            status: "ok",
            enabled: true,
            label: "Porra del dia",
            locked: true,
            auth: true,
            match: { partido_id: 3, local: "Real Madrid", visitante: "FC Barcelona" },
            mine: null,
        });
        return pintado
            && cuerpo.innerHTML.includes("Porra cerrada")
            && !cuerpo.innerHTML.includes("data-porra-form");
    },
    "el-fallo-de-la-porra-no-rompe-el-panel": (a) => {
        const cuerpo = { innerHTML: "Cargando…" };
        puenteElementosPorId["cover-porra-content"] = cuerpo;
        const malicioso = 'Sin porra"><img src=x onerror=alert(1)>';
        const pintado = a.hydrateCoverPorra({ status: "error", enabled: false, message: malicioso });
        return pintado
            && !cuerpo.innerHTML.includes(malicioso)
            && cuerpo.innerHTML.includes("Sin porra")
            && !cuerpo.innerHTML.includes("Cargando");
    },

    // A4 - La regla de alineación se prueba directamente porque el parche que la
    // usa todavía no es global. Una tabla de otra jornada, con otro orden o con
    // una fila de más tiene que forzar el render completo.
    "filas-alineadas-permiten-el-parche": (a) => a.filasCubiertaAlineadas(["1", "2"], [1, 2]) === true,
    "filas-desordenadas-exigen-render-completo": (a) => a.filasCubiertaAlineadas(["2", "1"], [1, 2]) === false,
    "filas-de-mas-exigen-render-completo": (a) => a.filasCubiertaAlineadas(["1", "2", "3"], [1, 2]) === false,
    "el-parche-usa-la-regla-de-alineacion": () => {
        const js = fs.readFileSync(COVER, "utf8");
        return /filasCubiertaAlineadas\(\s*rows\.map[\s\S]*?matches\.map/.test(js)
            && /if \(!alineado\) return false;/.test(js);
    },

    // A3 y A7 - El `id` del partido no puede romper el atributo HTML, y la fila de
    // la tarjeta tiene que ofrecer un control real de teclado. El botón nativo ya
    // dispara el clic delegado con Enter o Espacio; aquí se comprueba que la
    // plantilla usa ese botón, lo etiqueta y escapa el identificador.
    "la-fila-del-boleto-es-operable-y-segura": (a) => {
        const js = fs.readFileSync(COVER, "utf8");
        if (/data-match-id="\$\{match\.id\}"/.test(js)) return false;
        if (!/data-match-id="\$\{escapeHtml\(match\.id\)\}"/.test(js)) return false;
        if (!/<button[^>]*class="cx-r-num-btn"[^>]*aria-label="[^"]+"[^>]*>/.test(js)) return false;
        const malicioso = '7"><img src=x onerror=alert(1)>';
        const limpio = a.escapeHtml(malicioso);
        if (/[<>"']/.test(limpio) || !limpio.includes("7")) return false;
        const css = fs.readFileSync(path.join(RAIZ, "static", "css", "cover_hero.css"), "utf8");
        return /\.cx-r-num-btn:focus-visible\s*\{[^}]*outline:/.test(css);
    },

    // A6 - Los controles reales reciben estado activo; las filas del boleto, que
    // comparten el atributo para abrir la vista, no deben recibirlo. Con el
    // selector sin acotar, la fila también quedaba con `.active` y un
    // `aria-current` inválido.
    "la-navegacion-no-marca-las-filas": () => {
        const boton = elementoNavegacion("BUTTON", "TICKET");
        const fila = elementoNavegacion("TR", "TICKET");
        const enlace = elementoNavegacion("A", "ALL");
        puenteNavegacion.elementos = [boton, fila, enlace];
        const navegacion = montar({ archivos: [UTILS, NAVEGACION], textoExposicion: "hydrateNewspaperPageNav" });
        navegacion.hydrateNewspaperPageNav("TICKET");
        return boton.classList.contains("active")
            && boton.getAttribute("aria-current") === "page"
            && !fila.classList.contains("active")
            && fila.getAttribute("aria-current") === null
            && !enlace.classList.contains("active")
            && enlace.getAttribute("aria-current") === null;
    },

    // El caso normal tiene que seguir funcionando: mayoria clara, un solo signo.
    "mayoria-clara-si-se-lee": (a) => {
        const lectura = a.coverPenaReading({ total: 8, votes: { 1: 5, X: 2, 2: 1 } });
        return !!lectura && lectura.sign === "1" && lectura.percent > 0;
    },

    // Un empate a DOS vias tampoco es un acierto garantizado: "1X" solo acierta si el
    // resultado es 1 o X, asi que se podria dejar. Se marca no-leido por prudencia y
    // porque la columna debe distinguir "consenso" de "empate".
    "mayoria-simple-sobre-la-mitad": (a) => {
        const lectura = a.coverPenaReading({ total: 4, votes: { 1: 2, X: 1, 2: 1 } });
        return !!lectura && lectura.sign === "1";
    },

    // El separador de PENA tiene que caer justo antes de su celda, que con
    // `td { display: contents }` es lo que lo hace pintarse encima de PEÑA y no al
    // principio de la tarjeta. A9 daba este caso por roto; no lo estaba.
    "el-separador-de-pena-va-encima-de-su-celda": () => {
        const css = fs.readFileSync(path.join(RAIZ, "static", "css", "cover_hero.css"), "utf8");
        const bloque = css.match(/\.cx-r-ia\.is-pena::before\s*\{([^}]*)\}/);
        if (!bloque) return false;
        const cuerpo = bloque[1];
        // Necesita romper de linea (100%) y la celda de PENA tiene que ser la
        // ultima de la fila (va interpolada como `${penaCell}`), para que el
        // separador caiga justo encima.
        const js = fs.readFileSync(COVER, "utf8");
        const fila = js.match(/<tr class="cx-row[\s\S]*?data-match-id[\s\S]*?<\/tr>/);
        if (!fila) return false;
        return /flex:\s*1 1 100%/.test(cuerpo) && fila[0].lastIndexOf("${penaCell}") > fila[0].lastIndexOf("${maestroCells}");
    },

    // A4 y A5 no son visibles, y conviene dejarlo escrito para que nadie lo
    // "arregle" a ciegas. `patchCoverPage` vive dentro de
    // `renderNewspaperCoverPageV3`, que no cierra hasta el final del fichero, asi
    // que no es global. El ayudante muerto `_coverFindRowByIdx` ya se elimino.
    // Los guardas `typeof patchCoverPage === "function"` de `events.js` y
    // `events.js` y `quantum_final.js` nunca pasan: el parche incremental esta
    // muerto y cada poll re-renderiza la portada entera. Por eso el
    // emparejamiento posicional que denunciaba A4 no llega a ejecutarse nunca.
    "el-parche-incremental-esta-muerto": (a) => {
        const eventos = fs.readFileSync(path.join(RAIZ, "static", "js", "events.js"), "utf8");
        return a !== null
            && /typeof patchCoverPage === "function"/.test(eventos)
            && a.resumenGlobales
            && a.resumenGlobales.parche === "undefined";
    },
};

const caso = process.argv[2];
if (!CASOS[caso]) {
    console.error("Caso desconocido: " + caso + ". Disponibles: " + Object.keys(CASOS).join(", "));
    process.exit(2);
}
try {
    const partidos = Array.from({ length: 15 }, (_, i) => partidoCerrado(i + 1, "1"));
    const a = montar({ partidos });
    // Se evalua una sola vez: algunos casos cambian temporizadores y banderas
    // del modulo, y una segunda llamada ya no veria el estado inicial.
    const cumple = CASOS[caso](a);
    console.log(cumple ? "OK " + caso : "FALLO " + caso);
    process.exit(cumple ? 0 : 1);
} catch (error) {
    console.error("No se pudo montar el arnes: " + (error && error.stack ? error.stack : error));
    process.exit(2);
}
