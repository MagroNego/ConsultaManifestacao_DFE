"""Contrato de confiança e autorização do gateway corporativo."""
from dataclasses import replace
from pathlib import Path
import runpy

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from nfe_consulta.web.app import create_app
from nfe_consulta.web.auth import current_user, csrf_token

web = runpy.run_path(str(Path(__file__).with_name('test_web.py')))


def config(tmp_path):
    return replace(web['settings_web'](tmp_path), local_auth_enabled=False,
        corporate_auth_enabled=True, auth_mode='proxy',
        allowed_groups=frozenset({'atlas-consulta'}), admin_groups=frozenset({'atlas-admin'}))


def headers(cfg, groups='atlas-consulta', user='luan@empresa.local'):
    return {cfg.proxy_secret_header: cfg.proxy_secret, cfg.user_header: user, cfg.groups_header: groups}


def test_gateway_identity_and_permissions(tmp_path):
    cfg = config(tmp_path)
    web['criar_banco'](cfg.database_path)
    app = create_app(cfg)
    with TestClient(app) as client:
        assert client.get('/healthz').status_code == 200
        assert client.get('/consulta').status_code == 401
        forged = headers(cfg); forged.pop(cfg.proxy_secret_header)
        assert client.get('/consulta', headers=forged).status_code == 401
        assert client.get('/consulta', headers=headers(cfg, 'outro-grupo')).status_code == 401
        assert client.get('/consulta', headers=headers(cfg)).status_code == 200
        assert client.get('/atualizar', headers=headers(cfg)).status_code == 403
        assert client.post('/admin/agendamento', headers=headers(cfg), data={}).status_code == 403
        assert client.get('/atualizar', headers=headers(cfg, 'atlas-admin')).status_code == 200
        assert client.get('/admin/contas', headers=headers(cfg, 'atlas-admin')).status_code == 404
        assert client.post('/admin/agendamento', headers=headers(cfg, 'atlas-admin'), data={'csrf': 'errado'}).status_code == 403
        assert client.get('/consulta', headers=[*headers(cfg).items(), (cfg.user_header, 'outra@empresa.local')]).status_code == 401
    assert app.state.admin_accounts is None
    assert not (cfg.database_path.parent / 'admin_accounts.db').exists()


def test_csrf_is_bound_to_corporate_identity_and_groups(tmp_path):
    cfg = config(tmp_path)
    app = create_app(cfg)
    def user(name, groups):
        scope = {'type': 'http', 'app': app, 'headers': [(k.lower().encode(), v.encode()) for k,v in headers(cfg, groups, name).items()]}
        return current_user(Request(scope))
    first = user('LUAN@EMPRESA.LOCAL', 'atlas-consulta')
    assert first.username == 'luan@empresa.local'
    assert not first.is_admin
    assert csrf_token(first,cfg) != csrf_token(user('ana@empresa.local','atlas-consulta'),cfg)
    assert csrf_token(first,cfg) != csrf_token(user('luan@empresa.local','atlas-admin'),cfg)


@pytest.mark.parametrize('changes', [
    {'local_auth_enabled': True}, {'auth_mode':'dev'}, {'proxy_secret':None},
    {'proxy_secret':'curto'}, {'allowed_groups':frozenset(), 'admin_groups':frozenset()},
    {'groups_header':'X-NFE-User'},
])
def test_incomplete_configuration_fails_closed(tmp_path, changes):
    with pytest.raises(RuntimeError):
        create_app(replace(config(tmp_path), **changes))
