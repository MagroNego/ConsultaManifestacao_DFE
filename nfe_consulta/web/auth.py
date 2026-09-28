"""Autenticação simples da área administrativa."""

from __future__ import annotations

import hashlib
import hmac
import time
from dataclasses import dataclass

from fastapi import HTTPException, Request, Response, status

from nfe_consulta.web.admin_accounts import AdminAccounts
from nfe_consulta.web.settings import WebSettings


@dataclass(frozen=True)
class WebUser:
    username: str
    display_name: str
    is_admin: bool


PUBLIC_USER = WebUser(
    username="usuario-interno",
    display_name="Usuário",
    is_admin=False,
)


def _session_key(settings: WebSettings, password_hash: str) -> bytes:
    return hmac.new(
        settings.csrf_secret.encode("utf-8"),
        password_hash.encode("utf-8"),
        hashlib.sha256,
    ).digest()


def _session_signature(payload: str, settings: WebSettings, password_hash: str) -> str:
    return hmac.new(
        _session_key(settings, password_hash),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _new_session_token(settings: WebSettings, username: str, password_hash: str) -> str:
    expires_at = int(time.time()) + settings.admin_session_minutes * 60
    payload = f"{username}|{expires_at}"
    return f"{payload}|{_session_signature(payload, settings, password_hash)}"


def _session_username(token: str, settings: WebSettings, accounts: AdminAccounts) -> str | None:
    if not token:
        return None

    try:
        username, expires_raw, signature = token.rsplit("|", 2)
        expires_at = int(expires_raw)
    except (ValueError, TypeError):
        return None

    if expires_at <= int(time.time()):
        return None

    account = accounts.account(username)
    if account is None:
        return None
    payload = f"{username}|{expires_at}"
    esperado = _session_signature(payload, settings, account[1])
    return account[0] if hmac.compare_digest(signature, esperado) else None


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


def set_admin_cookie(response: Response, settings: WebSettings, accounts: AdminAccounts, username: str) -> None:
    account = accounts.account(username)
    if account is None:
        return
    response.set_cookie(
        key=settings.admin_cookie_name,
        value=_new_session_token(settings, account[0], account[1]),
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
