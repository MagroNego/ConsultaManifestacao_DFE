from pathlib import Path
import runpy

from fastapi.testclient import TestClient

from nfe_consulta.web.app import create_app
from nfe_consulta.web.downloads import DownloadArchive, RETENTION_SECONDS, period_label
from nfe_consulta.web import downloads, xml_store
from nfe_consulta.config import CNPJ_PADRAO

helpers = runpy.run_path(str(Path(__file__).with_name('test_xml_integrado.py')))
web = helpers['helpers']


def test_archive_expiration_persistence_permissions_and_duplicates(tmp_path, monkeypatch):
    clock = [100000.0]
    monkeypatch.setattr(downloads.time, 'time', lambda: clock[0])
    archive = DownloadArchive(tmp_path / 'downloads')
    public = archive.save(b'public', filename='report.csv', media_type='text/csv', documents=2, period='01/10/2026')
    private = archive.save(b'private', filename='report.csv', media_type='text/csv', documents=3, period='Não informado', admin_only=True)
    reopened = DownloadArchive(archive.directory)
    assert len(reopened.list()) == 1
    assert len(reopened.list(admin=True)) == 2
    assert reopened.get(private['id']) is None
    assert reopened.get('../anything') is None
    assert reopened.get(public['id'])['documents'] == 2
    clock[0] += RETENTION_SECONDS
    assert reopened.get(public['id']) is None
    assert (archive.directory / f"{public['id']}.bin").exists()
    reopened.cleanup()
    assert not list(archive.directory.iterdir())


def test_exports_archive_document_count_period_and_download_without_renewal(tmp_path):
    cfg = web['settings_web'](tmp_path)
    web['criar_banco'](cfg.database_path)
    source = tmp_path / 'nota.xml'
    source.write_bytes(helpers['xml']())
    xml_store.import_batch(cfg.database_path, CNPJ_PADRAO, [(source, 'nota.xml')])
    app = create_app(cfg)
    with TestClient(app) as client:
        assert client.get('/downloads').status_code == 200
        for url in ['/xml/exportar?formato=csv&tipo=itens&data_inicial=01/10/2026&data_final=31/10/2026', '/xml/exportar?formato=xlsx', '/xml/arquivo/' + helpers['CHAVE']]:
            response = client.get(url)
            assert response.status_code == 200, response.text
            item = app.state.downloads.list()[0]
            assert item['documents'] == 1
            assert item['period'] == ('01/10/2026 a 31/10/2026' if 'data_inicial' in url else '01/10/2026')
            restored = client.get('/downloads/' + item['id'])
            assert restored.content == response.content
            assert app.state.downloads.get(item['id'])['expires_at'] == item['expires_at']
        assert len(app.state.downloads.list()) == 3
        page = client.get('/downloads').text
        assert 'Documentos processados' in page and '01/10/2026 a 31/10/2026' in page
        assert 'Downloads' in client.get('/xml').text
    assert len(create_app(cfg).state.downloads.list()) == 3


def test_private_archive_not_visible_or_downloadable_publicly(tmp_path):
    cfg = web['settings_web'](tmp_path)
    app = create_app(cfg)
    item = app.state.downloads.save(b'private', filename='segredo.csv', media_type='text/csv', documents=1, period='Não informado', admin_only=True)
    with TestClient(app) as client:
        assert 'segredo.csv' not in client.get('/downloads').text
        assert client.get('/downloads/' + item['id']).status_code == 404
        web['entrar_admin'](client, cfg)
        assert 'segredo.csv' in client.get('/downloads').text
        assert client.get('/downloads/' + item['id']).content == b'private'


def test_period_without_dates():
    assert period_label([]) == 'Não informado'
    assert period_label(['2026-10-07T10:00:00', '01/10/2026']) == '01/10/2026 a 07/10/2026'


def test_excel_product_filter_counts_documents_from_all_sheets(tmp_path):
    cfg = web['settings_web'](tmp_path)
    web['criar_banco'](cfg.database_path)
    source = tmp_path / 'nota.xml'
    content = helpers['xml']()
    item = content[content.index(b'<det '):content.index(b'</det>') + len(b'</det>')]
    source.write_bytes(content.replace(item, item + item.replace(b'nItem="1"', b'nItem="2"')))
    xml_store.import_batch(cfg.database_path, CNPJ_PADRAO, [(source, 'nota.xml')])
    app = create_app(cfg)
    with TestClient(app) as client:
        for formato in ('csv', 'xlsx'):
            response = client.get('/xml/exportar', params={'formato': formato, 'tipo': 'itens', 'q': 'produto'})
            assert response.status_code == 200
            item = app.state.downloads.list()[0]
            assert item['documents'] == 1  # Dois itens da mesma nota.
            assert item['period'] == '01/10/2026'
