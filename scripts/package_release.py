"""Monta o pacote de instalação por lista explícita de arquivos permitidos."""
from __future__ import annotations

import hashlib
import re
import tomllib
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT_FILES = (
    "pyproject.toml", "README.md", "LEIA_PRIMEIRO.md",
    "MANUAL_DE_INSTALACAO.md", "MANUAL_DE_USO.md", "SERVIDOR_WEB.md",
    "SEGURANCA_BANCO.md", "ARQUITETURA.md", "CHANGELOG.md", "RELEASE_NOTES.md",
    "WEB_CONFIG.example", "INSTALAR.cmd", "CONFIGURAR_ADMIN.cmd", "INICIAR_WEB.cmd",
)


def package(root: Path) -> Path:
    version = tomllib.loads((root / "pyproject.toml").read_text("utf-8"))["project"]["version"]
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError("A release exige versão estável X.Y.Z.")
    if (root / "nfe_consulta/__init__.py").read_text("utf-8").strip() != f'__version__ = "{version}"':
        raise ValueError("Versões do pacote e da aplicação diferem.")
    prefix = f"ConsultaManifestacao_DFE-v{version}"
    sources = [root / name for name in ROOT_FILES]
    sources += list((root / "nfe_consulta").rglob("*.py"))
    for pattern in ("templates/*.html", "static/*.css", "static/*.js", "static/img/*.png"):
        sources += list((root / "nfe_consulta/web").glob(pattern))
    for source in sources:
        if not source.is_file() or source.is_symlink():
            raise ValueError(f"Arquivo inválido para o pacote: {source.name}")
    for logo in ("yorozu-dark.png", "yorozu-light.png"):
        if root / "nfe_consulta/web/static/img" / logo not in sources:
            raise ValueError(f"Recurso obrigatório ausente: {logo}")
    output = root / "dist" / f"{prefix}.zip"
    output.parent.mkdir(exist_ok=True)
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        for source in sorted(set(sources)):
            archive.write(source, f"{prefix}/{source.relative_to(root).as_posix()}")
        for directory in ("dados", "secrets", "logs", "entrada", "saidas"):
            archive.writestr(f"{prefix}/{directory}/", "")
    checksum = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix(".zip.sha256").write_text(f"{checksum}  {output.name}\n", encoding="utf-8")
    return output


if __name__ == "__main__":
    print(package(Path(__file__).resolve().parents[1]))
