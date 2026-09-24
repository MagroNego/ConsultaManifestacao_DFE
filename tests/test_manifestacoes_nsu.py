import base64
import gzip

import pytest

from nfe_consulta.banco import BancoManifestacoes
from nfe_consulta.modelos import (
    CertificadoWindows, NfeConsumoIndevidoErro, NfeErroComunicacao,
    NfeErroResposta, RetornoDistribuicao,
)
from nfe_consulta.parser_distribuicao import parse_retorno_distribuicao
from nfe_consulta.sincronizacao import sincronizar


CNPJ = "12345678000199"
CHAVE = "35260123456789000123550010000012341000012345"
CERT = CertificadoWindows("thumb", "empresa", "ac", "2030-01-01", CNPJ)


def test_resumo_de_evento_distribuido_chega_ao_banco(tmp_path, monkeypatch):
    evento = (f'<resEvento xmlns="http://www.portalfiscal.inf.br/nfe">'
              f'<chNFe>{CHAVE}</chNFe><tpEvento>210240</tpEvento>'
              '<dhEvento>2026-09-20T10:00:00-03:00</dhEvento>'
              '<nProt>135260000000100</nProt></resEvento>')
    zipado = base64.b64encode(gzip.compress(evento.encode())).decode()
    xml = ('<retDistDFeInt xmlns="http://www.portalfiscal.inf.br/nfe">'
           '<cStat>138</cStat><xMotivo>Encontrado</xMotivo>'
           '<ultNSU>1</ultNSU><maxNSU>1</maxNSU>'
           f'<loteDistDFeInt><docZip NSU="1" schema="resEvento_v1.01.xsd">{zipado}'
           '</docZip></loteDistDFeInt></retDistDFeInt>')
    monkeypatch.setattr(
        "nfe_consulta.sincronizacao.consultar_distribuicao",
        lambda *args: parse_retorno_distribuicao(xml),
    )
    banco = BancoManifestacoes(str(tmp_path / "banco.db"))
    try:
        resumo = sincronizar(banco, CNPJ, "33", CERT)
        assert resumo.completo and resumo.eventos_novos == 1
        assert banco.consultar_chave(CHAVE, CNPJ).manifestacoes[-1].codigo == "210240"
        assert sincronizar(banco, CNPJ, "33", CERT).cache
    finally:
        banco.fechar()


def test_137_e_656_respeitam_pausa_persistida(tmp_path, monkeypatch):
    chamadas = []

    def consultar(*args):
        chamadas.append(args)
        return RetornoDistribuicao(137, "Sem documentos", "0".zfill(15), "0".zfill(15), ())

    monkeypatch.setattr("nfe_consulta.sincronizacao.consultar_distribuicao", consultar)
    caminho = str(tmp_path / "banco.db")
    banco = BancoManifestacoes(caminho)
    assert sincronizar(banco, CNPJ, "33", CERT).completo
    banco.fechar()
    banco = BancoManifestacoes(caminho)
    assert sincronizar(banco, CNPJ, "33", CERT).cache
    assert len(chamadas) == 1

    def consumo(*args):
        raise NfeConsumoIndevidoErro("656")

    monkeypatch.setattr("nfe_consulta.sincronizacao.consultar_distribuicao", consumo)
    outro = "99999999000199"
    with pytest.raises(NfeConsumoIndevidoErro):
        sincronizar(banco, outro, "33", CERT)
    banco.fechar()
    banco = BancoManifestacoes(caminho)
    with pytest.raises(NfeErroComunicacao, match="nova tentativa apos"):
        sincronizar(banco, outro, "33", CERT)
    banco.fechar()


def test_retorno_com_nsu_invalido_nao_avanca_cursor(tmp_path):
    banco = BancoManifestacoes(str(tmp_path / "banco.db"))
    try:
        with pytest.raises(NfeErroResposta):
            banco.salvar_retorno(CNPJ, RetornoDistribuicao(
                138, "inconsistente", "2".zfill(15), "1".zfill(15), ()
            ))
        assert banco.obter_estado(CNPJ) == ("0".zfill(15), "0".zfill(15))
    finally:
        banco.fechar()
