import pytest

from nfe_consulta.modelos import NfeChaveInvalidaErro
from nfe_consulta.validacao import validar_chave


def test_valida_chave_correta():
    assert validar_chave("35260123456789000123550010000012341000012345") == "35260123456789000123550010000012341000012345"

def test_valida_chave_limpa():
    assert validar_chave("3526012345678-90001 235500100.00012341000012345") == "35260123456789000123550010000012341000012345"
    
def test_chave_curta_invalida():
    with pytest.raises(NfeChaveInvalidaErro):
        validar_chave("123")
