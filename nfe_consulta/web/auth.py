"""Autenticação simples da área administrativa."""

from __future__ import annotations

import hashlib
import hmac
import time
from dataclasses import dataclass

from fastapi import HTTPException, Request, Response, status

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


def _session_key(settings: WebSettings) -> bytes:
    material = settings.admin_password or "admin-not-configured"
    return hmac.new(
        settings.csrf_secret.encode("utf-8"),
        material.encode("utf-8"),
        hashlib.sha256,
    ).digest()


def _session_signature(payload: str, settings: WebSettings) -> str:
    return hmac.new(
        _session_key(settings),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _new_session_token(settings: WebSettings) -> str:
    expires_at = int(time.time()) + settings.admin_session_minutes * 60
    payload = f"{settings.admin_username}|{expires_at}"
    return f"{payload}|{_session_signature(payload, settings)}"


def _valid_session_token(token: str, settings: WebSettings) -> bool:
    if not token:
        return False

    try:
        username, expires_raw, signature = token.rsplit("|", 2)
        expires_at = int(expires_raw)
    except (ValueError, TypeError):
        return False

    if username.casefold() != settings.admin_username.casefold():
        return False
    if expires_at <= int(time.time()):
        return False

    payload = f"{username}|{expires_at}"
    esperado = _session_signature(payload, settings)
    return hmac.compare_digest(signature, esperado)


def admin_session_active(request: Request) -> bool:
    settings: WebSettings = request.app.state.settings
    token = request.cookies.get(settings.admin_cookie_name, "")
    return _valid_session_token(token, settings)


def current_user(request: Request) -> WebUser:
    settings: WebSettings = request.app.state.settings

    if settings.auth_mode == "proxy":
        usuario = request.headers.get(settings.user_header, "").strip()
        assinatura = request.headers.get(settings.proxy_secret_header, "")
        if (
            not settings.proxy_secret
            or not hmac.compare_digest(assinatura, settings.proxy_secret)
            or not usuario
            or len(usuario) > 128
            or any(c in usuario for c in "\r\n\t")
        ):
            return PUBLIC_USER
        nome = request.headers.get(settings.name_header, "").strip()
        if not nome or len(nome) > 128 or any(c in nome for c in "\r\n\t"):
            nome = usuario
        return WebUser(
            username=usuario,
            display_name=nome,
            is_admin=usuario.casefold() in settings.admin_users,
        )

    if admin_session_active(request):
        return WebUser(
            username=settings.admin_username,
            display_name="Administrador",
            is_admin=True,
        )

    return PUBLIC_USER


def require_admin(request: Request) -> WebUser:
    user = current_user(request)
    if not user.is_admin:
        raise HTTPException(
            status_code=(status.HTTP_403_FORBIDDEN if request.app.state.settings.auth_mode == "proxy"
                         else status.HTTP_401_UNAUTHORIZED),
            detail=("Seu usuário corporativo não tem acesso à área Atualizar."
                    if request.app.state.settings.auth_mode == "proxy"
                    else "Faça login para acessar a área Atualizar."),
        )
    return user


def authenticate_admin(
    username: str,
    password: str,
    settings: WebSettings,
) -> bool:
    if settings.auth_mode != "dev" or not settings.admin_password:
        return False

    usuario_ok = hmac.compare_digest(
        username.strip().casefold(),
        settings.admin_username.casefold(),
    )
    senha_ok = hmac.compare_digest(password, settings.admin_password)
    return usuario_ok and senha_ok


def set_admin_cookie(response: Response, settings: WebSettings) -> None:
    response.set_cookie(
        key=settings.admin_cookie_name,
        value=_new_session_token(settings),
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
