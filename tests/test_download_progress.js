// Run with: node tests/test_download_progress.js
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('nfe_consulta/web/static/downloads_ui.js', 'utf8');

async function scenario(failure, archived = false) {
  const values = [], notices = [], downloads = [];
  const bar = { set value(value) { values.push(value); }, removeAttribute() {} };
  const label = { textContent: '' };
  const progress = { dataset: {}, querySelector: selector => selector === 'progress' ? bar : label };
  let index = 0, released = false;
  const context = {
    window: {}, Blob, URL: { createObjectURL: () => 'blob:test', revokeObjectURL() {} },
    localStorage: { setItem: (_, value) => notices.push(JSON.parse(value)) },
    setTimeout() {},
    document: { addEventListener() {}, body: { appendChild: item => downloads.push(item) },
      createElement: () => ({ click() {}, remove() {} }) },
    fetch: async () => ({ ok: true,
      headers: { get: name => ({ 'Content-Length': '4', 'Content-Type': 'text/csv',
        'Content-Disposition': "attachment; filename*=UTF-8''Notas.csv" })[name] || null },
      body: { getReader: () => ({ releaseLock() { released = true; }, async read() {
        if (failure && index === 1) throw new Error('Conexão interrompida');
        return index++ < 2 ? { done: false, value: new Uint8Array([1, 2]) } : { done: true };
      } }) } }),
  };
  vm.runInNewContext(source, context);
  const result = context.window.nfeDownloads.download('/arquivo', {}, { progress, notification: !archived });
  if (failure) {
    await assert.rejects(result, /Conexão interrompida/);
    assert.deepEqual(values, [0, 0, 50]);
    assert.equal(progress.dataset.state, 'error');
    assert.equal(label.textContent, 'Erro no download');
    assert.equal(downloads.length, 0);
  } else {
    await result;
    assert.deepEqual(values, [0, 0, 50, 99, 100]);
    assert.equal(label.textContent, '100%');
    assert.equal(progress.dataset.state, 'complete');
    assert.equal(downloads[0].download, 'Notas.csv');
  }
  assert.ok(released);
  if (archived) assert.equal(notices.length, 0);
  else assert.equal(notices[0][0].type, failure ? 'error' : 'success');
}
(async () => {
  await scenario(false);
  await scenario(true);
  await scenario(false, true);
  process.stdout.write('3 streaming download and notification scenarios passed\n');
})().catch(error => { console.error(error); process.exitCode = 1; });
