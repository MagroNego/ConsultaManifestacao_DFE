"""Configuração da interface web corporativa."""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path


RAIZ_PROJETO = Path(__file__).resolve().parents[2]
SECRETS_DIR = RAIZ_PROJETO / "secrets"
DATABASE_PASSWORD_FILE = SECRETS_DIR / "db-password.txt"
ADMIN_USER_FILE = SECRETS_DIR / "admin-user.txt"
ADMIN_PASSWORD_FILE = SECRETS_DIR / "admin-password.txt"
CSRF_SECRET_FILE = SECRETS_DIR / "web-csrf-secret.txt"
CERT_PATH_FILE = SECRETS_DIR / "cert-path.txt"
CERT_PASSWORD_FILE = SECRETS_DIR / "cert-password.txt"
DATABASE_PATH_FILE = SECRETS_DIR / "db-path.txt"
EMAIL_RECIPIENTS_FILE = SECRETS_DIR / "email-recipients.json"
SMTP_PASSWORD_FILE = SECRETS_DIR / "smtp-password.txt"


def _lista(valor: str | None) -> frozenset[str]:
    if not valor:
        return frozenset()
    return frozenset(item.strip().casefold() for item in valor.split(",") if item.strip())


def _dias_semana(valor: str) -> tuple[int, ...]:
    try:
        dias = tuple(sorted({int(item.strip()) for item in valor.split(",") if item.strip()}))
    except ValueError as exc:
        raise RuntimeError("NFE_AUTO_SYNC_WEEKDAYS deve conter números de 0 a 6.") from exc
    if not dias or any(dia < 0 or dia > 6 for dia in dias):
        raise RuntimeError("NFE_AUTO_SYNC_WEEKDAYS deve conter ao menos um dia entre 0 e 6.")
    return dias


def _ler_segredo(caminho: Path, *, rotulo: str) -> str | None:
    """Lê segredos somente da pasta secrets da instalação."""
    if not caminho.is_file():
        return None

    valor = caminho.read_text(encoding="utf-8").rstrip("\r\n")
    if not valor:
        raise RuntimeError(f"Arquivo de {rotulo} está vazio: {caminho}")
    return valor


def _senha_banco() -> str | None:
    return _ler_segredo(DATABASE_PASSWORD_FILE, rotulo="senha do banco")


def _senha_admin() -> str | None:
    return _ler_segredo(ADMIN_PASSWORD_FILE, rotulo="senha do administrador")


def _usuario_admin() -> str:
    if ADMIN_USER_FILE.is_file():
        usuario = ADMIN_USER_FILE.read_text(encoding="utf-8").strip()
    else:
        usuario = "admin"

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
    sync_cooldown_minutes: int = 60
    max_upload_bytes: int = 2 * 1024 * 1024
    max_keys: int = 10_000
    admin_username: str = "admin"
    admin_password: str | None = None
    admin_session_minutes: int = 30
    admin_cookie_name: str = "nfe_admin_session"
    admin_accounts_path: Path | None = None
    certificate_path_file: Path | None = None
    certificate_password_file: Path | None = None
    database_path_file: Path | None = None
    database_password_file: Path | None = None
    auto_sync_enabled: bool = False
    auto_sync_interval_hours: int = 8
    auto_sync_hour: int = 8
    auto_sync_minute: int = 0
    auto_sync_weekdays: tuple[int, ...] = (0, 1, 2, 3, 4, 5, 6)
    auto_sync_max_lotes: int = 50
    auto_sync_once_date: date | None = None
    email_recipients_file: Path = EMAIL_RECIPIENTS_FILE
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_from: str = ""
    smtp_user: str = ""
    smtp_security: str = "starttls"
    smtp_password_file: Path = SMTP_PASSWORD_FILE

    @property
    def production(self) -> bool:
        return self.environment == "production"

    def current_database_password(self) -> str | None:
        """Retorna a senha atual do banco, priorizando o arquivo local configurado."""
        if self.database_password_file is not None:
            senha = _ler_segredo(
                self.database_password_file,
                rotulo="senha do banco",
            )
            if senha is not None:
                return senha
        return self.database_password


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
        if not csrf_secret:
            csrf_secret = _ler_segredo(CSRF_SECRET_FILE, rotulo="segredo da sessão Web")
        if not csrf_secret or len(csrf_secret) < 32:
            raise RuntimeError("Defina NFE_WEB_CSRF_SECRET ou secrets/web-csrf-secret.txt com pelo menos 32 caracteres.")
    elif not csrf_secret:
        csrf_secret = secrets.token_urlsafe(32)

    admin_password = _senha_admin()
    admin_username = _usuario_admin()
    if admin_password and len(admin_password) < 12:
        raise RuntimeError("A senha do administrador deve ter pelo menos 12 caracteres.")
    accounts_path = Path(os.getenv("NFE_ADMIN_ACCOUNTS_PATH", str(RAIZ_PROJETO / "dados" / "admin_accounts.db"))).expanduser()
    if ambiente == "production" and not admin_password and not accounts_path.is_file():
        raise RuntimeError(
            f"Configure {ADMIN_PASSWORD_FILE} para o primeiro acesso administrativo."
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

    auto_sync_enabled = os.getenv(
        "NFE_AUTO_SYNC_ENABLED",
        "0",
    ).strip() == "1"
    # Variáveis legadas não substituem os dois horários da rotina definitiva.
    auto_sync_once_date = None
    # Compatibilidade da configuração; a rotina recorrente usa 08:00 e 15:00.
    auto_sync_interval_hours = 8
    auto_sync_hour = 8
    auto_sync_minute = 0
    auto_sync_max_lotes = int(os.getenv("NFE_AUTO_SYNC_MAX_LOTES", "50"))
    auto_sync_weekdays = _dias_semana(
        os.getenv("NFE_AUTO_SYNC_WEEKDAYS", "0,1,2,3,4,5,6")
    )
    smtp_security = os.getenv("NFE_SMTP_SECURITY", "starttls").strip().lower()
    if smtp_security not in {"starttls", "ssl"}:
        raise RuntimeError("NFE_SMTP_SECURITY deve ser starttls ou ssl.")
    smtp_port = int(os.getenv("NFE_SMTP_PORT", "587"))
    if not 1 <= smtp_port <= 65535:
        raise RuntimeError("NFE_SMTP_PORT inválida.")
    smtp_from = os.getenv("NFE_SMTP_FROM", "").strip()
    if any(c in smtp_from for c in "\r\n"):
        raise RuntimeError("NFE_SMTP_FROM inválido.")

    if not 0 <= auto_sync_hour <= 23:
        raise RuntimeError("NFE_AUTO_SYNC_HOUR deve estar entre 0 e 23.")
    if not 0 <= auto_sync_minute <= 59:
        raise RuntimeError("NFE_AUTO_SYNC_MINUTE deve estar entre 0 e 59.")
    if not 1 <= auto_sync_max_lotes <= 500:
        raise RuntimeError("NFE_AUTO_SYNC_MAX_LOTES deve estar entre 1 e 500.")

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
        sync_cooldown_minutes=60,
        admin_username=admin_username,
        admin_password=admin_password,
        admin_accounts_path=accounts_path,
        admin_session_minutes=admin_session_minutes,
        admin_cookie_name=os.getenv(
            "NFE_ADMIN_COOKIE_NAME", "nfe_admin_session"
        ).strip() or "nfe_admin_session",
        certificate_path_file=CERT_PATH_FILE,
        certificate_password_file=CERT_PASSWORD_FILE,
        database_path_file=DATABASE_PATH_FILE,
        database_password_file=DATABASE_PASSWORD_FILE,
        auto_sync_enabled=auto_sync_enabled,
        auto_sync_interval_hours=auto_sync_interval_hours,
        auto_sync_hour=auto_sync_hour,
        auto_sync_minute=auto_sync_minute,
        auto_sync_weekdays=auto_sync_weekdays,
        auto_sync_max_lotes=auto_sync_max_lotes,
        auto_sync_once_date=auto_sync_once_date,
        smtp_host=os.getenv("NFE_SMTP_HOST", "").strip(),
        smtp_port=smtp_port,
        smtp_from=smtp_from,
        smtp_user=os.getenv("NFE_SMTP_USER", "").strip(),
        smtp_security=smtp_security,
    )
