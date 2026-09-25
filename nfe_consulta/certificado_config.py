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


def _path_file() -> Path:
    return Path(
        os.getenv(
            "NFE_CERT_PATH_FILE",
            str(RAIZ_PROJETO / "secrets" / "cert-path.txt"),
        )
    ).expanduser()


def _password_file() -> Path:
    return Path(
        os.getenv(
            "NFE_CERT_PASSWORD_FILE",
            str(RAIZ_PROJETO / "secrets" / "cert-password.txt"),
        )
    ).expanduser()


def carregar_config_certificado_arquivo() -> ConfigCertificadoArquivo | None:
    caminho_direto = os.getenv("NFE_CERT_PATH", "").strip()
    arquivo_caminho = _path_file()

    if caminho_direto:
        caminho = Path(caminho_direto).expanduser()
    elif arquivo_caminho.is_file():
        valor = arquivo_caminho.read_text(encoding="utf-8").strip()
        if not valor:
            return None
        caminho = Path(valor).expanduser()
    else:
        return None

    senha_direta = os.getenv("NFE_CERT_PASSWORD")
    arquivo_senha = _password_file()
    if senha_direta is not None:
        senha = senha_direta
    elif arquivo_senha.is_file():
        senha = arquivo_senha.read_text(encoding="utf-8").rstrip("\r\n")
    else:
        senha = ""

    return ConfigCertificadoArquivo(
        path=caminho.resolve(),
        password=senha,
    )


def salvar_config_certificado_arquivo(
    caminho: str | Path,
    senha: str,
) -> ConfigCertificadoArquivo:
    arquivo = Path(caminho).expanduser().resolve()

    # Valida antes de persistir qualquer segredo.
    carregar_certificado_arquivo(arquivo, senha)

    arquivo_caminho = _path_file()
    arquivo_senha = _password_file()
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
