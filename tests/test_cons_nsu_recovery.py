import base64
import gzip
import pytest
from nfe_consulta.banco import BancoManifestacoes
from nfe_consulta.modelos import RetornoDistribuicao, NfeConsumoIndevidoErro, NfeErroResposta
from nfe_consulta.recuperacao_nsu import recuperar_intervalos
from nfe_consulta.web.status_view import read_web_status

CNPJ='16840128000101'
CHAVE='35260123456789000123550010000012341000012345'

def resposta(nsu, status=138):
    evento=f'<resEvento><chNFe>{CHAVE}</chNFe><tpEvento>210210</tpEvento><dhEvento>2026-10-09T10:00:00-03:00</dhEvento></resEvento>'
    doc=base64.b64encode(gzip.compress(evento.encode())).decode()
    documento=f'<docZip NSU="{nsu}" schema="resEvento">{doc}</docZip>' if status==138 else ''
    return f'<retDistDFeInt><cStat>{status}</cStat><ultNSU>99</ultNSU><maxNSU>99</maxNSU>{documento}</retDistDFeInt>'

def banco(tmp_path, remoto=12):
    path=tmp_path/'b.db';b=BancoManifestacoes(str(path))
    b.salvar_retorno(CNPJ, RetornoDistribuicao(138,'','000000000000020','000000000000020',()))
    with b.conexao:
        b.conexao.execute('INSERT INTO recuperacoes_nsu(cnpj,nsu_local,nsu_sefaz,retomado_em) VALUES (?,?,?,CURRENT_TIMESTAMP)',(CNPJ,'000000000000010',str(remoto).zfill(15)))
    return path,b

def test_recupera_eventos_sem_mudar_cursor_e_fecha_intervalo(tmp_path,monkeypatch):
    path,b=banco(tmp_path);calls=[]
    def soap(xml,cert):
        assert '<consNSU>' in xml
        nsu=xml.split('<NSU>')[1].split('</NSU>')[0];calls.append(nsu)
        return resposta(nsu)
    monkeypatch.setattr('nfe_consulta.distribuicao._enviar_soap_windows',soap)
    assert recuperar_intervalos(b,CNPJ,'33',None)==2
    assert b.obter_estado(CNPJ)==('000000000000020',)*2
    assert read_web_status(path,CNPJ).complete
    assert recuperar_intervalos(b,CNPJ,'33',None)==0
    assert len(calls)==2
    assert b.conexao.execute('SELECT COUNT(*) FROM documentos_nsu').fetchone()[0]==2
    b.fechar()

def test_indisponivel_nao_fecha_intervalo_nem_repete(tmp_path,monkeypatch):
    path,b=banco(tmp_path,11)
    monkeypatch.setattr('nfe_consulta.distribuicao._enviar_soap_windows',lambda *a:resposta(11,137))
    recuperar_intervalos(b,CNPJ,'33',None)
    assert not read_web_status(path,CNPJ).complete
    assert not read_web_status(path,CNPJ).recovery_pending
    assert b.proximo_nsu_faltante(CNPJ) is None
    b.fechar()

def test_656_pausa_e_preserva_intervalo(tmp_path,monkeypatch):
    path,b=banco(tmp_path)
    monkeypatch.setattr('nfe_consulta.distribuicao._enviar_soap_windows',lambda *a:resposta(11,656))
    with pytest.raises(NfeConsumoIndevidoErro):recuperar_intervalos(b,CNPJ,'33',None)
    assert b.pausa_ativa(CNPJ)
    assert b.proximo_nsu_faltante(CNPJ)=='000000000000011'
    assert b.obter_estado(CNPJ)[0]=='000000000000020'
    b.fechar()

def test_limite_10_e_orcamento_compartilhado(tmp_path,monkeypatch):
    _,b=banco(tmp_path,45);calls=[]
    def soap(xml,*a):
        n=xml.split('<NSU>')[1].split('</NSU>')[0];calls.append(n);return resposta(n)
    monkeypatch.setattr('nfe_consulta.distribuicao._enviar_soap_windows',soap)
    for _ in range(15):b.registrar_consulta_pontual(CNPJ,CHAVE)
    assert recuperar_intervalos(b,CNPJ,'33',None)==5
    assert len(calls)==5
    b.fechar()

def test_gravacao_falha_reprocessa_sem_reconsultar(tmp_path,monkeypatch):
    _,b=banco(tmp_path,11);calls=[]
    monkeypatch.setattr('nfe_consulta.distribuicao._enviar_soap_windows',lambda *a:calls.append(1) or resposta(11))
    b.conexao.execute("CREATE TRIGGER falha BEFORE INSERT ON manifestacoes BEGIN SELECT RAISE(ABORT,'falha'); END")
    b.conexao.commit()
    with pytest.raises(Exception,match='falha'):recuperar_intervalos(b,CNPJ,'33',None)
    assert b.conexao.execute('SELECT COUNT(*) FROM documentos_nsu').fetchone()[0]==0
    b.conexao.execute('DROP TRIGGER falha');b.conexao.commit()
    assert recuperar_intervalos(b,CNPJ,'33',None)==1
    assert len(calls)==1
    b.fechar()

def test_nsu_errado_nao_importa(tmp_path,monkeypatch):
    _,b=banco(tmp_path,11)
    monkeypatch.setattr('nfe_consulta.distribuicao._enviar_soap_windows',lambda *a:resposta(12))
    with pytest.raises(NfeErroResposta):recuperar_intervalos(b,CNPJ,'33',None)
    assert b.conexao.execute('SELECT COUNT(*) FROM documentos_nsu').fetchone()[0]==0
    b.fechar()

def test_reinicio_reserva_sem_resposta_e_retentativa(tmp_path,monkeypatch):
    _,b=banco(tmp_path,11)
    with b.conexao:
        b.conexao.execute("INSERT INTO consultas_nsu(cnpj,nsu,tentado_em) VALUES (?,?,datetime('now','-2 hours'))",(CNPJ,'000000000000011'))
    monkeypatch.setattr('nfe_consulta.distribuicao._enviar_soap_windows',lambda *a:resposta(11))
    assert recuperar_intervalos(b,CNPJ,'33',None)==1
    b.fechar()

def test_documento_ignorado_fica_preservado_e_conta_na_conferencia(tmp_path,monkeypatch):
    path,b=banco(tmp_path,11)
    xml=b'<outroDocumento>teste</outroDocumento>'
    doc=base64.b64encode(gzip.compress(xml)).decode()
    retorno=f'<retDistDFeInt><cStat>138</cStat><ultNSU>20</ultNSU><maxNSU>20</maxNSU><docZip NSU="11" schema="outro">{doc}</docZip></retDistDFeInt>'
    monkeypatch.setattr('nfe_consulta.distribuicao._enviar_soap_windows',lambda *a:retorno)
    assert recuperar_intervalos(b,CNPJ,'33',None)==0
    assert b.conexao.execute('SELECT xml,classificacao FROM documentos_nsu').fetchone()==(xml,'ignorado')
    assert read_web_status(path,CNPJ).complete
    b.fechar()

def test_recuperacao_em_sqlcipher(tmp_path,monkeypatch):
    from nfe_consulta.seguranca_banco import migrar_banco
    path,b=banco(tmp_path,11);b.fechar()
    seguro=tmp_path/'seguro.db';migrar_banco(path,seguro,'senha-segura-teste')
    b=BancoManifestacoes(str(seguro),senha='senha-segura-teste')
    monkeypatch.setattr('nfe_consulta.distribuicao._enviar_soap_windows',lambda *a:resposta(11))
    assert recuperar_intervalos(b,CNPJ,'33',None)==1
    assert read_web_status(seguro,CNPJ,password='senha-segura-teste').complete
    b.fechar()

def test_integracao_sincronizacao_com_cache_recupera_lacuna(tmp_path,monkeypatch):
    from nfe_consulta.sincronizacao import sincronizar
    path,b=banco(tmp_path,11)
    calls=[]
    def soap(xml,*args):
        assert '<consNSU>' in xml
        calls.append(1);return resposta(11)
    monkeypatch.setattr('nfe_consulta.distribuicao._enviar_soap_windows',soap)
    resumo=sincronizar(b,CNPJ,'33',None,recuperar_lacunas=True)
    assert resumo.eventos_novos==1
    assert calls==[1]
    assert read_web_status(path,CNPJ).complete
    b.fechar()
