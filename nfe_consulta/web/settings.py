"""Configuração da interface web corporativa."""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


RAIZ_PROJETO = Path(__file__).resolve().parents[2]


def _lista(valor: str | None) -> frozenset[str]:
    if not valor:
        return frozenset()
    return frozenset(item.strip().casefold() for item in valor.split(",") if item.strip())


def _senha_banco() -> str | None:
    arquivo = os.getenv("NFE_DATABASE_PASSWORD_FILE", "").strip()
    if arquivo:
        caminho = Path(arquivo).expanduser()
        if not caminho.is_file():
            raise RuntimeError(f"Arquivo de senha do banco não encontrado: {caminho}")
        senha = caminho.read_text(encoding="utf-8").strip()
        if not senha:
            raise RuntimeError("Arquivo de senha do banco está vazio.")
        return senha

    senha = os.getenv("NFE_DATABASE_PASSWORD")
    return senha if senha else None


@dataclass(frozen=True)
class WebSettings:
    environment: str
    auth_mode: str
    user_header: str
    name_header: str
    proxy_secret_header: str
    proxy_secret: str | None
    admin_users: frozenset[str]
    dev_user: str
    dev_name: str
    dev_admin: bool
    csrf_secret: str
    database_path: Path
    database_password: str | None
    certificate_store: str
    certificate_thumbprint: str | None
    bind_host: str
    bind_port: int
    root_path: str
    audit_log: Path
    max_upload_bytes: int = 2 * 1024 * 1024
    max_keys: int = 10_000

    @property
    def production(self) -> bool:
        return self.environment == "production"


@lru_cache(maxsize=1)
def get_settings() -> WebSettings:
    ambiente = os.getenv("NFE_WEB_ENV", "development").strip().lower()
    if ambiente not in {"development", "production"}:
        raise RuntimeError("NFE_WEB_ENV deve ser development ou production.")

    modo_padrao = "proxy" if ambiente == "production" else "dev"
    auth_mode = os.getenv("NFE_WEB_AUTH_MODE", modo_padrao).strip().lower()
    if auth_mode not in {"proxy", "dev"}:
        raise RuntimeError("NFE_WEB_AUTH_MODE deve ser proxy ou dev.")
    if ambiente == "production" and auth_mode != "proxy":
        raise RuntimeError("Modo dev de autenticação é proibido em produção.")

    proxy_secret = os.getenv("NFE_WEB_PROXY_SECRET")
    if ambiente == "production" and (not proxy_secret or len(proxy_secret) < 24):
        raise RuntimeError("Defina NFE_WEB_PROXY_SECRET com pelo menos 24 caracteres.")

    csrf_secret = os.getenv("NFE_WEB_CSRF_SECRET")
    if ambiente == "production":
        if not csrf_secret or len(csrf_secret) < 32:
            raise RuntimeError("Defina NFE_WEB_CSRF_SECRET com pelo menos 32 caracteres.")
    elif not csrf_secret:
        csrf_secret = secrets.token_urlsafe(32)

    cert_store = os.getenv("NFE_CERT_STORE", "CurrentUser").strip()
    if cert_store not in {"CurrentUser", "LocalMachine"}:
        raise RuntimeError("NFE_CERT_STORE deve ser CurrentUser ou LocalMachine.")

    banco = Path(
        os.getenv(
            "NFE_DATABASE_PATH",
            str(RAIZ_PROJETO / "dados" / "nfe_manifestacoes_seguro.db"),
        )
    ).expanduser()

    audit = Path(
        os.getenv(
            "NFE_WEB_AUDIT_LOG",
            str(RAIZ_PROJETO / "logs" / "web_audit.log"),
        )
    ).expanduser()

    return WebSettings(
        environment=ambiente,
        auth_mode=auth_mode,
        user_header=os.getenv("NFE_WEB_USER_HEADER", "X-NFE-User").strip(),
        name_header=os.getenv("NFE_WEB_NAME_HEADER", "X-NFE-Name").strip(),
        proxy_secret_header=os.getenv(
            "NFE_WEB_PROXY_SECRET_HEADER", "X-NFE-Proxy-Secret"
        ).strip(),
        proxy_secret=proxy_secret,
        admin_users=_lista(os.getenv("NFE_WEB_ADMIN_USERS")),
        dev_user=os.getenv("NFE_WEB_DEV_USER", "dev@local").strip(),
        dev_name=os.getenv("NFE_WEB_DEV_NAME", "Desenvolvimento").strip(),
        dev_admin=os.getenv("NFE_WEB_DEV_ADMIN", "1").strip() == "1",
        csrf_secret=csrf_secret,
        database_path=banco,
        database_password=_senha_banco(),
        certificate_store=cert_store,
        certificate_thumbprint=(
            os.getenv("NFE_CERT_THUMBPRINT", "").replace(" ", "").strip() or None
        ),
        bind_host=os.getenv("NFE_WEB_HOST", "127.0.0.1").strip(),
        bind_port=int(os.getenv("NFE_WEB_PORT", "8080")),
        root_path=os.getenv("NFE_WEB_ROOT_PATH", "").strip(),
        audit_log=audit,
    )
