import sqlite3
from threading import Event

import pytest
from openpyxl import load_workbook

from nfe_consulta.export_control import cancel_event, ExportCancelled
from nfe_consulta.seguranca_banco import abrir_banco
from nfe_consulta.web.xml_store import export_excel, export_csv
from io import BytesIO


@pytest.mark.parametrize("export", [export_csv, lambda report: export_excel([("Notas", report)])])
def test_cancel_stops_before_consuming_entire_report(export):
    event = Event()
    visited = []
    def rows():
        for index in range(1000):
            visited.append(index)
            if index == 3:
                event.set()
            yield {"Numero Nota": str(index)}
    token = cancel_event.set(event)
    try:
        with pytest.raises(ExportCancelled):
            export({"columns": ["Numero Nota"], "rows": rows()})
        assert visited == [0, 1, 2, 3]
    finally:
        cancel_event.reset(token)


def test_cancel_interrupts_sql_without_modifying_database(tmp_path):
    path = tmp_path / "report.db"
    sqlite3.connect(path).close()
    event = Event()
    token = cancel_event.set(event)
    try:
        connection = abrir_banco(path, somente_leitura=True)
    finally:
        cancel_event.reset(token)
    try:
        event.set()
        with pytest.raises(sqlite3.OperationalError, match="interrupted"):
            connection.execute("WITH RECURSIVE n(x) AS (VALUES(1) UNION ALL SELECT x+1 FROM n WHERE x<1000000) SELECT sum(x) FROM n").fetchone()
    finally:
        connection.close()
    with abrir_banco(path, somente_leitura=True) as fresh:
        assert fresh.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


def test_excel_formats_and_rows_are_preserved():
    data = export_excel([("Notas", {"columns": ["Numero Nota", "Vl. Nota", "Data Emissao"],
        "rows": [{"Numero Nota": "0001", "Vl. Nota": "12.3456", "Data Emissao": "2026-10-16"}]})])
    book = load_workbook(BytesIO(data))
    sheet = book.active
    assert sheet["A2"].value == "0001" and sheet["A2"].data_type == "s"
    assert sheet["B2"].value == 12.3456 and sheet["B2"].number_format == "#,##0.0000"
    assert sheet["C2"].number_format == "dd/mm/yyyy"


def test_cancel_after_saving_removes_temporary_excel(tmp_path, monkeypatch):
    from openpyxl import Workbook
    from nfe_consulta.xlsx_writer import gravar_xlsx

    event = Event()
    def save_partial(self, filename):
        from pathlib import Path
        Path(filename).write_bytes(b'partial')
        event.set()
    monkeypatch.setattr(Workbook, 'save', save_partial)
    destination = tmp_path / 'report.xlsx'
    token = cancel_event.set(event)
    try:
        with pytest.raises(ExportCancelled):
            gravar_xlsx(str(destination), [], '')
    finally:
        cancel_event.reset(token)
    assert not destination.exists()
    assert list(tmp_path.iterdir()) == []
