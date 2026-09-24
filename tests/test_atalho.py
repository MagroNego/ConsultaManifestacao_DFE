from types import SimpleNamespace

import pytest

from nfe_consulta.banco import BancoManifestacoes
from nfe_consulta.cli import main
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


def test_cli_atualizar_monta_execucao_remota(tmp_path, monkeypatch):
    chaves = tmp_path / "CHAVES.txt"
    chaves.write_text(CHAVE + "\n", encoding="utf-8")
    banco = tmp_path / "historico.db"
    saida = tmp_path / "resultado.xlsx"

    capturado = {}

    def fake_executar(parametros, **kwargs):
        capturado["parametros"] = parametros
        return SimpleNamespace(
            total=1,
            com_evento=0,
            com_erro=0,
            saida=saida,
        )

    monkeypatch.setattr("nfe_consulta.cli.executar_consulta", fake_executar)

    main([
        "atualizar",
        str(chaves),
        "--banco",
        str(banco),
        "--saida",
        str(saida),
        "--max-lotes",
        "25",
    ])

    parametros = capturado["parametros"]
    assert parametros.cnpj == CNPJ_PADRAO
    assert parametros.sincronizar_sefaz
    assert parametros.max_lotes == 25


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
