from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from nfe_consulta import janela_consulta as janela
from nfe_consulta.banco import BancoManifestacoes
from nfe_consulta.modelos import RetornoDistribuicao, NfeErroResposta


@pytest.mark.parametrize('hora,minuto,esperada', [
    (7, 59, '2026-10-13T08:00:00-03:00'),
    (8, 0, '2026-10-13T08:00:00-03:00'),
    (17, 59, '2026-10-13T17:59:00-03:00'),
    (18, 0, '2026-10-14T08:00:00-03:00'),
    (22, 0, '2026-10-14T08:00:00-03:00'),
])
def test_limites_brasilia_e_utc(hora, minuto, esperada):
    instante = datetime(2026, 10, 13, hora, minuto, tzinfo=janela.BRASILIA)
    assert janela.proxima_abertura(instante).isoformat() == esperada
    assert janela.proxima_abertura(instante.astimezone(timezone.utc)).isoformat() == esperada


@pytest.mark.parametrize('hora', [0, 4, 7, 18, 22, 23])
def test_transporte_bloqueia_antes_do_certificado_e_da_rede(monkeypatch, hora):
    from nfe_consulta import distribuicao
    monkeypatch.setattr(janela, 'agora_brasilia', lambda: datetime(2026, 10, 13, hora, tzinfo=janela.BRASILIA))
    enviar = Mock(side_effect=AssertionError('Não deve executar PowerShell'))
    monkeypatch.setattr(distribuicao.subprocess, 'run', enviar)
    with pytest.raises(janela.NfeJanelaConsultaErro):
        distribuicao._enviar_soap_windows('<soap/>', None)
    enviar.assert_not_called()


def test_manual_bloqueia_antes_de_abrir_banco(monkeypatch):
    from nfe_consulta.web.sync_runtime import sincronizar_configurado
    monkeypatch.setattr(janela, 'agora_brasilia', lambda: datetime(2026, 10, 13, 22, tzinfo=janela.BRASILIA))
    with pytest.raises(janela.NfeJanelaConsultaErro):
        sincronizar_configurado(SimpleNamespace())


def test_scheduler_nao_executa_recuperacao_fora_da_janela(monkeypatch):
    import asyncio
    from nfe_consulta.web import scheduler
    monkeypatch.setattr(scheduler, 'agora_brasilia', lambda: datetime(2026, 10, 13, 22, tzinfo=janela.BRASILIA))
    executar = Mock(side_effect=AssertionError('Não deve consultar'))
    monkeypatch.setattr(scheduler, 'executar_sincronizacao_automatica', executar)
    async def parar(_):
        raise RuntimeError('fim')
    monkeypatch.setattr(scheduler.asyncio, 'sleep', parar)
    app = SimpleNamespace(state=SimpleNamespace(settings=SimpleNamespace(auto_sync_once_date=None)))
    with pytest.raises(RuntimeError, match='fim'):
        asyncio.run(scheduler.loop_sincronizacao_automatica(app))
    assert app.state.auto_sync_next_at == datetime(2026, 10, 14, 8, tzinfo=janela.BRASILIA)
    executar.assert_not_called()


def test_rejeicao_nao_pode_ser_gravada_como_sucesso(tmp_path):
    banco = BancoManifestacoes(str(tmp_path / 'teste.db'))
    try:
        with pytest.raises(NfeErroResposta, match='rejeitada'):
            banco.salvar_retorno('16840128000101', RetornoDistribuicao(656, 'erro', '100', '100', ()))
        assert int(banco.obter_estado('16840128000101')[0]) == 0
    finally:
        banco.fechar()


def test_fecha_entre_lotes_preservando_primeiro_lote(tmp_path, monkeypatch):
    from nfe_consulta import distribuicao
    from nfe_consulta.sincronizacao import sincronizar
    cnpj = '16840128000101'
    banco = BancoManifestacoes(str(tmp_path / 'lotes.db'))
    aberto = datetime(2026, 10, 13, 17, 59, tzinfo=janela.BRASILIA)
    fechado = aberto.replace(hour=18, minute=0)
    monkeypatch.setattr(janela, 'agora_brasilia', lambda: aberto)
    def responder(*args):
        monkeypatch.setattr(janela, 'agora_brasilia', lambda: fechado)
        return ('<retDistDFeInt><cStat>138</cStat><xMotivo>OK</xMotivo>'
                '<ultNSU>10</ultNSU><maxNSU>20</maxNSU></retDistDFeInt>')
    envio = Mock(side_effect=responder)
    monkeypatch.setattr(distribuicao, '_enviar_soap_windows', envio)
    try:
        with pytest.raises(janela.NfeJanelaConsultaErro):
            sincronizar(banco, cnpj, '33', None)
        assert envio.call_count == 1
        assert int(banco.obter_estado(cnpj)[0]) == 10
    finally:
        banco.fechar()


def test_recuperacao_fora_da_janela_nao_reserva_cota(tmp_path, monkeypatch):
    from nfe_consulta.recuperacao_nsu import recuperar_intervalos
    banco = BancoManifestacoes(str(tmp_path / 'recuperacao.db'))
    cnpj = '16840128000101'
    monkeypatch.setattr(janela, 'agora_brasilia', lambda: datetime(2026, 10, 13, 18, tzinfo=janela.BRASILIA))
    try:
        banco.registrar_recuperacao_nsu(cnpj, '10', '15')
        with pytest.raises(janela.NfeJanelaConsultaErro):
            recuperar_intervalos(banco, cnpj, '33', None)
        assert banco.conexao.execute('SELECT COUNT(*) FROM consultas_nsu').fetchone()[0] == 0
    finally:
        banco.fechar()
