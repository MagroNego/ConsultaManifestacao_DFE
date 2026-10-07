// Run with: node tests/test_download_form.js
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('nfe_consulta/web/static/app.js', 'utf8');
const downloadSource = fs.readFileSync('nfe_consulta/web/static/downloads_ui.js', 'utf8');

async function scenario(method, failure, csv = false) {
  const classes = new Set();
  const button = { disabled: false, textContent: 'Gerar Excel', dataset: {}, ...(csv ? { name: 'formato', value: 'csv' } : {}) };
  const notices = [];
  const downloads = [];
  let submit, finish, request;
  const form = {
    method, action: 'http://test/excel',
    hasAttribute: name => name === 'data-download-form',
    classList: { contains: x => classes.has(x), add: x => classes.add(x), remove: x => classes.delete(x) },
    querySelector: selector => selector.startsWith('button') ? button : null,
    addEventListener: (name, fn) => { if (name === 'submit') submit = fn; },
    appendChild: node => notices.push(node),
  };
  class TestURL extends URL {
    static createObjectURL() { return 'blob:download'; }
    static revokeObjectURL() {}
  }
  const context = {
    URL: TestURL,
    localStorage: { getItem: () => null, setItem() {} },
    window: { location: { href: 'http://test/consulta' }, matchMedia: () => ({ matches: false }), addEventListener() {} },
    FormData: class {
      constructor() { this.entries = [['numero', '123']]; }
      append(key, value) { this.entries.push([key, value]); }
      *[Symbol.iterator]() { yield* this.entries; }
    },
    fetch: (url, options) => { request = { url, options }; return new Promise(resolve => { finish = resolve; }); },
    setTimeout: () => {},
    document: {
      documentElement: { dataset: {} },
      querySelector: () => null,
      querySelectorAll: selector => selector === '[data-processing-form]' ? [form] : [],
      addEventListener: (name, fn) => { if (name === "DOMContentLoaded") fn(); },
      body: { appendChild: node => downloads.push(node) },
      createElement: () => ({ setAttribute() {}, click() { this.clicked = true; }, remove() {} }),
    },
  };
  const realm = vm.createContext(context);
  vm.runInContext(downloadSource, realm);
  vm.runInContext(source, realm);
  let prevented = false;
  const pending = submit({ submitter: button, preventDefault() { prevented = true; } });
  assert.ok(prevented);
  assert.ok(button.disabled && classes.has('busy'));
  await submit({ preventDefault() {} }); // Duplicate submit must not send a second request.
  finish({
    ok: !failure,
    headers: { get: key => key === 'Content-Type' ? failure ? 'application/json' : 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' : key === 'Content-Disposition' ? 'attachment; filename="Relatorio.xlsx"' : null },
    json: async () => ({ detail: 'O servidor está ocupado.' }),
    blob: async () => ({}),
  });
  await pending;
  assert.equal(button.disabled, false);
  assert.equal(button.textContent, 'Gerar Excel');
  assert.equal(classes.has('busy'), false);
  assert.equal(request.options.method, method.toUpperCase());
  if (method === 'get') assert.equal(request.url.searchParams.get('numero'), '123');
  else assert.ok(request.options.body);
  if (csv) assert.ok([...request.options.body].some(([key, value]) => key === 'formato' && value === 'csv'));
  if (failure) {
    assert.equal(notices.length, 1);
    assert.equal(notices[0].textContent, 'O servidor está ocupado.');
    assert.equal(downloads.length, 0);
  } else {
    assert.equal(downloads.length, 1);
    assert.equal(downloads[0].download, 'Relatorio.xlsx');
    assert.ok(downloads[0].clicked);
  }
}
(async () => {
  await scenario('get', false);
  await scenario('post', false);
  await scenario('post', true);
  await scenario('post', false, true);
  process.stdout.write('4 download form scenarios passed\n');
})().catch(error => { process.stderr.write(String(error)); process.exitCode = 1; });
