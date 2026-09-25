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


def _ler_segredo(arquivo_env: str, valor_env: str, *, rotulo: str) -> str | None:
    arquivo = os.getenv(arquivo_env, "").strip()
    if arquivo:
        caminho = Path(arquivo).expanduser()
        if not caminho.is_file():
            raise RuntimeError(f"Arquivo de {rotulo} não encontrado: {caminho}")
        valor = caminho.read_text(encoding="utf-8").strip()
        if not valor:
            raise RuntimeError(f"Arquivo de {rotulo} está vazio.")
        return valor

    valor = os.getenv(valor_env)
    return valor if valor else None


def _senha_banco() -> str | None:
    return _ler_segredo(
        "NFE_DATABASE_PASSWORD_FILE",
        "NFE_DATABASE_PASSWORD",
        rotulo="senha do banco",
    )


def _senha_admin() -> str | None:
    return _ler_segredo(
        "NFE_ADMIN_PASSWORD_FILE",
        "NFE_ADMIN_PASSWORD",
        rotulo="senha do administrador",
    )


def _usuario_admin() -> str:
    arquivo = os.getenv("NFE_ADMIN_USER_FILE", "").strip()
    if arquivo:
        caminho = Path(arquivo).expanduser()
        if not caminho.is_file():
            raise RuntimeError(f"Arquivo de usuário administrador não encontrado: {caminho}")
        usuario = caminho.read_text(encoding="utf-8").strip()
    else:
        usuario = os.getenv("NFE_ADMIN_USER", "admin").strip()

    if not usuario:
        raise RuntimeError("Usuário administrador não pode ficar vazio.")
    if len(usuario) > 64 or any(c in usuario for c in "\r\n\t"):
        raise RuntimeError("Usuário administrador inválido.")
    return usuario


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
    forwarded_allow_ips: str
    audit_log: Path
    sync_cooldown_minutes: int = 120
    max_upload_bytes: int = 2 * 1024 * 1024
    max_keys: int = 10_000
    admin_username: str = "admin"
    admin_password: str | None = None
    admin_session_minutes: int = 30
    admin_cookie_name: str = "nfe_admin_session"
    certificate_path_file: Path | None = None
    certificate_password_file: Path | None = None
    database_path_file: Path | None = None

    @property
    def production(self) -> bool:
        return self.environment == "production"


@lru_cache(maxsize=1)
def get_settings() -> WebSettings:
    ambiente = os.getenv("NFE_WEB_ENV", "development").strip().lower()
    if ambiente not in {"development", "production"}:
        raise RuntimeError("NFE_WEB_ENV deve ser development ou production.")

    modo_padrao = "dev"
    auth_mode = os.getenv("NFE_WEB_AUTH_MODE", modo_padrao).strip().lower()
    if auth_mode not in {"proxy", "dev"}:
        raise RuntimeError("NFE_WEB_AUTH_MODE deve ser proxy ou dev.")
    proxy_secret = os.getenv("NFE_WEB_PROXY_SECRET")

    csrf_secret = os.getenv("NFE_WEB_CSRF_SECRET")
    if ambiente == "production":
        if not csrf_secret or len(csrf_secret) < 32:
            raise RuntimeError("Defina NFE_WEB_CSRF_SECRET com pelo menos 32 caracteres.")
    elif not csrf_secret:
        csrf_secret = secrets.token_urlsafe(32)

    admin_password = _senha_admin()
    admin_username = _usuario_admin()
    if admin_password and len(admin_password) < 12:
        raise RuntimeError("A senha do administrador deve ter pelo menos 12 caracteres.")
    if ambiente == "production" and not admin_password:
        raise RuntimeError(
            "Defina NFE_ADMIN_PASSWORD_FILE para proteger a área Atualizar."
        )

    admin_session_minutes = int(os.getenv("NFE_ADMIN_SESSION_MINUTES", "30"))
    if not 5 <= admin_session_minutes <= 480:
        raise RuntimeError("NFE_ADMIN_SESSION_MINUTES deve estar entre 5 e 480.")

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
        forwarded_allow_ips=os.getenv(
            "NFE_WEB_FORWARDED_ALLOW_IPS", "127.0.0.1"
        ).strip(),
        audit_log=audit,
        sync_cooldown_minutes=int(os.getenv("NFE_SEFAZ_COOLDOWN_MINUTES", "120")),
        admin_username=admin_username,
        admin_password=admin_password,
        admin_session_minutes=admin_session_minutes,
        admin_cookie_name=os.getenv(
            "NFE_ADMIN_COOKIE_NAME", "nfe_admin_session"
        ).strip() or "nfe_admin_session",
        certificate_path_file=Path(
            os.getenv(
                "NFE_CERT_PATH_FILE",
                str(RAIZ_PROJETO / "secrets" / "cert-path.txt"),
            )
        ).expanduser(),
        certificate_password_file=Path(
            os.getenv(
                "NFE_CERT_PASSWORD_FILE",
                str(RAIZ_PROJETO / "secrets" / "cert-password.txt"),
            )
        ).expanduser(),
        database_path_file=Path(
            os.getenv(
                "NFE_DATABASE_PATH_FILE",
                str(RAIZ_PROJETO / "secrets" / "db-path.txt"),
            )
        ).expanduser(),
    )
