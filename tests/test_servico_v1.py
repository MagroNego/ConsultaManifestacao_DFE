from pathlib import Path

import pytest

from nfe_consulta.banco import BancoManifestacoes
from nfe_consulta.config import CNPJ_PADRAO
from nfe_consulta.servico import ParametrosConsulta, executar_consulta


CHAVE = "33260812345678000199550010000917791147439711"


def test_servico_local_gera_planilha_sem_acessar_sefaz(tmp_path, monkeypatch):
    chaves = tmp_path / "CHAVES.txt"
    chaves.write_text(CHAVE + "\n", encoding="utf-8")

    banco_path = tmp_path / "historico.db"
    banco = BancoManifestacoes(str(banco_path))
    banco.fechar()

    saida = tmp_path / "resultado.xlsx"

    import nfe_consulta.servico as servico
    monkeypatch.setattr(
        servico,
        "resolver_certificado",
        lambda *args, **kwargs: pytest.fail("certificado não deve ser usado"),
    )

    resultado = executar_consulta(
        ParametrosConsulta(
            chaves=chaves,
            banco=banco_path,
            saida=saida,
            cnpj=CNPJ_PADRAO,
            sincronizar_sefaz=False,
        )
    )

    assert saida.is_file()
    assert resultado.total == 1
    assert resultado.com_evento == 0
    assert resultado.sincronizacao is None


def test_servico_local_nao_cria_banco_ausente(tmp_path):
    chaves = tmp_path / "CHAVES.txt"
    chaves.write_text(CHAVE + "\n", encoding="utf-8")

    with pytest.raises(FileNotFoundError, match="Banco local não encontrado"):
        executar_consulta(
            ParametrosConsulta(
                chaves=chaves,
                banco=tmp_path / "nao_existe.db",
                saida=tmp_path / "resultado.xlsx",
                cnpj=CNPJ_PADRAO,
                sincronizar_sefaz=False,
            )
        )

    assert not (tmp_path / "nao_existe.db").exists()
