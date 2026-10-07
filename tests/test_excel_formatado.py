import csv
import io

from openpyxl import load_workbook

from nfe_consulta.csv_writer import gravar_csv
from nfe_consulta.modelos import Manifestacao, ResultadoConsulta
from nfe_consulta.validacao import numero_e_serie
from nfe_consulta.xlsx_writer import gravar_xlsx


CHAVE = "33260812345678000199550010000917791147439711"


def test_numero_serie_e_chave_como_texto_no_excel(tmp_path):
    assert numero_e_serie(CHAVE) == ("91779", "001")
    resultado = ResultadoConsulta(
        CHAVE, 0, "", None,
        (Manifestacao("210210", "Ciencia da Operacao",
                      "2026-08-03T11:47:53-03:00", "135260000000001"),),
    )
    saida = tmp_path / "resultado.xlsx"
    gravar_xlsx(str(saida), [resultado], "Historico local")
    ws = load_workbook(saida, data_only=True).active
    assert ws["A3"].value is None
    assert ws["A4"].value == "Chave NF-e"
    assert ws["A5"].value == CHAVE
    assert ws["A5"].data_type == "s"
    assert ws["B5"].value == 91779
    assert ws["C5"].value == "001"
    assert ws["D5"].value == "Ciência da Operação"
    assert ws["E5"].value == "03/08/2026 11:47 UTC-03:00"
    assert ws.auto_filter.ref == "A4:L5"
    assert ws.freeze_panes == "D5"
    textos = " ".join(str(c.value or "") for row in ws.iter_rows() for c in row)
    assert "Cobertura:" not in textos
    assert "não comprova ausência de manifestação" not in textos

    texto = io.StringIO()
    gravar_csv(texto, [resultado])
    linhas = list(csv.DictReader(io.StringIO(texto.getvalue()), delimiter=";"))
    assert linhas[0]["numero_nfe"] == "91779"
    assert linhas[0]["serie_nfe"] == "001"
