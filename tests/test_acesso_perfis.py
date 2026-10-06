"""Acesso interno sem login, com CSRF e dados existentes preservados."""
import runpy
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from nfe_consulta.web.admin_accounts import AdminAccounts, _hash_password
from nfe_consulta.web.auth import PUBLIC_USER, csrf_token
from nfe_consulta.web.app import create_app

helpers = runpy.run_path(str(Path(__file__).with_name("test_xml_integrado.py")))
PASSWORD = "Senha-individual-123!"


def setup(tmp_path):
    cfg = helpers["helpers"]["settings_web"](tmp_path)
    helpers["helpers"]["criar_banco"](cfg.database_path)
    return cfg, create_app(cfg)


@pytest.mark.parametrize("path", ["/consulta", "/status", "/xml", "/xml?tipo=itens", "/xml?tipo=retencoes", "/atualizar", "/admin/historico"])
def test_acesso_direto_sem_login(tmp_path, path):
    cfg, app = setup(tmp_path)
    with TestClient(app) as client:
        response = client.get(path)
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        assert '>Admin</a>' in response.text
        assert 'logout-form' not in response.text
        assert cfg.admin_cookie_name not in response.headers.get("set-cookie", "")


def test_importacao_somente_na_tela_admin_e_resultado_do_lote(tmp_path):
    cfg, app = setup(tmp_path)
    with TestClient(app) as client:
        assert 'name="files"' not in client.get('/xml').text
        assert 'name="files"' in client.get('/atualizar').text
        token = csrf_token(PUBLIC_USER, cfg)
        response = client.post('/xml/importar', data={'csrf': token},
            files={'files': ('nota.xml', helpers['xml']())}, follow_redirects=False)
        assert response.status_code == 303
        assert response.headers['location'].endswith('/atualizar?lote=1')
        result = client.get(response.headers['location'])
        assert '1 importada(s)' in result.text
        assert client.get('/xml/arquivo/' + helpers['CHAVE']).content == helpers['xml']()
        assert client.get('/xml/exportar?formato=csv').status_code == 200
        assert client.get('/xml/exportar?formato=xlsx').status_code == 200


def test_csrf_continua_obrigatorio_e_contas_nao_sao_usadas(tmp_path):
    cfg = helpers['helpers']['settings_web'](tmp_path)
    helpers['helpers']['criar_banco'](cfg.database_path)
    accounts = cfg.database_path.parent / 'admin_accounts.db'
    accounts.write_bytes(b'contas antigas preservadas')
    app = create_app(cfg)
    with TestClient(app) as client:
        assert client.get('/consulta').status_code == 200
        assert client.get('/admin/contas').status_code == 404
        assert client.post('/admin/login').status_code == 405
        for data in [{}, {'csrf': 'invalido'}]:
            response = client.post('/xml/importar', data=data, files={'files': ('nota.xml', helpers['xml']())})
            assert response.status_code == 403
    assert accounts.read_bytes() == b'contas antigas preservadas'


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


def test_historico_sem_login_preserva_privacidade_de_destinatarios(tmp_path):
    cfg, app = setup(tmp_path)
    with TestClient(app) as client:
        response = client.post('/atualizar/alertas-email', data={
            'csrf': csrf_token(PUBLIC_USER, cfg), 'recipients': 'fiscal@empresa.com'}, follow_redirects=False)
        assert response.status_code == 303
        history = client.get('/admin/historico')
        assert history.status_code == 200
        assert 'Destinatários dos alertas' in history.text
        assert 'usuario-interno' in history.text
        assert 'fiscal@empresa.com' not in history.text
