"""Contas locais para a área Atualizar, separadas do banco fiscal."""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import sqlite3
from pathlib import Path


ITERATIONS = 600_000
USERNAME = re.compile(r"[A-Za-z0-9._@-]{3,64}\Z")


def _hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    return f"pbkdf2_sha256${ITERATIONS}${salt.hex()}${digest.hex()}"


def _verify(password: str, encoded: str) -> bool:
    try:
        algorithm, rounds, salt, expected = encoded.split("$")
        if algorithm != "pbkdf2_sha256" or int(rounds) != ITERATIONS:
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(rounds))
        return hmac.compare_digest(actual, bytes.fromhex(expected))
    except (ValueError, TypeError):
        return False


class AdminAccounts:
    def __init__(self, path: Path, *, bootstrap_username: str, bootstrap_password: str | None):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        # O arquivo existente nunca é sobrescrito. Se já existe, a senha legada
        # não é importada novamente, inclusive após desativar a conta inicial.
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS admins (
                username TEXT PRIMARY KEY COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0, 1))
            )""")
            if bootstrap_password and db.execute("SELECT 1 FROM admins LIMIT 1").fetchone() is None:
                self._validate(bootstrap_username, bootstrap_password)
                db.execute("INSERT INTO admins VALUES (?, ?, 1)",
                           (bootstrap_username.strip(), _hash_password(bootstrap_password)))
        if os.name != "nt":
            path.chmod(0o600)

    def _connect(self):
        return sqlite3.connect(self.path, timeout=10)

    @staticmethod
    def _validate(username: str, password: str) -> None:
        if not USERNAME.fullmatch(username.strip()):
            raise ValueError("Usuário: use 3 a 64 caracteres (letras, números, ponto, @, _ ou -).")
        if len(password) < 12 or len(password) > 1024:
            raise ValueError("A senha deve ter entre 12 e 1024 caracteres.")

    def configured(self) -> bool:
        with self._connect() as db:
            return db.execute("SELECT 1 FROM admins WHERE active=1 LIMIT 1").fetchone() is not None

    def list_accounts(self) -> list[dict]:
        with self._connect() as db:
            rows = db.execute("SELECT username, active FROM admins ORDER BY username COLLATE NOCASE").fetchall()
        return [{"username": name, "active": bool(active)} for name, active in rows]

    def account(self, username: str) -> tuple[str, str] | None:
        with self._connect() as db:
            row = db.execute("SELECT username, password_hash FROM admins WHERE username=? AND active=1", (username,)).fetchone()
        return row

    def authenticate(self, username: str, password: str) -> str | None:
        row = self.account(username.strip())
        if row and _verify(password, row[1]):
            return row[0]
        return None

    def create(self, username: str, password: str) -> None:
        username = username.strip()
        self._validate(username, password)
        with self._connect() as db:
            try:
                db.execute("INSERT INTO admins VALUES (?, ?, 1)", (username, _hash_password(password)))
            except sqlite3.IntegrityError as exc:
                raise ValueError("Este usuário já existe.") from exc

    def reset_password(self, username: str, password: str) -> None:
        self._validate(username, password)
        with self._connect() as db:
            result = db.execute("UPDATE admins SET password_hash=? WHERE username=? AND active=1",
                                (_hash_password(password), username))
            if not result.rowcount:
                raise ValueError("Usuário ativo não encontrado.")

    def set_active(self, username: str, active: bool) -> None:
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT active FROM admins WHERE username=?", (username,)).fetchone()
            if row is None:
                raise ValueError("Usuário não encontrado.")
            if not active and row[0] and db.execute("SELECT count(*) FROM admins WHERE active=1").fetchone()[0] <= 1:
                raise ValueError("Mantenha pelo menos um administrador ativo.")
            db.execute("UPDATE admins SET active=? WHERE username=?", (int(active), username))
