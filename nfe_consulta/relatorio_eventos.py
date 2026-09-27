"""Exportação de consultas de eventos para Excel."""

from __future__ import annotations

import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from nfe_consulta.web.consulta_local import EventoNota, FiltrosEventos, TIPOS_MANIFESTACAO


HEADERS = [
    "Número NF",
    "Série",
    "Chave NF-e",
    "Código",
    "Manifestação",
    "Data do evento",
    "Protocolo",
    "NSU",
    "Recebido no banco",
]


def _excel_datetime(valor: str) -> datetime | str:
    valor = (valor or "").strip()
    if not valor:
        return ""
    try:
        instante = datetime.fromisoformat(valor.replace("Z", "+00:00"))
    except ValueError:
        return valor

    if instante.tzinfo is None:
        instante = instante.replace(tzinfo=timezone.utc)
    return instante.astimezone().replace(tzinfo=None)


def _resumo_filtros(filtros: FiltrosEventos) -> str:
    itens: list[str] = []
    if filtros.data_inicial or filtros.data_final:
        inicio = filtros.data_inicial.strftime("%d/%m/%Y") if filtros.data_inicial else "início"
        fim = filtros.data_final.strftime("%d/%m/%Y") if filtros.data_final else "hoje"
        itens.append(f"Período: {inicio} a {fim}")
    if filtros.numero is not None:
        itens.append(f"NF: {filtros.numero}")
    if filtros.serie is not None:
        itens.append(f"Série: {filtros.serie}")
    if filtros.chave:
        itens.append(f"Chave: {filtros.chave}")
    if filtros.codigo:
        itens.append(TIPOS_MANIFESTACAO.get(filtros.codigo, filtros.codigo))
    return "  |  ".join(itens) if itens else "Todos os eventos do banco"


def gravar_eventos_xlsx(
    caminho: str | Path,
    eventos: tuple[EventoNota, ...] | list[EventoNota],
    filtros: FiltrosEventos,
) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Manifestacoes"
    ws.sheet_view.zoomScale = 85
    ws.freeze_panes = "A5"

    azul = "17324F"
    branco = "FFFFFF"
    cinza = "F3F6F9"

    ws.merge_cells("A1:I1")
    ws["A1"] = "Consulta de manifestações · NF-e"
    ws["A1"].font = Font(size=17, bold=True, color=branco)
    ws["A1"].fill = PatternFill("solid", fgColor=azul)
    ws["A1"].alignment = Alignment(vertical="center", indent=1)
    ws.row_dimensions[1].height = 38

    ws.merge_cells("A2:I2")
    ws["A2"] = f"{len(eventos)} evento(s)  |  {_resumo_filtros(filtros)}"
    ws["A2"].font = Font(size=10, bold=True, color=azul)
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

    for indice, evento in enumerate(eventos, 5):
        valores = [
            evento.numero,
            evento.serie,
            evento.chave,
            evento.codigo,
            evento.descricao,
            _excel_datetime(evento.data),
            evento.protocolo,
            evento.nsu,
            _excel_datetime(evento.recebido_em),
        ]

        fundo = branco if indice % 2 else cinza
        for coluna, valor in enumerate(valores, 1):
            celula = ws.cell(indice, coluna, valor)
            if isinstance(valor, str):
                celula.data_type = "s"
            celula.fill = PatternFill("solid", fgColor=fundo)
            celula.font = Font(size=10, color=azul)
            celula.alignment = Alignment(vertical="center", wrap_text=coluna == 5)

        for coluna in (2, 3, 4, 7, 8):
            ws.cell(indice, coluna).number_format = "@"
        ws.cell(indice, 1).number_format = "0"
        for coluna in (6, 9):
            if isinstance(ws.cell(indice, coluna).value, datetime):
                ws.cell(indice, coluna).number_format = "dd/mm/yyyy hh:mm:ss"

        tom, letra = tons.get(evento.codigo, ("EBEEF2", "56616D"))
        ws.cell(indice, 5).fill = PatternFill("solid", fgColor=tom)
        ws.cell(indice, 5).font = Font(size=10, bold=True, color=letra)

    larguras = [13, 9, 49, 12, 31, 22, 22, 17, 22]
    for coluna, largura in enumerate(larguras, 1):
        ws.column_dimensions[get_column_letter(coluna)].width = largura

    ws.auto_filter.ref = f"A4:I{max(4, 4 + len(eventos))}"
    ws.print_options.horizontalCentered = False
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.fitToWidth = 1
    ws.page_setup.orientation = "landscape"

    destino = Path(caminho)
    destino.parent.mkdir(parents=True, exist_ok=True)
    descritor, temporario = tempfile.mkstemp(
        prefix=".nfe-eventos-",
        suffix=".xlsx",
        dir=destino.parent,
    )
    os.close(descritor)
    try:
        wb.save(temporario)
        os.replace(temporario, destino)
    finally:
        Path(temporario).unlink(missing_ok=True)
