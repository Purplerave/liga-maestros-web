/* Ejecuta los helpers de signo reales (utils.js + cover_page.js) y comprueba
   que un doble acierta cuando el resultado cae dentro del.
   Uso: node tests/js/check_sign_hits.js  (lo invoca tests/test_frontend_sign_scoring.py) */
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const root = path.resolve(__dirname, "..", "..");
const utilsSrc = fs.readFileSync(path.join(root, "static", "js", "utils.js"), "utf8");
const coverSrc = fs.readFileSync(path.join(root, "static", "js", "pages", "cover_page.js"), "utf8");

const ctx = vm.createContext({ console, setInterval: () => {}, document: undefined });

// Extrae una funcion por nombre contando llaves: asi el test no depende de que
// el resto de la portada (que pinta el DOM) se pueda ejecutar en node.
function extractFunction(source, name) {
  const start = source.indexOf(`function ${name}(`);
  if (start < 0) throw new Error(`no encuentro ${name} en el fuente`);
  let depth = 0;
  for (let i = source.indexOf("{", start); i < source.length; i += 1) {
    if (source[i] === "{") depth += 1;
    else if (source[i] === "}") {
      depth -= 1;
      if (depth === 0) return source.slice(start, i + 1);
    }
  }
  throw new Error(`llaves sin cerrar en ${name}`);
}

vm.runInContext(utilsSrc, ctx);
vm.runInContext(extractFunction(coverSrc, "_coverSignHit"), ctx);
vm.runInContext(extractFunction(coverSrc, "_coverRealRef"), ctx);

const cases = [
  // [pick, real, isPleno, expected]
  ["12", "1", false, true],   // el caso del usuario: 12 con resultado 1
  ["12", "2", false, true],
  ["12", "X", false, false],
  ["1X", "X", false, true],
  ["1X", "2", false, false],
  ["X2", "2", false, true],
  ["1", "1", false, true],
  ["1", "X", false, false],
  ["2", "1", false, false],
  ["-", "1", false, false],
  ["", "1", false, false],
  ["12", "", false, false],
  ["2-0", "2-0", true, true],
  ["2-0", "1-0", true, false],
  ["3-1", "M-1", true, true],  // 3+ es "M" en el pleno
  ["M-1", "3-1", true, true],
  ["1 2", "2", false, true],   // el payload puede traer el doble con espacio
  ["x2", "X", false, true],    // minusculas
  ["12", "X", false, false],
];

let failures = 0;
for (const [pick, real, isPleno, expected] of cases) {
  const viaCover = ctx._coverSignHit(pick, real, isPleno);
  const viaUtil = ctx.isHitSign(pick, real, isPleno);
  if (viaCover !== expected) {
    failures += 1;
    console.error(`FAIL _coverSignHit(${JSON.stringify(pick)}, ${JSON.stringify(real)}, pleno=${isPleno}) = ${viaCover}, esperado ${expected}`);
  }
  if (viaUtil !== expected) {
    failures += 1;
    console.error(`FAIL isHitSign(${JSON.stringify(pick)}, ${JSON.stringify(real)}, pleno=${isPleno}) = ${viaUtil}, esperado ${expected}`);
  }
}

// La portada no puede volver a comparar signos con igualdad estricta.
const strictComparisons = coverSrc.match(/===\s*(?:String\()?sign/g) || [];
if (strictComparisons.length) {
  failures += 1;
  console.error(`FAIL la portada sigue comparando signos con igualdad estricta: ${strictComparisons.join(", ")}`);
}

// Referencia del pleno: el marcador, no el 1X2.
const plenoRef = ctx._coverRealRef({ signo_actual: "1", marcador_base: "2-0", marcador: "2-0" }, true);
if (plenoRef !== "2-0") {
  failures += 1;
  console.error(`FAIL _coverRealRef pleno = ${plenoRef}, esperado 2-0`);
}
const normalRef = ctx._coverRealRef({ signo_actual: "1", marcador_base: "3-1" }, false);
if (normalRef !== "1") {
  failures += 1;
  console.error(`FAIL _coverRealRef normal = ${normalRef}, esperado 1`);
}

if (failures) {
  console.error(`${failures} fallo(s)`);
  process.exit(1);
}
console.log(`OK ${cases.length} casos de signo (doble, pleno y vacios) en portada y utils`);
