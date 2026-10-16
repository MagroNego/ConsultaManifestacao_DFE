"""Relógio da política de horário determinístico para testes com SEFAZ simulada."""
from datetime import datetime, timedelta

import pytest

from nfe_consulta import janela_consulta


@pytest.fixture(autouse=True)
def horario_noturno(monkeypatch):
    agora = datetime.now(janela_consulta.BRASILIA)
    referencia = agora.replace(hour=1, minute=0, second=0, microsecond=0)
    if referencia > agora:
        referencia -= timedelta(days=1)
    # Mantém o relógio da política anterior às reservas feitas no banco real.
    # Os testes específicos de janela sobrescrevem este relógio nos limites.
    monkeypatch.setattr(
        janela_consulta, "agora_brasilia",
        lambda: referencia,
    )


def authenticated_user(client):
    """Abre sessão comum para testes de consultas e relatórios protegidos."""
    from nfe_consulta.web.auth import PUBLIC_USER, WebUser, csrf_token
    app = client.app
    cfg = app.state.settings
    accounts = app.state.admin_accounts
    if accounts.role('teste-comum') is None:
        accounts.create('teste-comum', 'Senha-comum-teste-123!', 'fiscal')
    client.cookies.clear()
    response = client.post('/login', data={'csrf': csrf_token(PUBLIC_USER, cfg),
        'username': 'teste-comum', 'password': 'Senha-comum-teste-123!'}, follow_redirects=False)
    assert response.status_code == 303
    return csrf_token(WebUser('teste-comum', 'teste-comum', False,
        client.cookies[cfg.admin_cookie_name], 'fiscal'), cfg)


async def authenticated_async_user(client, app):
    from nfe_consulta.web.auth import PUBLIC_USER, WebUser, csrf_token
    cfg = app.state.settings
    accounts = app.state.admin_accounts
    accounts.create('teste-comum', 'Senha-comum-teste-123!', 'fiscal')
    response = await client.post('/login', data={'csrf': csrf_token(PUBLIC_USER, cfg),
        'username': 'teste-comum', 'password': 'Senha-comum-teste-123!'}, follow_redirects=False)
    assert response.status_code == 303
    return csrf_token(WebUser('teste-comum', 'teste-comum', False,
        client.cookies[cfg.admin_cookie_name], 'fiscal'), cfg)
