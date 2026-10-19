from pathlib import Path
import runpy
import sqlite3

import pytest
from fastapi.testclient import TestClient

from nfe_consulta.web.app import create_app
from nfe_consulta.web.auth import PUBLIC_USER, csrf_token

web = runpy.run_path(str(Path(__file__).with_name('test_web.py')))
PASSWORD = 'Senha-pessoal-teste-123!'


def setup(tmp_path):
    cfg = web['settings_web'](tmp_path)
    web['criar_banco'](cfg.database_path)
    from nfe_consulta.banco import BancoManifestacoes
    from nfe_consulta.config import CNPJ_PADRAO
    from nfe_consulta.modelos import Manifestacao, RetornoDistribuicao
    banco = BancoManifestacoes(str(cfg.database_path))
    banco.salvar_retorno(CNPJ_PADRAO, RetornoDistribuicao(138, 'ok', '1'.zfill(15), '1'.zfill(15),
        ((web['CHAVE'], Manifestacao('210240', 'Operação não Realizada', '2026-10-16T01:00:00-03:00', '1')),), 0))
    banco.fechar()
    return cfg, create_app(cfg)


def test_cadastro_proprio_tem_acesso_imediato_mas_nunca_admin(tmp_path):
    cfg, app = setup(tmp_path)
    with TestClient(app) as client:
        login_page = client.get('/login').text
        assert 'href="http://testserver/cadastro">Criar conta</a>' in login_page
        assert 'class="button secondary" href="http://testserver/login">Entrar</a>' in login_page
        assert 'Confirmar senha' in client.get('/cadastro').text
        data = {'csrf':csrf_token(PUBLIC_USER,cfg), 'username':'ana.teste', 'email':'ana@example.com', 'password':PASSWORD,
                'password_confirmation':PASSWORD, 'role':'admin', 'is_admin':'1'}
        assert client.post('/cadastro', data={**data,'csrf':'errado'}).status_code == 403
        assert app.state.admin_accounts.role('ana.teste') is None
        response = client.post('/cadastro',data=data)
        assert response.status_code == 200
        assert 'Conta criada' in response.text
        assert app.state.admin_accounts.role('ana.teste') == 'fiscal'
        assert client.post('/login',data={'csrf':data['csrf'],'username':'ana.teste',
            'password':PASSWORD}, follow_redirects=False).status_code == 303
        assert client.get('/consulta').status_code == 200
        assert client.get('/consulta/exportar').status_code == 200
        assert '>Admin</a>' not in client.get('/consulta').text
        assert client.get('/admin/contas', follow_redirects=False).status_code == 303
        assert client.post('/admin/contas',data={'action':'delete','username':'admin',
            'confirm_delete':'1'}).status_code == 401
    with sqlite3.connect(app.state.admin_accounts.path) as db:
        encoded = db.execute('SELECT password_hash FROM admins WHERE username=?',('ana.teste',)).fetchone()[0]
    assert PASSWORD not in encoded


def test_cadastro_valida_senha_confirmacao_e_duplicatas(tmp_path):
    cfg, app = setup(tmp_path)
    with TestClient(app) as client:
        data = {'csrf':csrf_token(PUBLIC_USER,cfg),'username':'novo','email':'novo@example.com','password':PASSWORD,
                'password_confirmation':'outra'}
        response = client.post('/cadastro',data=data)
        assert response.status_code == 400 and PASSWORD not in response.text
        assert app.state.admin_accounts.role('novo') is None
        data.update(password='curta',password_confirmation='curta')
        assert client.post('/cadastro',data=data).status_code == 400
        data.update(password=PASSWORD,password_confirmation=PASSWORD)
        assert client.post('/cadastro',data=data).status_code == 200
        assert client.post('/cadastro',data={**data,'username':'NOVO'}).status_code == 400
        assert client.post('/cadastro',data={**data,'username':'a'}).status_code == 400
        assert client.post('/cadastro',data={**data,'username':'sexto'}).status_code == 429
        assert app.state.admin_accounts.role('sexto') is None


@pytest.mark.parametrize('path',['/','/consulta','/status','/xml','/downloads',
    '/downloads/estado','/consulta/exportar','/xml/exportar','/downloads/id-inventado'])
def test_sem_sessao_nao_acessa_dados_nem_arquivos(tmp_path,path):
    cfg, app = setup(tmp_path)
    with TestClient(app) as client:
        response = client.get(path,follow_redirects=False)
        assert response.status_code == 303
        assert response.headers['location'].endswith('/login')
        response = client.get('/xml/exportar',headers={'X-NFE-Background':'1'},follow_redirects=False)
        assert response.status_code == 303
        assert not app.state.export_jobs.records
        assert client.post('/excel',data={'csrf':csrf_token(PUBLIC_USER,cfg)}).status_code == 401
        assert client.get('/healthz').status_code == 200
        assert client.get('/static/app.css').status_code == 200


def test_admin_exclui_conta_com_confirmacao_revoga_sessao_e_preserva_banco(tmp_path):
    cfg, app = setup(tmp_path)
    accounts=app.state.admin_accounts
    accounts.create('apagar',PASSWORD,'fiscal')
    session=accounts.new_session('apagar')
    before=cfg.database_path.read_bytes()
    with TestClient(app) as client:
        token=web['entrar_admin'](client,cfg)
        data={'csrf':token,'action':'delete','username':'apagar'}
        assert 'Excluir usuário' in client.get('/admin/contas').text
        assert client.post('/admin/contas',data=data).status_code == 400
        assert accounts.role('apagar') == 'fiscal'
        assert client.post('/admin/contas',data={**data,'confirm_delete':'1','csrf':'invalido'}).status_code == 403
        assert client.post('/admin/contas',data={**data,'confirm_delete':'1'},follow_redirects=False).status_code == 303
        assert accounts.role('apagar') is None
        assert accounts.session_identity(session,1800) is None
        assert client.post('/admin/contas',data={**data,'username':cfg.admin_username,
            'confirm_delete':'1'}).status_code == 400
        assert accounts.role(cfg.admin_username) == 'admin'
    assert cfg.database_path.read_bytes() == before


def test_admin_redefine_senha_sem_exibir_senha_anterior(tmp_path):
    cfg,app=setup(tmp_path)
    accounts=app.state.admin_accounts
    accounts.create('pessoal',PASSWORD,'fiscal')
    session=accounts.new_session('pessoal')
    nova='Outra-senha-individual-456!'
    with TestClient(app) as client:
        token=web['entrar_admin'](client,cfg)
        assert PASSWORD not in client.get('/admin/contas').text
        assert client.post('/admin/contas',data={'csrf':token,'action':'reset',
            'username':'pessoal','password':nova},follow_redirects=False).status_code == 303
        assert accounts.authenticate('pessoal',PASSWORD) is None
        assert accounts.authenticate('pessoal',nova) == 'pessoal'
        assert accounts.session_identity(session,1800) is None
        assert nova not in client.get('/admin/contas').text
