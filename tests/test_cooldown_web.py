from datetime import datetime, timedelta, timezone

import pytest

from nfe_consulta.banco import BancoManifestacoes
from nfe_consulta.config import CNPJ_PADRAO
from nfe_consulta.modelos import CertificadoWindows, NfeLimiteConsultaErro
from nfe_consulta.servico import ParametrosSincronizacao, sincronizar_banco
from nfe_consulta.sincronizacao import ResumoSincronizacao


def test_reserva_atomica_bloqueia_outra_conexao_sem_estender_prazo(tmp_path):
    path = str(tmp_path / "historico.db")
    primeiro = BancoManifestacoes(path)
    segundo = BancoManifestacoes(path)
    try:
        primeiro.reservar_sincronizacao(CNPJ_PADRAO, 60)
        ultima, proxima = primeiro.obter_janela_sincronizacao(CNPJ_PADRAO)
        assert proxima - ultima == timedelta(minutes=60)
        with pytest.raises(NfeLimiteConsultaErro):
            segundo.reservar_sincronizacao(CNPJ_PADRAO, 60)
        assert segundo.obter_janela_sincronizacao(CNPJ_PADRAO) == (ultima, proxima)
        assert primeiro.bloqueio_sincronizacao(CNPJ_PADRAO, agora=proxima) is None
    finally:
        primeiro.fechar()
        segundo.fechar()


@pytest.mark.parametrize("pausa", [False, True])
def test_servico_bloqueado_nao_resolve_certificado_nem_consulta(tmp_path, monkeypatch, pausa):
    path = tmp_path / "historico.db"
    banco = BancoManifestacoes(str(path))
    if pausa:
        banco.pausar_distribuicao(CNPJ_PADRAO, "656")
    else:
        banco.reservar_sincronizacao(CNPJ_PADRAO, 60)
    banco.fechar()
    def proibido(*args, **kwargs):
        pytest.fail("Tentativa bloqueada chegou ao certificado ou à SEFAZ")
    monkeypatch.setattr("nfe_consulta.servico.resolver_certificado", proibido)
    monkeypatch.setattr("nfe_consulta.servico.sincronizar", proibido)
    with pytest.raises(NfeLimiteConsultaErro):
        sincronizar_banco(ParametrosSincronizacao(banco=path, cnpj=CNPJ_PADRAO))


def test_cooldown_de_120_minutos_fica_persistido_no_banco(tmp_path, monkeypatch):
    banco_path = tmp_path / "historico.db"
    banco = BancoManifestacoes(str(banco_path))
    banco.fechar()

    certificado = CertificadoWindows(
        "ABC",
        "Empresa",
        "ICP-Brasil",
        "2030-01-01",
        CNPJ_PADRAO,
    )
    monkeypatch.setattr(
        "nfe_consulta.servico.resolver_certificado",
        lambda *args, **kwargs: certificado,
    )
    monkeypatch.setattr(
        "nfe_consulta.servico.sincronizar",
        lambda *args, **kwargs: ResumoSincronizacao(
            lotes=1,
            eventos_novos=0,
            documentos_ignorados=0,
            ult_nsu="1".zfill(15),
            max_nsu="1".zfill(15),
            completo=True,
        ),
    )

    antes = datetime.now(timezone.utc)
    sincronizar_banco(
        ParametrosSincronizacao(
            banco=banco_path,
            cnpj=CNPJ_PADRAO,
            cooldown_minutos=120,
        )
    )

    banco = BancoManifestacoes(str(banco_path))
    try:
        ultima, proxima = banco.obter_janela_sincronizacao(CNPJ_PADRAO)
        assert ultima is not None
        assert proxima is not None
        assert proxima - ultima == timedelta(minutes=120)
        assert ultima >= antes - timedelta(seconds=2)
        assert banco.bloqueio_sincronizacao(CNPJ_PADRAO)

        with pytest.raises(NfeLimiteConsultaErro, match="temporariamente bloqueada"):
            sincronizar_banco(
                ParametrosSincronizacao(
                    banco=banco_path,
                    cnpj=CNPJ_PADRAO,
                    cooldown_minutos=120,
                )
            )
    finally:
        banco.fechar()


def test_cooldown_expirado_libera_nova_sincronizacao(tmp_path):
    banco_path = tmp_path / "historico.db"
    banco = BancoManifestacoes(str(banco_path))
    agora = datetime.now(timezone.utc)
    try:
        banco.registrar_tentativa_sincronizacao(
            CNPJ_PADRAO,
            120,
            agora=agora - timedelta(hours=3),
        )
        assert banco.bloqueio_sincronizacao(CNPJ_PADRAO, agora=agora) is None
    finally:
        banco.fechar()
