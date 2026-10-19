"""Vínculo de e-mail, migração e identidade única sem expor credenciais."""
import sqlite3
import runpy
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from nfe_consulta.web.admin_accounts import AdminAccounts, _hash_password
from nfe_consulta.web.auth import PUBLIC_USER, csrf_token

helpers = runpy.run_path(str(Path(__file__).with_name('test_self_registration.py')))
PASSWORD = helpers['PASSWORD']


def accounts(tmp_path):
    return AdminAccounts(tmp_path/'accounts.db', bootstrap_username='admin', bootstrap_password=PASSWORD)


def test_existing_database_migration_preserves_password_role_and_session(tmp_path):
    path = tmp_path/'old.db'
    encoded = _hash_password(PASSWORD)
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE admins(username TEXT PRIMARY KEY COLLATE NOCASE,password_hash TEXT,active INTEGER,role TEXT)')
        db.execute('INSERT INTO admins VALUES (?,?,1,?)', ('legado', encoded, 'fiscal'))
    store = AdminAccounts(path, bootstrap_username='admin', bootstrap_password=None)
    session = store.new_session('legado')
    store = AdminAccounts(path, bootstrap_username='admin', bootstrap_password=None)
    assert store.authenticate('legado', PASSWORD) == 'legado'
    assert store.session_username(session, 1800) == 'legado'
    assert store.list_accounts() == [dict(username='legado', active=True, role='fiscal', email=None)]
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT password_hash FROM admins').fetchone()[0] == encoded


def test_email_login_normalization_uniqueness_and_revocation(tmp_path):
    store = accounts(tmp_path)
    store.create('fiscal', PASSWORD, 'fiscal', '  Fiscal+notas@EXAMPLE.COM  ')
    assert store.authenticate('FISCAL+NOTAS@example.com', PASSWORD) == 'fiscal'
    assert store.authenticate('fiscal', PASSWORD) == 'fiscal'
    assert store.authenticate('fiscal+notas@example.com', 'errada') is None
    with pytest.raises(ValueError):
        store.create('outro', PASSWORD, 'fiscal', 'fiscal+notas@example.com')
    session = store.new_session('fiscal')
    store.set_email('fiscal', 'novo@example.com')
    assert store.session_username(session, 1800) is None
    assert store.authenticate('fiscal+notas@example.com', PASSWORD) is None
    assert store.authenticate('novo@example.com', PASSWORD) == 'fiscal'
    store.set_active('fiscal', False)
    assert store.authenticate('novo@example.com', PASSWORD) is None
    with pytest.raises(ValueError):
        store.create('outro', PASSWORD, email='novo@example.com')


def test_email_cannot_shadow_existing_username_or_email(tmp_path):
    store = accounts(tmp_path)
    store.create('legado@example.com', PASSWORD)
    with pytest.raises(ValueError):
        store.create('novo', PASSWORD, email='LEGADO@example.com')
    store.create('segundo', PASSWORD, email='segundo@example.com')
    with pytest.raises(ValueError):
        store.create('SEGUNDO@example.com', PASSWORD)
    with pytest.raises(ValueError):
        store.set_email('admin', 'segundo@example.com')
    assert store.authenticate('segundo@example.com', PASSWORD) == 'segundo'


@pytest.mark.parametrize('email', ['', 'sem-arroba', 'a@localhost', 'a@-dominio.com', '.a@example.com', 'a..b@example.com', 'a@example.com\r\nBcc:b@example.com'])
def test_reject_invalid_email(tmp_path, email):
    store = accounts(tmp_path)
    with pytest.raises(ValueError):
        store.create('novo', PASSWORD, email=email)
    assert store.account('novo') is None


def test_register_requires_email_and_login_accepts_it(tmp_path):
    cfg, app = helpers['setup'](tmp_path)
    with TestClient(app) as client:
        data = dict(csrf=csrf_token(PUBLIC_USER, cfg), username='novo', password=PASSWORD, password_confirmation=PASSWORD)
        assert client.post('/cadastro', data=data).status_code == 400
        assert app.state.admin_accounts.account('novo') is None
        assert client.post('/cadastro', data={**data, 'email':'novo@example.com', 'role':'admin'}).status_code == 200
        assert app.state.admin_accounts.role('novo') == 'fiscal'
        response = client.post('/login', data=dict(csrf=data['csrf'], username='NOVO@example.com', password=PASSWORD), follow_redirects=False)
        assert response.status_code == 303
        assert client.get('/consulta').status_code == 200
        assert client.post('/admin/contas', data=dict(action='email', username='novo',email='hack@example.com')).status_code == 401


def test_admin_links_email_with_csrf_without_leaking_password(tmp_path):
    cfg, app = helpers['setup'](tmp_path)
    store = app.state.admin_accounts
    store.create('legado', PASSWORD, 'fiscal')
    session = store.new_session('legado')
    with TestClient(app) as client:
        csrf = helpers['web']['entrar_admin'](client, cfg)
        html = client.get('/admin/contas').text
        assert 'E-mail não vinculado' in html and 'data-password-toggle' in html
        assert PASSWORD not in html
        data = dict(csrf=csrf, action='email',username='legado',email='legado@example.com')
        assert client.post('/admin/contas', data={**data, 'csrf':'invalido'}).status_code == 403
        assert store.list_accounts()[-1]['email'] is None
        assert client.post('/admin/contas', data=data, follow_redirects=False).status_code == 303
        assert store.authenticate('legado@example.com', PASSWORD) == 'legado'
        assert store.session_username(session, 1800) is None
        html = client.get('/admin/contas').text
        assert 'legado@example.com' in html and PASSWORD not in html
        # Criação administrativa também exige e-mail.
        assert client.post('/admin/contas', data=dict(csrf=csrf,action='create',username='sememail',password=PASSWORD)).status_code == 400
        assert store.account('sememail') is None
