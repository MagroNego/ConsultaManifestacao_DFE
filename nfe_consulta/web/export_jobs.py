"""Geração em segundo plano, independente da conexão do navegador."""
from __future__ import annotations

import asyncio
import time
from contextvars import ContextVar
from datetime import datetime
from uuid import uuid4

from nfe_consulta.web.downloads import BRASILIA, RETENTION_SECONDS
from nfe_consulta.web.export_queue import ExportQueueBusy

current_export_job = ContextVar('current_export_job', default=None)


class ExportJobs:
    def __init__(self):
        self.records = {}
        self.tasks = set()

    def list(self):
        now = time.time()
        self.records = {key: item for key, item in self.records.items()
                        if item['created_at'] > now - RETENTION_SECONDS or item['status'] in {'queued', 'generating'}}
        return sorted(self.records.values(), key=lambda item: item['created_at'], reverse=True)

    def start(self, app, scope, body, *, period='Não informado'):
        queue = app.state.export_queue
        active = sum(item['status'] in {'queued', 'generating'} for item in self.list())
        if active >= queue.concurrency + queue.max_waiting:
            raise ExportQueueBusy('Há muitas solicitações de relatório. Aguarde um momento e tente novamente.', 429)
        now = time.time()
        item = dict(id=uuid4().hex, status='queued', created_at=now, period=period,
                    created_label=datetime.fromtimestamp(now, BRASILIA).strftime('%d/%m/%Y %H:%M'),
                    archive_id=None)
        self.records[item['id']] = item
        scope = dict(scope)
        scope['headers'] = [(key, value) for key, value in scope['headers'] if key.lower() != b'x-nfe-background']
        task = asyncio.create_task(self._run(app, scope, body, item))
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)
        return item

    async def _run(self, app, scope, body, item):
        token = current_export_job.set(item)
        first = True
        status = 500
        is_html = False
        async def receive():
            nonlocal first
            if first:
                first = False
                return {'type': 'http.request', 'body': body, 'more_body': False}
            # Uma navegação não cancela a geração já aceita pelo servidor.
            await asyncio.Event().wait()

        async def send(message):
            nonlocal status, is_html
            if message['type'] == 'http.response.start':
                status = message['status']
                is_html = any(key.lower() == b'content-type' and b'text/html' in value
                              for key, value in message.get('headers', []))

        try:
            await app(scope, receive, send)
            item['status'] = 'complete' if status == 200 and not is_html and item['archive_id'] else 'error'
        except asyncio.CancelledError:
            item['status'] = 'error'
            raise
        except Exception:
            item['status'] = 'error'
        finally:
            current_export_job.reset(token)

    async def close(self):
        tasks = list(self.tasks)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
