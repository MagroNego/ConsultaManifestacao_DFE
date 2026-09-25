"""Configuração persistente do certificado A1 usado pela Web e pelo job."""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from nfe_consulta.certificado_arquivo import carregar_certificado_arquivo


RAIZ_PROJETO = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class ConfigCertificadoArquivo:
    path: Path
    password: str


def _path_file(caminho: str | Path | None = None) -> Path:
    if caminho is not None:
        return Path(caminho).expanduser()
    return RAIZ_PROJETO / "secrets" / "cert-path.txt"


def _password_file(caminho: str | Path | None = None) -> Path:
    if caminho is not None:
        return Path(caminho).expanduser()
    return RAIZ_PROJETO / "secrets" / "cert-password.txt"


def carregar_config_certificado_arquivo(
    path_file: str | Path | None = None,
    password_file: str | Path | None = None,
) -> ConfigCertificadoArquivo | None:
    arquivo_caminho = _path_file(path_file)
    if not arquivo_caminho.is_file():
        return None

    valor = arquivo_caminho.read_text(encoding="utf-8").strip()
    if not valor:
        return None
    caminho = Path(valor).expanduser()

    arquivo_senha = _password_file(password_file)
    senha = (
        arquivo_senha.read_text(encoding="utf-8").rstrip("\r\n")
        if arquivo_senha.is_file()
        else ""
    )

    return ConfigCertificadoArquivo(
        path=caminho.resolve(),
        password=senha,
    )


def salvar_config_certificado_arquivo(
    caminho: str | Path,
    senha: str,
    *,
    path_file: str | Path | None = None,
    password_file: str | Path | None = None,
) -> ConfigCertificadoArquivo:
    arquivo = Path(caminho).expanduser().resolve()

    # Valida antes de persistir qualquer segredo.
    carregar_certificado_arquivo(arquivo, senha)

    arquivo_caminho = _path_file(path_file)
    arquivo_senha = _password_file(password_file)
    arquivo_caminho.parent.mkdir(parents=True, exist_ok=True)
    arquivo_senha.parent.mkdir(parents=True, exist_ok=True)

    _gravar_atomico(arquivo_caminho, str(arquivo))
    _gravar_atomico(arquivo_senha, senha)

    return ConfigCertificadoArquivo(arquivo, senha)


def _gravar_atomico(destino: Path, conteudo: str) -> None:
    fd, temporario = tempfile.mkstemp(
        prefix="." + destino.name + "-",
        dir=destino.parent,
        text=True,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as arquivo:
            arquivo.write(conteudo)
        os.replace(temporario, destino)
    finally:
        try:
            os.unlink(temporario)
        except FileNotFoundError:
            pass
