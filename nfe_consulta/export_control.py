"""Cancelamento cooperativo das exportações, inclusive nas threads de trabalho."""
from contextvars import ContextVar

cancel_event = ContextVar("export_cancel_event", default=None)


class ExportCancelled(Exception):
    """A exportação foi interrompida a pedido do usuário."""


def check_export_cancelled():
    event = cancel_event.get()
    if event is not None and event.is_set():
        raise ExportCancelled("Exportação cancelada.")


def cancellable_rows(rows):
    for row in rows:
        check_export_cancelled()
        yield row
    check_export_cancelled()


def install_progress_handler(connection):
    event = cancel_event.get()
    if event is not None:
        connection.set_progress_handler(lambda: int(event.is_set()), 1000)
