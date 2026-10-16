import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from nfe_consulta.banco import BancoManifestacoes
from nfe_consulta.config import CNPJ_PADRAO
from nfe_consulta.janela_consulta import BRASILIA
from nfe_consulta.modelos import CertificadoWindows, NfeConsumoIndevidoErro, RetornoDistribuicao
from nfe_consulta.web import sync_runtime
from nfe_consulta.web.sync_diagnostics import detalhes_erro, mensagem_erro
from nfe_consulta.web.sync_history import read_sync_history


def preparar(tmp_path, monkeypatch):
    caminho = tmp_path / 'eventos.db'
    banco = BancoManifestacoes(str(caminho))
    banco.salvar_retorno(CNPJ_PADRAO, RetornoDistribuicao(138, '', '10', '30', ()))
    banco.fechar()
    settings = SimpleNamespace(
        database_path=caminho, database_path_file=tmp_path/'db-path.txt',
        certificate_path_file=tmp_path/'cert-path.txt', certificate_password_file=tmp_path/'cert-password.txt',
        certificate_thumbprint='abc', certificate_store='CurrentUser', sync_cooldown_minutes=60,
        email_recipients_file=tmp_path/'recipients.json', current_database_password=lambda: None)
    monkeypatch.setattr('nfe_consulta.servico.resolver_certificado', lambda *args: CertificadoWindows('abc', '', '', '', CNPJ_PADRAO))
    monkeypatch.setattr(sync_runtime, 'enviar_pendentes', lambda *args: None)
    monkeypatch.setattr('nfe_consulta.janela_consulta.agora_brasilia', lambda: datetime(2026, 10, 13, 22, tzinfo=BRASILIA))
    registros = []
    audit = SimpleNamespace(write_system=lambda action, result, **details: registros.append((action, result, details)))
    return caminho, settings, audit, registros


def test_656_apos_lote_salvo_registra_estado_sem_mensagem_bruta(tmp_path, monkeypatch):
    caminho, settings, audit, registros = preparar(tmp_path, monkeypatch)
    respostas = iter([
        '<retDistDFeInt><cStat>138</cStat><ultNSU>20</ultNSU><maxNSU>30</maxNSU></retDistDFeInt>',
        '<retDistDFeInt><cStat>656</cStat><xMotivo>senha=segredo XML privado</xMotivo><ultNSU>25</ultNSU><maxNSU>30</maxNSU></retDistDFeInt>'])
    monkeypatch.setattr('nfe_consulta.distribuicao._enviar_soap_windows', lambda *args: next(respostas))
    with pytest.raises(NfeConsumoIndevidoErro) as erro:
        sync_runtime.sincronizar_configurado(settings, audit=audit)
    dados = detalhes_erro(erro.value)
    assert dados['etapa'] == 'distNSU'
    assert dados['cstat'] == 656
    assert int(dados['nsu_antes']) == 10
    assert int(dados['nsu_solicitado']) == int(dados['nsu_salvo']) == 20
    assert int(dados['nsu_sefaz']) == 25
    assert dados['lotes_gravados'] == 1
    assert dados['respostas_pendentes'] == 0
    assert dados['proxima_tentativa']
    assert 'segredo' not in json.dumps(registros)
    assert 'segredo' not in mensagem_erro(erro.value)
    assert dados['execucao'] in mensagem_erro(erro.value)
    assert len({r[2]['execucao'] for r in registros if r[0]=='sefaz_sync_diagnostico'}) == 1
    banco = BancoManifestacoes(str(caminho))
    assert int(banco.obter_estado(CNPJ_PADRAO)[0]) == 20
    banco.fechar()


def test_erro_gravacao_mostra_resposta_preservada_e_cursor_antigo(tmp_path, monkeypatch):
    caminho, settings, audit, _ = preparar(tmp_path, monkeypatch)
    banco = BancoManifestacoes(str(caminho))
    banco.conexao.execute("CREATE TRIGGER falha BEFORE UPDATE ON estado_distribuicao BEGIN SELECT RAISE(ABORT,'falha sensivel'); END")
    banco.conexao.commit()
    banco.fechar()
    monkeypatch.setattr('nfe_consulta.distribuicao._enviar_soap_windows', lambda *args:
        '<retDistDFeInt><cStat>138</cStat><ultNSU>20</ultNSU><maxNSU>30</maxNSU></retDistDFeInt>')
    with pytest.raises(Exception) as erro:
        sync_runtime.sincronizar_configurado(settings, audit=audit)
    dados = detalhes_erro(erro.value)
    assert dados['cstat'] == 138
    assert int(dados['nsu_salvo']) == 10
    assert dados['respostas_pendentes'] == 1
    assert dados['lotes_gravados'] == 0
    assert 'sensivel' not in mensagem_erro(erro.value)


def test_erro_recuperacao_indica_cons_nsu_sem_avancar_cursor(tmp_path, monkeypatch):
    caminho, settings, audit, _ = preparar(tmp_path, monkeypatch)
    banco = BancoManifestacoes(str(caminho))
    with banco.conexao:
        banco.registrar_recuperacao_nsu(CNPJ_PADRAO, '10', '15')
    banco.fechar()
    monkeypatch.setattr('nfe_consulta.distribuicao._enviar_soap_windows', lambda *args:
        '<retDistDFeInt><cStat>656</cStat><ultNSU>25</ultNSU><maxNSU>30</maxNSU></retDistDFeInt>')
    with pytest.raises(NfeConsumoIndevidoErro) as erro:
        sync_runtime.sincronizar_configurado(settings, audit=audit)
    dados = detalhes_erro(erro.value)
    assert dados['etapa'] == 'consNSU'
    assert int(dados['nsu_solicitado']) == 11
    assert int(dados['nsu_salvo']) == 10
    assert dados['recuperados_na_tentativa'] == 0


def test_falha_diagnostico_nao_oculta_erro_original(tmp_path, monkeypatch):
    _, settings, audit, _ = preparar(tmp_path, monkeypatch)
    def executar(*args, **kwargs):
        monkeypatch.setattr('nfe_consulta.web.status_view.read_web_status', Mock(side_effect=OSError('banco ocupado')))
        raise NfeConsumoIndevidoErro('erro original', ult_nsu='25')
    monkeypatch.setattr(sync_runtime, 'sincronizar_banco', executar)
    with pytest.raises(NfeConsumoIndevidoErro, match='erro original') as erro:
        sync_runtime.sincronizar_configurado(settings, audit=audit)
    assert detalhes_erro(erro.value)['cstat'] == 656


def test_historico_filtra_diagnostico_e_mostra_acao_horario_e_referencia(tmp_path):
    path = tmp_path/'audit.log'
    payload = dict(action='sefaz_sync_auto', result='erro', reason='NfeConsumoIndevidoErro',
        execucao='a'*32, etapa='consNSU', cstat=656, nsu_salvo='10', nsu_solicitado='11',
        nsu_sefaz='20', lotes_gravados=1, respostas_pendentes=1,
        quando='2026-10-14T01:00:00-03:00', proxima_tentativa='2026-10-14T22:00:00-03:00',
        detail='senha=segredo', banco='c:/privado', nsu_antes='<script>')
    path.write_text('2026-10-14 04:00:00 '+json.dumps(payload)+'\n')
    item = read_sync_history(path, now=datetime(2026, 10, 15, tzinfo=timezone.utc))[0]
    assert 'não altere o NSU' in item.detail
    assert 'consNSU' in item.diagnostic
    assert '000000000000011' in item.diagnostic
    assert item.reference == 'a'*32
    assert item.next_attempt == '14/10/2026 22:00 (Brasília)'
    assert item.when.endswith('(Brasília)')
    assert 'segredo' not in repr(item) and '<script>' not in repr(item) and 'privado' not in repr(item)


@pytest.mark.parametrize('mensagem,tipo,http', [
    ('Timeout ao conectar: senha=segredo', 'timeout', None),
    ('Resposta vazia da SEFAZ', 'resposta_vazia', None),
    ('HTTP 503 retornado pelo Ambiente Nacional: segredo', None, 503),
])
def test_comunicacao_distingue_timeout_http_sem_expor_mensagem(mensagem, tipo, http):
    from nfe_consulta.modelos import NfeErroComunicacao
    exc = NfeErroComunicacao(mensagem)
    dados = detalhes_erro(exc)
    assert dados.get('falha_comunicacao') == tipo
    assert dados.get('http_status') == http
    assert 'segredo' not in json.dumps(dados)
    assert 'segredo' not in mensagem_erro(exc)


def test_rejeicao_preservada_apos_reinicio_mantem_nsu_solicitado(tmp_path, monkeypatch):
    caminho, settings, audit, _ = preparar(tmp_path, monkeypatch)
    banco = BancoManifestacoes(str(caminho))
    banco.preservar_resposta(CNPJ_PADRAO, '10',
        '<retDistDFeInt><cStat>656</cStat><ultNSU>25</ultNSU><maxNSU>30</maxNSU></retDistDFeInt>')
    banco.fechar()
    envio = Mock(side_effect=AssertionError('Não deve consultar novamente'))
    monkeypatch.setattr('nfe_consulta.distribuicao._enviar_soap_windows', envio)
    with pytest.raises(NfeConsumoIndevidoErro) as erro:
        sync_runtime.sincronizar_configurado(settings, audit=audit)
    dados = detalhes_erro(erro.value)
    assert dados['etapa'] == 'distNSU'
    assert int(dados['nsu_solicitado']) == 10
    assert int(dados['nsu_salvo']) == 10
    envio.assert_not_called()


def test_metadados_invalidos_nao_quebram_historico(tmp_path):
    path = tmp_path/'audit.log'
    payload = dict(action='sefaz_sync', result='erro', reason='NfeErroComunicacao',
        etapa=[], falha_comunicacao={}, quando='0001-01-01T00:00:00+00:00',
        execucao={}, nsu_salvo=[], duracao_segundos='segredo')
    path.write_text('2026-10-14 04:00:00 '+json.dumps(payload)+'\n')
    item = read_sync_history(path, now=datetime(2026, 10, 15, tzinfo=timezone.utc))[0]
    assert item.result == 'Falhou'
    assert item.reference == ''
    assert 'segredo' not in repr(item)


def test_fechamento_apos_lote_gravado_nao_aparece_como_nao_executada(tmp_path):
    path = tmp_path/'audit.log'
    path.write_text('2026-10-14 07:00:00 '+json.dumps(dict(
        action='sefaz_sync_auto', result='ignorado', reason='fora_janela',
        lotes_gravados=1, nsu_salvo='20'))+'\n')
    item = read_sync_history(path, now=datetime(2026, 10, 15, tzinfo=timezone.utc))[0]
    assert item.result == 'Interrompida pelo horário'
    assert 'já foi gravado foi mantido' in item.detail


@pytest.mark.parametrize('habilitada', [False, True])
def test_pausa_cons_nsu_preserva_fila_e_separa_consulta_de_distribuicao(tmp_path, monkeypatch, habilitada):
    caminho, settings, audit, registros = preparar(tmp_path, monkeypatch)
    settings.recovery_enabled = habilitada
    banco = BancoManifestacoes(str(caminho))
    with banco.conexao:
        banco.registrar_recuperacao_nsu(CNPJ_PADRAO, '10', '15')
    fila = banco.conexao.execute('SELECT cnpj,nsu_local,nsu_sefaz FROM recuperacoes_nsu').fetchall()
    banco.fechar()
    chamadas = []
    def soap(xml, *args):
        chamadas.append(xml)
        if '<consNSU>' in xml:
            return '<retDistDFeInt><cStat>137</cStat><ultNSU>30</ultNSU><maxNSU>30</maxNSU></retDistDFeInt>'
        return '<retDistDFeInt><cStat>138</cStat><ultNSU>30</ultNSU><maxNSU>30</maxNSU></retDistDFeInt>'
    monkeypatch.setattr('nfe_consulta.distribuicao._enviar_soap_windows', soap)
    resumo = sync_runtime.sincronizar_configurado(settings, audit=audit)
    banco = BancoManifestacoes(str(caminho))
    assert banco.conexao.execute('SELECT cnpj,nsu_local,nsu_sefaz FROM recuperacoes_nsu').fetchall() == fila
    if habilitada:
        assert all('<consNSU>' in xml for xml in chamadas)
        assert resumo.somente_recuperacao
        assert int(banco.obter_estado(CNPJ_PADRAO)[0]) == 10
    else:
        assert len(chamadas) == 1 and '<distNSU>' in chamadas[0]
        assert '<ultNSU>000000000000010</ultNSU>' in chamadas[0]
        assert not resumo.somente_recuperacao
        assert banco.conexao.execute('SELECT COUNT(*) FROM consultas_nsu').fetchone()[0] == 0
        assert int(banco.obter_estado(CNPJ_PADRAO)[0]) == 30
        assert banco.proximo_nsu_faltante(CNPJ_PADRAO) == '000000000000011'
    banco.fechar()
