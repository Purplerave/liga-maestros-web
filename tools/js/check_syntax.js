// Validador de sintaxis JS que funciona en este entorno.
//
// `node --check <fichero>` devuelve 0 SIEMPRE en esta maquina (comprobado: pasa
// incluso un fichero con `prueba( )`), asi que no sirve para validar nada. Este
// script compila el fuente con el parser de V8 de verdad, en modo classique o
// modulo segun la sintaxis, que es lo que hace `node --check` en Linux.
//
// Uso (necesita el flag para SourceTextModule):
//   node --experimental-vm-modules tools/js/check_syntax.js
//
// Sale con codigo 1 si algun .js no parsea, y lista los ficheros rotos.

const fs = require("fs");
const path = require("path");
const vm = require("vm");

const ROOT = process.argv[2] ? path.resolve(process.argv[2]) : process.cwd();
const JS_DIR = path.join(ROOT, "static", "js");

const Module = vm.SourceTextModule;
if (typeof Module !== "function") {
  console.error("Falta --experimental-vm-modules. Uso: node --experimental-vm-modules tools/js/check_syntax.js");
  process.exit(2);
}

function walk(dir) {
  const out = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) out.push(...walk(full));
    else if (entry.name.endsWith(".js")) out.push(full);
  }
  return out;
}

const looksLikeModule = (src) => /(^|\n)\s*(export\s|import\s)/.test(src);

const files = walk(JS_DIR).sort();
const rotos = [];

for (const file of files) {
  const src = fs.readFileSync(file, "utf8");
  try {
    if (looksLikeModule(src)) {
      new Module(src, { identifier: file });
    } else {
      new vm.Script(src, { filename: file });
    }
  } catch (err) {
    if (err instanceof SyntaxError) {
      rotos.push({ file: path.relative(ROOT, file), linea: err.lineNumber || "?", mensaje: err.message });
    }
  }
}

console.log(`Comprobados ${files.length} ficheros JavaScript en static/js`);

if (rotos.length) {
  console.error(`\n${rotos.length} fichero(s) con error de sintaxis:\n`);
  for (const r of rotos) {
    console.error(`  ${r.file}:${r.linea}  ${r.mensaje}`);
  }
  process.exit(1);
}

console.log("Todos parsean correctamente.");
