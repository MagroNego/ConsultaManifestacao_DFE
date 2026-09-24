import subprocess
import sys

from nfe_consulta.config import NOME_BANCO, NOME_PLANILHA, resolver_caminhos


def test_instalacao_nova_usa_pastas_do_projeto(tmp_path):
    projeto = tmp_path / "app"
    downloads = tmp_path / "Downloads"
    projeto.mkdir()
    downloads.mkdir()

    caminhos = resolver_caminhos(projeto, downloads)

    assert caminhos.chaves == projeto / "entrada" / "CHAVES.txt"
    assert caminhos.banco == projeto / "dados" / NOME_BANCO
    assert caminhos.saida == projeto / "saidas" / NOME_PLANILHA


def test_help_v1_mostra_cli_curta():
    retorno = subprocess.run(
        [sys.executable, "-m", "nfe_consulta.cli", "--help"],
        capture_output=True,
        text=True,
    )
    assert retorno.returncode == 0
    assert "atualizar" in retorno.stdout
    assert "excel" in retorno.stdout
    assert "status" in retorno.stdout
    assert "proteger-banco" in retorno.stdout
    assert "--manifestacoes" not in retorno.stdout
