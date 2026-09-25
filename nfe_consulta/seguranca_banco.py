"""Abertura e migração explícita de bancos SQLCipher.

O arquivo SQLite original nunca é modificado pela migração.
"""

import os
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path

CABECALHO_SQLITE = b"SQLite format 3\x00"


def criptografado(caminho: str | Path) -> bool:
    arquivo = Path(caminho)
    if not arquivo.is_file() or arquivo.stat().st_size == 0:
        return False
    with arquivo.open("rb") as f:
        return f.read(16) != CABECALHO_SQLITE


def _cipher():
    try:
        from sqlcipher3 import dbapi2
        return dbapi2
    except ImportError as exc:
        raise RuntimeError("SQLCipher ausente. Reinstale o aplicativo com INSTALAR.cmd.") from exc


def _literal(valor: str) -> str:
    if not valor or any(c in valor for c in "\x00\r\n"):
        raise ValueError("Senha vazia ou com caracteres de controle.")
    return "'" + valor.replace("'", "''") + "'"


def abrir_banco(caminho: str | Path, senha: str | None = None, *, somente_leitura: bool = False):
    arquivo = Path(caminho).expanduser().resolve()

    if not arquivo.is_file():
        raise FileNotFoundError(f"Banco não encontrado: {arquivo}")

    if criptografado(arquivo):
        if senha is None:
            raise ValueError("Banco criptografado: informe a senha para abri-lo.")

        modulo = _cipher()

        # SQLCipher + URI file: no Windows pode falhar em caminhos com drive
        # e barras invertidas. Abrimos pelo caminho nativo e usamos query_only
        # para garantir que telas como Status não alterem o banco.
        conexao = modulo.connect(str(arquivo))
        try:
            conexao.execute("PRAGMA key = " + _literal(senha))
            conexao.execute("SELECT count(*) FROM sqlite_master").fetchone()
            if somente_leitura:
                conexao.execute("PRAGMA query_only = ON")
        except modulo.DatabaseError as exc:
            conexao.close()
            raise ValueError("Senha incorreta ou banco criptografado inválido.") from exc
        return conexao

    conexao = sqlite3.connect(str(arquivo))
    if somente_leitura:
        conexao.execute("PRAGMA query_only = ON")
    return conexao


def migrar_banco(origem: str | Path, destino: str | Path, senha: str) -> None:
    """Cria banco cifrado novo, verifica conteúdo e mantém intacto o original."""
    origem, destino = Path(origem).resolve(), Path(destino).resolve()
    _literal(senha)
    if len(senha) < 12:
        raise ValueError("Use uma senha com pelo menos 12 caracteres.")
    if not origem.is_file() or criptografado(origem):
        raise ValueError("A origem deve ser um banco SQLite existente sem criptografia.")
    if destino.exists() or origem == destino:
        raise ValueError("Escolha um nome novo para o banco protegido; destino já existe.")
    if not destino.parent.is_dir():
        raise ValueError("A pasta do destino não existe.")
    modulo = _cipher()
    fd, temporario = tempfile.mkstemp(prefix=".nfe-cifrado-", suffix=".db", dir=destino.parent)
    os.close(fd)
    os.unlink(temporario)
    try:
        with closing(modulo.connect(str(origem))) as conexao:
            if conexao.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("Banco original não passou na verificação de integridade.")
            tabelas = [r[0] for r in conexao.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )]
            originais = {nome: conexao.execute('SELECT count(*) FROM "' + nome.replace('"', '""') + '"').fetchone()[0]
                         for nome in tabelas}
            conexao.execute("ATTACH DATABASE ? AS encrypted KEY " + _literal(senha), (temporario,))
            try:
                conexao.execute("SELECT sqlcipher_export('encrypted')").fetchone()
            finally:
                conexao.execute("DETACH DATABASE encrypted")
        with closing(abrir_banco(temporario, senha, somente_leitura=True)) as cifrado:
            if cifrado.execute("PRAGMA cipher_integrity_check").fetchall():
                raise ValueError("Banco protegido não passou na verificação de integridade.")
            for nome, total in originais.items():
                if cifrado.execute('SELECT count(*) FROM "' + nome.replace('"', '""') + '"').fetchone()[0] != total:
                    raise ValueError("A migração não preservou todas as linhas do banco.")
        if destino.exists():
            raise ValueError("Destino criado durante a migração; nenhum arquivo foi substituído.")
        os.replace(temporario, destino)
    finally:
        for resto in (temporario, temporario + "-wal", temporario + "-shm", temporario + "-journal"):
            try:
                os.unlink(resto)
            except FileNotFoundError:
                pass
