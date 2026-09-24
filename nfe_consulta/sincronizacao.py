from dataclasses import dataclass
from typing import Callable

from nfe_consulta.banco import BancoManifestacoes
from nfe_consulta.distribuicao import consultar_distribuicao
from nfe_consulta.modelos import CertificadoWindows, NfeErroComunicacao, NfeConsumoIndevidoErro


@dataclass(frozen=True)
class ResumoSincronizacao:
    lotes: int
    eventos_novos: int
    documentos_ignorados: int
    ult_nsu: str
    max_nsu: str
    completo: bool
    cache: bool = False


def sincronizar(
    banco: BancoManifestacoes,
    cnpj: str,
    c_uf_autor: str,
    certificado: CertificadoWindows,
    max_lotes: int = 50,
    progresso_fn: Callable | None = None,
) -> ResumoSincronizacao:
    if max_lotes < 1:
        raise ValueError("max_lotes deve ser maior que zero")
    ult_nsu, max_nsu = banco.obter_estado(cnpj)
    pausa = banco.pausa_ativa(cnpj)
    if pausa:
        raise NfeErroComunicacao(pausa)
    if banco.sincronizacao_recente_e_completa(cnpj):
        return ResumoSincronizacao(0, 0, 0, ult_nsu, max_nsu, True, True)
    lotes = 0
    eventos_novos = 0
    ignorados = 0
    completo = False

    while lotes < max_lotes:
        anterior = ult_nsu
        try:
            retorno = consultar_distribuicao(cnpj, c_uf_autor, ult_nsu, certificado)
        except NfeConsumoIndevidoErro as exc:
            banco.pausar_distribuicao(cnpj, str(exc))
            raise
        if retorno.status_codigo == 137 and retorno.ult_nsu != retorno.max_nsu:
            raise NfeErroComunicacao("Resposta 137 com NSUs inconsistentes; cursor nao foi salvo")
        if retorno.status_codigo == 138 and retorno.ult_nsu == anterior:
            raise NfeErroComunicacao("A SEFAZ nao avancou o ultNSU; sincronizacao interrompida")
        lotes += 1
        eventos_novos += banco.salvar_retorno(cnpj, retorno)
        ignorados += retorno.documentos_ignorados
        ult_nsu, max_nsu = retorno.ult_nsu, retorno.max_nsu

        if progresso_fn:
            progresso_fn(lotes, ult_nsu, max_nsu, eventos_novos)

        if retorno.status_codigo == 137 or ult_nsu == max_nsu:
            completo = True
            break

    return ResumoSincronizacao(
        lotes=lotes,
        eventos_novos=eventos_novos,
        documentos_ignorados=ignorados,
        ult_nsu=ult_nsu,
        max_nsu=max_nsu,
        completo=completo,
    )
