"""Assistente de texto mantido como alternativa ao modo gráfico."""

import subprocess
import sys
from pathlib import Path

from nfe_consulta.config import (
    CNPJ_PADRAO as CNPJ_YAB,
    NOME_PLANILHA,
    UF_PADRAO as UF_YAB,
    resolver_caminhos,
)


def _caminho_perguntado(rotulo: str, padrao: Path) -> Path:
    resposta = input(f"{rotulo} [{padrao}]: ").strip().strip('"')
    return Path(resposta).expanduser() if resposta else padrao


def montar_comando(
    chaves: Path,
    saida: Path,
    banco: Path,
    sincronizar: bool,
) -> list[str]:
    comando = [
        sys.executable,
        "-m",
        "nfe_consulta.cli",
        "atualizar" if sincronizar else "excel",
        str(chaves),
        "--banco",
        str(banco),
        "--saida",
        str(saida),
    ]
    if sincronizar:
        comando += ["--max-lotes", "500"]
    return comando


def main() -> int:
    pasta = Path(__file__).resolve().parent.parent
    caminhos = resolver_caminhos(pasta, Path.home() / "Downloads")

    print("\nCONSULTA DE MANIFESTACOES YAB")
    print("1 - Atualizar SEFAZ e gerar Excel")
    print("2 - Gerar Excel com o banco local")
    print("3 - Ver status do banco")

    opcao = input("Escolha [1]: ").strip() or "1"
    if opcao not in ("1", "2", "3"):
        print("Opcao invalida.")
        return 2

    if opcao == "3":
        banco = _caminho_perguntado("Banco", caminhos.banco)
        return subprocess.call(
            [
                sys.executable,
                "-m",
                "nfe_consulta.cli",
                "status",
                "--banco",
                str(banco),
            ],
            cwd=pasta,
        )

    chaves = _caminho_perguntado("TXT", caminhos.chaves)
    if not chaves.is_file():
        print(f"Arquivo nao encontrado: {chaves}")
        return 2

    banco = _caminho_perguntado("Banco", caminhos.banco)
    saida = _caminho_perguntado("Planilha", caminhos.saida)
    if saida.suffix.lower() != ".xlsx":
        print("A planilha precisa terminar em .xlsx")
        return 2

    saida.parent.mkdir(parents=True, exist_ok=True)
    codigo = subprocess.call(
        montar_comando(chaves, saida, banco, opcao == "1"),
        cwd=pasta,
    )
    if codigo == 0:
        print(f"\nPlanilha: {saida}")
    return codigo


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyboardInterrupt, EOFError):
        print("\nConsulta cancelada.")
        raise SystemExit(130)
