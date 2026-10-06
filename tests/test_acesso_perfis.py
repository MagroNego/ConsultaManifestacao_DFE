"""Admin exige sessão; consultas e exportações continuam públicas."""
import runpy
import sqlite3
from pathlib import Path
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient
from nfe_consulta.web.admin_accounts import AdminAccounts, _hash_password
from nfe_consulta.web.auth import PUBLIC_USER, csrf_token
from nfe_consulta.web.app import create_app
from nfe_consulta.web.configure_admin import configure_account

helpers = runpy.run_path(str(Path(__file__).with_name("test_xml_integrado.py")))
PASSWORD = "Senha-individual-123!"


def setup(tmp_path):
    cfg = helpers['helpers']['settings_web'](tmp_path)
    helpers['helpers']['criar_banco'](cfg.database_path)
    from nfe_consulta.banco import BancoManifestacoes
    from nfe_consulta.modelos import Manifestacao, RetornoDistribuicao
    from nfe_consulta.config import CNPJ_PADRAO
    banco = BancoManifestacoes(str(cfg.database_path))
    banco.salvar_retorno(CNPJ_PADRAO, RetornoDistribuicao(138, 'ok', '1'.zfill(15), '1'.zfill(15),
        ((helpers['CHAVE'], Manifestacao('210240', 'Operação não Realizada', '2026-10-01T10:00:00-03:00', '1')),), 0))
    banco.fechar()
    return cfg, create_app(cfg)


@pytest.mark.parametrize('path', ['/consulta', '/status', '/xml', '/xml?tipo=itens', '/xml?tipo=retencoes', '/xml/exportar?formato=csv', '/consulta/exportar'])
def test_leitura_e_exportacao_publicas(tmp_path, path):
    cfg, app = setup(tmp_path)
    with TestClient(app) as client:
        assert client.get(path).status_code == 200
        assert 'Sair do Admin' not in client.get('/consulta').text


@pytest.mark.parametrize('path', ['/atualizar', '/admin/historico', '/xml/lote/1/registro'])
def test_admin_redireciona_para_login(tmp_path, path):
    cfg, app = setup(tmp_path)
    with TestClient(app) as client:
        response = client.get(path, follow_redirects=False)
        assert response.status_code == 303
        assert response.headers['location'].endswith('/admin/login')
        assert 'Entrar no Admin' in client.get(path).text


def test_todas_mutacoes_admin_bloqueadas_sem_sessao(tmp_path):
    cfg, app = setup(tmp_path)
    with TestClient(app) as client:
        for route in app.routes:
            if 'POST' in getattr(route, 'methods', set()) and (route.path.startswith('/atualizar') or route.path == '/xml/importar'):
                response = client.post(route.path, data={'csrf': csrf_token(PUBLIC_USER, cfg)})
                assert response.status_code == 401
        assert client.post('/xml/importar', files={'files': ('nota.xml', helpers['xml']())}, data={'csrf': 'invalido'}).status_code == 401


def test_login_admin_importa_e_logout_revoga_sessao(tmp_path):
    cfg, app = setup(tmp_path)
    with TestClient(app) as client:
        token = helpers['login'](client, cfg)
        cookie = client.cookies[cfg.admin_cookie_name]
        assert 'name="files"' in client.get('/atualizar').text
        assert 'name="files"' not in client.get('/xml').text
        assert client.post('/xml/importar', data={'csrf': 'invalido'}, files={'files': ('a.xml', helpers['xml']())}).status_code == 403
        response = client.post('/xml/importar', data={'csrf': token}, files={'files': ('a.xml', helpers['xml']())}, follow_redirects=False)
        assert response.status_code == 303
        assert '1 importada(s)' in client.get(response.headers['location']).text
        assert client.post('/admin/logout', data={'csrf': token}, follow_redirects=False).status_code == 303
        client.cookies.set(cfg.admin_cookie_name, cookie)
        assert client.get('/atualizar', follow_redirects=False).status_code == 303
        assert client.get('/xml/arquivo/' + helpers['CHAVE']).status_code == 200
        assert client.post('/xml/importar', data={'csrf': token}, files={'files': ('a.xml', helpers['xml']())}).status_code == 401


def test_login_recusa_senha_invalida_e_conta_fiscal(tmp_path):
    cfg, app = setup(tmp_path)
    app.state.admin_accounts.create('fiscal', PASSWORD, 'fiscal')
    with TestClient(app) as client:
        for username, password in [('admin', 'errada'), ('fiscal', PASSWORD)]:
            response = client.post('/admin/login', data={'csrf': csrf_token(PUBLIC_USER, cfg), 'username': username, 'password': password})
            assert response.status_code == 401
        assert client.get('/atualizar', follow_redirects=False).status_code == 303


@pytest.mark.parametrize('url, secure', [('http://172.16.190.130:8080', False), ('https://app.empresa.test', True)])
def test_sessao_em_producao_funciona_em_http_local_e_https(tmp_path, url, secure):
    cfg, _ = setup(tmp_path)
    cfg = replace(cfg, environment='production')
    with TestClient(create_app(cfg), base_url=url) as client:
        response = client.post('/admin/login', data={'csrf': csrf_token(PUBLIC_USER, cfg), 'username': cfg.admin_username, 'password': cfg.admin_password}, follow_redirects=False)
        assert response.status_code == 303
        assert ('; Secure' in response.headers['set-cookie']) == secure
        assert 'HttpOnly' in response.headers['set-cookie']
        assert client.get('/atualizar').status_code == 200


def test_configurador_redefine_so_conta_escolhida_e_revoga_sessoes(tmp_path):
    path = tmp_path / 'contas.db'
    accounts = AdminAccounts(path, bootstrap_username='admin', bootstrap_password=PASSWORD)
    accounts.create('outro', PASSWORD, 'fiscal')
    token = accounts.new_session('admin')
    nova = 'Nova-senha-administrativa-123!'
    configure_account(path, 'admin', nova)
    assert accounts.authenticate('admin', nova) == 'admin'
    assert accounts.authenticate('admin', PASSWORD) is None
    assert accounts.authenticate('outro', PASSWORD) == 'outro'
    assert accounts.session_username(token, 1800) is None
    assert len(list(tmp_path.glob('contas_backup_*.db'))) == 1
    assert nova.encode() not in path.read_bytes()


def test_migracao_preserva_senha_e_admin_e_revoga_sessoes_antigas(tmp_path):
    path=tmp_path/'contas.db'
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE admins(username TEXT PRIMARY KEY COLLATE NOCASE,password_hash TEXT NOT NULL,active INTEGER NOT NULL DEFAULT 1)')
        encoded=_hash_password(PASSWORD)
        db.execute('INSERT INTO admins VALUES (?,?,1)',('legado',encoded))
        db.execute('CREATE TABLE admin_sessions(token_hash TEXT PRIMARY KEY, username TEXT,created_at INTEGER,last_seen INTEGER,expires_at INTEGER)')
        db.execute('INSERT INTO admin_sessions VALUES (?,?,?,?,?)',('antigo','legado',1,1,9999999999))
    accounts=AdminAccounts(path,bootstrap_username='admin',bootstrap_password=PASSWORD)
    assert accounts.authenticate('legado',PASSWORD)=='legado'
    assert accounts.role('legado')=='admin'
    assert accounts.role('admin') is None
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT count(*) FROM admin_sessions').fetchone()[0]==0
        assert db.execute('SELECT password_hash FROM admins').fetchone()[0]==encoded
    accounts.create('novo',PASSWORD)
    assert accounts.role('novo')=='consulta'
