"""Política de acesso aos dados fiscais, inclusive URLs diretas."""
import json
import runpy
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from nfe_consulta.web.admin_accounts import AdminAccounts, _hash_password
from nfe_consulta.web.auth import PUBLIC_USER, WebUser, csrf_token
from nfe_consulta.web.app import create_app
from nfe_consulta.web import xml_store as store
from nfe_consulta.config import CNPJ_PADRAO

helpers = runpy.run_path(str(Path(__file__).with_name('test_xml_integrado.py')))
CHAVE = helpers['CHAVE']
PASSWORD = 'Senha-individual-123!'


def setup(tmp_path):
    cfg = helpers['helpers']['settings_web'](tmp_path)
    helpers['helpers']['criar_banco'](cfg.database_path)
    source = tmp_path / 'nota.xml'
    source.write_bytes(helpers['xml']())
    store.import_batch(cfg.database_path,CNPJ_PADRAO,[(source,'nota.xml')])
    from nfe_consulta.banco import BancoManifestacoes
    from nfe_consulta.modelos import Manifestacao, RetornoDistribuicao
    banco=BancoManifestacoes(str(cfg.database_path))
    banco.salvar_retorno(CNPJ_PADRAO,RetornoDistribuicao(138,'ok','1'.zfill(15),'1'.zfill(15),((CHAVE,Manifestacao('210240','Operação não Realizada','2026-10-01T10:00:00-03:00','1')),),0))
    banco.fechar()
    app=create_app(cfg)
    for role in ['consulta','fiscal']:
        app.state.admin_accounts.create(role,PASSWORD,role)
    return cfg, app


def login(client,cfg,role):
    name = 'admin' if role == 'admin' else role
    password = cfg.admin_password if role == 'admin' else PASSWORD
    response=client.post('/admin/login',data={'csrf':csrf_token(PUBLIC_USER,cfg),'username':name,'password':password},follow_redirects=False)
    assert response.status_code==303
    assert response.headers['location'].endswith('/atualizar' if role=='admin' else '/consulta')
    user=WebUser(name,name,role=='admin',client.cookies[cfg.admin_cookie_name],role)
    return csrf_token(user,cfg)


@pytest.mark.parametrize('path', ['/consulta','/status','/xml','/xml?tipo=itens','/xml?tipo=retencoes','/xml/arquivo/'+CHAVE,'/xml/exportar','/consulta/exportar','/xml/lote/1/registro','/admin/contas','/admin/historico','/openapi.json','/docs'])
def test_anonimo_nao_recebe_dados_por_url_direta(tmp_path,path):
    cfg,app=setup(tmp_path)
    with TestClient(app) as client:
        response=client.get(path,follow_redirects=False)
        assert response.status_code in (303,401)
        assert response.headers['cache-control']=='no-store'
        assert CHAVE not in response.text and 'Produto de teste' not in response.text
        forged=client.get(path,headers={'X-NFE-User':'admin','X-NFE-Name':'Administrador'},cookies={cfg.admin_cookie_name:'token-falso'},follow_redirects=False)
        assert forged.status_code in (303,401)


@pytest.mark.parametrize('role',['consulta','fiscal','admin'])
def test_matriz_de_permissoes_no_servidor_e_na_tela(tmp_path,role):
    cfg,app=setup(tmp_path)
    with TestClient(app) as client:
        token=login(client,cfg,role)
        for path in ['/consulta','/status','/xml','/xml?tipo=itens','/xml?tipo=retencoes']:
            assert client.get(path).status_code==200
        xml_page=client.get('/xml')
        assert ('Importar e arquivar' in xml_page.text) == (role=='admin')
        assert ('/xml/arquivo/' in xml_page.text) == (role!='consulta')
        assert ('>EXCEL</button>' in xml_page.text) == (role!='consulta')
        assert ('>Atualizar</a>' in xml_page.text) == (role=='admin')
        assert 'Sair' in xml_page.text
        for path in ['/xml/arquivo/'+CHAVE,'/xml/exportar?formato=csv','/xml/exportar?formato=xlsx','/consulta/exportar']:
            response=client.get(path)
            assert response.status_code == (403 if role=='consulta' else 200)
        response=client.post('/excel',data={'csrf':token},files={'files':('chaves.txt',CHAVE)})
        assert response.status_code == (403 if role=='consulta' else 200)
        for path in ['/admin/contas','/admin/historico','/atualizar','/xml/lote/1/registro']:
            assert client.get(path).status_code == (200 if role=='admin' else 403)
        if role!='admin':
            for path in ['/atualizar/sincronizar','/atualizar/banco','/atualizar/certificado','/atualizar/alertas-email','/atualizar/alertas-email/enviar-pendentes']:
                response=client.post(path,data={'csrf':token,'confirmacao':'sincronizar'})
                assert response.status_code==403
            response=client.post('/xml/importar',data={'csrf':token},files={'files':('nota.xml',helpers['xml']())})
            assert response.status_code==403
            response=client.post('/admin/contas',data={'csrf':token,'action':'role','username':role,'role':'admin'})
            assert response.status_code==403
            assert app.state.admin_accounts.role(role)==role
        logout=client.post('/admin/logout',data={'csrf':token},follow_redirects=False)
        assert logout.status_code==303
        assert client.get('/xml/arquivo/'+CHAVE).status_code==401


@pytest.mark.parametrize('operation',['role','reset','deactivate'])
def test_administrador_revoga_sessao_ao_mudar_acesso(tmp_path,operation):
    cfg,app=setup(tmp_path)
    with TestClient(app) as admin,TestClient(app) as fiscal:
        token=login(admin,cfg,'admin');oldcsrf=login(fiscal,cfg,'fiscal');cookie=fiscal.cookies[cfg.admin_cookie_name]
        response=admin.post('/admin/contas',data={'csrf':token,'action':operation,'username':'fiscal','role':'consulta','password':'Senha-nova-individual-123!'},follow_redirects=False)
        assert response.status_code==303
        fiscal.cookies.clear()
        fiscal.cookies.set(cfg.admin_cookie_name,cookie,domain='testserver.local',path='/')
        assert fiscal.get('/xml/arquivo/'+CHAVE).status_code==401
        assert fiscal.post('/excel',data={'csrf':oldcsrf},files={'files':('chaves.txt',CHAVE)}).status_code==401
        if operation=='role':
            login(fiscal,cfg,'fiscal')  # mesmo usuário, agora Consulta
            assert fiscal.get('/xml/arquivo/'+CHAVE).status_code==403


def test_cadastro_padrao_consulta_e_ultimo_admin_protegido(tmp_path):
    cfg,app=setup(tmp_path)
    with TestClient(app) as client:
        token=login(client,cfg,'admin')
        response=client.post('/admin/contas',data={'csrf':token,'action':'create','username':'novo','password':PASSWORD},follow_redirects=False)
        assert response.status_code==303
        assert app.state.admin_accounts.role('novo')=='consulta'
        for action in ['role','deactivate']:
            response=client.post('/admin/contas',data={'csrf':token,'action':action,'username':'admin','role':'fiscal'})
            assert response.status_code==400 and 'pelo menos um' in response.text
        assert app.state.admin_accounts.role('admin')=='admin'
        assert client.post('/admin/contas',data={'csrf':token,'action':'role','username':'novo','role':'superuser'}).status_code==400


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


def test_auditoria_identifica_fiscal_sem_conteudo_xml(tmp_path):
    cfg,app=setup(tmp_path)
    with TestClient(app) as client:
        login(client,cfg,'fiscal')
        assert client.get('/xml/arquivo/'+CHAVE).status_code==200
        assert client.get('/xml/exportar?formato=csv').status_code==200
    lines=cfg.audit_log.read_text()
    payloads=[json.loads(line[line.index('{'):]) for line in lines.splitlines()]
    assert any(x['user']=='fiscal' and x['action']=='admin_login' and x['role']=='fiscal' for x in payloads)
    assert any(x['user']=='fiscal' and x['action']=='xml_download' and x['role']=='fiscal' for x in payloads)
    assert any(x['user']=='fiscal' and x['action']=='xml_export' for x in payloads)
    assert PASSWORD not in lines and 'Produto de teste' not in lines and CHAVE not in lines


def test_todas_rotas_de_escrita_negam_anonimo_antes_de_processar_corpo(tmp_path):
    cfg,app=setup(tmp_path)
    with TestClient(app) as client:
        for route in app.routes:
            if 'POST' in getattr(route,'methods',set()) and route.path != '/admin/login':
                assert client.post(route.path,data={'csrf':csrf_token(PUBLIC_USER,cfg)}).status_code==401


def test_sessao_expirada_nao_libera_xml(tmp_path):
    cfg,app=setup(tmp_path)
    with TestClient(app) as client:
        login(client,cfg,'fiscal')
        with sqlite3.connect(app.state.admin_accounts.path) as db:
            db.execute('UPDATE admin_sessions SET last_seen=1')
        assert client.get('/xml/arquivo/'+CHAVE).status_code==401


def test_csrf_fiscal_vinculado_a_sessao(tmp_path):
    cfg,app=setup(tmp_path)
    with TestClient(app) as client:
        old=login(client,cfg,'fiscal')
        assert client.post('/admin/logout',data={'csrf':csrf_token(PUBLIC_USER,cfg)}).status_code==403
        client.post('/admin/logout',data={'csrf':old})
        login(client,cfg,'fiscal')
        assert client.post('/excel',data={'csrf':old},files={'files':('chaves.txt',CHAVE)}).status_code==403
