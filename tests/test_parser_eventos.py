from pathlib import Path
from nfe_consulta.parser import parse_retorno_consulta

def test_parse_com_manifestacoes():
    xml = Path("tests/fixtures/ret_cons_sit_com_manifestacoes.xml").read_text()
    resultado = parse_retorno_consulta(xml, "35260123456789000123550010000012341000012345")
    
    assert len(resultado.manifestacoes) == 2
    
    m1 = resultado.manifestacoes[0]
    assert m1.codigo == "210210"
    assert m1.descricao == "Ciencia da Operacao"
    assert m1.protocolo == "135260000000001"
    
    m2 = resultado.manifestacoes[1]
    assert m2.codigo == "210200"
    assert m2.descricao == "Confirmacao da Operacao"
    assert m2.protocolo == "135260000000002"
