from nfe_consulta.banco import BancoManifestacoes, NSU_INICIAL
import pytest

from nfe_consulta.modelos import (
    Manifestacao,
    NfeLimiteConsultaErro,
    RetornoDistribuicao,
)


CHAVE = "35260123456789000123550010000012341000012345"
CNPJ = "12345678000199"


def _retorno():
    evento = Manifestacao(
        "210200",
        "Confirmacao da Operacao",
        "2026-09-17T10:01:00-03:00",
        "135260000000001",
        "12",
        "procEventoNFe_v1.00.xsd",
    )
    return RetornoDistribuicao(138, "Documentos localizados", "12".zfill(15), "15".zfill(15), ((CHAVE, evento),))


def test_banco_persiste_estado_e_deduplica(tmp_path):
    banco = BancoManifestacoes(str(tmp_path / "teste.db"))
    try:
        assert banco.obter_estado(CNPJ) == (NSU_INICIAL, NSU_INICIAL)
        assert banco.salvar_retorno(CNPJ, _retorno()) == 1
        assert banco.salvar_retorno(CNPJ, _retorno()) == 0
        assert banco.obter_estado(CNPJ) == ("12".zfill(15), "15".zfill(15))

        resultado = banco.consultar_chave(CHAVE, CNPJ)
        assert len(resultado.manifestacoes) == 1
        assert resultado.manifestacoes[0].codigo == "210200"
    finally:
        banco.fechar()


def test_consulta_pontual_nao_altera_cursor_dist_nsu(tmp_path):
    banco = BancoManifestacoes(str(tmp_path / "teste.db"))
    try:
        assert banco.salvar_manifestacoes(CNPJ, _retorno()) == 1
        assert banco.obter_estado(CNPJ) == (NSU_INICIAL, NSU_INICIAL)
    finally:
        banco.fechar()


def test_limite_persistente_de_vinte_consultas(tmp_path):
    banco = BancoManifestacoes(str(tmp_path / "teste.db"))
    try:
        chaves = [str(numero).zfill(44) for numero in range(20)]
        banco.validar_limite_pontual(CNPJ, chaves)
        for chave in chaves:
            banco.registrar_consulta_pontual(CNPJ, chave)

        assert banco.consultas_na_ultima_hora(CNPJ) == 20
        with pytest.raises(NfeLimiteConsultaErro):
            banco.validar_limite_pontual(CNPJ, ["9" * 44])

        # Uma chave ja consultada usa o cache e nao cria nova chamada.
        banco.validar_limite_pontual(CNPJ, [chaves[0]])
    finally:
        banco.fechar()
