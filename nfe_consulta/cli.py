import argparse
import sqlite3
import sys
from getpass import getpass
from pathlib import Path

from nfe_consulta import __version__
from nfe_consulta.banco import BancoManifestacoes
from nfe_consulta.certificado_windows import (
    listar_certificados_cliente,
    selecionar_certificado,
)
from nfe_consulta.csv_writer import gravar_csv
from nfe_consulta.xlsx_writer import gravar_xlsx
from nfe_consulta.formatador import formatar_resultado
from nfe_consulta.lote import ler_chaves, processar_lote
from nfe_consulta.sincronizacao import sincronizar
from nfe_consulta.status import consultar_status
from nfe_consulta.seguranca_banco import criptografado, migrar_banco
from nfe_consulta.modelos import (
    NfeConsultaErro,
    NfeErroCertificado,
)
from nfe_consulta.validacao import validar_cnpj, validar_uf
from nfe_consulta.assistente import CNPJ_YAB, UF_YAB, NOME_PLANILHA


def _ler_senha(pergunta: str) -> str:
    if sys.stdin.isatty():
        return getpass(pergunta)
    senha = sys.stdin.readline().rstrip("\r\n")
    if not senha:
        raise ValueError("Senha não recebida. Execute em um terminal interativo.")
    return senha


def _configurar_atalho(args, downloads: Path, *, pasta: Path | None = None,
                      sincronizar: bool = True) -> None:
    """Atalho conservador: nunca cria um banco novo nem usa o banco antigo."""
    pasta = pasta or Path(__file__).resolve().parent.parent
    entrada_projeto = pasta / "entrada" / "CHAVES.txt"
    banco_projeto = pasta / "dados" / "nfe_manifestacoes_seguro.db"
    usar_projeto = entrada_projeto.exists() or banco_projeto.exists()
    args.cnpj, args.uf, args.manifestacoes = CNPJ_YAB, UF_YAB if sincronizar else None, sincronizar
    args.lote = str(entrada_projeto if usar_projeto else downloads / "CHAVES.txt")
    args.xlsx = str((pasta / "saidas" if usar_projeto else downloads) / NOME_PLANILHA)
    args.banco = str(banco_projeto if usar_projeto else downloads / "nfe_manifestacoes_seguro.db")
    for rotulo, arquivo in (("TXT de chaves", args.lote), ("banco protegido", args.banco)):
        if not Path(arquivo).is_file():
            raise ValueError(f"{rotulo} não encontrado: {arquivo}")
    if not criptografado(args.banco):
        raise ValueError(f"O banco do atalho não está criptografado: {args.banco}")


def _progresso(atual: int, total: int) -> None:
    print(f"\r{atual}/{total} chaves processadas", end="", flush=True)


def _selecionar_certificado(indice: int | None, cnpj: str):
    certs = listar_certificados_cliente()
    if len(certs) > 1:
        print("Certificados disponiveis:")
        for i, cert in enumerate(certs):
            cert_cnpj = f" | CNPJ {cert.cnpj}" if cert.cnpj else ""
            print(f"  [{i}] {cert.subject} | valido ate {cert.valid_to}{cert_cnpj}")
    if indice is None:
        candidatos = [i for i, cert in enumerate(certs) if cert.cnpj == cnpj]
        if len(candidatos) != 1:
            candidatos = [i for i, cert in enumerate(certs)
                          if cert.cnpj and cert.cnpj[:8] == cnpj[:8]]
        if len(candidatos) != 1:
            raise NfeErroCertificado(
                "Nao foi possivel identificar um unico certificado do CNPJ informado. "
                "Informe --cert-indice apos conferir a lista de certificados do Windows."
            )
        indice = candidatos[0]
    print(f"Usando certificado [{indice}]")
    return selecionar_certificado(certs, indice)


def _gravar_resultados(caminho: str, resultados: list, cobertura: str) -> None:
    with open(caminho, "w", encoding="utf-8-sig", newline="") as arquivo:
        gravar_csv(arquivo, resultados, cobertura)
    erros = sum(1 for resultado in resultados if resultado.erro)
    print(f"CSV gerado: {caminho}")
    print(f"Total: {len(resultados)} | Validas: {len(resultados)-erros} | Erros: {erros}")


def _criar_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nfe-consulta",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "Consulta manifestacoes de NF-e emitidas por NSU e cruza as chaves com o historico local"
        ),
        epilog=(
            "EXEMPLOS (PowerShell):\n"
            "  nfe-consulta --atualizar\n"
            "  nfe-consulta --excel\n"
            "  nfe-consulta --gui\n"
            "  nfe-consulta --cnpj 16840128000101 --lote CHAVES.txt "
            "--xlsx Consulta_Manifestacao_YAB.xlsx --banco nfe_manifestacoes.db\n"
            "  nfe-consulta --manifestacoes --cnpj 16840128000101 --uf RJ "
            "--lote CHAVES.txt --xlsx Consulta_Manifestacao_YAB.xlsx "
            "--banco nfe_manifestacoes.db\n"
            "  nfe-consulta --status --cnpj 16840128000101 "
            "--banco nfe_manifestacoes.db\n\n"
            "  nfe-consulta --criptografar-banco nfe_manifestacoes_seguro.db "
            "--banco nfe_manifestacoes.db\n\n"
            "Para um passo a passo, abra MANUAL_DE_USO.md na pasta do aplicativo.\n"
            "Sem --manifestacoes, usa apenas dados locais; nenhuma chamada a SEFAZ."
        ),
    )
    parser.add_argument("-help", action="help", help="Exibir este manual rapido e sair")
    parser.add_argument("--gui", action="store_true", help="Abrir a interface grafica de consulta")
    parser.add_argument("--atualizar", action="store_true",
                        help="Atualizar na SEFAZ e gerar XLSX usando CHAVES.txt e banco protegido de Downloads")
    parser.add_argument("--excel", action="store_true",
                        help="Gerar XLSX apenas com dados locais do banco protegido em Downloads (sem SEFAZ)")
    parser.add_argument("--status", action="store_true", help="Mostrar o estado local da sincronizacao, sem consultar a SEFAZ")
    parser.add_argument("--criptografar-banco", metavar="NOVO_ARQUIVO",
                        help="Criar copia protegida do banco indicado em --banco (solicita senha)")
    parser.add_argument("chave", nargs="?", help="Chave de 44 digitos da NF-e")
    parser.add_argument(
        "--manifestacoes", "--consultar-sefaz", "--sincronizar",
        dest="manifestacoes",
        action="store_true",
        help="Sincronizar eventos do emitente via distNSU antes de exportar",
    )
    parser.add_argument("--cnpj", help="CNPJ do emitente consultado")
    parser.add_argument("--uf", help="UF do emitente, por sigla ou codigo IBGE (ex.: RJ)")
    parser.add_argument("--lote", help="Arquivo .txt com uma chave por linha")
    parser.add_argument("--csv", help="Caminho do CSV de saida (usado com --lote)")
    parser.add_argument("--xlsx", help="Planilha Excel formatada (usado com --lote)")
    parser.add_argument("--max-lotes", type=int, default=50, help="Maximo de lotes de 50 NSUs por execucao (padrao: 50)")
    parser.add_argument(
        "--banco",
        default="nfe_manifestacoes.db",
        help="Banco SQLite local (padrao: nfe_manifestacoes.db)",
    )
    parser.add_argument(
        "--cert-indice",
        type=int,
        default=None,
        help="Indice do certificado do Windows (padrao: selecao pelo CNPJ)",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def main() -> None:
    parser = _criar_parser()
    args = parser.parse_args()

    if args.atualizar or args.excel:
        if any((args.gui, args.status, args.criptografar_banco, args.manifestacoes,
                args.chave, args.lote, args.csv, args.xlsx, args.cnpj, args.uf,
                args.cert_indice is not None, args.banco != "nfe_manifestacoes.db",
                args.max_lotes != 50, args.atualizar and args.excel)):
            parser.error("--atualizar e --excel devem ser usados separadamente")
        try:
            _configurar_atalho(args, Path.home() / "Downloads",
                              pasta=Path(__file__).resolve().parent.parent,
                              sincronizar=args.atualizar)
        except ValueError as exc:
            parser.error(str(exc))
        print(f"TXT: {args.lote}\nBanco: {args.banco}\nExcel: {args.xlsx}")

    if args.criptografar_banco:
        if any((args.gui, args.status, args.manifestacoes, args.chave, args.lote, args.csv,
                args.xlsx, args.cnpj, args.uf, args.cert_indice is not None)):
            parser.error("--criptografar-banco aceita apenas --banco e o caminho do novo arquivo")
        try:
            senha = _ler_senha("Nova senha do banco protegido: ")
            if senha != _ler_senha("Repita a senha: "):
                raise ValueError("As senhas não coincidem.")
            migrar_banco(args.banco, args.criptografar_banco, senha)
            print(f"Banco protegido criado: {args.criptografar_banco}")
            print("O banco original permanece sem criptografia. Use --banco com o novo arquivo daqui em diante.")
        except (ValueError, RuntimeError, OSError, sqlite3.DatabaseError) as exc:
            print(f"Falha na migração: {exc}", file=sys.stderr)
            sys.exit(1)
        return

    if args.gui:
        if any((args.status, args.manifestacoes, args.chave, args.lote, args.csv, args.xlsx,
                args.cnpj, args.uf, args.cert_indice is not None)):
            parser.error("--gui deve ser usado sozinho")
        from nfe_consulta.gui import main as iniciar_interface
        iniciar_interface()
        return

    if args.status:
        if not args.cnpj:
            parser.error("Informe --cnpj com --status")
        if args.chave or args.lote or args.csv or args.xlsx or args.manifestacoes or args.uf or args.cert_indice is not None:
            parser.error("--status aceita apenas --cnpj e --banco")
        try:
            cnpj = validar_cnpj(args.cnpj)
            senha = _ler_senha("Senha do banco: ") if criptografado(args.banco) else None
            print(consultar_status(args.banco, cnpj, senha=senha))
        except ValueError as exc:
            parser.error(str(exc))
        except (OSError, UnicodeError, sqlite3.DatabaseError, RuntimeError) as exc:
            print(f"Erro ao ler banco: {exc}", file=sys.stderr)
            sys.exit(1)
        return

    if not args.chave and not args.lote:
        parser.error("Informe uma chave ou use --lote arquivo.txt")
    if args.lote and not (args.csv or args.xlsx):
        parser.error("Informe --csv ou --xlsx com --lote")
    if (args.csv or args.xlsx) and not args.lote:
        parser.error("--csv e --xlsx so podem ser usados com --lote")
    if args.manifestacoes and (not args.cnpj or not args.uf):
        parser.error("--cnpj e --uf sao obrigatorios com --manifestacoes")
    if args.max_lotes < 1:
        parser.error("--max-lotes deve ser maior que zero")

    try:
        cnpj = validar_cnpj(args.cnpj) if args.cnpj else None
        c_uf = validar_uf(args.uf) if args.uf else None
    except ValueError as exc:
        parser.error(str(exc))

    try:
        chaves_raw = ler_chaves(args.lote) if args.lote else [args.chave]
    except (OSError, UnicodeError, NfeConsultaErro) as exc:
        print(f"Erro ao abrir lote: {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        senha = _ler_senha("Senha do banco: ") if criptografado(args.banco) else None
        banco = BancoManifestacoes(args.banco, senha=senha)
    except (ValueError, RuntimeError, OSError, sqlite3.DatabaseError) as exc:
        print(f"Erro ao abrir banco: {exc}", file=sys.stderr)
        sys.exit(1)
    try:
        cobertura = "Somente historico local; sincronizacao nao executada"
        if cnpj:
            ult_local, max_local = banco.obter_estado(cnpj)
            if int(ult_local) or int(max_local):
                cobertura += f"; ultimo NSU salvo {ult_local}; maximo conhecido {max_local}"
        if args.manifestacoes:
            try:
                certificado = _selecionar_certificado(args.cert_indice, cnpj)
                if not certificado.cnpj or certificado.cnpj[:8] != cnpj[:8]:
                    raise NfeErroCertificado(
                        "O certificado selecionado nao apresenta CNPJ compativel. "
                        "Selecione o certificado da empresa no repositorio do Windows."
                    )
                resumo = sincronizar(
                    banco, cnpj, c_uf, certificado, max_lotes=args.max_lotes,
                    progresso_fn=lambda n, ult, maximo, novos: print(
                        f"Lote {n} | ultNSU {ult} | maxNSU {maximo} | eventos novos {novos}",
                        flush=True,
                    ),
                )
                cobertura = (
                    "Sincronizacao concluida; eventos antigos podem estar indisponiveis"
                    if resumo.completo else
                    "Sincronizacao parcial; rode novamente para continuar do ultimo NSU"
                )
                if resumo.cache:
                    print("Sincronizacao recente concluida; usando historico local (intervalo minimo de 1 hora).")
                if not resumo.completo:
                    print(f"AVISO: {cobertura}. ultNSU {resumo.ult_nsu} / maxNSU {resumo.max_nsu}")
            except NfeConsultaErro as exc:
                print(f"\nConsulta interrompida: {exc}", file=sys.stderr)
                sys.exit(3)
        resultados = processar_lote(
            chaves_raw, lambda chave: banco.consultar_chave(chave, cnpj), _progresso
        )
        print()

        if args.lote:
            if args.csv:
                try:
                    _gravar_resultados(args.csv, resultados, cobertura)
                except OSError as exc:
                    print(f"Erro ao gravar CSV: {exc}", file=sys.stderr)
                    sys.exit(4)
            if args.xlsx:
                try:
                    gravar_xlsx(args.xlsx, resultados, cobertura)
                    print(f"Planilha gerada: {args.xlsx}")
                except OSError as exc:
                    print(f"Erro ao gravar planilha: {exc}", file=sys.stderr)
                    sys.exit(4)
        else:
            print(formatar_resultado(resultados[0]))
    finally:
        banco.fechar()


if __name__ == "__main__":
    main()
