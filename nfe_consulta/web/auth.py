"""Autenticação e autorização da aplicação web."""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass

from fastapi import HTTPException, Request, status

from nfe_consulta.web.settings import WebSettings


@dataclass(frozen=True)
class WebUser:
    username: str
    display_name: str
    is_admin: bool


def _admin(username: str, settings: WebSettings) -> bool:
    return username.casefold() in settings.admin_users


def current_user(request: Request) -> WebUser:
    settings: WebSettings = request.app.state.settings

    if settings.auth_mode == "dev":
        return WebUser(
            username=settings.dev_user,
            display_name=settings.dev_name or settings.dev_user,
            is_admin=settings.dev_admin or _admin(settings.dev_user, settings),
        )

    segredo_recebido = request.headers.get(settings.proxy_secret_header, "")
    if not settings.proxy_secret or not hmac.compare_digest(
        segredo_recebido,
        settings.proxy_secret,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Requisição não autenticada pelo proxy corporativo.",
        )

    username = request.headers.get(settings.user_header, "").strip()
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário corporativo não informado pelo proxy.",
        )

    display_name = request.headers.get(settings.name_header, "").strip() or username
    return WebUser(
        username=username,
        display_name=display_name,
        is_admin=_admin(username, settings),
    )


def require_admin(request: Request) -> WebUser:
    user = current_user(request)
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso restrito a administradores.",
        )
    return user


def csrf_token(user: WebUser, settings: WebSettings) -> str:
    mensagem = f"{user.username.casefold()}|nfe-web-v2".encode("utf-8")
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
