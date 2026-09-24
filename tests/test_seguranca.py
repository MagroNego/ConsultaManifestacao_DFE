import base64
import csv
import gzip
import io
import subprocess
import sys

import pytest
from openpyxl import load_workbook

from nfe_consulta.assistente import montar_comando, NOME_PLANILHA
from nfe_consulta.csv_writer import gravar_csv
from nfe_consulta.modelos import NfeErroResposta, ResultadoConsulta
from nfe_consulta.parser_distribuicao import MAX_XML_BYTES, parse_retorno_distribuicao
from nfe_consulta.xlsx_writer import gravar_xlsx


def test_rejeita_entidades_xml():
    xml = ('<!DOCTYPE retDistDFeInt [<!ENTITY seg "expandir">]>'
           '<retDistDFeInt><cStat>137</cStat><xMotivo>&seg;</xMotivo>'
           '<ultNSU>0</ultNSU><maxNSU>0</maxNSU></retDistDFeInt>')
    with pytest.raises(NfeErroResposta):
        parse_retorno_distribuicao(xml)


def test_bloqueia_gzip_que_expande_demais():
    zipado = base64.b64encode(gzip.compress(b" " * (MAX_XML_BYTES + 1))).decode()
    xml = ('<retDistDFeInt><cStat>138</cStat><ultNSU>1</ultNSU><maxNSU>1</maxNSU>'
           f'<docZip NSU="1" schema="evento">{zipado}</docZip></retDistDFeInt>')
    with pytest.raises(NfeErroResposta, match="limite"):
        parse_retorno_distribuicao(xml)


def test_exportacoes_tratam_texto_que_parece_formula(tmp_path):
    resultado = ResultadoConsulta("=HYPERLINK(\"https://example.com\")", 0, "", None, (), "=SUM(1,1)")
    destino = tmp_path / NOME_PLANILHA
    gravar_xlsx(str(destino), [resultado], "=SUM(2,2)")
    ws = load_workbook(destino).active
    assert ws.title == "Consulta_Manifestacao_YAB"
    assert ws["A5"].data_type == "s"
    assert ws["J5"].data_type == "s"
    assert ws["A3"].value is None

    texto = io.StringIO()
    gravar_csv(texto, [resultado], "=SUM(2,2)")
    registro = next(csv.DictReader(io.StringIO(texto.getvalue()), delimiter=";"))
    assert registro["chave"].startswith("'=")
    assert registro["erro"].startswith("'=")
    assert registro["cobertura"].startswith("'=")


def test_assistente_nao_usa_shell_e_help_funciona(tmp_path):
    comando = montar_comando(tmp_path / "chaves.txt", tmp_path / NOME_PLANILHA, tmp_path / "banco.db", True)
    assert comando[:3] == [sys.executable, "-m", "nfe_consulta.cli"]
    assert "--manifestacoes" in comando
    assert "--max-lotes" in comando
    retorno = subprocess.run([sys.executable, "-m", "nfe_consulta.cli", "-help"], capture_output=True, text=True)
    assert retorno.returncode == 0
    assert "EXEMPLOS" in retorno.stdout


def test_assistente_reutiliza_banco_antigo_e_nome_padrao(tmp_path, monkeypatch):
    import nfe_consulta.assistente as assistente

    pacote = tmp_path / "app"
    (pacote / "nfe_consulta").mkdir(parents=True)
    downloads = tmp_path / "Downloads"
    downloads.mkdir()
    (downloads / "CHAVES.txt").write_text("1" * 44, encoding="utf-8")
    (downloads / "nfe_manifestacoes.db").write_bytes(b"banco existente")
    monkeypatch.setattr(assistente, "__file__", str(pacote / "nfe_consulta" / "assistente.py"))
    monkeypatch.setattr(assistente.Path, "home", lambda: tmp_path)
    respostas = iter(["2", "", "", ""])
    monkeypatch.setattr("builtins.input", lambda *_: next(respostas))
    comandos = []
    monkeypatch.setattr(assistente.subprocess, "call", lambda args, cwd: comandos.append((args, cwd)) or 0)
    assert assistente.main() == 0
    args, cwd = comandos[0]
    assert args[args.index("--banco") + 1] == str(downloads / "nfe_manifestacoes.db")
    assert args[args.index("--xlsx") + 1] == str(pacote / "saidas" / NOME_PLANILHA)
    assert "--manifestacoes" not in args
