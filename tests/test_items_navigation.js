const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('nfe_consulta/web/static/items_navigation.js', 'utf8');

function load(url, stored, blocked = false) {
  let ready, click, restored;
  const storage = new Map(stored ? [['nfe-items-return', stored]] : []);
  const context = {
    window: { location: { pathname: url.split('?')[0], search: url.includes('?') ? '?' + url.split('?')[1] : '' }, scrollY: 725, scrollTo: (_, y) => restored = y },
    document: { addEventListener: (_, fn) => ready = fn, querySelectorAll: () => [{ addEventListener: (_, fn) => click = fn }] },
    sessionStorage: { getItem: key => { if (blocked) throw new Error('blocked'); return storage.get(key); }, setItem: (key, val) => { if (blocked) throw new Error('blocked'); storage.set(key, val); }, removeItem: key => storage.delete(key) },
    requestAnimationFrame: fn => fn(),
  };
  vm.runInNewContext(source, context);
  ready();
  return { click, storage, restored: () => restored };
}

test('opening items records the exact filtered page and scroll; returning restores once', () => {
  const url = '/xml?pagina=3&item=peca';
  const page = load(url);
  page.click();
  const state = page.storage.get('nfe-items-return');
  assert.deepEqual(JSON.parse(state), { url, y: 725 });
  assert.equal(load('/xml/itens/123', state).restored(), undefined);
  const returned = load(url, state);
  assert.equal(returned.restored(), 725);
  assert.equal(returned.storage.has('nfe-items-return'), false);
});

test('unrelated URLs and unavailable storage never break navigation', () => {
  assert.equal(load('/xml?pagina=1', JSON.stringify({ url: '/xml?pagina=3', y: 725 })).restored(), undefined);
  assert.doesNotThrow(() => load('/xml', null, true).click());
  assert.doesNotThrow(() => load('/xml', '{invalid'));
});
