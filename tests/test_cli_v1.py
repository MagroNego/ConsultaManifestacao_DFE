import subprocess
import sys

from nfe_consulta import cli
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



def test_cli_ler_senha_de_arquivo_para_job(tmp_path, monkeypatch):
    arquivo = tmp_path / "db-password.txt"
    arquivo.write_text("senha-segura-do-banco\n", encoding="utf-8")

    monkeypatch.setenv("NFE_DATABASE_PASSWORD_FILE", str(arquivo))
    monkeypatch.delenv("NFE_DATABASE_PASSWORD", raising=False)
    monkeypatch.setattr(cli, "criptografado", lambda _caminho: True)

    assert cli._senha_do_banco(tmp_path / "banco.db") == "senha-segura-do-banco"


def test_cli_atualizar_usa_configuracao_do_servidor(monkeypatch):
    monkeypatch.setenv("NFE_DATABASE_PATH", r"C:\ConsultaManifestacao\dados\banco.db")
    monkeypatch.setenv("NFE_CERT_STORE", "LocalMachine")
    monkeypatch.setenv("NFE_CERT_THUMBPRINT", "ABC123")
    monkeypatch.setenv("NFE_SEFAZ_COOLDOWN_MINUTES", "120")

    args = cli._criar_parser().parse_args(["atualizar"])

    assert args.banco == r"C:\ConsultaManifestacao\dados\banco.db"
    assert args.cert_store == "LocalMachine"
    assert args.cert_thumbprint == "ABC123"
    assert args.cooldown_minutos == 120
