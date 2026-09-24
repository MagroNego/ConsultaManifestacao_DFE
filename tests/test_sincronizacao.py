from nfe_consulta.banco import BancoManifestacoes
from nfe_consulta.modelos import CertificadoWindows, Manifestacao, RetornoDistribuicao
from nfe_consulta.sincronizacao import sincronizar


CHAVE = "35260123456789000123550010000012341000012345"
CNPJ = "12345678000199"


def test_sincronizacao_avanca_ate_max_nsu(tmp_path, monkeypatch):
    respostas = [
        RetornoDistribuicao(
            138,
            "Documentos localizados",
            "10".zfill(15),
            "20".zfill(15),
            ((CHAVE, Manifestacao("210210", "Ciencia da Operacao", "2026-09-17T09:00:00-03:00", "1", "10", "evento")),),
        ),
        RetornoDistribuicao(
            138,
            "Documentos localizados",
            "20".zfill(15),
            "20".zfill(15),
            ((CHAVE, Manifestacao("210200", "Confirmacao da Operacao", "2026-09-17T10:00:00-03:00", "2", "20", "evento")),),
        ),
    ]
    nsus_recebidos = []

    def consultar(cnpj, uf, ult_nsu, certificado):
        nsus_recebidos.append(ult_nsu)
        return respostas.pop(0)

    monkeypatch.setattr("nfe_consulta.sincronizacao.consultar_distribuicao", consultar)
    banco = BancoManifestacoes(str(tmp_path / "teste.db"))
    cert = CertificadoWindows("abc", "empresa", "ac", "2030-01-01", CNPJ)
    try:
        resumo = sincronizar(banco, CNPJ, "33", cert)
        assert resumo.completo is True
        assert resumo.lotes == 2
        assert resumo.eventos_novos == 2
        assert nsus_recebidos == ["000000000000000", "000000000000010"]
    finally:
        banco.fechar()
