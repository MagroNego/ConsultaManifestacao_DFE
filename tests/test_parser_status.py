from pathlib import Path
from nfe_consulta.parser import parse_retorno_consulta

def test_parse_status_sem_manifestacao():
    xml = Path("tests/fixtures/ret_cons_sit_sem_manifestacao.xml").read_text()
    resultado = parse_retorno_consulta(xml, "35260123456789000123550010000012341000012345")
    
    assert resultado.status_codigo == 100
    assert resultado.status_motivo == "Autorizado o uso da NF-e"
    assert resultado.protocolo_nfe == "135260000000000"
    assert len(resultado.manifestacoes) == 0
