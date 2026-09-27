"""Configuração persistente do banco central usado pela aplicação Web."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from nfe_consulta.seguranca_banco import abrir_banco


RAIZ_PROJETO = Path(__file__).resolve().parents[1]


def _path_file(caminho: str | Path | None = None) -> Path:
    if caminho is not None:
        return Path(caminho).expanduser()
    return Path(
        os.getenv(
            "NFE_DATABASE_PATH_FILE",
            str(RAIZ_PROJETO / "secrets" / "db-path.txt"),
        )
    ).expanduser()


def carregar_caminho_banco(
    caminho_padrao: str | Path,
    *,
    path_file: str | Path | None = None,
) -> Path:
    arquivo_config = _path_file(path_file)
    if arquivo_config.is_file():
        valor = arquivo_config.read_text(encoding="utf-8").strip()
        if valor:
            return Path(valor).expanduser().resolve()
    return Path(caminho_padrao).expanduser().resolve()


def validar_banco(caminho: str | Path, senha: str | None) -> Path:
    arquivo = Path(caminho).expanduser().resolve()
    if not arquivo.is_file():
        raise FileNotFoundError(f"Banco não encontrado: {arquivo}")
    if arquivo.suffix.lower() not in {".db", ".sqlite", ".sqlite3"}:
        raise ValueError("Selecione um arquivo de banco .db, .sqlite ou .sqlite3.")

    conexao = abrir_banco(arquivo, senha, somente_leitura=True)
    try:
        tabelas = {
            linha[0]
            for linha in conexao.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        if "manifestacoes" not in tabelas:
            raise ValueError(
                "O arquivo selecionado não é um banco de manifestações válido."
            )
    finally:
        conexao.close()

    return arquivo


def salvar_caminho_banco(
    caminho: str | Path,
    senha: str | None,
    *,
    path_file: str | Path | None = None,
) -> Path:
    arquivo = validar_banco(caminho, senha)
    destino = _path_file(path_file)
    destino.parent.mkdir(parents=True, exist_ok=True)

    fd, temporario = tempfile.mkstemp(
        prefix="." + destino.name + "-",
        dir=destino.parent,
        text=True,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(str(arquivo))
        os.replace(temporario, destino)
    finally:
        try:
            os.unlink(temporario)
        except FileNotFoundError:
            pass

    return arquivo
