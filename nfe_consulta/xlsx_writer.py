"""Planilha de consulta pronta para abrir no Excel, mantendo chaves como texto."""

import os
import tempfile
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from nfe_consulta.cte import export_label
from nfe_consulta.cancelamento import status_label
from nfe_consulta.validacao import numero_e_serie


HEADERS = [
    "Chave NF-e", "Número", "Série", "Manifestação", "Data do evento",
    "Protocolo", "Código", "Eventos", "Histórico", "Erro", "Situação", "CT-e vinculado",
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

    ws["A1"] = "Consulta de manifestações"
    ws["A1"].font = Font(size=12, bold=True)

    encontradas = sum(bool(r.manifestacoes) for r in resultados)
    ws["A2"] = f"{len(resultados)} chaves | {encontradas} com evento | {len(resultados)-encontradas} sem evento localizado"
    ws.row_dimensions[3].height = 8

    for coluna, titulo in enumerate(HEADERS, 1):
        celula = ws.cell(4, coluna, titulo)
        celula.font = Font(bold=True)
        celula.fill = PatternFill("solid", fgColor="E7E7E7")
        celula.alignment = Alignment(vertical="center")
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
            status_label(resultado.cancelada),
            export_label(resultado.ctes),
        ]
        for coluna, valor in enumerate(valores, 1):
            celula = ws.cell(indice, coluna, valor)
            if isinstance(valor, str):
                celula.data_type = "s"  # impede formula de conteudo externo
            celula.alignment = Alignment(vertical="center", wrap_text=coluna in (4, 9, 10))
        for coluna in (1, 3, 6, 7):
            ws.cell(indice, coluna).number_format = "@"
        ws.cell(indice, 2).number_format = "0"
        ws.cell(indice, 8).number_format = "0"
        ws.row_dimensions[indice].height = min(70, max(30, 15 * len(resultado.manifestacoes)))

    larguras = [49, 12, 9, 31, 26, 21, 12, 10, 58, 31, 31, 65]
    for i, largura in enumerate(larguras, 1):
        ws.column_dimensions[get_column_letter(i)].width = largura
    ws.auto_filter.ref = f"A4:L{max(4, 4 + len(resultados))}"
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
