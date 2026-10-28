// Exercise the actual lazy loader and modal without relying on a browser package.
const assert = require('assert');
const fs = require('fs');
const vm = require('vm');

async function testAssets(first, second) {
  const elements = new Map();
  const inserted = [];
  const document = {
    body: { dataset: { assetsV: 'test' }, appendChild: append },
    head: { appendChild: append },
    addEventListener() {},
    getElementById(id) { return elements.get(id) || null; },
    createElement(tag) {
      return { tag, dataset: {}, listeners: {}, addEventListener(type, cb) { this.listeners[type] = cb; } };
    },
  };
  function append(el) {
    elements.set(el.id, el);
    inserted.push(el);
    queueMicrotask(() => el.listeners.load());
  }
  const context = vm.createContext({ document, console, Promise, encodeURIComponent });
  vm.runInContext(fs.readFileSync('static/js/navigation.js', 'utf8'), context);
  await context.ensureViewAssets(first);
  const style = elements.get('view-pleno-modal-styles');
  assert(style && style.href.includes('/static/css/components/pleno_modal.css'));
  assert(elements.has('view-pleno-modal-script'));
  await context.ensureViewAssets(second);
  assert.strictEqual(inserted.filter(el => el.id === 'view-pleno-modal-styles').length, 1);
  assert.strictEqual(inserted.filter(el => el.id === 'view-pleno-modal-script').length, 1);
}

function testModal() {
  const listeners = {};
  const goalButtons = ['local', 'visitante'].flatMap(side => ['0', '1', '2', 'M'].map(goal => ({
    dataset: { plenoSide: side, goal },
    classList: { toggle() {} }, setAttribute() {}, focus() {},
    closest() { return this; },
  })));
  const preview = { textContent: '' };
  const actions = {};
  let overlay;
  let matchClick;
  const matchesBody = { addEventListener(type, fn) { if (type === 'click') matchClick = fn; } };
  const document = {
    activeElement: null,
    body: { appendChild(el) { overlay = el; } },
    getElementById() { return null; },
    querySelectorAll() { return []; },
    addEventListener() {}, removeEventListener() {},
    createElement() {
      return {
        classList: { add() {}, remove() {} },
        addEventListener(type, fn) { listeners[type] = fn; },
        remove() {},
        querySelector(selector) {
          if (selector === '#pleno-preview') return preview;
          if (selector === '.pleno-goal-btn.active') return goalButtons[0];
          if (selector === '.pleno-modal-cancel' || selector === '.pleno-modal-save') {
            return { addEventListener(type, fn) { actions[selector] = fn; } };
          }
          return null;
        },
        querySelectorAll(selector) { return goalButtons.filter(b => selector.includes(`"${b.dataset.plenoSide}"`)); },
      };
    },
  };
  let persisted = 0, rendered = 0, unlocked = 0;
  const context = vm.createContext({
    document, HTMLElement: class {}, Date,
    // Missing an earlier fixture: the 15th match is not at array index 14.
    state: { user: { id: 'test' }, data: { jornada: 1, max_jornada: 1, partidos: [{ id: 1, local: 'Otro', visitante: 'Partido' }, { id: 15, local: 'Pleno local', visitante: 'Pleno visitante' }] }, my_signs: Array(15).fill('-') },
    qs: id => id === 'matches-body' ? matchesBody : null,
    hasSavedTicket: () => false,
    showToast: message => { throw new Error(message); },
    window: { requestAnimationFrame(fn) { fn(); }, setTimeout(fn) { fn(); } },
    logoBadge: () => '', teamLogo: () => '', escapeHtml: s => s, getShortName: s => s,
    persistDraft: () => persisted++, hydrateHero: () => {}, renderArena: () => rendered++,
    lmBloquearScroll: () => () => unlocked++,
  });
  vm.runInContext(fs.readFileSync('static/js/components/pleno_modal.js', 'utf8'), context);
  vm.runInContext(fs.readFileSync('static/js/events.js', 'utf8'), context);
  context.bindEvents();
  const plenoButton = {
    dataset: { pleno: 'true', matchIdx: '14' },
    closest(selector) { return selector === '.clickable' ? this : null; },
  };
  matchClick({ target: plenoButton });
  assert(overlay.innerHTML.includes('Pleno al 15'));
  assert(overlay.innerHTML.includes('Pleno local'));
  assert(overlay.innerHTML.includes('Pleno visitante'));
  listeners.click({ target: goalButtons.find(b => b.dataset.plenoSide === 'local' && b.dataset.goal === 'M') });
  listeners.click({ target: goalButtons.find(b => b.dataset.plenoSide === 'visitante' && b.dataset.goal === '1') });
  assert.strictEqual(preview.textContent, 'M-1');
  actions['.pleno-modal-save']();
  assert.strictEqual(context.state.my_signs[14], 'M-1');
  assert.strictEqual(context.state.draftDirty, true);
  assert.strictEqual(persisted, 1);
  assert.strictEqual(rendered, 1);
  assert.strictEqual(unlocked, 1);
  context.openPlenoModal(14);
  actions['.pleno-modal-cancel']();
  assert.strictEqual(context.state.my_signs[14], 'M-1');
  assert.strictEqual(persisted, 1);
  assert.strictEqual(unlocked, 2);
}

(async () => {
  await testAssets('ALL', 'TICKET');
  await testAssets('TICKET', 'ALL');
  testModal();
  console.log('Pleno picker OK');
})().catch(error => { console.error(error); process.exitCode = 1; });
