// Arnes minimo para ejercitar la logica de borradores de state.js fuera del
// navegador. Ejecuta utils.js y state.js reales dentro de un contexto vm con los
// stubs justos (localStorage, window, state) y expone las funciones internas.
//
// Motivo: los tests de este repo sobre el front solo hacen busquedas de cadenas
// sobre el fuente, y una busqueda no puede notar que `draft || serverSigns`
// dejaba al servidor por detras del borrador. Aqui se ejecuta de verdad, con la
// misma `sameSigns` que usa la pagina.
//
// Uso: node tools/js/state_draft_harness.js <caso>
//   0 = el caso se cumple, 1 = no se cumple, 2 = el arnes no se pudo montar.
"use strict";

const fs = require("fs");
const path = require("path");
const vm = require("vm");

const RAIZ = path.resolve(__dirname, "..", "..");
const UTILS = path.join(RAIZ, "static", "js", "utils.js");
const STATE = path.join(RAIZ, "static", "js", "state.js");

const CLAVE = (owner, jornada) => `liga_maestros_borrador_${owner}_${jornada}`;

// Se engancha al final de state.js para sacar de su ambito lexico las funciones
// que hay que poder llamar. Sin esto el harness solo podria dareload().
const EXPOSICION =
    "\n;globalThis.__a = { readDraft, persistDraft, hydrateUserSigns, sameSigns, draftKey, clearDraft, state };\n";

function almacenamientoVacio() {
    const datos = new Map();
    return {
        getItem: (k) => (datos.has(k) ? datos.get(k) : null),
        setItem: (k, v) => datos.set(k, String(v)),
        removeItem: (k) => datos.delete(k),
        _datos: datos,
    };
}

function montar({ signosServidor, userId = "u1", jornada = 1 }) {
    const almacenamiento = almacenamientoVacio();
    const context = {
        window: { localStorage: almacenamiento, location: { search: "" } },
        localStorage: almacenamiento,
        console,
        Date,
        JSON,
        Array,
        Number,
        Object,
        String,
        Boolean,
        Math,
        URLSearchParams,
        URL,
        isNaN,
        parseInt,
        setTimeout: () => 0,
        clearTimeout: () => {},
        document: {
            addEventListener() {},
            querySelector: () => null,
            querySelectorAll: () => [],
            body: { classList: { toggle() {}, add() {}, remove() {}, contains: () => false } },
        },
        location: { search: "", href: "https://ejemplo.test/" },
        navigator: { userAgent: "harness" },
        fetch: () => Promise.reject(new Error("sin red en el arnes")),
    };
    context.globalThis = context;
    vm.createContext(context);

    for (const fichero of [UTILS, STATE]) {
        const fuente = fs.readFileSync(fichero, "utf8");
        // Solo state.js se expone; utils.js se carga por sus globales (sameSigns).
        const completa = fichero === STATE ? fuente + EXPOSICION : fuente;
        new vm.Script(completa, { filename: path.basename(fichero) }).runInContext(context);
    }

    const a = context.__a;
    // `state` es un `const` propio de state.js: el del sandbox queda sombreado, asi
    // que hay que sembrarlo a traves de la exposicion, no desde fuera.
    a.state.user = userId ? { id: userId } : null;
    a.state.jornada = jornada;
    a.state.data = { jornada, predicciones_actuales: {} };
    a.state.my_signs = Array(15).fill("-");
    a.state.server_signs = signosServidor.slice();
    a.state.editMode = false;
    a.state.draftDirty = false;
    if (userId) a.state.data.predicciones_actuales[userId] = { signos: signosServidor.slice() };

    return Object.assign(a, { almacenamiento });
}

function borrador({ signos, edadHoras }) {
    return {
        jornada: 1,
        signos,
        updated_at: new Date(Date.now() - edadHoras * 3600 * 1000).toISOString(),
    };
}

const SUFIJOS = ["1", "X", "2"];

const CASOS = {
    // Un draft de hace 48 h tiene que ignorarse: casi seguro esta obsoleto y
    // pisar con el el boleto real es perder el trabajo del usuario.
    "borrador-obsoleto-se-ignora": (a) => {
        a.almacenamiento.setItem(CLAVE("u1", 1), JSON.stringify(borrador({ signos: Array(15).fill("2"), edadHoras: 48 })));
        return a.readDraft() === null && !a.almacenamiento.getItem(CLAVE("u1", 1));
    },

    // Uno de hace un minuto si se restaura: no hay que tirar trabajo reciente.
    "borrador-reciente-se-restaura": (a) => {
        const signos = Array(15).fill("2");
        a.almacenamiento.setItem(CLAVE("u1", 1), JSON.stringify(borrador({ signos, edadHoras: 0.02 })));
        const leido = a.readDraft();
        return Array.isArray(leido) && leido[0] === "2";
    },

    // La regresion: con el boleto completo en el servidor, un draft distinto
    // pierde. Antes ganaba `draft || serverSigns` y el boleto se veia como
    // "cambios sin guardar"; el primer clic reenviaba el draft y lo machacaba.
    "el-servidor-gana-al-borrador": (a) => {
        a.almacenamiento.setItem(CLAVE("u1", 1), JSON.stringify(borrador({ signos: Array(15).fill("2"), edadHoras: 1 })));
        a.hydrateUserSigns();
        return (
            a.sameSigns(a.state.my_signs, a.state.server_signs) === true &&
            a.state.draftDirty === false &&
            a.state.editMode === false
        );
    },

    // Un draft que coincide con el servidor no es "sucio": no hay nada que guardar.
    "borrador-igual-al-servidor-no-esta-sucio": (a) => {
        a.almacenamiento.setItem(CLAVE("u1", 1), JSON.stringify(borrador({ signos: a.state.server_signs.slice(), edadHoras: 1 })));
        a.hydrateUserSigns();
        return a.state.draftDirty === false;
    },

    // Con el boleto del servidor incompleto el draft si manda: son cambios
    // reales sin guardar y perderlos seria el bug opuesto.
    "borrador-parcial-se-respeta": (a) => {
        const vacio = Array(15).fill("-");
        a.state.server_signs = vacio.slice();
        a.state.data.predicciones_actuales.u1 = { signos: vacio.slice() };
        a.almacenamiento.setItem(CLAVE("u1", 1), JSON.stringify(borrador({ signos: Array(15).fill("2"), edadHoras: 1 })));
        a.hydrateUserSigns();
        return a.state.my_signs[0] === "2" && a.state.draftDirty === true;
    },

    // Sin draft y con boleto completo, la pagina entra en solo lectura.
    "boleto-completo-sin-borrador-es-solo-lectura": (a) => {
        a.hydrateUserSigns();
        return a.state.draftDirty === false && a.state.editMode === false && a.state.my_signs[0] !== "-";
    },
};

const caso = process.argv[2];
if (!CASOS[caso]) {
    console.error("Caso desconocido: " + caso + ". Disponibles: " + Object.keys(CASOS).join(", "));
    process.exit(2);
}
try {
    const servidorCompleto = Array(14).fill("1").concat(["X"]);
    const a = montar({ signosServidor: caso === "borrador-parcial-se-respeta" ? Array(15).fill("-") : servidorCompleto });
    console.log(CASOS[caso](a) ? "OK " + caso : "FALLO " + caso);
    process.exit(CASOS[caso](a) ? 0 : 1);
} catch (error) {
    console.error("No se pudo montar el arnes: " + (error && error.stack ? error.stack : error));
    process.exit(2);
}
