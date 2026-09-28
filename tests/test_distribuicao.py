import base64
import gzip
import json

import pytest

from nfe_consulta.distribuicao import (
    _motivo_exibivel,
    consultar_distribuicao,
    consultar_por_chave,
    montar_cons_chave,
    montar_dist_nsu,
    montar_soap,
)
from nfe_consulta.modelos import CertificadoWindows, NfeConsumoIndevidoErro
from nfe_consulta.parser_distribuicao import parse_retorno_distribuicao


CHAVE = "35260123456789000123550010000012341000012345"


def _doc_zip(xml: str) -> str:
    return base64.b64encode(gzip.compress(xml.encode())).decode()


def test_monta_requisicao_dist_nsu():
    dist = montar_dist_nsu("12345678000199", "33", "42")
    soap = montar_soap(dist)

    assert 'versao="1.01"' in soap
    assert "<cUFAutor>33</cUFAutor>" in soap
    assert "<CNPJ>12345678000199</CNPJ>" in soap
    assert "<ultNSU>000000000000042</ultNSU>" in soap
    assert "nfeDistDFeInteresse" in soap


def test_monta_requisicao_consulta_por_chave():
    consulta = montar_cons_chave("12345678000199", "33", CHAVE)
    assert "<cUFAutor>33</cUFAutor>" in consulta
    assert "<CNPJ>12345678000199</CNPJ>" in consulta
    assert f"<consChNFe><chNFe>{CHAVE}</chNFe></consChNFe>" in consulta
    assert "distNSU" not in consulta


def test_consulta_por_chave_interrompe_no_656(monkeypatch):
    resposta = """
    <retDistDFeInt xmlns="http://www.portalfiscal.inf.br/nfe" versao="1.01">
      <cStat>656</cStat><xMotivo>Consumo Indevido</xMotivo>
      <ultNSU>0</ultNSU><maxNSU>0</maxNSU>
    </retDistDFeInt>
    """
    monkeypatch.setattr(
        "nfe_consulta.distribuicao._enviar_soap_windows",
        lambda soap, certificado: resposta,
    )
    cert = CertificadoWindows("abc", "empresa", "ac", "2030-01-01")
    with pytest.raises(NfeConsumoIndevidoErro):
        consultar_por_chave("12345678000199", "33", CHAVE, cert)


def test_rejeicao_656_exibe_xmotivo_sem_controles_de_terminal(monkeypatch):
    resposta = """<retDistDFeInt xmlns="http://www.portalfiscal.inf.br/nfe">
      <cStat>656</cStat><xMotivo>Deve ser utilizado o ultNSU nas solicitacoes subsequentes.\n</xMotivo>
      <ultNSU>10</ultNSU><maxNSU>10</maxNSU>
    </retDistDFeInt>"""
    monkeypatch.setattr("nfe_consulta.distribuicao._enviar_soap_windows",
                        lambda soap, certificado: resposta)
    cert = CertificadoWindows("abc", "empresa", "ac", "2030-01-01")
    with pytest.raises(NfeConsumoIndevidoErro) as erro:
        consultar_distribuicao("12345678000199", "33", "10", cert)
    assert "xMotivo: Deve ser utilizado o ultNSU" in str(erro.value)
    assert "ultNSU enviado: 000000000000010" in str(erro.value)
    assert "ultNSU informado pela SEFAZ: 000000000000010" in str(erro.value)
    assert _motivo_exibivel("NSU\x1b[31m\nseguinte") == "NSU[31m seguinte"


def test_rejeicao_656_sem_nsu_na_resposta_nao_inventa_cursor(monkeypatch):
    resposta = """<retDistDFeInt><cStat>656</cStat>
      <xMotivo>Sequencia incorreta</xMotivo></retDistDFeInt>"""
    monkeypatch.setattr("nfe_consulta.distribuicao._enviar_soap_windows",
                        lambda soap, certificado: resposta)
    cert = CertificadoWindows("abc", "empresa", "ac", "2030-01-01")
    with pytest.raises(NfeConsumoIndevidoErro) as erro:
        consultar_distribuicao("12345678000199", "33", "563813", cert)
    assert "ultNSU enviado: 000000000563813" in str(erro.value)
    assert "ultNSU da SEFAZ: não informado na rejeição" in str(erro.value)


def test_parse_retorno_com_evento_compactado():
    evento = f"""
    <procEventoNFe xmlns="http://www.portalfiscal.inf.br/nfe" versao="1.00">
      <evento><infEvento><chNFe>{CHAVE}</chNFe><dhEvento>2026-09-17T10:00:00-03:00</dhEvento><tpEvento>210200</tpEvento></infEvento></evento>
      <retEvento><infEvento><cStat>135</cStat><dhRegEvento>2026-09-17T10:01:00-03:00</dhRegEvento><nProt>135260000000001</nProt></infEvento></retEvento>
    </procEventoNFe>
    """
    xml = f"""
    <soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
      <soap:Body><retDistDFeInt xmlns="http://www.portalfiscal.inf.br/nfe" versao="1.01">
        <cStat>138</cStat><xMotivo>Documento(s) localizado(s)</xMotivo>
        <ultNSU>12</ultNSU><maxNSU>15</maxNSU>
        <loteDistDFeInt><docZip NSU="12" schema="procEventoNFe_v1.00.xsd">{_doc_zip(evento)}</docZip></loteDistDFeInt>
      </retDistDFeInt></soap:Body>
    </soap:Envelope>
    """

    retorno = parse_retorno_distribuicao(xml)

    assert retorno.status_codigo == 138
    assert retorno.ult_nsu == "000000000000012"
    assert retorno.max_nsu == "000000000000015"
    assert len(retorno.manifestacoes) == 1
    chave, manifestacao = retorno.manifestacoes[0]
    assert chave == CHAVE
    assert manifestacao.codigo == "210200"
    assert manifestacao.descricao == "Confirmacao da Operacao"
    assert manifestacao.data == "2026-09-17T10:01:00-03:00"
    assert manifestacao.protocolo == "135260000000001"
    assert manifestacao.nsu == "12"


def test_parse_ignora_documento_que_nao_e_manifestacao():
    resumo_nfe = f'<resNFe xmlns="http://www.portalfiscal.inf.br/nfe"><chNFe>{CHAVE}</chNFe></resNFe>'
    xml = f"""
    <retDistDFeInt xmlns="http://www.portalfiscal.inf.br/nfe" versao="1.01">
      <cStat>138</cStat><xMotivo>Documento(s) localizado(s)</xMotivo>
      <ultNSU>1</ultNSU><maxNSU>1</maxNSU>
      <loteDistDFeInt><docZip NSU="1" schema="resNFe_v1.01.xsd">{_doc_zip(resumo_nfe)}</docZip></loteDistDFeInt>
    </retDistDFeInt>
    """
    retorno = parse_retorno_distribuicao(xml)
    assert retorno.manifestacoes == ()
    assert retorno.documentos_ignorados == 1



def test_envio_soap_passa_pfx_por_stdin(monkeypatch, tmp_path):
    from types import SimpleNamespace
    from nfe_consulta.distribuicao import _enviar_soap_windows

    capturado = {}

    def fake_run(*args, **kwargs):
        capturado["payload"] = json.loads(kwargs["input"])
        return SimpleNamespace(returncode=0, stdout="<resposta/>", stderr="")

    monkeypatch.setattr("nfe_consulta.distribuicao.subprocess.run", fake_run)

    arquivo = tmp_path / "certificado.pfx"
    cert = CertificadoWindows(
        "ABC",
        "Empresa",
        "ICP-Brasil",
        "2030-01-01",
        "16840128000101",
        "Arquivo",
        str(arquivo),
        "Senha-PFX-123!",
    )

    assert _enviar_soap_windows("<soap/>", cert) == "<resposta/>"
    assert capturado["payload"]["path"] == str(arquivo)
    assert capturado["payload"]["password"] == "Senha-PFX-123!"
    assert capturado["payload"]["store"] == "Arquivo"
