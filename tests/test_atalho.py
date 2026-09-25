from types import SimpleNamespace

import pytest

from nfe_consulta.banco import BancoManifestacoes
from nfe_consulta.cli import COOLDOWN_SEFAZ_MINUTOS, main
from nfe_consulta.config import CNPJ_PADRAO


CHAVE = "33260812345678000199550010000917791147439711"


def test_cli_excel_usa_somente_banco_local(tmp_path, monkeypatch):
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
        lambda *args, **kwargs: pytest.fail("certificado nao deve ser usado"),
    )

    main([
        "excel",
        str(chaves),
        "--banco",
        str(banco_path),
        "--saida",
        str(saida),
    ])

    assert saida.is_file()


def test_cli_atualizar_somente_sincroniza_banco(tmp_path, monkeypatch):
    banco = tmp_path / "historico.db"
    capturado = {}

    def fake_sync(parametros, **kwargs):
        capturado["parametros"] = parametros
        return SimpleNamespace(
            lotes=1,
            eventos_novos=2,
            ult_nsu="10".zfill(15),
            max_nsu="10".zfill(15),
        )

    monkeypatch.setattr("nfe_consulta.cli.sincronizar_banco", fake_sync)

    main([
        "atualizar",
        "--banco",
        str(banco),
        "--max-lotes",
        "25",
    ])

    parametros = capturado["parametros"]
    assert parametros.cnpj == CNPJ_PADRAO
    assert parametros.max_lotes == 25
    assert parametros.cooldown_minutos == COOLDOWN_SEFAZ_MINUTOS
    assert not hasattr(parametros, "chaves")
    assert not hasattr(parametros, "saida")


def test_cli_excel_recusa_banco_ausente(tmp_path):
    chaves = tmp_path / "CHAVES.txt"
    chaves.write_text(CHAVE + "\n", encoding="utf-8")

    with pytest.raises(SystemExit) as erro:
        main([
            "excel",
            str(chaves),
            "--banco",
            str(tmp_path / "ausente.db"),
            "--saida",
            str(tmp_path / "resultado.xlsx"),
        ])

    assert erro.value.code == 1
    assert not (tmp_path / "ausente.db").exists()
