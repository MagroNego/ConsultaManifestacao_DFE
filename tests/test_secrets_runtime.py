from pathlib import Path
import pytest

from nfe_consulta import certificado_config
from nfe_consulta.web import settings


def test_producao_exige_gateway_e_lista_admin(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "ADMIN_PASSWORD_FILE", tmp_path / "admin-password.txt")
    monkeypatch.setenv("NFE_WEB_ENV", "production")
    monkeypatch.setenv("NFE_WEB_CSRF_SECRET", "c" * 64)
    settings.get_settings.cache_clear()
    try:
        with pytest.raises(RuntimeError, match="NFE_WEB_PROXY_SECRET"):
            settings.get_settings()
        monkeypatch.setenv("NFE_WEB_PROXY_SECRET", "p" * 64)
        with pytest.raises(RuntimeError, match="NFE_WEB_ADMIN_USERS"):
            settings.get_settings()
        monkeypatch.setenv("NFE_WEB_ADMIN_USERS", "DOMINIO\\luan.a")
        cfg = settings.get_settings()
        assert cfg.auth_mode == "proxy"
        assert cfg.admin_password is None
        monkeypatch.setenv("NFE_WEB_HOST", "0.0.0.0")
        settings.get_settings.cache_clear()
        with pytest.raises(RuntimeError, match="NFE_WEB_HOST"):
            settings.get_settings()
    finally:
        settings.get_settings.cache_clear()


def test_web_settings_usa_senhas_da_pasta_secrets_e_ignora_env(tmp_path, monkeypatch):
    secrets_dir = tmp_path / "secrets"
    secrets_dir.mkdir()

    admin_user = secrets_dir / "admin-user.txt"
    admin_password = secrets_dir / "admin-password.txt"
    db_password = secrets_dir / "db-password.txt"
    cert_path = secrets_dir / "cert-path.txt"
    cert_password = secrets_dir / "cert-password.txt"
    db_path = secrets_dir / "db-path.txt"

    admin_user.write_text("administrador\n", encoding="utf-8")
    admin_password.write_text("Senha-Admin-Arquivo-123!\n", encoding="utf-8")
    db_password.write_text("Senha-Banco-Arquivo-123!\n", encoding="utf-8")

    monkeypatch.setattr(settings, "ADMIN_USER_FILE", admin_user)
    monkeypatch.setattr(settings, "ADMIN_PASSWORD_FILE", admin_password)
    monkeypatch.setattr(settings, "DATABASE_PASSWORD_FILE", db_password)
    monkeypatch.setattr(settings, "CERT_PATH_FILE", cert_path)
    monkeypatch.setattr(settings, "CERT_PASSWORD_FILE", cert_password)
    monkeypatch.setattr(settings, "DATABASE_PATH_FILE", db_path)

    monkeypatch.setenv("NFE_ADMIN_USER", "usuario-env")
    monkeypatch.setenv("NFE_ADMIN_PASSWORD", "Senha-Admin-ENV-999!")
    monkeypatch.setenv("NFE_DATABASE_PASSWORD", "Senha-Banco-ENV-999!")
    monkeypatch.setenv("NFE_ADMIN_PASSWORD_FILE", str(tmp_path / "admin-env.txt"))
    monkeypatch.setenv("NFE_DATABASE_PASSWORD_FILE", str(tmp_path / "db-env.txt"))

    settings.get_settings.cache_clear()
    try:
        cfg = settings.get_settings()
    finally:
        settings.get_settings.cache_clear()

    assert cfg.admin_username == "administrador"
    assert cfg.admin_password == "Senha-Admin-Arquivo-123!"
    assert cfg.database_password == "Senha-Banco-Arquivo-123!"
    assert cfg.certificate_path_file == cert_path
    assert cfg.certificate_password_file == cert_password
    assert cfg.database_path_file == db_path


def test_certificado_usa_caminho_e_senha_dos_arquivos_secrets(tmp_path, monkeypatch):
    secrets_dir = tmp_path / "secrets"
    secrets_dir.mkdir()

    arquivo_pfx = tmp_path / "TI" / "certificado.pfx"
    path_file = secrets_dir / "cert-path.txt"
    password_file = secrets_dir / "cert-password.txt"

    path_file.write_text(str(arquivo_pfx), encoding="utf-8")
    password_file.write_text("Senha-PFX-Arquivo-123!\n", encoding="utf-8")

    monkeypatch.setenv("NFE_CERT_PATH", str(tmp_path / "outro.pfx"))
    monkeypatch.setenv("NFE_CERT_PASSWORD", "Senha-PFX-ENV-999!")

    cfg = certificado_config.carregar_config_certificado_arquivo(
        path_file,
        password_file,
    )

    assert cfg is not None
    assert cfg.path == arquivo_pfx.resolve()
    assert cfg.password == "Senha-PFX-Arquivo-123!"
