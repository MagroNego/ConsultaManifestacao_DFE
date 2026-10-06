"""Identidade interna e proteção CSRF do aplicativo sem login."""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass

from fastapi import HTTPException, Request

from nfe_consulta.web.settings import WebSettings


@dataclass(frozen=True)
class WebUser:
    username: str
    display_name: str
    is_admin: bool
    session_token: str = ""
    role: str = "consulta"

    @property
    def authenticated(self) -> bool:
        return bool(self.session_token)

    @property
    def can_export(self) -> bool:
        return self.is_admin or self.role == "fiscal"


PUBLIC_USER = WebUser(
    username="usuario-interno",
    display_name="Usuário",
    is_admin=True,
    role="admin",
)


def current_user(request: Request) -> WebUser:
    """Acesso interno sem login; a rede determina quem alcança o aplicativo."""
    return PUBLIC_USER


def require_user(request: Request) -> WebUser:
    return current_user(request)


def require_admin(request: Request) -> WebUser:
    return current_user(request)


def require_export(request: Request) -> WebUser:
    return current_user(request)


def csrf_token(user: WebUser, settings: WebSettings) -> str:
    # Os formulários internos usam um token assinado pelo segredo do servidor.
    identidade = user.session_token if user.authenticated else "publico"
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
            status_code=403,
            detail="Token de segurança inválido.",
        )
