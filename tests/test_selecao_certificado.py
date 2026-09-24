import pytest

from nfe_consulta.cli import _selecionar_certificado
from nfe_consulta.modelos import CertificadoWindows, NfeErroCertificado


def test_auto_seleciona_empresa_em_vez_de_certificado_fortinet(monkeypatch):
    fortinet = CertificadoWindows("f", "Fortinet", "Fortinet", "2030-01-01")
    empresa = CertificadoWindows("e", "Empresa", "ICP-Brasil", "2030-01-01", "16840128000101")
    monkeypatch.setattr("nfe_consulta.cli.listar_certificados_cliente", lambda: [fortinet, empresa])
    assert _selecionar_certificado(None, "16840128000101") == empresa
    assert _selecionar_certificado(1, "16840128000101") == empresa


def test_auto_recusa_certificado_sem_cnpj_compativel(monkeypatch):
    fortinet = CertificadoWindows("f", "Fortinet", "Fortinet", "2030-01-01")
    monkeypatch.setattr("nfe_consulta.cli.listar_certificados_cliente", lambda: [fortinet])
    with pytest.raises(NfeErroCertificado, match="--cert-indice"):
        _selecionar_certificado(None, "16840128000101")
