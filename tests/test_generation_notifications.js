// Run with: node tests/test_generation_notifications.js
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('nfe_consulta/web/static/downloads_ui.js', 'utf8');

function element() {
  return { dataset: {}, hidden: true, children: [], handlers: {}, attributes: {},
    append(...items) { this.children.push(...items); },
    appendChild(item) { this.children.push(item); },
    replaceChildren() { this.children = []; },
    setAttribute(key, value) { this.attributes[key] = value; },
    addEventListener(key, handler) { this.handlers[key] = handler; },
    contains() { return false; }, focus() { this.focused = true; } };
}

async function scenario(status, initiallyEmpty = false) {
  const id = 'b'.repeat(32), timers = [], events = {};
  const storage = new Map([['nfe-generation-jobs-v1', JSON.stringify([{ id, time: Date.now(), status: 'queued' }])]]);
  const pendingJob = storage.get('nfe-generation-jobs-v1');
  if (initiallyEmpty) storage.set('nfe-generation-jobs-v1', '[]');
  const bell = element(), panel = element(), count = element(), list = element(), clear = element();
  panel.dataset = { downloadsUrl: 'http://test/downloads', stateUrl: 'http://test/downloads/estado' };
  const nodes = { '[data-notification-bell]': bell, '[data-notification-panel]': panel,
    '[data-notification-count]': count, '[data-notification-list]': list, '[data-notification-clear]': clear };
  let fetches = 0;
  const context = {
    URL, window: { location: { href: 'http://test/xml' }, addEventListener: (key, handler) => { events['window:' + key] = handler; } },
    localStorage: { getItem: key => storage.get(key), setItem: (key, value) => storage.set(key, value) },
    document: { querySelector: selector => nodes[selector] || null, querySelectorAll: () => [],
      createElement: element, addEventListener: (key, handler) => { events[key] = handler; } },
    setTimeout: (handler, ms) => timers.push({ handler, ms }), clearTimeout() {},
    fetch: async () => ({ ok: true, json: async () => ({ jobs: [{ id, status: fetches++ ? status : 'generating' }] }) }),
  };
  vm.runInNewContext(source, context);
  events.DOMContentLoaded();
  if (initiallyEmpty) {
    assert.equal(fetches, 0);
    storage.set('nfe-generation-jobs-v1', pendingJob);
    events['window:storage']({ key: 'nfe-generation-jobs-v1' });
  }
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(list.children[0].children[0].textContent, 'Gerando arquivo');
  assert.equal(list.children[0].children[1].value, undefined); // Progresso indeterminado, sem percentual inventado.
  assert.equal(count.textContent, '1');
  await timers.shift().handler();
  assert.deepEqual(JSON.parse(storage.get('nfe-generation-jobs-v1')), []);
  assert.equal(list.children[0].children[0].textContent, status === 'complete' ? 'Processamento concluído' : 'Erro na geração');
  if (status === 'complete') assert.equal(list.children[0].children[2].value, 100);
  bell.handlers.click();
  assert.equal(panel.hidden, false);
  assert.equal(count.hidden, true);
  events.keydown({ key: 'Escape' });
  assert.equal(panel.hidden, true);
  assert.ok(bell.focused);
  clear.handlers.click();
  assert.deepEqual(JSON.parse(storage.get('nfe-download-notifications-v1')), []);
  assert.equal(list.children[0].textContent, 'Nenhuma notificação recente.');
}
(async () => {
  await scenario('complete');
  await scenario('error');
  await scenario('complete', true);
  process.stdout.write('3 background generation bell scenarios passed\n');
})().catch(error => { console.error(error); process.exitCode = 1; });
