from pathlib import Path
import io
import sys

import pytest

from nfe_consulta.banco import BancoManifestacoes
from nfe_consulta.cli import _configurar_atalho, _criar_parser, main
from nfe_consulta.seguranca_banco import migrar_banco


def test_atalho_exige_txt_e_banco_protegido(tmp_path):
    args = _criar_parser().parse_args(["--atualizar"])
    with pytest.raises(ValueError, match="TXT de chaves não encontrado"):
        _configurar_atalho(args, tmp_path)
    (tmp_path / "CHAVES.txt").write_text("1" * 44 + "\n")
    with pytest.raises(ValueError, match="banco protegido não encontrado"):
        _configurar_atalho(args, tmp_path)


def test_atalho_aponta_para_o_banco_seguro_e_excel(tmp_path):
    (tmp_path / "CHAVES.txt").write_text("1" * 44 + "\n")
    original = tmp_path / "nfe_manifestacoes.db"
    banco = BancoManifestacoes(str(original))
    banco.fechar()
    migrar_banco(original, tmp_path / "nfe_manifestacoes_seguro.db", "senha longa de teste")
    args = _criar_parser().parse_args(["--atualizar"])
    _configurar_atalho(args, tmp_path)
    assert args.manifestacoes and args.cnpj == "16840128000101" and args.uf == "RJ"
    assert Path(args.banco).name == "nfe_manifestacoes_seguro.db"
    assert Path(args.xlsx).name == "Consulta_Manifestacao_YAB.xlsx"


def test_atalho_prefere_projeto_quando_os_arquivos_estao_nas_pastas(tmp_path):
    pasta = tmp_path / "projeto"
    downloads = tmp_path / "Downloads"
    (pasta / "entrada").mkdir(parents=True)
    (pasta / "dados").mkdir()
    downloads.mkdir()
    (pasta / "entrada" / "CHAVES.txt").write_text("1" * 44 + "\n")
    (downloads / "CHAVES.txt").write_text("2" * 44 + "\n")
    original = tmp_path / "original.db"
    banco = BancoManifestacoes(str(original))
    banco.fechar()
    migrar_banco(original, pasta / "dados" / "nfe_manifestacoes_seguro.db", "senha longa de teste")
    migrar_banco(original, downloads / "nfe_manifestacoes_seguro.db", "senha longa de teste")
    args = _criar_parser().parse_args(["--excel"])
    _configurar_atalho(args, downloads, pasta=pasta, sincronizar=False)
    assert Path(args.lote) == pasta / "entrada" / "CHAVES.txt"
    assert Path(args.banco) == pasta / "dados" / "nfe_manifestacoes_seguro.db"
    assert Path(args.xlsx) == pasta / "saidas" / "Consulta_Manifestacao_YAB.xlsx"


def test_atalho_nao_mistura_banco_do_projeto_com_txt_de_downloads(tmp_path):
    pasta, downloads = tmp_path / "projeto", tmp_path / "Downloads"
    (pasta / "dados").mkdir(parents=True)
    downloads.mkdir()
    (downloads / "CHAVES.txt").write_text("1" * 44 + "\n")
    (pasta / "dados" / "nfe_manifestacoes_seguro.db").write_bytes(b"arquivo presente")
    args = _criar_parser().parse_args(["--atualizar"])
    with pytest.raises(ValueError, match="TXT de chaves não encontrado"):
        _configurar_atalho(args, downloads, pasta=pasta)


def test_planilha_usa_so_dados_locais_sem_certificado_ou_sefaz(tmp_path, monkeypatch):
    downloads = tmp_path / "Downloads"
    downloads.mkdir()
    chave = "33260812345678000199550010000917791147439711"
    (downloads / "CHAVES.txt").write_text(chave + "\n", encoding="utf-8")
    origem = tmp_path / "original.db"
    banco = BancoManifestacoes(str(origem))
    banco.fechar()
    migrar_banco(origem, downloads / "nfe_manifestacoes_seguro.db", "senha longa de teste")
    args = _criar_parser().parse_args(["--excel"])
    _configurar_atalho(args, downloads, sincronizar=False)
    assert not args.manifestacoes and args.uf is None
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr(sys, "argv", ["nfe-consulta", "--excel"])
    monkeypatch.setattr(sys, "stdin", io.StringIO("senha longa de teste\n"))
    import nfe_consulta.cli as cli
    monkeypatch.setattr(cli, "_selecionar_certificado", lambda *a: pytest.fail("certificado nao deve ser usado"))
    monkeypatch.setattr(cli, "sincronizar", lambda *a, **k: pytest.fail("SEFAZ nao deve ser consultada"))
    main()
    assert (downloads / "Consulta_Manifestacao_YAB.xlsx").is_file()
