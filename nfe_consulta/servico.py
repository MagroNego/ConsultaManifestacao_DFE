"""Camada de aplicação compartilhada pela interface Web e rotinas internas.

Toda a regra de orquestração fica aqui para manter HTTP, agendamento e
persistência desacoplados das integrações fiscais.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from nfe_consulta.banco import BancoManifestacoes
from nfe_consulta.certificado_arquivo import carregar_certificado_arquivo
from nfe_consulta.certificado_windows import (
    listar_certificados_cliente,
    selecionar_certificado,
)
from nfe_consulta.lote import ler_chaves, processar_lote
from nfe_consulta.modelos import (
    CertificadoWindows,
    NfeErroCertificado,
    NfeLimiteConsultaErro,
    ResultadoConsulta,
)
from nfe_consulta.seguranca_banco import criptografado
from nfe_consulta.sincronizacao import ResumoSincronizacao, sincronizar
from nfe_consulta.validacao import validar_cnpj, validar_uf
from nfe_consulta.xlsx_writer import gravar_xlsx


ProgressoSincronizacao = Callable[[int, str, str, int], None]
ProgressoLote = Callable[[int, int], None]


@dataclass(frozen=True)
class ParametrosConsulta:
    chaves: Path
    banco: Path
    saida: Path
    cnpj: str
    uf: str = "RJ"
    sincronizar_sefaz: bool = False
    max_lotes: int = 50
    senha_banco: str | None = None
    cert_indice: int | None = None
    cert_thumbprint: str | None = None
    cert_store: str | None = None
    cert_arquivo: Path | None = None
    cert_senha_arquivo: str | None = None


@dataclass(frozen=True)
class ResultadoExecucao:
    resultados: tuple[ResultadoConsulta, ...]
    cobertura: str
    saida: Path
    sincronizacao: ResumoSincronizacao | None = None

    @property
    def total(self) -> int:
        return len(self.resultados)

    @property
    def com_evento(self) -> int:
        return sum(bool(item.manifestacoes) for item in self.resultados)

    @property
    def com_erro(self) -> int:
        return sum(bool(item.erro) for item in self.resultados)


def banco_precisa_senha(caminho: str | Path) -> bool:
    return criptografado(caminho)


def resolver_certificado(
    cnpj: str,
    indice: int | None = None,
    thumbprint: str | None = None,
    store: str | None = None,
    arquivo: str | Path | None = None,
    senha_arquivo: str | None = None,
) -> CertificadoWindows:
    """Seleciona o certificado do CNPJ sem interação de terminal."""
    if arquivo:
        certificado = carregar_certificado_arquivo(arquivo, senha_arquivo)
        if not certificado.cnpj or certificado.cnpj[:8] != cnpj[:8]:
            raise NfeErroCertificado(
                "O certificado configurado não apresenta CNPJ compatível com a empresa."
            )
        return certificado

    certs = listar_certificados_cliente(store)
    if not certs:
        raise NfeErroCertificado("Nenhum certificado de cliente foi encontrado no Windows.")

    if thumbprint:
        procurado = thumbprint.replace(" ", "").upper()
        candidatos_thumb = [
            cert for cert in certs
            if cert.thumbprint.replace(" ", "").upper() == procurado
        ]
        if len(candidatos_thumb) != 1:
            raise NfeErroCertificado("Certificado configurado não foi encontrado.")
        certificado = candidatos_thumb[0]
        if not certificado.cnpj or certificado.cnpj[:8] != cnpj[:8]:
            raise NfeErroCertificado(
                "O certificado configurado não apresenta CNPJ compatível com a empresa."
            )
        return certificado

    if indice is None:
        candidatos = [i for i, cert in enumerate(certs) if cert.cnpj == cnpj]
        if len(candidatos) != 1:
            candidatos = [
                i for i, cert in enumerate(certs)
                if cert.cnpj and cert.cnpj[:8] == cnpj[:8]
            ]
        if len(candidatos) != 1:
            raise NfeErroCertificado(
                "Não foi possível identificar um único certificado compatível com o CNPJ."
            )
        indice = candidatos[0]

    certificado = selecionar_certificado(certs, indice)
    if not certificado.cnpj or certificado.cnpj[:8] != cnpj[:8]:
        raise NfeErroCertificado(
            "O certificado selecionado não apresenta CNPJ compatível com a empresa."
        )
    return certificado



@dataclass(frozen=True)
class ParametrosSincronizacao:
    banco: Path
    cnpj: str
    uf: str = "RJ"
    max_lotes: int = 50
    senha_banco: str | None = None
    cert_indice: int | None = None
    cert_thumbprint: str | None = None
    cert_store: str | None = None
    cert_arquivo: Path | None = None
    cert_senha_arquivo: str | None = None
    cooldown_minutos: int = 0


def sincronizar_banco(
    parametros: ParametrosSincronizacao,
    *,
    progresso_sincronizacao: ProgressoSincronizacao | None = None,
) -> ResumoSincronizacao:
    """Sincroniza somente o banco, sem depender de TXT ou gerar planilha."""
    banco_path = Path(parametros.banco).expanduser()
    if parametros.max_lotes < 1 or parametros.max_lotes > 500:
        raise ValueError("max_lotes deve estar entre 1 e 500.")

    cnpj = validar_cnpj(parametros.cnpj)
    c_uf = validar_uf(parametros.uf)
    certificado = resolver_certificado(
        cnpj,
        parametros.cert_indice,
        parametros.cert_thumbprint,
        parametros.cert_store,
        parametros.cert_arquivo,
        parametros.cert_senha_arquivo,
    )

    banco = BancoManifestacoes(str(banco_path), senha=parametros.senha_banco)
    try:
        if parametros.cooldown_minutos:
            bloqueio = banco.bloqueio_sincronizacao(cnpj)
            if bloqueio:
                raise NfeLimiteConsultaErro(bloqueio)
            banco.registrar_tentativa_sincronizacao(
                cnpj,
                parametros.cooldown_minutos,
            )

        return sincronizar(
            banco,
            cnpj,
            c_uf,
            certificado,
            max_lotes=parametros.max_lotes,
            progresso_fn=progresso_sincronizacao,
        )
    finally:
        banco.fechar()

def _cobertura_local(banco: BancoManifestacoes, cnpj: str) -> str:
    ult_nsu, max_nsu = banco.obter_estado(cnpj)
    if int(ult_nsu) or int(max_nsu):
        return (
            "Somente histórico local; sincronização não executada; "
            f"último NSU salvo {ult_nsu}; máximo conhecido {max_nsu}"
        )
    return "Somente histórico local; sincronização não executada"


def executar_consulta(
    parametros: ParametrosConsulta,
    *,
    progresso_sincronizacao: ProgressoSincronizacao | None = None,
    progresso_lote: ProgressoLote | None = None,
) -> ResultadoExecucao:
    """Executa o fluxo completo e grava a planilha de forma atômica."""
    chaves_path = Path(parametros.chaves).expanduser()
    banco_path = Path(parametros.banco).expanduser()
    saida_path = Path(parametros.saida).expanduser()

    if not chaves_path.is_file():
        raise FileNotFoundError(f"Arquivo de chaves não encontrado: {chaves_path}")
    if saida_path.suffix.lower() != ".xlsx":
        raise ValueError("A saída deve ser uma planilha .xlsx.")
    if not parametros.sincronizar_sefaz and not banco_path.is_file():
        raise FileNotFoundError(f"Banco local não encontrado: {banco_path}")
    if parametros.max_lotes < 1 or parametros.max_lotes > 500:
        raise ValueError("max_lotes deve estar entre 1 e 500.")

    cnpj = validar_cnpj(parametros.cnpj)
    c_uf = validar_uf(parametros.uf)
    chaves = ler_chaves(str(chaves_path))

    banco = BancoManifestacoes(str(banco_path), senha=parametros.senha_banco)
    try:
        cobertura = _cobertura_local(banco, cnpj)
        resumo: ResumoSincronizacao | None = None

        if parametros.sincronizar_sefaz:
            certificado = resolver_certificado(
                cnpj,
                parametros.cert_indice,
                parametros.cert_thumbprint,
                parametros.cert_store,
                parametros.cert_arquivo,
                parametros.cert_senha_arquivo,
            )
            resumo = sincronizar(
                banco,
                cnpj,
                c_uf,
                certificado,
                max_lotes=parametros.max_lotes,
                progresso_fn=progresso_sincronizacao,
            )
            cobertura = (
                "Sincronização concluída; eventos antigos podem estar indisponíveis"
                if resumo.completo
                else "Sincronização parcial; execute novamente para continuar do último NSU"
            )

        resultados = processar_lote(
            chaves,
            lambda chave: banco.consultar_chave(chave, cnpj),
            progresso_lote,
        )
        gravar_xlsx(str(saida_path), resultados, cobertura)
        return ResultadoExecucao(
            resultados=tuple(resultados),
            cobertura=cobertura,
            saida=saida_path,
            sincronizacao=resumo,
        )
    finally:
        banco.fechar()
