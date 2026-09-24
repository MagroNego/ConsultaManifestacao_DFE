"""Interface de linha de comando da Consulta de Manifestação v1."""

from __future__ import annotations

import argparse
import sqlite3
import sys
from getpass import getpass
from pathlib import Path

from nfe_consulta import __version__
from nfe_consulta.config import (
    CNPJ_PADRAO,
    UF_PADRAO,
    resolver_caminhos,
)
from nfe_consulta.modelos import NfeConsultaErro
from nfe_consulta.seguranca_banco import criptografado, migrar_banco
from nfe_consulta.servico import ParametrosConsulta, executar_consulta
from nfe_consulta.status import consultar_status


def _ler_senha(pergunta: str) -> str:
    if sys.stdin.isatty():
        return getpass(pergunta)
    senha = sys.stdin.readline().rstrip("\r\n")
    if not senha:
        raise ValueError("Senha não recebida.")
    return senha


def _progresso(atual: int, total: int) -> None:
    print(f"\r{atual}/{total}", end="", flush=True)


def _criar_parser() -> argparse.ArgumentParser:
    caminhos = resolver_caminhos()
    parser = argparse.ArgumentParser(
        prog="nfe-consulta",
        description="Consulta de manifestação de NF-e",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    comandos = parser.add_subparsers(dest="comando")

    comandos.add_parser("gui", help="Abrir a interface gráfica")

    atualizar = comandos.add_parser(
        "atualizar",
        help="Sincronizar com a SEFAZ e gerar Excel",
    )
    atualizar.add_argument(
        "chaves",
        nargs="?",
        default=str(caminhos.chaves),
        help="TXT com as chaves",
    )
    atualizar.add_argument("--banco", default=str(caminhos.banco))
    atualizar.add_argument("--saida", default=str(caminhos.saida))
    atualizar.add_argument("--max-lotes", type=int, default=50)
    atualizar.add_argument("--cert-indice", type=int)

    excel = comandos.add_parser(
        "excel",
        help="Gerar Excel usando somente o banco local",
    )
    excel.add_argument(
        "chaves",
        nargs="?",
        default=str(caminhos.chaves),
        help="TXT com as chaves",
    )
    excel.add_argument("--banco", default=str(caminhos.banco))
    excel.add_argument("--saida", default=str(caminhos.saida))

    status = comandos.add_parser(
        "status",
        help="Mostrar o estado local da sincronização",
    )
    status.add_argument("--banco", default=str(caminhos.banco))

    proteger = comandos.add_parser(
        "proteger-banco",
        help="Criar uma cópia SQLCipher do banco",
    )
    proteger.add_argument("origem")
    proteger.add_argument("destino")

    return parser


def _abrir_gui() -> None:
    from nfe_consulta.gui import main as iniciar_interface

    iniciar_interface()


def _senha_do_banco(caminho: str | Path) -> str | None:
    return _ler_senha("Senha do banco: ") if criptografado(caminho) else None


def _executar_status(args: argparse.Namespace) -> None:
    senha = _senha_do_banco(args.banco)
    print(consultar_status(args.banco, CNPJ_PADRAO, senha=senha))


def _proteger_banco(args: argparse.Namespace) -> None:
    senha = _ler_senha("Nova senha do banco protegido: ")
    confirmacao = _ler_senha("Repita a senha: ")
    if senha != confirmacao:
        raise ValueError("As senhas não coincidem.")
    migrar_banco(args.origem, args.destino, senha)
    print(f"Banco protegido criado: {args.destino}")


def _executar_consulta(args: argparse.Namespace) -> None:
    sincronizar = args.comando == "atualizar"
    senha = _senha_do_banco(args.banco)

    parametros = ParametrosConsulta(
        chaves=Path(args.chaves),
        banco=Path(args.banco),
        saida=Path(args.saida),
        cnpj=CNPJ_PADRAO,
        uf=UF_PADRAO,
        sincronizar_sefaz=sincronizar,
        max_lotes=args.max_lotes if sincronizar else 50,
        senha_banco=senha,
        cert_indice=args.cert_indice if sincronizar else None,
    )

    resultado = executar_consulta(
        parametros,
        progresso_sincronizacao=(
            lambda lote, ult, maximo, novos: print(
                f"SEFAZ {lote}: NSU {ult}/{maximo} | +{novos} evento(s)",
                flush=True,
            )
            if sincronizar
            else None
        ),
        progresso_lote=_progresso,
    )
    print()
    print(
        f"{resultado.total} nota(s) | "
        f"{resultado.com_evento} com evento | "
        f"{resultado.com_erro} erro(s)"
    )
    print(f"Planilha: {resultado.saida}")


def main(argv: list[str] | None = None) -> None:
    argumentos = list(sys.argv[1:] if argv is None else argv)

    if not argumentos:
        _abrir_gui()
        return

    parser = _criar_parser()
    args = parser.parse_args(argumentos)

    try:
        if args.comando == "gui":
            _abrir_gui()
        elif args.comando == "status":
            _executar_status(args)
        elif args.comando == "proteger-banco":
            _proteger_banco(args)
        elif args.comando in {"atualizar", "excel"}:
            _executar_consulta(args)
        else:
            parser.print_help()
    except (OSError, ValueError, RuntimeError, sqlite3.DatabaseError, NfeConsultaErro) as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
