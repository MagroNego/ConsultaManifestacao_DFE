"""Autenticação simples da área administrativa."""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass

from fastapi import HTTPException, Request, Response, status

from nfe_consulta.web.admin_accounts import AdminAccounts
from nfe_consulta.web.settings import WebSettings


@dataclass(frozen=True)
class WebUser:
    username: str
    display_name: str
    is_admin: bool
    session_token: str = ""


PUBLIC_USER = WebUser(
    username="usuario-interno",
    display_name="Usuário",
    is_admin=False,
)


def _session_username(token: str, settings: WebSettings, accounts: AdminAccounts) -> str | None:
    return accounts.session_username(token, settings.admin_session_minutes * 60)


def admin_session_active(request: Request) -> bool:
    settings: WebSettings = request.app.state.settings
    token = request.cookies.get(settings.admin_cookie_name, "")
    return _session_username(token, settings, request.app.state.admin_accounts) is not None


def current_user(request: Request) -> WebUser:
    settings: WebSettings = request.app.state.settings

    username = _session_username(
        request.cookies.get(settings.admin_cookie_name, ""),
        settings, request.app.state.admin_accounts,
    )
    if username:
        return WebUser(
            username=username,
            display_name=username,
            is_admin=True,
            session_token=request.cookies.get(settings.admin_cookie_name, ""),
        )

    return PUBLIC_USER


def require_admin(request: Request) -> WebUser:
    user = current_user(request)
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Faça login para acessar a área Atualizar.",
        )
    return user


def set_admin_cookie(response: Response, settings: WebSettings, token: str) -> None:
    response.set_cookie(
        key=settings.admin_cookie_name,
        value=token,
        max_age=settings.admin_session_minutes * 60,
        httponly=True,
        secure=settings.production,
        samesite="strict",
        path="/",
    )


def clear_admin_cookie(response: Response, settings: WebSettings) -> None:
    response.delete_cookie(
        key=settings.admin_cookie_name,
        path="/",
        secure=settings.production,
        httponly=True,
        samesite="strict",
    )


def csrf_token(user: WebUser, settings: WebSettings) -> str:
    # A área pública usa um token de origem; a área administrativa vincula
    # cada formulário à sessão concreta, revogada no logout.
    identidade = user.session_token if user.is_admin else "publico"
    mensagem = f"{user.username.casefold()}|{identidade}|nfe-web-v3".encode("utf-8")
    return hmac.new(
        settings.csrf_secret.encode("utf-8"),
        mensagem,
        hashlib.sha256,
    ).hexdigest()


def validate_csrf(token: str, user: WebUser, settings: WebSettings) -> None:
    esperado = csrf_token(user, settings)
    if not token or not hmac.compare_digest(token, esperado):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token de segurança inválido.",
        )
