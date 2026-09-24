import sys

from nfe_consulta.config import NOME_PLANILHA
from nfe_consulta.cli import main as cli_main
from nfe_consulta.gui import caminhos_iniciais, resumir_status


CHAVE = "33260812345678000199550010000917791147439711"


def test_gui_padrao_reutiliza_banco_de_downloads(tmp_path):
    pasta = tmp_path / "app"
    (pasta / "entrada").mkdir(parents=True)
    (pasta / "dados").mkdir()
    downloads = tmp_path / "Downloads"
    downloads.mkdir()
    (downloads / "CHAVES.txt").write_text(CHAVE, encoding="utf-8")
    (downloads / "nfe_manifestacoes.db").write_bytes(b"banco existente")
    chaves, banco, saida = caminhos_iniciais(pasta, downloads)
    assert chaves == downloads / "CHAVES.txt"
    assert banco == downloads / "nfe_manifestacoes.db"
    assert saida == pasta / "saidas" / NOME_PLANILHA


def test_gui_prefere_banco_protegido_na_pasta_do_projeto(tmp_path):
    pasta, downloads = tmp_path / "projeto", tmp_path / "Downloads"
    (pasta / "entrada").mkdir(parents=True)
    (pasta / "dados").mkdir()
    downloads.mkdir()
    (pasta / "dados" / "nfe_manifestacoes.db").write_bytes(b"antigo")
    (pasta / "dados" / "nfe_manifestacoes_seguro.db").write_bytes(b"seguro")
    (_, banco, _) = caminhos_iniciais(pasta, downloads)
    assert banco == pasta / "dados" / "nfe_manifestacoes_seguro.db"


def test_gui_mostra_cursor_salvo_e_distingue_pausa_de_fila_percorrida():
    base = ("Ultima resposta da SEFAZ salva: 24/09/2026 09:30:00 -0300 (horario local)\n"
            "ultNSU salvo: 000000000563245 | maxNSU conhecido: 000000000563245\n")
    assert resumir_status(base) == ("24/09/2026 09:30", "000000000563245",
                                   "000000000563245", "Sincronizado")
    assert resumir_status(base + "Pausa por 656: aguarde ate 10:30")[-1] == "Em pausa"
    assert resumir_status("Banco nao encontrado: arquivo.db")[-1] == "Banco indisponível"


def test_cli_gui_aciona_a_interface_sem_requerer_chave(monkeypatch):
    import nfe_consulta.gui as gui
    chamadas = []
    monkeypatch.setattr(gui, "main", lambda: chamadas.append(True))
    monkeypatch.setattr(sys, "argv", ["nfe-consulta", "gui"])
    cli_main()
    assert chamadas == [True]
