from pathlib import Path
import runpy
import pytest
from fastapi.testclient import TestClient
from nfe_consulta.cancelamento import change_manual_status, cancelled_keys, lookup_cancelled
from nfe_consulta.config import CNPJ_PADRAO
from nfe_consulta.seguranca_banco import abrir_banco
from nfe_consulta.web.app import create_app
from nfe_consulta.web.xml_store import query_report
from nfe_consulta.web.consulta_local import consultar_eventos, normalizar_filtros

h = runpy.run_path(str(Path(__file__).with_name('test_filtro_situacao.py')))
KEY, KEY2 = h['KEY'], h['KEY2']


def change(cfg, notes=KEY2, action='cancelar', **kwargs):
    return change_manual_status(cfg.database_path, CNPJ_PADRAO, notes, user='admin', reason='Correção conferida', action=action, **kwargs)


def test_manual_status_shared_and_reversible_without_clearing_sefaz(tmp_path):
    cfg = h['setup'](tmp_path)
    assert change(cfg, '124\n' + KEY2) == 1
    for kind in ('notas', 'itens', 'retencoes'):
        assert query_report(cfg.database_path, CNPJ_PADRAO, kind=kind, situacao='cancelada')['total'] == 2
    assert consultar_eventos(cfg.database_path, CNPJ_PADRAO, normalizar_filtros(situacao='cancelada')).total == 2
    conn = abrir_banco(cfg.database_path)
    assert lookup_cancelled(conn, CNPJ_PADRAO, number=124)[0]['chave'] == KEY2
    assert conn.execute('SELECT usuario,motivo FROM cancelamentos_manuais WHERE chave=?', (KEY2,)).fetchone() == ('admin', 'Correção conferida')
    conn.close()
    h['helpers']['batch'](cfg, tmp_path, [h['helpers']['helpers']['xml'](chave=KEY2)])
    assert query_report(cfg.database_path, CNPJ_PADRAO, situacao='cancelada')['total'] == 2
    change(cfg, KEY + '\n' + KEY2)
    change(cfg, KEY + '\n' + KEY2, 'remover')
    assert query_report(cfg.database_path, CNPJ_PADRAO, situacao='cancelada')['rows'][0]['Chave Acesso'] == KEY
    conn = abrir_banco(cfg.database_path)
    assert conn.execute('SELECT COUNT(*) FROM historico_cancelamentos_manuais').fetchone()[0] == 5
    assert cancelled_keys(conn, '00000000000000', [KEY, KEY2]) == set()
    conn.close()


def test_invalid_batch_is_atomic_and_ambiguous_number_requires_key(tmp_path):
    cfg = h['setup'](tmp_path)
    with pytest.raises(ValueError, match='não encontrada'):
        change(cfg, KEY2 + '\n999999999')
    assert query_report(cfg.database_path, CNPJ_PADRAO, situacao='cancelada')['total'] == 1
    other = KEY2[:22] + '002' + KEY2[25:]
    h['helpers']['batch'](cfg, tmp_path, [h['helpers']['helpers']['xml'](chave=other)])
    with pytest.raises(ValueError, match='mais de uma'):
        change(cfg, '124')
    assert change(cfg, other) == 1
    for notes in ('', 'abc', '-1', '\n'.join(str(n) for n in range(101))):
        with pytest.raises(ValueError):
            change(cfg, notes)


def test_admin_only_csrf_and_ui_export(tmp_path):
    cfg = h['setup'](tmp_path)
    with TestClient(create_app(cfg)) as client:
        data = {'notas': '124', 'motivo': 'Correção', 'acao': 'cancelar'}
        assert client.post('/admin/notas/situacao', data=data, follow_redirects=False).status_code == 401
        token = h['helpers']['web']['entrar_admin'](client, cfg)
        assert 'Alterar situação de notas' in client.get('/atualizar').text
        assert client.post('/admin/notas/situacao', data={**data, 'csrf': 'invalid'}).status_code == 403
        response = client.post('/admin/notas/situacao', data={**data, 'csrf': token})
        assert response.status_code == 200 and '1 nota(s) marcada(s)' in response.text
        for url in ('/xml', '/consulta'):
            rows = client.get(url + '?situacao=cancelada').text.split('<tbody>')[1].split('</tbody>')[0]
            assert KEY2 in rows
        response = client.get('/xml/exportar?formato=csv&situacao=cancelada')
        assert response.status_code == 200 and KEY2 in response.content.decode('utf-8-sig')
        response = client.post('/admin/notas/situacao', data={**data, 'csrf': token, 'acao': 'remover'})
        assert response.status_code == 200 and 'Marcação manual removida' in response.text
        assert query_report(cfg.database_path, CNPJ_PADRAO, situacao='cancelada')['total'] == 1
