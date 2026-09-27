import sqlite3
from datetime import datetime, timedelta, timezone

from nfe_consulta.banco import BancoManifestacoes
from nfe_consulta.modelos import RetornoDistribuicao
from nfe_consulta.status import consultar_status


CNPJ = "16840128000101"


def test_status_parcial_completo_e_pausa(tmp_path):
    caminho = tmp_path / "historico.db"
    banco = BancoManifestacoes(str(caminho))
    banco.salvar_retorno(CNPJ, RetornoDistribuicao(138, "", "10".zfill(15), "20".zfill(15), ()))
    agora = datetime.now(timezone.utc)
    try:
        assert "Sincronizacao parcial" in consultar_status(str(caminho), CNPJ, agora)
        banco.salvar_retorno(CNPJ, RetornoDistribuicao(138, "", "20".zfill(15), "20".zfill(15), ()))
        atual = consultar_status(str(caminho), CNPJ, agora)
        assert "Fila percorrida" in atual
        assert "Proxima verificacao recomendada" in atual
        banco.pausar_distribuicao(CNPJ, "656")
        assert "Pausa por 656" in consultar_status(str(caminho), CNPJ, agora)
        banco.conexao.execute(
            "UPDATE estado_distribuicao SET atualizado_em = ? WHERE cnpj = ?",
            ((agora - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S"), CNPJ),
        )
        banco.conexao.commit()
        assert "Proxima verificacao recomendada" in consultar_status(str(caminho), CNPJ, agora)
        assert "Pausa por 656" in consultar_status(str(caminho), CNPJ, agora)
        assert "Ja pode executar a opcao 1" in consultar_status(str(caminho), CNPJ, agora + timedelta(hours=2))
    finally:
        banco.fechar()


def test_status_banco_anterior_sem_tabela_pausa(tmp_path):
    caminho = tmp_path / "antigo.db"
    with sqlite3.connect(caminho) as conexao:
        conexao.execute("CREATE TABLE estado_distribuicao(cnpj TEXT, ult_nsu TEXT, max_nsu TEXT, atualizado_em TEXT)")
        conexao.execute("INSERT INTO estado_distribuicao VALUES (?, ?, ?, ?)",
                       (CNPJ, "1", "1", "2026-09-01 12:00:00"))
    assert "Fila percorrida" in consultar_status(str(caminho), CNPJ)


def test_motivo_656_persistido_sem_avancar_cursor(tmp_path, monkeypatch):
    from nfe_consulta.modelos import CertificadoWindows, NfeConsumoIndevidoErro
    from nfe_consulta.sincronizacao import sincronizar
    from nfe_consulta.distribuicao import consultar_distribuicao
    import pytest

    caminho = tmp_path / "historico.db"
    banco = BancoManifestacoes(str(caminho))
    banco.salvar_retorno(CNPJ, RetornoDistribuicao(138, "", "10".zfill(15), "20".zfill(15), ()))
    motivo = "Deve ser utilizado o ultNSU nas solicitacoes subsequentes"
    resposta = ("<retDistDFeInt><cStat>656</cStat>"
                f"<xMotivo>{motivo}</xMotivo><ultNSU>11</ultNSU><maxNSU>20</maxNSU>"
                "</retDistDFeInt>")
    monkeypatch.setattr("nfe_consulta.distribuicao._enviar_soap_windows",
                        lambda soap, certificado: resposta)
    monkeypatch.setattr("nfe_consulta.sincronizacao.consultar_distribuicao", consultar_distribuicao)
    certificado = CertificadoWindows("abc", "empresa", "ac", "2030-01-01", CNPJ)
    try:
        with pytest.raises(NfeConsumoIndevidoErro, match="xMotivo"):
            sincronizar(banco, CNPJ, "33", certificado)
        assert banco.obter_estado(CNPJ) == ("10".zfill(15), "20".zfill(15))
        assert motivo in consultar_status(str(caminho), CNPJ)
        assert motivo in consultar_status(str(caminho), CNPJ, datetime.now(timezone.utc) + timedelta(hours=2))
    finally:
        banco.fechar()
