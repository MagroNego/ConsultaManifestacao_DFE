"""Planilha de consulta pronta para abrir no Excel, mantendo chaves como texto."""

import os
import tempfile
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from nfe_consulta.validacao import numero_e_serie


HEADERS = [
    "Chave NF-e", "Número", "Série", "Manifestação", "Data do evento",
    "Protocolo", "Código", "Eventos", "Histórico", "Erro",
]
DESCRICOES = {
    "210200": "Confirmação da Operação",
    "210210": "Ciência da Operação",
    "210220": "Desconhecimento da Operação",
    "210240": "Operação não Realizada",
}


def _data_exibicao(iso: str) -> str:
    if not iso:
        return ""
    try:
        data = datetime.fromisoformat(iso)
    except ValueError:
        return iso
    fuso = data.strftime("%z")
    sufixo = f" UTC{fuso[:3]}:{fuso[3:]}" if fuso else ""
    return data.strftime("%d/%m/%Y %H:%M") + sufixo


def gravar_xlsx(caminho: str, resultados: list, cobertura: str) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Consulta_Manifestacao_YAB"
    ws.sheet_view.zoomScale = 85
    ws.freeze_panes = "D5"

    azul = "17324F"
    azul_claro = "E8F0F7"
    cinza = "F3F6F9"
    branco = "FFFFFF"
    ws.merge_cells("A1:J1")
    ws["A1"] = "Manifestação do destinatário · NF-e emitidas"
    ws["A1"].font = Font(size=17, bold=True, color=branco)
    ws["A1"].fill = PatternFill("solid", fgColor=azul)
    ws["A1"].alignment = Alignment(vertical="center", indent=1)
    ws.row_dimensions[1].height = 38

    encontradas = sum(bool(r.manifestacoes) for r in resultados)
    ws.merge_cells("A2:J2")
    ws["A2"] = f"{len(resultados)} chaves  |  {encontradas} com evento  |  {len(resultados)-encontradas} sem evento localizado"
    ws["A2"].font = Font(size=11, bold=True, color=azul)
    ws["A2"].alignment = Alignment(vertical="center", indent=1)
    ws.row_dimensions[2].height = 28

    ws.row_dimensions[3].height = 10

    for coluna, titulo in enumerate(HEADERS, 1):
        celula = ws.cell(4, coluna, titulo)
        celula.font = Font(bold=True, color=branco)
        celula.fill = PatternFill("solid", fgColor=azul)
        celula.alignment = Alignment(vertical="center", indent=1)
    ws.row_dimensions[4].height = 27

    tons = {
        "210200": ("DCF3E7", "126B45"),
        "210210": ("DEEDFB", "205780"),
        "210220": ("FCE6E6", "942F2F"),
        "210240": ("FFF0D8", "815518"),
    }
    for indice, resultado in enumerate(resultados, 5):
        numero, serie = numero_e_serie(resultado.chave)
        evento = resultado.manifestacoes[-1] if resultado.manifestacoes else None
        valores = [
            resultado.chave, int(numero) if numero else None, serie,
            DESCRICOES.get(evento.codigo, evento.descricao) if evento else "Sem evento localizado",
            _data_exibicao(evento.data) if evento else "",
            evento.protocolo if evento else "",
            evento.codigo if evento else "",
            len(resultado.manifestacoes),
            "\n".join(f"{_data_exibicao(e.data)} · {DESCRICOES.get(e.codigo, e.descricao)} · {e.protocolo}"
                      for e in resultado.manifestacoes),
            resultado.erro or "",
        ]
        fundo = branco if indice % 2 else cinza
        for coluna, valor in enumerate(valores, 1):
            celula = ws.cell(indice, coluna, valor)
            if isinstance(valor, str):
                celula.data_type = "s"  # impede formula de conteudo externo
            celula.fill = PatternFill("solid", fgColor=fundo)
            celula.font = Font(size=10, color=azul)
            celula.alignment = Alignment(vertical="center", wrap_text=coluna in (4, 9, 10))
        for coluna in (1, 3, 6, 7):
            ws.cell(indice, coluna).number_format = "@"
        ws.cell(indice, 2).number_format = "0"
        ws.cell(indice, 8).number_format = "0"
        tom, letra = tons.get(evento.codigo, ("EBEEF2", "56616D")) if evento else ("EBEEF2", "56616D")
        ws.cell(indice, 4).fill = PatternFill("solid", fgColor=tom)
        ws.cell(indice, 4).font = Font(size=10, bold=True, color=letra)
        ws.row_dimensions[indice].height = min(70, max(30, 15 * len(resultado.manifestacoes)))

    larguras = [49, 12, 9, 31, 26, 21, 12, 10, 58, 31]
    for i, largura in enumerate(larguras, 1):
        ws.column_dimensions[get_column_letter(i)].width = largura
    ws.auto_filter.ref = f"A4:J{max(4, 4 + len(resultados))}"
    ws.print_options.horizontalCentered = False
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.fitToWidth = 1
    ws.page_setup.orientation = "landscape"

    destino = Path(caminho)
    destino.parent.mkdir(parents=True, exist_ok=True)
    descritor, temporario = tempfile.mkstemp(prefix=".nfe-consulta-", suffix=".xlsx", dir=destino.parent)
    os.close(descritor)
    try:
        wb.save(temporario)
        os.replace(temporario, destino)
    finally:
        Path(temporario).unlink(missing_ok=True)
