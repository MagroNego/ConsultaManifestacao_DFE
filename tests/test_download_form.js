// Run with: node tests/test_download_form.js
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('nfe_consulta/web/static/app.js', 'utf8');

async function scenario(method, failure) {
  const classes = new Set();
  const button = { disabled: false, textContent: 'Gerar Excel', dataset: {} };
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
    localStorage: { getItem: () => null },
    window: { location: { href: 'http://test/consulta' }, matchMedia: () => ({ matches: false }) },
    FormData: class { *[Symbol.iterator]() { yield ['numero', '123']; } },
    fetch: (url, options) => { request = { url, options }; return new Promise(resolve => { finish = resolve; }); },
    setTimeout: () => {},
    document: {
      documentElement: { dataset: {} },
      querySelector: () => null,
      querySelectorAll: selector => selector === '[data-processing-form]' ? [form] : [],
      addEventListener: (name, fn) => fn(),
      body: { appendChild: node => downloads.push(node) },
      createElement: () => ({ setAttribute() {}, click() { this.clicked = true; }, remove() {} }),
    },
  };
  vm.runInNewContext(source, context);
  let prevented = false;
  const pending = submit({ preventDefault() { prevented = true; } });
  assert.ok(prevented);
  assert.ok(button.disabled && classes.has('busy'));
  await submit({ preventDefault() {} }); // Duplicate submit must not send a second request.
  finish({
    ok: !failure,
    headers: { get: key => key === 'Content-Type' ? failure ? 'application/json' : 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' : 'attachment; filename="Relatorio.xlsx"' },
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
  process.stdout.write('3 download form scenarios passed\n');
})().catch(error => { process.stderr.write(String(error)); process.exitCode = 1; });
