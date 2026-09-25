import pytest

from nfe_consulta.banco import BancoManifestacoes
from nfe_consulta.modelos import CertificadoWindows, NfeLimiteConsultaErro
from nfe_consulta.servico import ParametrosSincronizacao, sincronizar_banco
from nfe_consulta.sincronizacao import ResumoSincronizacao


CNPJ = "16840128000101"


def test_cooldown_de_duas_horas_persiste_no_banco(tmp_path, monkeypatch):
    banco_path = tmp_path / "historico.db"
    banco = BancoManifestacoes(str(banco_path))
    banco.fechar()

    certificado = CertificadoWindows(
        "abc",
        "Empresa",
        "ICP-Brasil",
        "2030-01-01",
        CNPJ,
    )
    monkeypatch.setattr(
        "nfe_consulta.servico.resolver_certificado",
        lambda *args, **kwargs: certificado,
    )
    monkeypatch.setattr(
        "nfe_consulta.servico.sincronizar",
        lambda *args, **kwargs: ResumoSincronizacao(
            1, 0, 0, "1".zfill(15), "1".zfill(15), True, False
        ),
    )

    parametros = ParametrosSincronizacao(
        banco=banco_path,
        cnpj=CNPJ,
        cooldown_minutos=120,
    )

    sincronizar_banco(parametros)

    with pytest.raises(NfeLimiteConsultaErro, match="temporariamente bloqueada"):
        sincronizar_banco(parametros)

    reaberto = BancoManifestacoes(str(banco_path))
    try:
        ultima, proxima = reaberto.obter_janela_sincronizacao(CNPJ)
        assert ultima is not None
        assert proxima is not None
        segundos = (proxima - ultima).total_seconds()
        assert 7199 <= segundos <= 7201
    finally:
        reaberto.fechar()
