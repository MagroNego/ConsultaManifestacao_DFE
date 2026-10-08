import base64
import gzip
import sqlite3
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from nfe_consulta.banco import BancoManifestacoes
from nfe_consulta.modelos import CertificadoWindows, NfeConsumoIndevidoErro, NfeErroResposta, RetornoDistribuicao
from nfe_consulta.sincronizacao import sincronizar
from nfe_consulta.web.status_view import read_web_status
from nfe_consulta.web.scheduler import proxima_recuperacao_nsu

CNPJ = "16840128000101"
CHAVE = "35260123456789000123550010000012341000012345"
CERT = CertificadoWindows("abc", "empresa", "ac", "2030-01-01", CNPJ)


def response(status, ult="", maximo="20", documento=""):
    return (f"<retDistDFeInt><cStat>{status}</cStat><xMotivo>Sequencia NSU</xMotivo>"
            f"<ultNSU>{ult}</ultNSU><maxNSU>{maximo}</maxNSU>{documento}</retDistDFeInt>")


def setup_bank(tmp_path):
    path = tmp_path / "fiscal.db"
    banco = BancoManifestacoes(str(path))
    banco.salvar_retorno(CNPJ, RetornoDistribuicao(138, "", "10".zfill(15), "20".zfill(15), ()))
    return path, banco


def release_pause(banco):
    with banco.conexao:
        banco.conexao.execute("DELETE FROM pausa_distribuicao")


def test_656_preserva_cursor_pausa_e_retoma_com_nsu_da_sefaz(tmp_path, monkeypatch):
    path, banco = setup_bank(tmp_path)
    respostas = [response(656, "15"), response(138, "20")]
    enviados = []

    def soap(xml, certificado):
        enviados.append(xml)
        return respostas.pop(0)

    monkeypatch.setattr("nfe_consulta.distribuicao._enviar_soap_windows", soap)
    with pytest.raises(NfeConsumoIndevidoErro):
        sincronizar(banco, CNPJ, "33", CERT)
    assert banco.obter_estado(CNPJ)[0] == "10".zfill(15)
    assert banco.nsu_para_consulta(CNPJ) == "15".zfill(15)
    assert read_web_status(path, CNPJ).complete is False
    with pytest.raises(Exception, match="nova tentativa"):
        sincronizar(banco, CNPJ, "33", CERT)
    assert len(enviados) == 1
    release_pause(banco)
    banco.fechar()
    banco = BancoManifestacoes(str(path))
    resumo = sincronizar(banco, CNPJ, "33", CERT)
    assert "<ultNSU>000000000000015</ultNSU>" in enviados[-1]
    assert resumo.completo
    status = read_web_status(path, CNPJ)
    assert not status.complete  # Retomada não comprova os documentos do intervalo.
    assert status.nsu_gaps[0][2] is not None
    assert banco.respostas_pendentes(CNPJ) == []
    banco.fechar()


@pytest.mark.parametrize("informado", ["", "abc", "9", "10", "1234567890123456"])
def test_656_sem_nsu_valido_maior_nao_altera_ponto_de_leitura(tmp_path, monkeypatch, informado):
    _, banco = setup_bank(tmp_path)
    monkeypatch.setattr("nfe_consulta.distribuicao._enviar_soap_windows",
                        lambda *args: response(656, informado))
    with pytest.raises(NfeConsumoIndevidoErro):
        sincronizar(banco, CNPJ, "33", CERT)
    assert banco.nsu_para_consulta(CNPJ) == "10".zfill(15)
    assert not banco.conexao.execute("SELECT * FROM recuperacoes_nsu").fetchall()
    banco.fechar()


def test_lote_recuperado_apos_falha_de_gravacao_sem_nova_chamada(tmp_path, monkeypatch):
    path, banco = setup_bank(tmp_path)
    evento = (f"<resEvento><chNFe>{CHAVE}</chNFe><tpEvento>210210</tpEvento>"
              "<dhEvento>2026-10-08T10:00:00-03:00</dhEvento><nProt>123</nProt></resEvento>")
    doc = base64.b64encode(gzip.compress(evento.encode())).decode()
    xml = response(138, "20", documento=f'<docZip NSU="000000000000020" schema="resEvento">{doc}</docZip>')
    chamados = []
    monkeypatch.setattr("nfe_consulta.distribuicao._enviar_soap_windows",
                        lambda *args: chamados.append(1) or xml)
    banco.conexao.execute("CREATE TRIGGER falha BEFORE UPDATE ON estado_distribuicao "
                          "BEGIN SELECT RAISE(ABORT, 'falha simulada'); END")
    banco.conexao.commit()
    with pytest.raises(sqlite3.IntegrityError, match="falha simulada"):
        sincronizar(banco, CNPJ, "33", CERT)
    assert banco.obter_estado(CNPJ)[0] == "10".zfill(15)
    assert banco.conexao.execute("SELECT COUNT(*) FROM manifestacoes").fetchone()[0] == 0
    assert read_web_status(path, CNPJ).pending_responses == 1
    banco.conexao.execute("DROP TRIGGER falha")
    banco.conexao.commit()
    banco.fechar()
    banco = BancoManifestacoes(str(path))
    resumo = sincronizar(banco, CNPJ, "33", CERT)
    assert resumo.eventos_novos == 1
    assert len(chamados) == 1
    assert banco.obter_estado(CNPJ)[0] == "20".zfill(15)
    assert banco.respostas_pendentes(CNPJ) == []
    assert banco.conexao.execute("SELECT resposta_xml FROM respostas_distribuicao").fetchone()[0] is None
    banco.fechar()


def test_resposta_invalida_fica_preservada_e_nao_pula_lote(tmp_path, monkeypatch):
    path, banco = setup_bank(tmp_path)
    chamados = []
    monkeypatch.setattr("nfe_consulta.distribuicao._enviar_soap_windows",
                        lambda *args: chamados.append(1) or "<invalido")
    for _ in range(2):
        with pytest.raises(NfeErroResposta):
            sincronizar(banco, CNPJ, "33", CERT)
    assert len(chamados) == 1
    assert banco.obter_estado(CNPJ)[0] == "10".zfill(15)
    assert read_web_status(path, CNPJ).pending_responses == 1
    banco.fechar()


def test_scheduler_recupera_so_apos_pausa_e_cooldown(tmp_path):
    path, banco = setup_bank(tmp_path)
    with banco.conexao:
        banco.registrar_recuperacao_nsu(CNPJ, "10", "15")
    banco.reservar_sincronizacao(CNPJ, 120)
    banco.pausar_distribuicao(CNPJ, "656")
    settings = SimpleNamespace(database_path=path, database_path_file=tmp_path / "ausente",
                               current_database_password=lambda: None)
    proxima = proxima_recuperacao_nsu(settings)
    assert proxima > datetime.now(timezone.utc) + timedelta(minutes=119)
    banco.fechar()


def test_recuperacao_em_banco_sqlcipher(tmp_path, monkeypatch):
    from nfe_consulta.seguranca_banco import migrar_banco

    origem, banco = setup_bank(tmp_path)
    banco.fechar()
    path = tmp_path / "seguro.db"
    migrar_banco(origem, path, "Senha-Forte-123!")
    banco = BancoManifestacoes(str(path), senha="Senha-Forte-123!")
    monkeypatch.setattr("nfe_consulta.distribuicao._enviar_soap_windows",
                        lambda *args: response(656, "15"))
    with pytest.raises(NfeConsumoIndevidoErro):
        sincronizar(banco, CNPJ, "33", CERT)
    assert read_web_status(path, CNPJ, password="Senha-Forte-123!").nsu_gaps
    banco.fechar()


def test_loop_agenda_retoma_antes_da_proxima_janela(tmp_path, monkeypatch):
    import asyncio
    from nfe_consulta.web import scheduler

    path, banco = setup_bank(tmp_path)
    with banco.conexao:
        banco.registrar_recuperacao_nsu(CNPJ, "10", "15")
    banco.pausar_distribuicao(CNPJ, "656")
    settings = SimpleNamespace(database_path=path, database_path_file=tmp_path / "ausente",
                               current_database_password=lambda: None,
                               auto_sync_once_date=None, auto_sync_weekdays=tuple(range(7)))
    agora = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=-3))).replace(hour=15)
    monkeypatch.setattr(scheduler, "agora_brasilia", lambda: agora)
    monkeypatch.setattr(scheduler, "ultima_janela_concluida", lambda _: None)
    chamados, esperas = [], []

    async def executar(*args, **kwargs):
        chamados.append(1)

    async def dormir(segundos):
        esperas.append(segundos)
        raise RuntimeError("encerrar teste")

    monkeypatch.setattr(scheduler, "executar_sincronizacao_automatica", executar)
    monkeypatch.setattr(scheduler.asyncio, "sleep", dormir)
    app = SimpleNamespace(state=SimpleNamespace(settings=settings))
    with pytest.raises(RuntimeError, match="encerrar teste"):
        asyncio.run(scheduler.loop_sincronizacao_automatica(app))
    assert chamados == [1]
    assert 0 < esperas[0] < 4 * 3600
    banco.fechar()
