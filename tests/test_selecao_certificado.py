import pytest

from nfe_consulta.certificado_windows import normalizar_store
from nfe_consulta.modelos import CertificadoWindows, NfeErroCertificado
from nfe_consulta.servico import resolver_certificado


CNPJ = "16840128000101"


def test_auto_seleciona_empresa_em_vez_de_certificado_fortinet(monkeypatch):
    fortinet = CertificadoWindows("f", "Fortinet", "Fortinet", "2030-01-01")
    empresa = CertificadoWindows("e", "Empresa", "ICP-Brasil", "2030-01-01", CNPJ)
    monkeypatch.setattr(
        "nfe_consulta.servico.listar_certificados_cliente",
        lambda store=None: [fortinet, empresa],
    )

    assert resolver_certificado(CNPJ) == empresa
    assert resolver_certificado(CNPJ, 1) == empresa


def test_auto_recusa_certificado_sem_cnpj_compativel(monkeypatch):
    fortinet = CertificadoWindows("f", "Fortinet", "Fortinet", "2030-01-01")
    monkeypatch.setattr(
        "nfe_consulta.servico.listar_certificados_cliente",
        lambda store=None: [fortinet],
    )

    with pytest.raises(NfeErroCertificado, match="certificado compatível"):
        resolver_certificado(CNPJ)


def test_servidor_pode_fixar_thumbprint_e_store(monkeypatch):
    empresa = CertificadoWindows(
        "AA BB CC",
        "Empresa",
        "ICP-Brasil",
        "2030-01-01",
        CNPJ,
        "LocalMachine",
    )
    stores = []

    def listar(store=None):
        stores.append(store)
        return [empresa]

    monkeypatch.setattr("nfe_consulta.servico.listar_certificados_cliente", listar)

    escolhido = resolver_certificado(
        CNPJ,
        thumbprint="aabbcc",
        store="LocalMachine",
    )

    assert escolhido == empresa
    assert stores == ["LocalMachine"]


def test_store_invalido_e_recusado():
    with pytest.raises(NfeErroCertificado, match="CurrentUser ou LocalMachine"):
        normalizar_store("QualquerCoisa")
