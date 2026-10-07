"""Espera assíncrona e limitada para geração de relatórios concorrentes."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager


class ExportQueueBusy(Exception):
    def __init__(self, detail, status_code):
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


class ExportQueue:
    def __init__(self, *, concurrency=2, max_waiting=16, timeout=300):
        if concurrency < 1 or max_waiting < 0 or timeout <= 0:
            raise ValueError('Limites de exportação inválidos.')
        self.concurrency = concurrency
        self.max_waiting = max_waiting
        self.timeout = timeout
        self.active = 0
        self._admitted = 0
        self._slots = asyncio.Semaphore(concurrency)

    @property
    def waiting(self):
        return self._admitted - self.active

    @asynccontextmanager
    async def slot(self):
        # Executado no loop do servidor, sem await entre conferir e reservar.
        if self._admitted >= self.concurrency + self.max_waiting:
            raise ExportQueueBusy('Há muitas solicitações de relatório. Aguarde um momento e tente novamente.', 429)
        self._admitted += 1
        acquired = False
        try:
            try:
                await asyncio.wait_for(self._slots.acquire(), timeout=self.timeout)
            except TimeoutError as exc:
                raise ExportQueueBusy('O servidor ainda está gerando outros relatórios. Tente novamente em instantes.', 503) from exc
            acquired = True
            self.active += 1
            yield
        finally:
            if acquired:
                self.active -= 1
                self._slots.release()
            self._admitted -= 1
