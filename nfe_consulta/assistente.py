"""Assistente de linha de comando para uso por duplo clique no Windows."""

import subprocess
import sys
from pathlib import Path


NOME_PLANILHA = "Consulta_Manifestacao_YAB.xlsx"
CNPJ_YAB = "16840128000101"
UF_YAB = "RJ"


def _caminho_perguntado(rotulo: str, padrao: Path) -> Path:
    resposta = input(f"{rotulo} [{padrao}]: ").strip().strip('"')
    return Path(resposta).expanduser() if resposta else padrao


def montar_comando(chaves: Path, saida: Path, banco: Path, sincronizar: bool) -> list[str]:
    comando = [
        sys.executable, "-m", "nfe_consulta.cli", "--cnpj", CNPJ_YAB,
        "--lote", str(chaves), "--xlsx", str(saida), "--banco", str(banco),
    ]
    if sincronizar:
        comando += ["--manifestacoes", "--uf", UF_YAB, "--max-lotes", "500"]
    return comando


def main() -> int:
    pasta = Path(__file__).resolve().parent.parent
    downloads = Path.home() / "Downloads"
    chaves_padrao = pasta / "entrada" / "CHAVES.txt"
    if not chaves_padrao.is_file():
        chaves_padrao = downloads / "CHAVES.txt"
    banco_padrao = pasta / "dados" / "nfe_manifestacoes.db"
    for candidato in (pasta / "dados" / "nfe_manifestacoes_seguro.db",
                      downloads / "nfe_manifestacoes_seguro.db", banco_padrao,
                      downloads / "nfe_manifestacoes.db"):
        if candidato.exists():
            banco_padrao = candidato
            break
    saida_padrao = pasta / "saidas" / NOME_PLANILHA

    print("\nCONSULTA DE MANIFESTACOES YAB")
    print("1 - Atualizar eventos na SEFAZ e gerar Excel")
    print("2 - Gerar Excel com os eventos ja salvos (sem SEFAZ)")
    print("3 - Ver status do banco (sem consultar a SEFAZ)")
    opcao = input("Escolha [1]: ").strip() or "1"
    if opcao not in ("1", "2", "3"):
        print("Opcao invalida.")
        return 2
    if opcao == "3":
        banco = _caminho_perguntado("Banco de eventos", banco_padrao)
        return subprocess.call([
            sys.executable, "-m", "nfe_consulta.cli", "--status", "--cnpj", CNPJ_YAB,
            "--banco", str(banco),
        ], cwd=pasta)
    chaves = _caminho_perguntado("TXT com as chaves", chaves_padrao)
    if not chaves.is_file():
        print(f"Arquivo de chaves nao encontrado: {chaves}")
        return 2
    banco = _caminho_perguntado("Banco de eventos", banco_padrao)
    saida = _caminho_perguntado("Salvar planilha em", saida_padrao)
    if saida.suffix.lower() != ".xlsx":
        print("A planilha precisa ter a extensao .xlsx")
        return 2
    saida.parent.mkdir(parents=True, exist_ok=True)
    print("\nExecutando consulta... Mantenha esta janela aberta.")
    codigo = subprocess.call(montar_comando(chaves, saida, banco, opcao == "1"), cwd=pasta)
    if codigo == 0:
        print(f"\nPronto. Planilha: {saida}")
    else:
        print(f"\nConsulta nao concluida (codigo {codigo}). Veja a mensagem acima.")
    return codigo


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyboardInterrupt, EOFError):
        print("\nConsulta cancelada.")
        raise SystemExit(130)
    except OSError as exc:
        print(f"\nFalha ao acessar arquivo ou pasta: {exc}")
        raise SystemExit(4)
