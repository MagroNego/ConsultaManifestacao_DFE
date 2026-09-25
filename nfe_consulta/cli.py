"""Interface de linha de comando da Consulta de Manifestação v2."""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path

from nfe_consulta import __version__
from nfe_consulta.config import CNPJ_PADRAO, UF_PADRAO, resolver_caminhos
from nfe_consulta.certificado_config import carregar_config_certificado_arquivo
from nfe_consulta.modelos import NfeConsultaErro
from nfe_consulta.seguranca_banco import criptografado, migrar_banco
from nfe_consulta.servico import (
    ParametrosConsulta,
    ParametrosSincronizacao,
    executar_consulta,
    sincronizar_banco,
)
from nfe_consulta.status import consultar_status


COOLDOWN_SEFAZ_MINUTOS = 120
RAIZ_PROJETO = Path(__file__).resolve().parents[1]
DATABASE_PASSWORD_FILE = RAIZ_PROJETO / "secrets" / "db-password.txt"


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
        help="Sincronizar o banco local com a SEFAZ",
    )
    atualizar.add_argument(
        "--banco",
        default=os.getenv("NFE_DATABASE_PATH", str(caminhos.banco)),
    )
    atualizar.add_argument("--max-lotes", type=int, default=50)
    atualizar.add_argument("--cert-indice", type=int)
    atualizar.add_argument(
        "--cert-store",
        choices=("CurrentUser", "LocalMachine"),
        default=os.getenv("NFE_CERT_STORE", "CurrentUser"),
    )
    atualizar.add_argument(
        "--cert-thumbprint",
        default=os.getenv("NFE_CERT_THUMBPRINT") or None,
    )
    atualizar.add_argument(
        "--cooldown-minutos",
        type=int,
        default=int(os.getenv("NFE_SEFAZ_COOLDOWN_MINUTES", str(COOLDOWN_SEFAZ_MINUTOS))),
    )

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
    excel.add_argument(
        "--banco",
        default=os.getenv("NFE_DATABASE_PATH", str(caminhos.banco)),
    )
    excel.add_argument("--saida", default=str(caminhos.saida))

    status = comandos.add_parser(
        "status",
        help="Mostrar o estado da última gravação local",
    )
    status.add_argument(
        "--banco",
        default=os.getenv("NFE_DATABASE_PATH", str(caminhos.banco)),
    )

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
    if not criptografado(caminho):
        return None

    arquivo = DATABASE_PASSWORD_FILE
    if not arquivo.is_file():
        raise ValueError(
            f"Banco criptografado: configure a senha em {arquivo}."
        )

    senha = arquivo.read_text(encoding="utf-8").rstrip("\r\n")
    if not senha:
        raise ValueError(f"Arquivo de senha do banco está vazio: {arquivo}")
    return senha


def _executar_status(args: argparse.Namespace) -> None:
    senha = _senha_do_banco(args.banco)
    print(consultar_status(args.banco, CNPJ_PADRAO, senha=senha))


def _proteger_banco(args: argparse.Namespace) -> None:
    arquivo = DATABASE_PASSWORD_FILE
    if not arquivo.is_file():
        raise ValueError(
            f"Configure a nova senha do banco em {arquivo} antes de proteger o arquivo."
        )

    senha = arquivo.read_text(encoding="utf-8").rstrip("\r\n")
    if not senha:
        raise ValueError(f"Arquivo de senha do banco está vazio: {arquivo}")
    if len(senha) < 12:
        raise ValueError("A senha do banco em secrets deve ter pelo menos 12 caracteres.")

    migrar_banco(args.origem, args.destino, senha)
    print(f"Banco protegido criado: {args.destino}")


def _executar_atualizacao(args: argparse.Namespace) -> None:
    senha = _senha_do_banco(args.banco)
    cert_arquivo = carregar_config_certificado_arquivo()
    resumo = sincronizar_banco(
        ParametrosSincronizacao(
            banco=Path(args.banco),
            cnpj=CNPJ_PADRAO,
            uf=UF_PADRAO,
            max_lotes=args.max_lotes,
            senha_banco=senha,
            cert_indice=args.cert_indice,
            cert_thumbprint=None if cert_arquivo is not None else args.cert_thumbprint,
            cert_store=args.cert_store,
            cert_arquivo=cert_arquivo.path if cert_arquivo is not None else None,
            cert_senha_arquivo=cert_arquivo.password if cert_arquivo is not None else None,
            cooldown_minutos=args.cooldown_minutos,
        ),
        progresso_sincronizacao=lambda lote, ult, maximo, novos: print(
            f"SEFAZ {lote}: NSU {ult}/{maximo} | +{novos} evento(s)",
            flush=True,
        ),
    )
    print(
        f"Sincronização concluída | lotes: {resumo.lotes} | "
        f"eventos novos: {resumo.eventos_novos} | "
        f"NSU {resumo.ult_nsu}/{resumo.max_nsu}"
    )


def _executar_excel(args: argparse.Namespace) -> None:
    senha = _senha_do_banco(args.banco)
    resultado = executar_consulta(
        ParametrosConsulta(
            chaves=Path(args.chaves),
            banco=Path(args.banco),
            saida=Path(args.saida),
            cnpj=CNPJ_PADRAO,
            uf=UF_PADRAO,
            sincronizar_sefaz=False,
            senha_banco=senha,
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
        elif args.comando == "atualizar":
            _executar_atualizacao(args)
        elif args.comando == "excel":
            _executar_excel(args)
        else:
            parser.print_help()
    except (OSError, ValueError, RuntimeError, sqlite3.DatabaseError, NfeConsultaErro) as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
