"""Configuração local da conta administrativa, sem expor senhas no terminal."""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime
from contextlib import closing
from getpass import getpass
from pathlib import Path

from nfe_consulta.web.settings import RAIZ_PROJETO
from nfe_consulta.web.admin_accounts import AdminAccounts, _hash_password


def configure_account(path: Path, username: str, password: str) -> None:
    username = username.strip()
    AdminAccounts._validate(username, password)
    if path.is_file():
        backup = path.with_name(f"{path.stem}_backup_{datetime.now():%Y%m%d_%H%M%S_%f}.db")
        with closing(sqlite3.connect(path)) as source, closing(sqlite3.connect(backup)) as target:
            source.backup(target)
    accounts = AdminAccounts(path, bootstrap_username=username, bootstrap_password=None)
    with closing(accounts._connect()) as db, db:
        db.execute("INSERT INTO admins(username,password_hash,active,role) VALUES (?,?,1,'admin') "
                   "ON CONFLICT(username) DO UPDATE SET password_hash=excluded.password_hash,active=1,role='admin'",
                   (username, _hash_password(password)))
        db.execute("DELETE FROM admin_sessions WHERE username=? COLLATE NOCASE", (username,))


def main() -> None:
    username = input("Usuario do Admin [admin]: ").strip() or "admin"
    password = getpass("Nova senha (minimo 12 caracteres): ")
    if password != getpass("Repita a senha: "):
        raise SystemExit("As senhas nao conferem.")
    path = Path(os.getenv("NFE_ADMIN_ACCOUNTS_PATH", str(RAIZ_PROJETO / "dados" / "admin_accounts.db"))).expanduser()
    try:
        configure_account(path, username, password)
    except (ValueError, OSError, sqlite3.Error) as exc:
        raise SystemExit(f"Nao foi possivel configurar: {exc}") from exc
    print(f"Conta administrativa configurada: {username}")
    print("A senha foi salva como hash no banco de contas. As demais contas foram preservadas.")


if __name__ == "__main__":
    main()
